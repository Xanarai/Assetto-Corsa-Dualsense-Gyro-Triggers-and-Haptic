"""
DualSense controller HID interface and virtual gamepad bridge.
Handles USB and Bluetooth HID I/O, adaptive trigger packet synthesis,
gyroscope steering injection, and ViGEmBus virtual Xbox 360 controller emulation.
"""

import time
import array
import base64
import threading
import logging
import struct
from typing import Optional, Tuple
import hid

try:
    import vgamepad as vg
    HAS_VGAMEPAD = True
except Exception:
    vg = None
    HAS_VGAMEPAD = False

_vigem_checked = False
_vigem_ok = False
_vigem_error = ""


def check_vigembus_driver(force_refresh: bool = False) -> Tuple[bool, str]:
    """
    Checks if ViGEmBus driver is installed and functional.
    Returns (is_available, error_message).
    """
    global _vigem_checked, _vigem_ok, _vigem_error
    if _vigem_checked and not force_refresh:
        return _vigem_ok, _vigem_error

    if not HAS_VGAMEPAD or vg is None:
        _vigem_checked = True
        _vigem_ok = False
        _vigem_error = "vgamepad module missing or failed to import"
        return False, _vigem_error

    try:
        test_pad = vg.VX360Gamepad()
        del test_pad
        _vigem_checked = True
        _vigem_ok = True
        _vigem_error = ""
        return True, ""
    except Exception as e:
        logger.warning(f"ViGEmBus driver verification failed: {e}")
        _vigem_checked = True
        _vigem_ok = False
        _vigem_error = str(e)
        return False, _vigem_error

from .gyro_processor import GyroProcessor

logger = logging.getLogger("DualSenseACBridge.DualSense")

SONY_VID = 0x054C
DUALSENSE_PID = 0x0CE6
DUALSENSE_EDGE_PID = 0x0DF2
SUPPORTED_PIDS = (DUALSENSE_PID, DUALSENSE_EDGE_PID)

CONN_DISCONNECTED = 0
CONN_USB = 1
CONN_BT = 2

_CRC_B64 = (
    "je8C0hvfBaWhjgw8N74LS5Qrb9UCG2iiuEphOy56Zky/Z9ncKVfeq5MG1zIFNtBFpqO02zCTs6yKwro1HPK9Qun/tc9/z7K4xZ67IVOuvFbwO9jIZgvfv9xa1iZKatFR23duw"
    "U1Habb3FmAvYSZnWMKzA8ZUgwSx7tINKHjiCl9Fz2zp0/9rnmmuYgf/nmVwXAsB7so7Bplwag8A5loId3dHt+fhd7CQWya5Cc0Wvn5ug9rg+LPdl0Li1A7U0tN5Id/b9Lfv3"
    "IMNvtUam47SbTgbtvOuK7GEFHq4HYJKv2oTVwD6hWcHjT82DhSpBgljCpNt/Zyjaoom8mMTsMJkZB2u3qSLntnTMc/QSqf/1z0EarOjklq01CgLvU2+O7o6LyYFqrkWAt0D"
    "RwtElXcMMzbiaK2g0m/aGoNmQ4yzYTR5vmm5745uzlXfZ1fD72AgYHoEvvZKA8lMGwpQ2isNJ0s2srfdBrXAZ1e8WfFnuy5S8t+wxMLYx36T0V7oo9Yp1Y6wn0O+t+j5775x"
    "b9+5BsxK3Zhaetrv4CvTdnYb1AHnBmuRcTZs5stnZX9dV2II/sIGlmjyAeHSowh4RJMPD7GeB4InrgD1nf8JbAvPDhuoWmqFPmpt8oQ7ZGsSC2McgxbcjBUm2/uvd9JiOUfV"
    "FZrSsYsM4rb8trO/ZSCDuBKtbLo/O1y9SIENtNEXPbOmtKjXOCKY0E+YydnWDvneoZ/kYTEJ1GZGs4Vv3yW1aKiGIAw2EBALQapBAtg8cQWvyXwNIl9MClXlHQPMcy0Eu9C4"
    "YCVGiGdS/Nluy2rpabz79NYsbcTRW9eV2MJBpd+14jC7K3QAvFzOUbXFWGGysmVM1ATzfNNzSS3a6t8d3Z18iLkD6ri+dFDpt+3G2bCaV8QPCsH0CH17pQHk7ZUGk04AYg3Y"
    "MGV6YmFs4/RRa5QBXGMZl2xkbi09bfe7DWqAGJgOHo6oCWk0+QDwoskHhzPUuBel5L9gH7W2+YmFsY4qENUQvCDSZwZx2/6QQdyJPS1mSasdYT4RTGinh3xv0CTpC06y2Qw5"
    "CIgFoJ64AtcPpb1HmZW6MCPEs6m19LTeFmHQQIBR1zc6AN6urDDZ2Vk90VTPDdYjdVzfuuNs2M1A+bxT1sm7JGyYsr36qLXKa7UKWv2FDS1H1AS00eQDw3JxZ13kQWAqXhBp"
    "s8ggbsT1DQhyYz0PBdlsBpxPXAHr7MlldXr5YgLAqGubVphs7MeF03xRtdQL6+Tdkn3U2uXeQb57SHG5DPIgsJVkELfikR2/bwctuBi9fLGBK0y29ojZ0mge6dUfpLjchjKI"
    "2/GjlWRhNaVjFo/0ao8ZxG34ulEJZixhDhGWMAeIAAAA/w=="
)
_CRC_TABLE = array.array('I', base64.b64decode(_CRC_B64))


