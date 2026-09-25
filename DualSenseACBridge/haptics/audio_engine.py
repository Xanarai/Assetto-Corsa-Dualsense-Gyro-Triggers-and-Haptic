"""
Multi-Texture HD Audio Haptic Engine for DualSense Voice Coil Actuators.
Generates distinct tactile layers:
- Kerb: Sharp, biting high-frequency transient pulses
- Drift/Slip: Granular, low-frequency rubber-scrubbing texture
- Gear Shift: Heavy single-cycle transmission thud (Kick impulse)
- Lockup/ABS: Rhythmic hydraulic valve pulsation
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

        # Незалежні шари телеметрії
        self.lock = threading.Lock()
        self.kerb_l: float = 0.0
        self.kerb_r: float = 0.0
        self.drift: float = 0.0
        self.gear_shift: float = 0.0
        self.lockup_l: float = 0.0
        self.lockup_r: float = 0.0
        self.ffb_l: float = 0.0
        self.ffb_r: float = 0.0

        # Фази для безшовного відтворення хвиль
        self.phase_kerb_l: float = 0.0
        self.phase_kerb_r: float = 0.0
        self.phase_drift: float = 0.0
        self.phase_gear: float = 0.0
        self.phase_abs: float = 0.0
        self.phase_ffb_l: float = 0.0
        self.phase_ffb_r: float = 0.0

    def find_dualsense_audio_device(self) -> Tuple[Optional[int], str, int]:
        if not HAS_AUDIO_LIBS or sd is None:
            return None, "sounddevice library missing", 0
        try:
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

            if not candidates:
                return None, "Not Detected", 0
            candidates.sort(key=lambda c: c[0], reverse=True)
            return candidates[0][1], candidates[0][2], candidates[0][3]
        except Exception as e:
            return None, f"Error: {e}", 0

    def start(self) -> bool:
        if not HAS_AUDIO_LIBS:
            self.is_active = False
            return False
        if self.running and self.stream and self.stream.active:
            return True

        dev_idx, dev_name, dev_channels = self.find_dualsense_audio_device()
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

    def ensure_started(self) -> bool:
        if self.is_active and self.running and self.stream and self.stream.active:
            return True
        now = time.time()
        if now - self.last_retry_time < 4.0:
            return False
        self.last_retry_time = now
        return self.start()

    def stop(self):
        self.running = False
        self.is_active = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    def update_layers(self, kerb_l=0.0, kerb_r=0.0, drift=0.0, gear_shift=0.0, lockup_l=0.0, lockup_r=0.0, ffb_l=0.0, ffb_r=0.0):
        """Оновлює шари з різними фізичними джерелами."""
        with self.lock:
            self.kerb_l = float(max(0.0, min(1.0, kerb_l)))
            self.kerb_r = float(max(0.0, min(1.0, kerb_r)))
            self.drift = float(max(0.0, min(1.0, drift)))
            self.gear_shift = float(max(0.0, min(1.0, gear_shift)))
            self.lockup_l = float(max(0.0, min(1.0, lockup_l)))
            self.lockup_r = float(max(0.0, min(1.0, lockup_r)))
            self.ffb_l = float(max(0.0, min(1.0, ffb_l)))
            self.ffb_r = float(max(0.0, min(1.0, ffb_r)))

    def update_haptics(self, left_amp: float, right_amp: float, left_freq: float = 135.0, right_freq: float = 135.0, abs_l: float = 0.0, abs_r: float = 0.0):
        # Метод для зворотної сумісності (якщо викликається за старим форматом)
        self.update_layers(ffb_l=left_amp, ffb_r=right_amp, lockup_l=abs_l, lockup_r=abs_r)

    def _audio_callback(self, outdata, frames, time_info, status):
        with self.lock:
            k_l, k_r = self.kerb_l, self.kerb_r
            drift = self.drift
            gear = self.gear_shift
            l_l, l_r = self.lockup_l, self.lockup_r
            f_l, f_r = self.ffb_l, self.ffb_r

        # Якщо всі ефекти на нулі — глушимо потік
        if max(k_l, k_r, drift, gear, l_l, l_r, f_l, f_r) < 0.001:
            outdata.fill(0.0)
            return

        dt = 1.0 / self.sample_rate
        two_pi = 2.0 * math.pi
        t = np.arange(frames, dtype=np.float32) * dt

        # ── 1. ПОРЕБРИКИ: Гостра, кусача пилкоподібна хвиля (190 Гц) ──
        # Дає відчуття чітких твердих ударів об бетонні насічки
        out_k_l = np.zeros(frames, dtype=np.float32)
        out_k_r = np.zeros(frames, dtype=np.float32)
        if k_l > 0.01 or k_r > 0.01:
            step_k = two_pi * 190.0
            p_k_l = (self.phase_kerb_l + step_k * t) % two_pi
            p_k_r = (self.phase_kerb_r + step_k * t) % two_pi
            self.phase_kerb_l = (self.phase_kerb_l + step_k * frames * dt) % two_pi
            self.phase_kerb_r = (self.phase_kerb_r + step_k * frames * dt) % two_pi

            # Комбінація синуса і непарних гармонік для гострого «хрускоту»
            saw_l = np.sin(p_k_l) + 0.5 * np.sin(2.0 * p_k_l) + 0.25 * np.sin(4.0 * p_k_l)
            saw_r = np.sin(p_k_r) + 0.5 * np.sin(2.0 * p_k_r) + 0.25 * np.sin(4.0 * p_k_r)
            out_k_l = saw_l * (k_l * 0.7)
            out_k_r = saw_r * (k_r * 0.7)

        # ── 2. ДРИФТ / ЗНОС: Шорсткий низькочастотний гуркіт резини (55 Гц + шум) ──
        # Відчувається як зерниста вібрація тертя шин по асфальту
        out_drift = np.zeros(frames, dtype=np.float32)
        if drift > 0.01:
            step_d = two_pi * 55.0
            p_d = (self.phase_drift + step_d * t) % two_pi
            self.phase_drift = (self.phase_drift + step_d * frames * dt) % two_pi
            noise = np.random.uniform(-0.35, 0.35, frames).astype(np.float32)
            out_drift = (np.sin(p_d) * 0.75 + noise) * (drift * 0.65)

        # ── 3. ПЕРЕДАЧА: Важкий монолітний бас-удар (45 Гц) ──
        # Відчувається як масивний поштовх коробки передач
        out_gear = np.zeros(frames, dtype=np.float32)
        if gear > 0.01:
            step_g = two_pi * 48.0
            p_g = (self.phase_gear + step_g * t) % two_pi
            self.phase_gear = (self.phase_gear + step_g * frames * dt) % two_pi
            out_gear = np.sin(p_g) * (gear * 0.95)

        # ── 4. БЛОКУВАННЯ / ABS: Стробоскопічний клацаючий імпульс (26 Гц) ──
        out_abs_l = np.zeros(frames, dtype=np.float32)
        out_abs_r = np.zeros(frames, dtype=np.float32)
        if l_l > 0.01 or l_r > 0.01:
            step_abs = two_pi * 26.0
            p_abs = (self.phase_abs + step_abs * t) % two_pi
            self.phase_abs = (self.phase_abs + step_abs * frames * dt) % two_pi
            # Прямокутний імпульс: імітує клапан ABS
            valve_pulse = np.where(np.sin(p_abs) > 0.1, 0.85, -0.15).astype(np.float32)
            out_abs_l = valve_pulse * l_l
            out_abs_r = valve_pulse * l_r

        # ── 5. FFB (Опір керма): Гладкий низький гул (75 Гц) ──
        out_ffb_l = np.zeros(frames, dtype=np.float32)
        out_ffb_r = np.zeros(frames, dtype=np.float32)
        if f_l > 0.01 or f_r > 0.01:
            step_f = two_pi * 75.0
            p_f_l = (self.phase_ffb_l + step_f * t) % two_pi
            p_f_r = (self.phase_ffb_r + step_f * t) % two_pi
            self.phase_ffb_l = (self.phase_ffb_l + step_f * frames * dt) % two_pi
            self.phase_ffb_r = (self.phase_ffb_r + step_f * frames * dt) % two_pi
            out_ffb_l = np.sin(p_f_l) * (f_l * 0.35)
            out_ffb_r = np.sin(p_f_r) * (f_r * 0.35)

        # ── МІКШУВАННЯ ВСІХ ТЕКСТУР РАЗОМ ──
        mix_left = out_k_l + out_drift + out_gear + out_abs_l + out_ffb_l
        mix_right = out_k_r + out_drift + out_gear + out_abs_r + out_ffb_r

        # Розподіл по каналах (0 і 1 мовчать, 2 і 3 — ліва та права котушки)
        outdata[:, 0] = 0.0
        outdata[:, 1] = 0.0
        outdata[:, 2] = np.clip(mix_left, -1.0, 1.0)
        outdata[:, 3] = np.clip(mix_right, -1.0, 1.0)
