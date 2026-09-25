"""
Telemetry receiver and adaptive trigger/haptic coordinator.
Listens for DualSenseXLink UDP instructions and polls Assetto Corsa shared memory
when running without an external telemetry relay.
"""

import socket
import json
import time
import math
import colorsys
import threading
import logging
from typing import Optional, Callable
from ..controller.dualsense import DualSenseController
from .ac_shared_memory import ACSharedMemoryReader
from ..config import Config

logger = logging.getLogger("DualSenseACBridge.Receiver")


class TelemetryReceiver:
    """Coordinates telemetry reception, adaptive trigger effects, and audio haptics dispatch."""

    def __init__(self, controller: DualSenseController, host: str = "127.0.0.1", port: int = 6969):
        self.controller = controller
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None

        self.sm = ACSharedMemoryReader()
        self.sm_thread: Optional[threading.Thread] = None
        self.flash_timer: float = 0.0
        self.flash_level: bool = True

        cfg = Config()

        self.left_trigger_scale: float = float(cfg.get("left_trigger_scale", 1.0))
        self.right_trigger_scale: float = float(cfg.get("right_trigger_scale", 1.0))
        self.brake_wall_pos: int = int(cfg.get("brake_wall_pos", 7))
        self.brake_wall_force: int = int(cfg.get("brake_wall_force", 6))
        self.throttle_spring_force: int = int(cfg.get("throttle_spring_force", 3))
        self.rgb_brightness_scale: float = float(cfg.get("rgb_brightness_scale", 1.0))
        self.enable_triggers: bool = bool(cfg.get("enable_triggers", True))
        self.enable_rgb: bool = bool(cfg.get("enable_rgb", True))
        self.enable_player_leds: bool = bool(cfg.get("enable_player_leds", True))
        self.enable_audio_haptics: bool = bool(cfg.get("enable_audio_haptics", True))

        from ..haptics import HapticTelemetryProcessor, HapticAudioEngine
        self.haptic_processor = HapticTelemetryProcessor()
        self.audio_engine = HapticAudioEngine()

        self.haptic_processor.master_gain = float(cfg.get("haptic_master_gain", 1.0))
        self.haptic_processor.ffb_gain = float(cfg.get("haptic_ffb_gain", 0.7))
        self.haptic_processor.kerb_gain = float(cfg.get("haptic_kerb_gain", 1.0))
        self.haptic_processor.lockup_gain = float(cfg.get("haptic_lockup_gain", 1.0))
        self.haptic_processor.drift_gain = float(cfg.get("haptic_drift_gain", 0.85))
        self.haptic_processor.gearshift_gain = float(cfg.get("haptic_gearshift_gain", 0.8))

        self.packet_count: int = 0
        self.packets_per_second: float = 0.0
        self.last_packet_time: float = 0.0
        self.last_udp_packet_time: float = 0.0
        self.is_game_active: bool = False
        self.last_lt_info = {"mode": 0, "strength": 0, "freq": 0}
        self.last_rt_info = {"mode": 0, "strength": 0, "freq": 0}
        self.last_rgb = (0, 0, 0)
        self.last_player_leds = 0

        self.is_testing = False
        self._fps_count = 0
        self._fps_timer = time.time()
        self.on_telemetry_updated: Optional[Callable] = None

        self.auto_exit_on_game_close: bool = bool(cfg.get("auto_exit_on_game_close", True))
        self.on_game_closed: Optional[Callable] = None

    def _is_ac_process_alive(self) -> bool:
        """Checks whether an Assetto Corsa process instance is running."""
        try:
            import psutil
            for p in psutil.process_iter(['name']):
                try:
                    name = p.info['name']
                    if name and name.lower() in ('acs.exe', 'acs_x86.exe', 'assettocorsa.exe'):
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass
        return False

    def start(self) -> bool:
        """Starts UDP socket listener and shared memory background polling threads."""
        if self.running:
            return True
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(0.5)
            self.sock.bind((self.host, self.port))
            self.running = True

            if self.enable_audio_haptics:
                self.audio_engine.start()

            logger.info(f"UDP Receiver listening on {self.host}:{self.port}")
            self.thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.thread.start()

            self.sm_thread = threading.Thread(target=self._sm_loop, daemon=True)
            self.sm_thread.start()
            return True
        except OSError as e:
            logger.warning(f"Could not bind UDP port {self.port}: {e}. Another instance is running.")
            self.running = False
            return False

    def stop(self):
        """Stops listener threads and releases network and audio resources."""
        self.running = False
        self.is_game_active = False
        self.sm.close()
        self.audio_engine.stop()
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None
        if self.sm_thread:
            self.sm_thread.join(timeout=1.0)
            self.sm_thread = None

    def _listen_loop(self):
        """Worker loop receiving incoming UDP datagrams."""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                if not data:
                    continue
                self._handle_packet(data)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.warning(f"Error receiving UDP packet: {e}")
                continue

    def _handle_packet(self, data: bytes):
        """Decodes JSON telemetry packet and dispatches DualSenseXLink instructions."""
        try:
            payload = json.loads(data.decode("utf-8", errors="ignore"))
        except Exception:
            return

        instructions = payload.get("instructions", [])
        if not instructions:
            return

        now = time.time()
        self.controller.touch_telemetry()
        self.packet_count += 1
        self.last_packet_time = now
        self.last_udp_packet_time = now
        self._fps_count += 1
        if now - self._fps_timer >= 1.0:
            self.packets_per_second = self._fps_count / (now - self._fps_timer)
            self._fps_count = 0
            self._fps_timer = now

        for inst in instructions:
            itype = inst.get("type", 0)
            params = inst.get("parameters", [])

            # DualSenseXLink type 1: adaptive trigger command
            if itype == 1 and len(params) >= 3:
                trigger_side = params[1]
                mode = params[2]
                start_pos = params[3] if len(params) > 3 else 0
                strength = params[4] if len(params) > 4 else 0
                freq = params[5] if len(params) > 5 else 0

                if not self.enable_triggers:
                    mode = 0
                    strength = 0

                if trigger_side == 1:
                    scaled_str = int(round(strength * self.left_trigger_scale))
                    self.last_lt_info = {"mode": mode, "strength": scaled_str, "freq": freq}
                    self.controller.set_left_trigger(mode, start_pos, scaled_str, freq)
                elif trigger_side == 2:
                    scaled_str = int(round(strength * self.right_trigger_scale))
                    self.last_rt_info = {"mode": mode, "strength": scaled_str, "freq": freq}
                    self.controller.set_right_trigger(mode, start_pos, scaled_str, freq)

            # DualSenseXLink type 2: RGB lightbar
            elif itype == 2 and len(params) >= 4:
                r, g, b = params[1], params[2], params[3]
                if self.enable_rgb:
                    r = int(round(r * self.rgb_brightness_scale))
                    g = int(round(g * self.rgb_brightness_scale))
                    b = int(round(b * self.rgb_brightness_scale))
                else:
                    r, g, b = 0, 0, 0
                self.last_rgb = (r, g, b)
                self.controller.set_led(r, g, b)

            # DualSenseXLink type 3: player indicator LEDs bitmask
            elif itype == 3:
                mask = 0
                for i in range(1, min(6, len(params))):
                    if params[i]:
                        mask |= (1 << (i - 1))
                if not self.enable_player_leds:
                    mask = 0
                self.last_player_leds = mask
                self.controller.set_player_leds(mask)

            # DualSenseXLink type 4: discrete audio haptic amplitudes & frequencies
            elif itype == 4 and len(params) >= 7:
                left_amp, right_amp, left_freq, right_freq, abs_l, abs_r = params[1:7]
                if self.enable_audio_haptics:
                    self.audio_engine.ensure_started()
                    if self.audio_engine.is_active:
                        self.audio_engine.update_haptics(
                            left_amp=left_amp,
                            right_amp=right_amp,
                            left_freq=left_freq,
                            right_freq=right_freq,
                            abs_l=abs_l,
                            abs_r=abs_r,
                        )
                self.controller.set_rumble(0, 0)

        if self.on_telemetry_updated:
            self.on_telemetry_updated()

    def _sm_loop(self):
        """Polls Assetto Corsa Shared Memory when UDP packets are not arriving."""
        brake_debounce = 0.0
        traction_debounce = 0.0
        was_game_running = False
        game_seen_active = False
        game_stopped_time = 0.0

        while self.running:
            time.sleep(0.016)
            now = time.time()

            sm_running = self.sm.is_game_running()
            udp_recent = (now - self.last_udp_packet_time < 1.0) and (self.packet_count > 0)
            is_game_active = sm_running or udp_recent
            self.is_game_active = is_game_active

            if not is_game_active:
                if was_game_running:
                    was_game_running = False
                    game_stopped_time = now
                    logger.info("Assetto Corsa телеметрія зупинена/сесію завершено. Скидання ефектів...")
                    self.controller.reset_effects()
                    self.sm.close()
                    self.last_lt_info = {"mode": 0, "strength": 0, "freq": 0}
                    self.last_rt_info = {"mode": 0, "strength": 0, "freq": 0}
                    self.last_rgb = (0, 0, 0)
                    self.controller.speed_kmh = 0.0
                    if self.enable_audio_haptics and self.audio_engine.is_active:
                        self.audio_engine.update_layers(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

                # Auto-exit only in CLI mode (when on_game_closed is registered).
                # In GUI mode, the app stays running in tray waiting for the next session.
                if self.on_game_closed is not None and self.auto_exit_on_game_close and game_seen_active and (now - game_stopped_time > 2.0):
                    if not self._is_ac_process_alive():
                        logger.info("Процес Assetto Corsa завершено (CLI). Автоматичне закриття...")
                        self.running = False
                        self.on_game_closed()
                        return
                continue

            was_game_running = True
            game_seen_active = True

            try:
                phys = self.sm.physics
                if phys:
                    self.controller.speed_kmh = float(phys.speedKmh)
            except Exception:
                phys = None

            if not phys:
                if self.enable_audio_haptics and self.audio_engine.is_active:
                    self.audio_engine.update_layers(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
                self.controller.set_rumble(0, 0)
                continue

            hap_state = self.haptic_processor.process(
                phys,
                delta_t=0.016,
                in_kerb_l=self.controller.game_rumble_left,
                in_kerb_r=self.controller.game_rumble_right,
            )

            if self.enable_audio_haptics:
                self.audio_engine.ensure_started()
                if self.audio_engine.is_active and not self.is_testing:
                    self.audio_engine.update_layers(
                        kerb_l=hap_state.kerb_l,
                        kerb_r=hap_state.kerb_r,
                        drift=hap_state.drift,
                        gear_shift=hap_state.gear_shift,
                        lockup_l=hap_state.lockup_l,
                        lockup_r=hap_state.lockup_r,
                        ffb_l=hap_state.ffb_l,
                        ffb_r=hap_state.ffb_r,
                    )

            self.controller.set_rumble(0, 0)

            if now - self.last_udp_packet_time < 0.5:
                continue

            try:
                rpm = phys.rpms
                max_rpm = self.sm.max_rpm if self.sm.max_rpm > 0 else 7000
                rpm_percent = max(0.0, min(1.0, rpm / max_rpm))

                in_pit = (self.sm.graphics and self.sm.graphics.isInPitLine == 1) or (phys.pitLimiterOn == 1)
                self.flash_timer += 0.016
                if in_pit:
                    if self.flash_timer > 0.5:
                        self.flash_level = not self.flash_level
                        self.flash_timer = 0
                elif rpm_percent > 0.96:
                    if self.flash_timer > 0.0625:
                        self.flash_level = not self.flash_level
                        self.flash_timer = 0
                else:
                    self.flash_level = True

                brightness = self.rgb_brightness_scale if self.flash_level else 0.0
                hue = max(0.0, min(0.33, 1.2 - (rpm_percent * 1.25)))
                rgb_float = colorsys.hsv_to_rgb(hue, 1.0, brightness)
                r = int(rgb_float[0] * 255) if self.enable_rgb else 0
                g = int(rgb_float[1] * 255) if self.enable_rgb else 0
                b = int(rgb_float[2] * 255) if self.enable_rgb else 0
                self.last_rgb = (r, g, b)
                self.controller.set_led(r, g, b)

                slips = list(phys.wheelSlip)
                min_slip = min(slips) if slips else 0.0
                abs_active = (phys.abs > 0.0)
                speed_kmh = phys.speedKmh

                is_locking = (speed_kmh > 3.0) and (abs_active or (min_slip < -0.15))
                if is_locking:
                    brake_debounce = 0.08
                elif brake_debounce > 0.0:
                    brake_debounce -= 0.016

                # 1. Brake (L2): progressive hydraulic pedal with threshold wall + ABS pulse
                # - Pre-wall travel: progressive resistance for trail-braking
                # - Wall position: tactile step preventing accidental wheel lockup
                # - ABS / Lockup: 24 Hz hydraulic pulse beyond wall
                wall_pos = max(5, min(8, self.brake_wall_pos))
                wall_force = max(3, min(7, self.brake_wall_force))

                if self.enable_triggers:
                    if brake_debounce > 0.0:
                        # Hydraulic ABS pulse beyond threshold wall (24 Hz, strength 6)
                        scaled_str = int(round(6 * self.left_trigger_scale))
                        self.controller.set_left_trigger(17, wall_pos, scaled_str, 24)
                        self.last_lt_info = {"mode": 17, "strength": scaled_str, "freq": 24}
                    else:
                        # Progressive hydraulic resistance up to threshold wall
                        scaled_str = int(round(wall_force * self.left_trigger_scale))
                        self.controller.set_left_trigger(13, wall_pos, scaled_str)
                        self.last_lt_info = {"mode": 13, "strength": scaled_str, "freq": 0}
                else:
                    self.controller.set_left_trigger(0, 0, 0)
                    self.last_lt_info = {"mode": 0, "strength": 0, "freq": 0}

                # 2. Throttle (R2): progressive spring resistance + traction loss rumble (22 Hz)
                throttle_spring = max(1, min(6, self.throttle_spring_force))

                w_speeds = list(phys.wheelAngularSpeed)
                front_w_spd = (abs(w_speeds[0]) + abs(w_speeds[1])) * 0.5
                rear_w_spd = (abs(w_speeds[2]) + abs(w_speeds[3])) * 0.5
                spd_diff = abs(rear_w_spd - front_w_spd)
                min_w_spd = min(front_w_spd, rear_w_spd)
                max_w_spd = max(front_w_spd, rear_w_spd)

                if min_w_spd > 3.0:
                    true_wheelspin = (spd_diff / min_w_spd) > 0.16
                else:
                    true_wheelspin = (max_w_spd > 12.0) and (min_w_spd < 4.0)

                drive_slip = max(abs(s) for s in slips) if slips else 0.0
                tc_active = (phys.tc > 0.0)
                is_in_gear = (phys.gear != 1)
                clutch_pressed = (phys.clutch > 0.8)
                has_throttle = (phys.gas > 0.12)
                is_powered = is_in_gear and not clutch_pressed and has_throttle
                is_spinning = is_powered and (tc_active or true_wheelspin or drive_slip > 0.20)

                if is_spinning:
                    traction_debounce = 0.08
                elif traction_debounce > 0.0:
                    traction_debounce -= 0.016

                if self.enable_triggers:
                    if traction_debounce > 0.0:
                        # Traction loss / wheelspin vibration (22 Hz)
                        scaled_str = int(round(4 * self.right_trigger_scale))
                        self.controller.set_right_trigger(17, 0, scaled_str, 22)
                        self.last_rt_info = {"mode": 17, "strength": scaled_str, "freq": 22}
                    else:
                        # Progressive throttle pedal resistance
                        scaled_str = int(round(throttle_spring * self.right_trigger_scale))
                        self.controller.set_right_trigger(13, 0, scaled_str)
                        self.last_rt_info = {"mode": 13, "strength": scaled_str, "freq": 0}
                else:
                    self.controller.set_right_trigger(0, 0, 0)
                    self.last_rt_info = {"mode": 0, "strength": 0, "freq": 0}

                self.controller.touch_telemetry()
                self.packet_count += 1
                self.last_packet_time = now
                self._fps_count += 1
                if now - self._fps_timer >= 1.0:
                    self.packets_per_second = self._fps_count / (now - self._fps_timer)
                    self._fps_count = 0
                    self._fps_timer = now

                if self.on_telemetry_updated:
                    self.on_telemetry_updated()
            except Exception as e:
                logger.debug(f"Shared memory read error: {e}")