def _compute_bt_crc(buf) -> int:
    """Computes the CRC32 checksum required by Bluetooth HID output report 0x31."""
    res = 0xEADA2D49
    res = _CRC_TABLE[(res & 0xFF) ^ 0xA2] ^ (res >> 8)
    for i in range(74):
        res = _CRC_TABLE[(res & 0xFF) ^ (buf[i] & 0xFF)] ^ (res >> 8)
    return res


def build_trigger_bytes(mode: int, start_pos: int, strength: int, freq: int = 0) -> list:
    """
    Constructs the 11-byte trigger effect payload for DualSense HID output reports.

    Modes:
      - 0: Off (0x05)
      - 17: Vibration / pulse effect (0x26) across active zones with frequency
      - 2: Rigid stop / sectional resistance (0x21) starting from start_pos
      - 13 (or 1, 7): Continuous progressive resistance profile (0x21)
      - 16: Bow effect (0x25)
    """
    buf = [0] * 11
    if mode == 0 or strength <= 0:
        buf[0] = 0x05
        return buf

    pos = max(0, min(9, int(start_pos)))
    str_val = max(0, min(8, int(strength)))
    freq_val = max(0, min(255, int(freq)))

    if mode == 17:
        if freq_val <= 0:
            buf[0] = 0x05
            return buf
        strength_val = max(1, min(7, (str_val - 1) & 0x07))
        amp_zones = 0
        active_zones = 0
        for i in range(pos, 10):
            amp_zones |= (strength_val << (3 * i))
            active_zones |= (1 << i)

        buf[0] = 0x26
        buf[1] = active_zones & 0xFF
        buf[2] = (active_zones >> 8) & 0xFF
        buf[3] = amp_zones & 0xFF
        buf[4] = (amp_zones >> 8) & 0xFF
        buf[5] = (amp_zones >> 16) & 0xFF
        buf[6] = (amp_zones >> 24) & 0xFF
        buf[9] = freq_val & 0xFF
        return buf

    elif mode == 2:
        force_val = max(1, min(7, (str_val - 1) & 0x07))
        force_zones = 0
        active_zones = 0
        for i in range(10):
            if i >= pos:
                force_zones |= (force_val << (3 * i))
                active_zones |= (1 << i)
        
        buf[0] = 0x21
        buf[1] = active_zones & 0xFF
        buf[2] = (active_zones >> 8) & 0xFF
        buf[3] = force_zones & 0xFF
        buf[4] = (force_zones >> 8) & 0xFF
        buf[5] = (force_zones >> 16) & 0xFF
        buf[6] = (force_zones >> 24) & 0xFF
        return buf

    elif mode in (13, 1, 7):
        force_val = max(1, min(7, (str_val - 1) & 0x07))
        force_zones = 0
        active_zones = 0

        if pos == 0:
            for i in range(10):
                frac = 0.25 + 0.75 * (i / 9.0)
                zone_f = max(1, min(7, int(round(frac * force_val))))
                force_zones |= (zone_f << (3 * i))
                active_zones |= (1 << i)
        else:
            for i in range(10):
                if i < pos:
                    pre_frac = i / float(pos)
                    zone_f = max(0, min(3, int(round(pre_frac * 3.0))))
                    if zone_f > 0:
                        force_zones |= (zone_f << (3 * i))
                        active_zones |= (1 << i)
                else:
                    zone_f = force_val
                    force_zones |= (zone_f << (3 * i))
                    active_zones |= (1 << i)

        buf[0] = 0x21
        buf[1] = active_zones & 0xFF
        buf[2] = (active_zones >> 8) & 0xFF
        buf[3] = force_zones & 0xFF
        buf[4] = (force_zones >> 8) & 0xFF
        buf[5] = (force_zones >> 16) & 0xFF
        buf[6] = (force_zones >> 24) & 0xFF
        return buf

    elif mode == 16:
        buf[0] = 0x25
        active_zones = (1 << pos) | (1 << min(9, pos + 2))
        buf[1] = active_zones & 0xFF
        buf[2] = (active_zones >> 8) & 0xFF
        buf[3] = (str_val - 1) & 0x07
        return buf

    buf[0] = 0x05
    return buf


