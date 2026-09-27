"""
Multi-layer audio haptics synthesizer for DualSense Voice Coil Actuators.
Synthesizes distinct frequency profiles routed directly to DualSense haptic channels (channels 2 & 3).
"""

import math
import time
import logging
import threading
from typing import Optional, Tuple

try:
    import numpy as np
    import sounddevice as sd
    HAS_AUDIO_LIBS = True
except Exception:
    np = None
    sd = None
    HAS_AUDIO_LIBS = False

logger = logging.getLogger("DualSenseACBridge.AudioHaptics")


class HapticAudioEngine:
    """Manages 4-channel audio stream to drive DualSense voice coil haptic actuators."""

    def __init__(self, sample_rate: int = 48000, block_size: int = 512):
        self.sample_rate = sample_rate
        self.block_size = block_size

        self.stream: Optional[sd.OutputStream] = None
        self.running: bool = False
        self.is_active: bool = False
        self.device_index: Optional[int] = None
        self.device_name: str = "Not Found"
        self.device_channels: int = 0
        self.last_retry_time: float = 0.0

        # Telemetry layer amplitudes [0.0, 1.0]
        self.lock = threading.Lock()
        self.kerb_l: float = 0.0
        self.kerb_r: float = 0.0
        self.drift: float = 0.0
        self.gear_shift: float = 0.0
        self.lockup_l: float = 0.0
        self.lockup_r: float = 0.0
        self.ffb_l: float = 0.0
        self.ffb_r: float = 0.0
        self.test_l: float = 0.0
        self.test_r: float = 0.0
        self.test_freq_l: float = 120.0
        self.test_freq_r: float = 120.0

        # Continuous phase accumulators for seamless waveform synthesis across audio blocks
        self.phase_kerb_l: float = 0.0
        self.phase_kerb_r: float = 0.0
        self.phase_drift: float = 0.0
        self.phase_gear: float = 0.0
        self.phase_abs: float = 0.0
        self.phase_ffb_l: float = 0.0
        self.phase_ffb_r: float = 0.0
        self.phase_test_l: float = 0.0
        self.phase_test_r: float = 0.0

        # Safety watchdog: timestamp of the most recent telemetry layer update
        self.last_update_time: float = 0.0

    def refresh_devices(self):
        """Forces PortAudio to re-enumerate Windows audio devices without restarting Python."""
        if HAS_AUDIO_LIBS and sd is not None:
            try:
                sd._terminate()
                sd._initialize()
                logger.debug("PortAudio device cache re-initialized.")
            except Exception as e:
                logger.debug(f"PortAudio re-init note: {e}")

    def find_dualsense_audio_device(self, force_refresh: bool = False) -> Tuple[Optional[int], str, int]:
        """Locates DualSense 4-channel audio endpoint, prioritizing WASAPI on Windows."""
        if not HAS_AUDIO_LIBS or sd is None:
            return None, "sounddevice library missing", 0
        try:
            if force_refresh:
                self.refresh_devices()

            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
            wasapi_api_indices = [i for i, h in enumerate(hostapis) if "WASAPI" in h.get("name", "").upper()]

            candidates = []
            keywords = ("WIRELESS CONTROLLER", "DUALSENSE", "PLAYSTATION")
            for idx, dev in enumerate(devices):
                name = dev.get("name", "").upper()
                out_ch = dev.get("max_output_channels", 0)
                host_api = dev.get("hostapi", -1)
                if out_ch > 0 and any(kw in name for kw in keywords):
                    is_wasapi = host_api in wasapi_api_indices
                    score = (10 if is_wasapi else 1) + (10 if out_ch >= 4 else 0)
                    candidates.append((score, idx, dev.get("name", ""), out_ch, is_wasapi))

            # If not found on the cached list and we haven't refreshed yet, refresh PortAudio and retry once
            if not candidates and not force_refresh:
                self.refresh_devices()
                devices = sd.query_devices()
                for idx, dev in enumerate(devices):
                    name = dev.get("name", "").upper()
                    out_ch = dev.get("max_output_channels", 0)
                    host_api = dev.get("hostapi", -1)
                    if out_ch > 0 and any(kw in name for kw in keywords):
                        is_wasapi = host_api in wasapi_api_indices
                        score = (10 if is_wasapi else 1) + (10 if out_ch >= 4 else 0)
                        candidates.append((score, idx, dev.get("name", ""), out_ch, is_wasapi))

            if not candidates:
                return None, "Not Detected", 0
            candidates.sort(key=lambda c: c[0], reverse=True)
            return candidates[0][1], candidates[0][2], candidates[0][3]
        except Exception as e:
            return None, f"Error: {e}", 0

    def start(self, force_refresh: bool = False) -> bool:
        """Initializes and starts the 4-channel low-latency audio stream."""
        if not HAS_AUDIO_LIBS:
            self.is_active = False
            return False
        if self.running and self.stream and self.stream.active:
            return True

        # Auto-configure Windows audio device (volume + 4-channel format) before opening stream
        try:
            from .audio_setup import configure_dualsense_audio
            configure_dualsense_audio(target_volume=1.0, channels=4, sample_rate=self.sample_rate)
        except Exception as _cfg_err:
            logger.debug(f"Audio auto-config skipped: {_cfg_err}")

        dev_idx, dev_name, dev_channels = self.find_dualsense_audio_device(force_refresh=force_refresh)
        self.device_index = dev_idx
        self.device_name = dev_name
        self.device_channels = dev_channels

        if dev_idx is None or dev_channels < 4:
            self.is_active = False
            return False

        try:
            wasapi_settings = sd.WasapiSettings(exclusive=True)
            self.stream = sd.OutputStream(
                device=dev_idx,
                channels=4,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                dtype="float32",
                latency="low",
                callback=self._audio_callback,
                extra_settings=wasapi_settings,
            )
            self.stream.start()
            self.running = True
            self.is_active = True
            return True
        except Exception:
            try:
                self.stream = sd.OutputStream(
                    device=dev_idx,
                    channels=4,
                    samplerate=self.sample_rate,
                    blocksize=self.block_size,
                    dtype="float32",
                    latency="low",
                    callback=self._audio_callback,
                )
                self.stream.start()
                self.running = True
                self.is_active = True
                return True
            except Exception:
                self.is_active = False
                return False

    def ensure_started(self, force_retry: bool = False) -> bool:
        """Attempts to start the engine with retry backoff unless force_retry=True."""
        if self.is_active and self.running and self.stream and self.stream.active:
            return True
        now = time.time()
        if not force_retry and (now - self.last_retry_time < 3.0):
            return False
        self.last_retry_time = now
        return self.start(force_refresh=True)

    def stop(self):
        """Stops and closes active audio stream."""
        self.running = False
        self.is_active = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    def update_layers(self, kerb_l=0.0, kerb_r=0.0, drift=0.0, gear_shift=0.0, lockup_l=0.0, lockup_r=0.0, ffb_l=0.0, ffb_r=0.0, *args, **kwargs):
        """Thread-safe update of individual telemetry effect layer intensities."""
        with self.lock:
            self.kerb_l = float(max(0.0, min(1.0, kerb_l)))
            self.kerb_r = float(max(0.0, min(1.0, kerb_r)))
            self.drift = float(max(0.0, min(1.0, drift)))
            self.gear_shift = float(max(0.0, min(1.0, gear_shift)))
            self.lockup_l = float(max(0.0, min(1.0, lockup_l)))
            self.lockup_r = float(max(0.0, min(1.0, lockup_r)))
            self.ffb_l = float(max(0.0, min(1.0, ffb_l)))
            self.ffb_r = float(max(0.0, min(1.0, ffb_r)))
            self.last_update_time = time.time()

    def update_haptics(self, left_amp: float, right_amp: float, left_freq: float = 120.0, right_freq: float = 120.0, abs_l: float = 0.0, abs_r: float = 0.0, *args, **kwargs):
        """Direct / Diagnostic haptics update with progressive amplitude and frequency."""
        with self.lock:
            self.test_l = float(max(0.0, min(1.0, left_amp)))
            self.test_r = float(max(0.0, min(1.0, right_amp)))
            self.test_freq_l = float(left_freq) if left_freq > 10 else 120.0
            self.test_freq_r = float(right_freq) if right_freq > 10 else 120.0
            if abs_l > 0.0 or abs_r > 0.0:
                self.lockup_l = float(max(0.0, min(1.0, abs_l)))
                self.lockup_r = float(max(0.0, min(1.0, abs_r)))
            self.last_update_time = time.time()

    def stop_all(self):
        """Reset all active telemetry and test haptic layers to zero."""
        with self.lock:
            self.kerb_l = 0.0
            self.kerb_r = 0.0
            self.drift = 0.0
            self.gear_shift = 0.0
            self.lockup_l = 0.0
            self.lockup_r = 0.0
            self.ffb_l = 0.0
            self.ffb_r = 0.0
            self.test_l = 0.0
            self.test_r = 0.0
            self.last_update_time = 0.0

    def _audio_callback(self, outdata, frames, time_info, status):
        """Real-time audio callback synthesizing and mixing tactile waveforms into buffer."""
        # Watchdog: if no telemetry updates received within 200ms, auto-silence buffer
        if (time.time() - self.last_update_time) > 0.20:
            outdata.fill(0.0)
            return

        with self.lock:
            k_l, k_r = self.kerb_l, self.kerb_r
            drift = self.drift
            gear = self.gear_shift
            l_l, l_r = self.lockup_l, self.lockup_r
            f_l, f_r = self.ffb_l, self.ffb_r
            t_l, t_r = self.test_l, self.test_r
            freq_t_l, freq_t_r = self.test_freq_l, self.test_freq_r

        # Mute output if all effect layers are zeroed
        if max(k_l, k_r, drift, gear, l_l, l_r, f_l, f_r, t_l, t_r) < 0.001:
            outdata.fill(0.0)
            return

        dt = 1.0 / self.sample_rate
        two_pi = 2.0 * math.pi
        t = np.arange(frames, dtype=np.float32) * dt

        # 1. Kerbs: 190 Hz composite wave with odd harmonics for sharp transient bite
        out_k_l = np.zeros(frames, dtype=np.float32)
        out_k_r = np.zeros(frames, dtype=np.float32)
        if k_l > 0.01 or k_r > 0.01:
            step_k = two_pi * 190.0
            p_k_l = (self.phase_kerb_l + step_k * t) % two_pi
            p_k_r = (self.phase_kerb_r + step_k * t) % two_pi
            self.phase_kerb_l = (self.phase_kerb_l + step_k * frames * dt) % two_pi
            self.phase_kerb_r = (self.phase_kerb_r + step_k * frames * dt) % two_pi

            saw_l = np.sin(p_k_l) + 0.5 * np.sin(2.0 * p_k_l) + 0.25 * np.sin(4.0 * p_k_l)
            saw_r = np.sin(p_k_r) + 0.5 * np.sin(2.0 * p_k_r) + 0.25 * np.sin(4.0 * p_k_r)
            out_k_l = saw_l * (k_l * 0.7)
            out_k_r = saw_r * (k_r * 0.7)

        # 2. Drift / Slip: 55 Hz fundamental mixed with band-limited white noise for tire scrub
        out_drift = np.zeros(frames, dtype=np.float32)
        if drift > 0.01:
            step_d = two_pi * 55.0
            p_d = (self.phase_drift + step_d * t) % two_pi
            self.phase_drift = (self.phase_drift + step_d * frames * dt) % two_pi
            noise = np.random.uniform(-0.35, 0.35, frames).astype(np.float32)
            out_drift = (np.sin(p_d) * 0.75 + noise) * (drift * 0.65)

        # 3. Gear Shift: 48 Hz single-pulse kick transient
        out_gear = np.zeros(frames, dtype=np.float32)
        if gear > 0.01:
            step_g = two_pi * 48.0
            p_g = (self.phase_gear + step_g * t) % two_pi
            self.phase_gear = (self.phase_gear + step_g * frames * dt) % two_pi
            out_gear = np.sin(p_g) * (gear * 0.95)

        # 4. Lockup / ABS: 26 Hz square pulse simulating hydraulic valve cycling
        out_abs_l = np.zeros(frames, dtype=np.float32)
        out_abs_r = np.zeros(frames, dtype=np.float32)
        if l_l > 0.01 or l_r > 0.01:
            step_abs = two_pi * 26.0
            p_abs = (self.phase_abs + step_abs * t) % two_pi
            self.phase_abs = (self.phase_abs + step_abs * frames * dt) % two_pi
            valve_pulse = np.where(np.sin(p_abs) > 0.1, 0.85, -0.15).astype(np.float32)
            out_abs_l = valve_pulse * l_l
            out_abs_r = valve_pulse * l_r

        # 5. Diagnostic / Test Vibration: progressive smooth tone (120 Hz)
        out_test_l = np.zeros(frames, dtype=np.float32)
        out_test_r = np.zeros(frames, dtype=np.float32)
        if t_l > 0.005 or t_r > 0.005:
            step_t_l = two_pi * freq_t_l
            step_t_r = two_pi * freq_t_r
            p_t_l = (self.phase_test_l + step_t_l * t) % two_pi
            p_t_r = (self.phase_test_r + step_t_r * t) % two_pi
            self.phase_test_l = (self.phase_test_l + step_t_l * frames * dt) % two_pi
            self.phase_test_r = (self.phase_test_r + step_t_r * frames * dt) % two_pi
        # 6. Force Feedback (FFB): 38 Hz smooth mechanical rack load & transient jolts
        out_ffb_l = np.zeros(frames, dtype=np.float32)
        out_ffb_r = np.zeros(frames, dtype=np.float32)
        if f_l > 0.01 or f_r > 0.01:
            step_f = two_pi * 38.0
            p_f_l = (self.phase_ffb_l + step_f * t) % two_pi
            p_f_r = (self.phase_ffb_r + step_f * t) % two_pi
            self.phase_ffb_l = (self.phase_ffb_l + step_f * frames * dt) % two_pi
            self.phase_ffb_r = (self.phase_ffb_r + step_f * frames * dt) % two_pi
            out_ffb_l = np.sin(p_f_l) * (f_l * 0.50)
            out_ffb_r = np.sin(p_f_r) * (f_r * 0.50)

        # Mix synthesized layers for left and right actuators
        mix_left = out_k_l + out_drift + out_gear + out_abs_l + out_test_l + out_ffb_l
        mix_right = out_k_r + out_drift + out_gear + out_abs_r + out_test_r + out_ffb_r

        # DualSense USB audio endpoint routing:
        # Channels 0 & 1: 3.5mm headphone jack
        # Channels 2 & 3: Left & Right Voice Coil Actuators (haptic motors)
        outdata[:, 0] = 0.0
        outdata[:, 1] = 0.0
        outdata[:, 2] = np.clip(mix_left, -1.0, 1.0)
        outdata[:, 3] = np.clip(mix_right, -1.0, 1.0)