class DualSenseController:
    """HID controller management, force feedback synthesis, and virtual gamepad synchronizer."""

    def __init__(self):
        self.dev: Optional[hid.device] = None
        self.device_path: Optional[bytes] = None
        self.conn_type: int = CONN_DISCONNECTED
        self.product_name: str = "Not Connected"
        self.is_edge: bool = False

        self.left_trigger_data: list = build_trigger_bytes(0, 0, 0)
        self.right_trigger_data: list = build_trigger_bytes(0, 0, 0)
        self.motor_left: int = 0
        self.motor_right: int = 0
        self.enable_rumble: bool = False
        self.led_rgb: Tuple[int, int, int] = (0, 0, 0)
        self.target_rgb: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.current_rgb: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.player_leds: int = 0
        self.enable_rgb: bool = True
        self.enable_player_leds: bool = True

        self.last_telemetry_time: float = 0
        self.telemetry_active: bool = False
        self.watchdog_timeout: float = 0.25

        self.running: bool = False
        self.lock = threading.Lock()
        self._write_lock = threading.Lock()
        self.worker_thread: Optional[threading.Thread] = None

        self.packets_sent: int = 0
        self.on_state_change = None

        # Gyroscope & Virtual Xbox 360 controller
        self.gyro: GyroProcessor = GyroProcessor()
        self.virtual_gamepad: Optional[vg.VX360Gamepad] = None
        self.virtual_gamepad_active: bool = False
        self.vigem_ok: bool
        self.vigem_error: str
        self.vigem_ok, self.vigem_error = check_vigembus_driver()
        self.speed_kmh: float = 0.0
        self.last_l2: float = 0.0
        self.last_r2: float = 0.0

        # Intercepted in-game rumble normalized to [0.0, 1.0] from ViGEmBus
        self.game_rumble_left: float = 0.0
        self.game_rumble_right: float = 0.0

        # Gamma curves (Load Cell / progressive resistance modeling)
        from ..config import Config
        cfg = Config()
        self.brake_gamma: float = float(cfg.get("brake_gamma", 2.4))
        self.throttle_gamma: float = float(cfg.get("throttle_gamma", 1.4))
        
        # Real-time state for Diagnostics UI
        self.state_l2: float = 0.0
        self.state_r2: float = 0.0
        self.state_ax: int = 0
        self.state_ay: int = 0
        self.state_az: int = 0
        self.state_gx: int = 0
        self.state_gy: int = 0
        self.state_gz: int = 0

    def _on_vgamepad_notification(self, client, target, large_motor, small_motor, led_number, user_data):
        """Callback for ViGEmBus XInput rumble notifications (large_motor/small_motor: 0..255)."""
        self.game_rumble_left = float(large_motor) / 255.0
        self.game_rumble_right = float(small_motor) / 255.0

    def _ensure_virtual_gamepad(self):
        """Initializes virtual Xbox 360 gamepad and registers rumble notification hook."""
        if not HAS_VGAMEPAD or vg is None:
            self.vigem_ok = False
            self.vigem_error = "vgamepad module missing or failed to import"
            return
        if self.virtual_gamepad is None:
            try:
                self.virtual_gamepad = vg.VX360Gamepad()
                try:
                    self.virtual_gamepad.register_notification(callback_function=self._on_vgamepad_notification)
                except Exception as ex:
                    logger.warning(f"Could not register rumble notification callback: {ex}")
                self.virtual_gamepad_active = True
                self.vigem_ok = True
                self.vigem_error = ""
                logger.info("Virtual Xbox 360 controller initialized with Rumble Hook.")
            except Exception as e:
                logger.warning(f"Could not initialize Virtual Xbox 360 controller: {e}")
                self.virtual_gamepad = None
                self.virtual_gamepad_active = False
                self.vigem_ok = False
                self.vigem_error = str(e)

    def _sync_gamepad(
        self,
        steer_x: float,
        phys_lx: float,
        phys_ly: float,
        phys_rx: float,
        phys_ry: float,
        l2_norm: float,
        r2_norm: float,
        b0: int,
        b1: int,
        b2: int
    ):
        """Synchronizes controller inputs, stick overrides, and triggers to the virtual Xbox 360 gamepad."""
        if not self.virtual_gamepad:
            return

        if self.gyro.stick_override and abs(phys_lx) > self.gyro.stick_override_threshold:
            final_steer = phys_lx
        else:
            final_steer = steer_x

        self.virtual_gamepad.left_joystick_float(x_value_float=final_steer, y_value_float=phys_ly)
        self.virtual_gamepad.right_joystick_float(x_value_float=phys_rx, y_value_float=phys_ry)
        self.virtual_gamepad.left_trigger_float(value_float=l2_norm)
        self.virtual_gamepad.right_trigger_float(value_float=r2_norm)

        dpad = b0 & 0x0F
        btn_map = [
            (dpad in (0, 1, 7), vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP),
            (dpad in (3, 4, 5), vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN),
            (dpad in (5, 6, 7), vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT),
            (dpad in (1, 2, 3), vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT),
            (bool(b0 & 0x20), vg.XUSB_BUTTON.XUSB_GAMEPAD_A),
            (bool(b0 & 0x40), vg.XUSB_BUTTON.XUSB_GAMEPAD_B),
            (bool(b0 & 0x10), vg.XUSB_BUTTON.XUSB_GAMEPAD_X),
            (bool(b0 & 0x80), vg.XUSB_BUTTON.XUSB_GAMEPAD_Y),
            (bool(b1 & 0x01), vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER),
            (bool(b1 & 0x02), vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER),
            (bool(b1 & 0x10), vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK),
            (bool(b1 & 0x20), vg.XUSB_BUTTON.XUSB_GAMEPAD_START),
            (bool(b1 & 0x40), vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB),
            (bool(b1 & 0x80), vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB),
        ]

        for is_pressed, btn in btn_map:
            if is_pressed:
                self.virtual_gamepad.press_button(button=btn)
            else:
                self.virtual_gamepad.release_button(button=btn)

        self.virtual_gamepad.update()

    def find_devices(self) -> list:
        """Enumerates and ranks connected DualSense / DualSense Edge controllers by connection quality."""
        devices = hid.enumerate(SONY_VID, 0)
        candidates = []
        for d in devices:
            pid = d.get('product_id', 0)
            if pid not in SUPPORTED_PIDS:
                continue
            path = d.get('path', b'')
            name = d.get('product_string', 'DualSense Wireless Controller')
            is_edge = (pid == DUALSENSE_EDGE_PID)
            usage_page = d.get('usage_page', 0)
            usage = d.get('usage', 0)
            interface_num = d.get('interface_number', -1)

            path_str = path.decode('latin-1', errors='ignore').lower()
            is_bt = ('bth' in path_str) or ('bluetooth' in path_str) or (interface_num == -1)
            conn_type = CONN_BT if is_bt else CONN_USB

            score = 0
            if not is_bt:
                if (usage_page == 1 and usage == 5) or interface_num == 3 or ('mi_03' in path_str):
                    score = 10
                elif interface_num >= 0:
                    score = 3
                else:
                    score = 1
            else:
                if usage_page == 1 and usage == 5:
                    score = 10
                elif usage_page == 0:
                    score = 8
                else:
                    score = 4

            candidates.append((score, path, conn_type, name, is_edge))

        candidates.sort(key=lambda c: c[0], reverse=True)
        return [(path, conn_type, name, is_edge) for _, path, conn_type, name, is_edge in candidates]

    def connect(self) -> bool:
        """Opens HID connection to the highest-priority DualSense device candidate."""
        if self.dev:
            try:
                self.dev.close()
            except Exception:
                pass
            self.dev = None

        candidates = self.find_devices()
        if not candidates:
            if self.conn_type != CONN_DISCONNECTED:
                self.conn_type = CONN_DISCONNECTED
                self.product_name = "Not Connected"
                if self.on_state_change:
                    try:
                        self.on_state_change()
                    except Exception:
                        pass
            return False

        for path, conn_type, name, is_edge in candidates:
            try:
                dev = hid.device()
                dev.open_path(path)
                try:
                    dev.set_nonblocking(True)
                except Exception:
                    pass
                self.dev = dev
                self.device_path = path
                self.conn_type = conn_type
                self.product_name = name
                self.is_edge = is_edge
                logger.info(f"Connected to {name} via {'Bluetooth' if conn_type == CONN_BT else 'USB'}")

                # If Bluetooth, request feature report 0x05 to switch firmware into full 0x31 report mode with live IMU/triggers
                if conn_type == CONN_BT:
                    try:
                        dev.get_feature_report(0x05, 64)
                        logger.info("Activated full 0x31 report mode over Bluetooth via feature report 0x05.")
                    except Exception as ex:
                        logger.debug(f"Could not request BT feature report 0x05: {ex}")

                self._ensure_virtual_gamepad()
                self.reset_effects()
                if self.on_state_change:
                    try:
                        self.on_state_change()
                    except Exception:
                        pass
                return True
            except Exception as e:
                logger.debug(f"Could not open device candidate {path}: {e}")
                continue

        self.dev = None
        self.conn_type = CONN_DISCONNECTED
        return False

    def disconnect(self, reset: bool = True):
        """Resets controller state and closes HID handle."""
        with self.lock:
            self.motor_left = 0
            self.motor_right = 0
        if self.dev:
            if reset:
                try:
                    self._send_reset_report()
                except Exception:
                    pass
            try:
                self.dev.close()
            except Exception:
                pass
            self.dev = None
        if self.virtual_gamepad:
            try:
                self.virtual_gamepad.reset()
                self.virtual_gamepad.update()
            except Exception:
                pass
        self.device_path = None
        self.conn_type = CONN_DISCONNECTED
        self.product_name = "Not Connected"
        if self.on_state_change:
            try:
                self.on_state_change()
            except Exception:
                pass

    def set_left_trigger(self, mode: int, start_pos: int, strength: int, freq: int = 0):
        """Updates left adaptive trigger profile."""
        with self.lock:
            self.left_trigger_data = build_trigger_bytes(mode, start_pos, strength, freq)
            if mode > 0 or strength > 0:
                self.last_telemetry_time = time.time()
                self.telemetry_active = True

    def set_right_trigger(self, mode: int, start_pos: int, strength: int, freq: int = 0):
        """Updates right adaptive trigger profile."""
        with self.lock:
            self.right_trigger_data = build_trigger_bytes(mode, start_pos, strength, freq)
            if mode > 0 or strength > 0:
                self.last_telemetry_time = time.time()
                self.telemetry_active = True

    def set_led(self, r: int, g: int, b: int):
        """Sets target RGB color for touchpad lightbar."""
        with self.lock:
            self.target_rgb = (float(max(0, min(255, int(r)))),
                               float(max(0, min(255, int(g)))),
                               float(max(0, min(255, int(b)))))

    def set_player_leds(self, mask: int):
        """Sets player indicator LEDs bitmask (5 LEDs below touchpad)."""
        with self.lock:
            self.player_leds = int(mask) & 0x1F

    def set_rumble(self, left: int, right: int):
        """ERM rumble stub (disabled in favor of audio voice coil haptics)."""
        with self.lock:
            # Standard ERM rumble disabled in favor of audio-based HD haptics
            self.motor_left = 0
            self.motor_right = 0
            if left > 0 or right > 0:
                self.last_telemetry_time = time.time()
                self.telemetry_active = True

    def touch_telemetry(self):
        """Signals active telemetry flow to reset watchdog."""
        self.last_telemetry_time = time.time()
        self.telemetry_active = True

    def _send_reset_report(self):
        """Builds and dispatches zeroed state output report."""
        with self.lock:
            self.left_trigger_data = build_trigger_bytes(0, 0, 0)
            self.right_trigger_data = build_trigger_bytes(0, 0, 0)
            self.motor_left = 0
            self.motor_right = 0
            self.target_rgb = (0.0, 0.0, 0.0)
            self.current_rgb = (0.0, 0.0, 0.0)
            self.led_rgb = (0, 0, 0)
            self.player_leds = 0
        self._write_report()

    def reset_effects(self):
        """Clears all trigger resistance and LED effects."""
        try:
            self._send_reset_report()
        except Exception:
            pass

    def _write_report(self) -> bool:
        """
        Sends HID output report to controller.
        Uses report ID 0x02 (48 bytes) on USB, or report ID 0x31 (78 bytes + CRC32) on Bluetooth.
        """
        if not self.dev:
            return False

        with self.lock:
            lt = list(self.left_trigger_data)
            rt = list(self.right_trigger_data)
            ml = self.motor_left if self.enable_rumble else 0
            mr = self.motor_right if self.enable_rumble else 0
            rgb = self.led_rgb if self.enable_rgb else (0, 0, 0)
            pled = self.player_leds if self.enable_player_leds else 0

        try:
            valid_flag0 = 0x04 | 0x08
            if self.enable_rumble:
                valid_flag0 |= 0x01 | 0x02
            valid_flag1 = 0x04 | 0x10 | 0x01 | 0x02

            if self.conn_type == CONN_USB:
                report = [0] * 48
                report[0] = 0x02
                report[1] = valid_flag0
                report[2] = valid_flag1
                report[3] = mr
                report[4] = ml
                report[11:22] = rt
                report[22:33] = lt
                report[44] = pled
                report[45] = rgb[0]
                report[46] = rgb[1]
                report[47] = rgb[2]

                with self._write_lock:
                    res = self.dev.write(bytes(report))
                if res <= 0:
                    logger.warning("HID write returned error; disconnecting device")
                    self.disconnect(reset=False)
                    return False
                self.packets_sent += 1
                return True

            elif self.conn_type == CONN_BT:
                report = [0] * 78
                report[0] = 0x31
                report[1] = 0x02
                report[2] = 0x10
                report[3] = valid_flag0
                report[4] = valid_flag1
                report[5] = mr
                report[6] = ml
                report[13:24] = rt
                report[24:35] = lt
                report[46] = pled
                report[47] = rgb[0]
                report[48] = rgb[1]
                report[49] = rgb[2]

                crc = _compute_bt_crc(report)
                report[74] = crc & 0xFF
                report[75] = (crc >> 8) & 0xFF
                report[76] = (crc >> 16) & 0xFF
                report[77] = (crc >> 24) & 0xFF

                with self._write_lock:
                    res = self.dev.write(bytes(report))
                if res <= 0:
                    logger.warning("HID write returned error; disconnecting device")
                    self.disconnect(reset=False)
                    return False
                self.packets_sent += 1
                return True

        except Exception as e:
            logger.warning(f"HID write failed: {e}")
            self.disconnect(reset=False)
            return False

        return False

    def start(self):
        """Starts background HID I/O polling thread."""
        if self.running:
            return
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        """Stops I/O polling, releases HID devices, and destroys virtual gamepad."""
        self.running = False
        with self.lock:
            self.motor_left = 0
            self.motor_right = 0
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
        self.disconnect(reset=True)
        if self.virtual_gamepad:
            try:
                self.virtual_gamepad.reset()
                self.virtual_gamepad.update()
            except Exception:
                pass
            self.virtual_gamepad = None
            self.virtual_gamepad_active = False

    def _worker_loop(self):
        """High-frequency (up to 250 Hz) HID read/write and virtual gamepad synchronization loop."""
        last_write_time = 0.0
        while self.running:
            try:
                now = time.time()
                if not self.dev:
                    if not self.connect():
                        time.sleep(0.5)
                        continue
                    else:
                        self._ensure_virtual_gamepad()

                has_input = False
                try:
                    data = self.dev.read(128)
                except Exception:
                    data = None

                if data and len(data) >= 30:
                    has_input = True
                    report_id = data[0]

                    # If on Bluetooth and received basic 0x01 report, poke it to switch to 0x31
                    if self.conn_type == CONN_BT and report_id != 0x31:
                        if now - getattr(self, '_last_bt_poke', 0.0) > 1.0:
                            self._last_bt_poke = now
                            try:
                                self.dev.get_feature_report(0x05, 64)
                            except Exception:
                                pass

                    if report_id == 0x01:
                        offset = 1
                        motion_offset = 16
                    else:
                        offset = 2
                        motion_offset = 17

                    if len(data) >= motion_offset + 12:
                        raw_bytes = bytes(data)
                        gx, gy, gz, ax, ay, az = struct.unpack_from('<hhhhhh', raw_bytes, motion_offset)

                        phys_lx = (data[offset] - 128) / 128.0
                        phys_ly = -((data[offset + 1] - 128) / 128.0)
                        phys_rx = (data[offset + 2] - 128) / 128.0
                        phys_ry = -((data[offset + 3] - 128) / 128.0)
                        raw_l2 = data[offset + 4] / 255.0
                        raw_r2 = data[offset + 5] / 255.0

                        # Non-linear gamma curve modeling progressive pedal resistance
                        l2_norm = raw_l2 ** self.brake_gamma
                        r2_norm = raw_r2 ** self.throttle_gamma
                        self.last_l2 = l2_norm
                        self.last_r2 = r2_norm
                        
                        # Save raw states for Diagnostics
                        self.state_l2 = raw_l2
                        self.state_r2 = raw_r2
                        self.state_ax = ax
                        self.state_ay = ay
                        self.state_az = az
                        self.state_gx = gx
                        self.state_gy = gy
                        self.state_gz = gz

                        b0 = data[offset + 7]
                        b1 = data[offset + 8]
                        b2 = data[offset + 9]
                        touchpad_click = bool(b2 & 0x02)

                        steer_x = self.gyro.process_imu(
                            ax_raw=ax, ay_raw=ay, az_raw=az,
                            gx_raw=gx, gy_raw=gy, gz_raw=gz,
                            speed_kmh=self.speed_kmh,
                            touchpad_clicked=touchpad_click
                        )

                        if self.virtual_gamepad:
                            self._sync_gamepad(
                                steer_x, phys_lx, phys_ly, phys_rx, phys_ry,
                                l2_norm, r2_norm, b0, b1, b2
                            )

                # Telemetry watchdog: clear active effects if no updates received within timeout
                if self.telemetry_active and (now - self.last_telemetry_time > self.watchdog_timeout):
                    self.telemetry_active = False
                    with self.lock:
                        self.left_trigger_data = build_trigger_bytes(0, 0, 0)
                        self.right_trigger_data = build_trigger_bytes(0, 0, 0)
                        self.motor_left = 0
                        self.motor_right = 0
                        self.target_rgb = (0.0, 0.0, 0.0)
                        self.player_leds = 0

                # Rate-limit HID output reports to ~60 Hz with EMA color smoothing
                if now - last_write_time >= 0.016:
                    with self.lock:
                        cr, cg, cb = self.current_rgb
                        tr, tg, tb = self.target_rgb
                        nr = cr + (tr - cr) * 0.25
                        ng = cg + (tg - cg) * 0.25
                        nb = cb + (tb - cb) * 0.25
                        self.current_rgb = (nr, ng, nb)
                        self.led_rgb = (int(round(nr)), int(round(ng)), int(round(nb)))

                    self._write_report()
                    last_write_time = now

                if not has_input:
                    time.sleep(0.001)

            except Exception as e:
                logger.error(f"Error in controller worker loop: {e}")
                self.disconnect(reset=False)
                time.sleep(0.5)
