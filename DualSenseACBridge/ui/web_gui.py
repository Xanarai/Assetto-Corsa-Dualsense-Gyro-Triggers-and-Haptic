"""
PyWebView frontend host for DualSense AC Bridge.
Uses WebView2 (Edge Chromium) with BridgeAPI exposed via pywebview js_api.
"""

import os
import sys
import time
import threading
import logging
import webview
from PIL import Image
import pystray
from pystray import MenuItem as item

from ..controller.dualsense import DualSenseController, CONN_USB, CONN_BT
from ..ac_integration.receiver import TelemetryReceiver
from ..config import Config
from .i18n import (
    LANG_EN, DEFAULT_LANG, t, CONFIG_SECTIONS, CONFIG_ITEMS
)

logger = logging.getLogger("DualSenseACBridge.WebGUI")


def get_asset_path(filename: str) -> str:
    """Resolve asset path across development directory, web folder, and PyInstaller bundle."""
    candidates = []
    if hasattr(sys, '_MEIPASS'):
        candidates.append(os.path.join(sys._MEIPASS, "assets", filename))
        candidates.append(os.path.join(sys._MEIPASS, "ui", "web", filename))
        candidates.append(os.path.join(sys._MEIPASS, filename))

    cur_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(cur_dir, "web", filename))
    candidates.append(os.path.join(cur_dir, "..", "assets", filename))
    candidates.append(os.path.join(cur_dir, "..", "..", "assets", filename))
    candidates.append(os.path.join(os.getcwd(), "assets", filename))

    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    return os.path.abspath(candidates[0])


_last_ds4_check = 0.0
_ds4_running = False


def check_ds4windows_process() -> bool:
    """Checks if DS4Windows process is currently active with 3-second cache."""
    global _last_ds4_check, _ds4_running
    now = time.time()
    if now - _last_ds4_check < 3.0:
        return _ds4_running
    _last_ds4_check = now
    try:
        import psutil
        _ds4_running = any(
            p.info.get('name') and p.info['name'].lower() == 'ds4windows.exe'
            for p in psutil.process_iter(['name'])
        )
    except Exception:
        _ds4_running = False
    return _ds4_running


class BridgeAPI:
    """JS-accessible API exposing configuration and status telemetry."""
    def __init__(self, app):
        self._app = app

    def log_info(self, msg: str):
        """Allows frontend to log diagnostics directly to python console."""
        logger.info(f"[UI] {msg}")
        return True

    def get_initial_data(self):
        """Return configuration, localized strings, haptic status, and status for frontend boot."""
        haptic_status = self._app.get_haptic_status()
        vigem_ok = getattr(self._app.controller, "vigem_ok", True)
        from ..controller.dualsense import check_directinput_driver
        directinput_ok, directinput_err = check_directinput_driver()
        return {
            "config": self._app.config.data,
            "lang": self._app.current_lang,
            "sections": CONFIG_SECTIONS,
            "items": CONFIG_ITEMS,
            "texts": {
                LANG_EN: self._app.get_translations(LANG_EN)
            },
            "is_active": self._app.is_active,
            "haptic_status": haptic_status,
            "vigem_ok": vigem_ok,
            "directinput_ok": directinput_ok,
            "directinput_error": directinput_err,
            "ds4_running": check_ds4windows_process(),
        }

    def set_language(self, lang: str):
        """Update active language and persist to config."""
        self._app.set_language(lang)

    def save_config(self, config_dict: dict):
        """Save configuration dictionary and apply immediately to active devices."""
        for k, v in config_dict.items():
            valid, err = self._app.config.validate_key(k, v)
            if not valid:
                logger.error(f"[UI CONFIG REJECTED] {err}")
                return {"success": False, "error": err}
        for k, v in config_dict.items():
            self._app.config.data[k] = v
        self._app.config.save()
        self._app.apply_live_config()
        return {"success": True}

    def save_single_key(self, key: str, value):
        """Save a single configuration key and apply live."""
        valid, err = self._app.config.validate_key(key, value)
        if not valid:
            logger.error(f"[UI CONFIG REJECTED] {err}")
            return {"success": False, "error": err}
        self._app.config.data[key] = value
        self._app.config.save()
        self._app.apply_live_config()
        return {"success": True}

    def toggle_service(self):
        """Toggle bridge processing state between active and paused."""
        is_active = self._app.toggle_service()
        return {"is_active": is_active}

    def get_status(self):
        """Return controller connection, UDP/shared memory heartbeat, and packet rate."""
        conn_str = "disconnected"
        if self._app.controller.conn_type == CONN_USB:
            conn_str = "usb"
        elif self._app.controller.conn_type == CONN_BT:
            conn_str = "bt"

        now = time.time()
        udp_active = (now - self._app.receiver.last_udp_packet_time < 1.0) and (self._app.receiver.packet_count > 0)
        sm_active = self._app.receiver.is_game_active
        engine = getattr(self._app.receiver, "audio_engine", None)
        audio_active = engine is not None and engine.is_active
        vigem_ok = getattr(self._app.controller, "vigem_ok", True)

        return {
            "ctrl_conn": conn_str,
            "udp_active": udp_active,
            "sm_active": sm_active,
            "packet_rate": self._app.receiver.packets_per_second,
            "is_active": self._app.is_active,
            "audio_active": audio_active,
            "vigem_ok": vigem_ok,
            "ds4_running": check_ds4windows_process(),
        }

    def open_vigembus_download(self):
        """Open official ViGEmBus download page in default browser."""
        import webbrowser
        url = "https://vigembusdriver.com/"
        logger.info(f"[UI] Opening ViGEmBus download link: {url}")
        try:
            webbrowser.open(url)
            return {"ok": True}
        except Exception as e:
            logger.warning(f"Failed to open browser for ViGEmBus: {e}")
            return {"ok": False, "error": str(e)}

    def check_vigembus_status(self):
        """Re-test ViGEmBus driver availability."""
        from ..controller.dualsense import check_vigembus_driver, check_directinput_driver
        ok, err = check_vigembus_driver(force_refresh=True)
        ds4_ok, ds4_err = check_directinput_driver(force_refresh=True)
        self._app.controller.vigem_ok = ok
        self._app.controller.vigem_error = err
        logger.info(f"[UI] check_vigembus_status: ok={ok}, err={err}, directinput_ok={ds4_ok}")
        return {"vigem_ok": ok, "error": err, "directinput_ok": ds4_ok, "directinput_error": ds4_err}

    def check_haptic_status(self):
        """Read-only diagnostic check of DualSense audio device configuration."""
        from ..controller.dualsense import CONN_BT, CONN_DISCONNECTED
        if self._app.controller.conn_type == CONN_BT:
            return self._app.get_haptic_status()

        if self._app.controller.conn_type == CONN_DISCONNECTED:
            try:
                self._app.controller.connect()
            except Exception:
                pass

        engine = getattr(self._app.receiver, "audio_engine", None)
        if engine and not engine.is_active and self._app.controller.conn_type != CONN_DISCONNECTED:
            try:
                engine.ensure_started(force_retry=True)
            except Exception:
                pass

        st = self._app.get_haptic_status()
        logger.info(f"[UI] check_haptic_status: {st}")
        return st

    def open_sound_settings(self):
        """Open Windows Sound Settings page (ms-settings:sound or mmsys.cpl)."""
        try:
            from ..haptics.audio_setup import open_sound_settings
            return {"ok": open_sound_settings()}
        except Exception as e:
            logger.debug(f"open_sound_settings error: {e}")
            return {"ok": False, "error": str(e)}

    def open_mmsys_cpl(self):
        """Directly open classic Windows Sound Control Panel (mmsys.cpl)."""
        try:
            from ..haptics.audio_setup import open_mmsys_cpl
            logger.info("[UI] Opening classic Sound Control Panel (mmsys.cpl)")
            return {"ok": open_mmsys_cpl()}
        except Exception as e:
            logger.warning(f"open_mmsys_cpl error: {e}")
            return {"ok": False, "error": str(e)}

    def run_haptic_wizard(self):
        """Attempt to enable DualSense device and apply 4-channel format."""
        from ..controller.dualsense import CONN_BT
        if self._app.controller.conn_type == CONN_BT:
            return {
                "format_ok": False,
                "volume_ok": False,
                "device_enabled": False,
                "error": "Audio haptics are not supported over Bluetooth. Connect via USB cable.",
            }
        logger.info("[UI] run_haptic_wizard requested")
        try:
            from ..haptics.audio_setup import (
                enable_dualsense_endpoint_com,
                check_dualsense_audio_status,
                run_elevated_setup,
                _set_volume_pycaw,
            )

            # 1. First try non-elevated COM enable (no UAC dialog needed for simple enable!)
            com_ok = enable_dualsense_endpoint_com()
            st = check_dualsense_audio_status()
            logger.info(f"[UI] Initial COM enable: {com_ok}, status: {st}")

            # If device is now active and already 4-channel, ensure volume is 100% and start engine
            if st.get("device_found") and not st.get("device_disabled") and st.get("is_4ch"):
                vol_ok, name = _set_volume_pycaw(1.0)
                engine = getattr(self._app.receiver, "audio_engine", None)
                if engine and not engine.is_active:
                    try:
                        engine.ensure_started(force_retry=True)
                    except Exception:
                        pass
                logger.info(f"[UI] Device already 4-ch, volume set: {vol_ok} ({name})")
                return {
                    "format_ok": True,
                    "device_enabled": True,
                    "volume_ok": vol_ok,
                    "device_name": name,
                    "error": None,
                }

            # 2. Otherwise run elevated setup for 4-channel registry format
            logger.info("[UI] Invoking run_elevated_setup...")
            res = run_elevated_setup()
            logger.info(f"[UI] run_elevated_setup completed: {res}")
            if res.get("format_ok") or res.get("device_enabled"):
                engine = getattr(self._app.receiver, "audio_engine", None)
                if engine:
                    try:
                        engine.ensure_started(force_retry=True)
                    except Exception:
                        pass
            return res
        except Exception as e:
            logger.error(f"[UI] run_haptic_wizard exception: {e}", exc_info=True)
            return {
                "format_ok": False,
                "volume_ok": False,
                "device_enabled": False,
                "error": str(e),
            }

    def set_haptic_volume(self):
        """Set DualSense volume to 100% (no admin needed)."""
        from ..controller.dualsense import CONN_BT
        if self._app.controller.conn_type == CONN_BT:
            return {"volume_ok": False, "error": "Not applicable over Bluetooth."}
        try:
            from ..haptics.audio_setup import _set_volume_pycaw
            ok, name = _set_volume_pycaw(1.0)
            return {"volume_ok": ok, "device_name": name}
        except Exception as e:
            return {"volume_ok": False, "error": str(e)}

    def test_feedback(self):
        """Legacy compatibility hook: launches triggers test."""
        logger.info("BridgeAPI.test_feedback called (legacy redirect -> start_diagnostics('triggers'))")
        return self.start_diagnostics('triggers')

    def start_diagnostics(self, mode: str):
        """mode: 'triggers' or 'gyro'"""
        logger.info(f"BridgeAPI.start_diagnostics called: mode={mode}")
        self._app.diagnostics_mode = mode
        
        if mode == 'triggers':
            # Ensure controller HID handle is active and connected
            if not self._app.controller.dev:
                logger.info("Diagnostics: Controller not connected, reconnecting...")
                self._app.controller.connect()

            self._app.controller.set_led(0, 150, 255)
            # Continuous progressive force feedback (mode 1, start 0, strength 8)
            self._app.controller.set_left_trigger(1, 0, 8)
            self._app.controller.set_right_trigger(1, 0, 8)
            self._app.controller.touch_telemetry()
            
            engine = getattr(self._app.receiver, "audio_engine", None)
            audio_started = False
            if engine:
                try:
                    audio_started = engine.ensure_started(force_retry=True)
                    logger.info(f"Diagnostics: audio_engine.ensure_started -> {audio_started}, is_active={engine.is_active}")
                except Exception as e:
                    logger.warning(f"Could not start audio engine: {e}")
            
            haptic_status = self._app.get_haptic_status()
            audio_ok = audio_started or (engine is not None and engine.is_active)
            
            def _trigger_test_loop():
                logger.info("Started trigger diagnostics loop.")
                while self._app.diagnostics_mode == 'triggers':
                    self._app.controller.touch_telemetry()  # Prevent watchdog timeout!
                    l2 = getattr(self._app.controller, 'state_l2', 0.0)
                    r2 = getattr(self._app.controller, 'state_r2', 0.0)
                    if engine and engine.is_active:
                        engine.update_haptics(l2, r2, 120.0, 120.0)
                    else:
                        self._app.controller.set_rumble(int(l2 * 255), int(r2 * 255))
                    time.sleep(0.016)
                if engine and engine.is_active:
                    engine.stop_all()
                self._app.controller.set_rumble(0, 0)
                self._app.controller.reset_effects()
                logger.info("Trigger diagnostics loop finished.")
                
            threading.Thread(target=_trigger_test_loop, daemon=True).start()
            return {
                "status": "ok",
                "mode": mode,
                "audio_ok": audio_ok,
                "haptic_status": haptic_status,
            }
        
        elif mode == 'gyro':
            self._app.controller.set_led(160, 32, 240)  # Violet/Purple for gyro
            
            def _gyro_watchdog_loop():
                logger.info("Started gyro diagnostics loop.")
                while self._app.diagnostics_mode == 'gyro':
                    self._app.controller.touch_telemetry()
                    time.sleep(0.05)
                self._app.controller.reset_effects()
                logger.info("Gyro diagnostics loop finished.")
                
            threading.Thread(target=_gyro_watchdog_loop, daemon=True).start()
            
        return {"status": "ok", "mode": mode}

    def stop_diagnostics(self):
        logger.info("BridgeAPI.stop_diagnostics called")
        self._app.diagnostics_mode = None
        self._app.controller.reset_effects()
        self._app.controller.set_rumble(0, 0)
        engine = getattr(self._app.receiver, "audio_engine", None)
        if engine and engine.is_active:
            engine.stop_all()
        return {"status": "stopped"}

    def get_diagnostics_data(self):
        ctrl = self._app.controller
        steer_angle = float(getattr(ctrl.gyro, 'filtered_angle', 0.0))
        steer_out = float(getattr(ctrl.gyro, 'final_output', 0.0))
        max_angle = float(getattr(ctrl.gyro, 'max_steer_angle', 65.0))
        return {
            "l2": getattr(ctrl, 'state_l2', 0.0),
            "r2": getattr(ctrl, 'state_r2', 0.0),
            "steer_angle": round(steer_angle, 1),
            "steer_output": round(steer_out * 100.0, 1),
            "max_angle": round(max_angle, 1),
            "ax": getattr(ctrl, 'state_ax', 0),
            "ay": getattr(ctrl, 'state_ay', 0),
            "az": getattr(ctrl, 'state_az', 0),
            "gx": getattr(ctrl, 'state_gx', 0),
            "gy": getattr(ctrl, 'state_gy', 0),
            "gz": getattr(ctrl, 'state_gz', 0),
        }


class WebBridgeApp:
    def __init__(self, controller: DualSenseController, receiver: TelemetryReceiver, config: Config):
        self.controller = controller
        self.receiver = receiver
        self.config = config

        self.current_lang = LANG_EN

        self.is_active = True
        self._closing = False
        self.diagnostics_mode = None
        self.tray_icon = None
        self.window = None

        self.api = BridgeAPI(self)
        self._setup_tray()

    def get_haptic_status(self) -> dict:
        """
        Returns runtime haptic status based on actual controller and audio engine state.

        Logic:
          - Controller not connected → no status shown (needs_setup=False, device_found=False)
          - Controller connected + audio engine active → all OK
          - Controller connected + audio engine NOT active → needs setup
        """
        from ..controller.dualsense import CONN_DISCONNECTED, CONN_BT

        ctrl_connected = self.controller.conn_type != CONN_DISCONNECTED

        if not ctrl_connected:
            # No controller → nothing to show, no setup needed banner
            return {
                "device_found": False,
                "device_disabled": False,
                "device_name": "",
                "channels": 0,
                "is_4ch": False,
                "volume_ok": True,
                "volume_level": 1.0,
                "needs_setup": False,
                "ctrl_connected": False,
            }

        # Bluetooth connection: Windows does not expose 4-channel audio haptics over standard BT.
        # Mark needs_setup as False so NO setup banners or popups are ever triggered!
        if self.controller.conn_type == CONN_BT:
            return {
                "device_found": False,
                "device_disabled": False,
                "device_name": "Bluetooth (Haptics via USB only)",
                "channels": 0,
                "is_4ch": False,
                "volume_ok": True,
                "volume_level": 1.0,
                "needs_setup": False,
                "ctrl_connected": True,
                "is_bt": True,
            }

        # Controller is connected — check audio engine runtime state
        engine = getattr(self.receiver, "audio_engine", None)
        engine_active = engine is not None and engine.is_active

        if engine_active:
            # Audio engine running with 4ch stream — everything is fine
            return {
                "device_found": True,
                "device_disabled": False,
                "device_name": getattr(engine, "device_name", "DualSense"),
                "channels": 4,
                "is_4ch": True,
                "volume_ok": True,
                "volume_level": 1.0,
                "needs_setup": False,
                "ctrl_connected": True,
            }

        # Engine not active — run diagnostic to find out why
        try:
            from ..haptics.audio_setup import check_dualsense_audio_status
            result = check_dualsense_audio_status()
            result["ctrl_connected"] = True

            # If device is already active, 4-channel and enabled, auto-start audio engine right now!
            if result.get("device_found") and not result.get("device_disabled") and result.get("is_4ch"):
                if engine and not engine.is_active:
                    try:
                        started = engine.ensure_started(force_retry=True)
                        if started:
                            result["needs_setup"] = False
                    except Exception as e_start:
                        logger.debug(f"Auto-starting audio engine in get_haptic_status: {e_start}")

            return result
        except Exception as e:
            logger.debug(f"Haptic status check failed: {e}")
            return {
                "device_found": False, "device_disabled": False, "device_name": "",
                "channels": 0, "is_4ch": False,
                "volume_ok": False, "volume_level": 0.0,
                "needs_setup": True, "ctrl_connected": True,
            }

    def get_translations(self, lang: str):
        """Return translation dictionary for the requested language."""
        from .i18n import TEXTS
        return TEXTS.get(lang, TEXTS[DEFAULT_LANG])

    def set_language(self, lang: str):
        """Update language preference (English only) and rebuild tray menu."""
        self.current_lang = LANG_EN
        self.config.set("language", LANG_EN)
        self._rebuild_tray_menu()

    def toggle_service(self) -> bool:
        """Toggle telemetry processing and reset hardware states when pausing."""
        self.is_active = not self.is_active
        if self.is_active:
            self.receiver.enable_triggers = self.config.get("enable_triggers", True)
            self.receiver.enable_abs_vibration = self.config.get("enable_abs_vibration", True)
            self.receiver.enable_audio_haptics = self.config.get("enable_audio_haptics", True)
            self.receiver.enable_rgb = self.config.get("enable_rgb", True)
            self.controller.enable_rgb = self.receiver.enable_rgb
            self.controller.gyro.enabled = self.config.get("enable_gyro", True)
            logger.info("Bridge service resumed by user.")
        else:
            self.receiver.enable_triggers = False
            self.receiver.enable_audio_haptics = False
            self.receiver.enable_rgb = False
            self.controller.enable_rgb = False
            self.controller.gyro.enabled = False

            self.controller.reset_effects()
            if self.receiver.audio_engine and self.receiver.audio_engine.is_active:
                self.receiver.audio_engine.stop_all()
            logger.info("Bridge service paused by user.")
        return self.is_active

    def apply_live_config(self):
        """Synchronize in-memory config values with active controller and receiver modules."""
        try:
            self.receiver.enable_triggers = self.config.get("enable_triggers", True)
            self.receiver.enable_abs_vibration = self.config.get("enable_abs_vibration", True)
            self.receiver.enable_audio_haptics = self.config.get("enable_audio_haptics", True)
            self.receiver.enable_rgb = self.config.get("enable_rgb", True)
            self.controller.enable_rgb = self.receiver.enable_rgb
            self.controller.enable_player_leds = self.config.get("enable_player_leds", True)

            self.controller.gyro.enabled = self.config.get("enable_gyro", True)
            max_gyro = min(90.0, float(self.config.get("gyro_max_angle", 65.0)))
            self.controller.gyro.max_steer_angle = max_gyro
            self.controller.gyro.deadzone = float(self.config.get("gyro_deadzone", 0.002))
            self.controller.gyro.gamma = float(self.config.get("gyro_gamma", 1.0))
            self.controller.gyro.invert_steer = bool(self.config.get("gyro_invert", False))
            self.controller.gyro.stick_override = bool(self.config.get("gyro_stick_override", True))
            self.controller.gyro.stick_override_threshold = float(self.config.get("gyro_stick_override_threshold", 0.20))
            self.controller.gyro.speed_sensitivity = float(self.config.get("gyro_speed_sensitivity", 0.15))
            self.controller.gyro.enable_speed_sensitivity = bool(self.config.get("gyro_enable_speed_sensitivity", True))
            self.controller.gyro.gyro_axis = str(self.config.get("gyro_axis", "y")).lower()
            self.controller.gyro.gyro_rate_invert = bool(self.config.get("gyro_rate_invert", False))
            if hasattr(self.controller.gyro, "set_centering_tau"):
                try:
                    self.controller.gyro.set_centering_tau(self.config.get("gyro_centering_tau", 0.06))
                except ValueError as e:
                    logger.error(f"[LIVE CONFIG ERROR] Could not apply gyro_centering_tau: {e}")

            self.receiver.left_trigger_scale = float(self.config.get("left_trigger_scale", 1.0))
            self.receiver.right_trigger_scale = float(self.config.get("right_trigger_scale", 1.0))
            self.receiver.rgb_brightness_scale = float(self.config.get("rgb_brightness_scale", 1.0))
            self.receiver.haptic_processor.master_gain = float(self.config.get("haptic_master_gain", 1.8))
            self.receiver.haptic_processor.kerb_gain = float(self.config.get("haptic_kerb_gain", 1.6))
            self.receiver.haptic_processor.lockup_gain = float(self.config.get("haptic_lockup_gain", 1.5))
            self.receiver.haptic_processor.drift_gain = float(self.config.get("haptic_drift_gain", 1.2))
            self.receiver.haptic_processor.gearshift_gain = float(self.config.get("haptic_gearshift_gain", 1.5))
            self.receiver.haptic_processor.ffb_gain = float(self.config.get("haptic_ffb_gain", 1.0))
            self.receiver.auto_exit_on_game_close = bool(self.config.get("auto_exit_on_game_close", False))
            
            new_mode = str(self.config.get("controller_mode", "xinput")).lower()
            if hasattr(self.controller, "controller_mode"):
                self.controller.controller_mode = new_mode

            key_binds = self.config.get("key_binds", {})
            if hasattr(self.controller, "keyboard_emulator") and self.controller.keyboard_emulator:
                self.controller.keyboard_emulator.update_binds(key_binds)
                
        except Exception as e:
            logger.warning(f"Error applying live settings: {e}")

    def _setup_tray(self):
        """Initialize system tray icon with context menu."""
        icon_path = get_asset_path("icon_64.png")
        if not os.path.exists(icon_path):
            icon_path = get_asset_path("icon.png")

        try:
            tray_img = Image.open(icon_path)
        except Exception:
            tray_img = Image.new('RGB', (64, 64), color=(30, 30, 30))

        self.tray_icon = pystray.Icon("DualSenseACBridge", tray_img, "DualSense AC Bridge", self._create_tray_menu())
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _create_tray_menu(self):
        return pystray.Menu(
            item(t("tray_show", self.current_lang), self._tray_show_window, default=True),
            item(t("tray_toggle", self.current_lang), self._tray_toggle),
            pystray.Menu.SEPARATOR,
            item(t("tray_quit", self.current_lang), self._tray_quit)
        )

    def _rebuild_tray_menu(self):
        if self.tray_icon:
            try:
                self.tray_icon.menu = self._create_tray_menu()
            except Exception as e:
                logger.debug(f"Could not update tray menu: {e}")

    def _tray_show_window(self, icon, item_obj):
        if self.window:
            self.window.show()
            self.window.restore()

    def _tray_toggle(self, icon, item_obj):
        self.toggle_service()

    def _tray_quit(self, icon, item_obj):
        self.quit_app()

    def on_window_closing(self):
        """Minimize to system tray on window close instead of terminating."""
        if self._closing:
            return True
        if self.window:
            self.window.hide()
            return False
        return True

    def run(self):
        """Launch pywebview Edge/Chromium window and enter UI event loop."""
        html_path = os.path.join(os.path.dirname(__file__), "web", "index.html")
        if not os.path.exists(html_path):
            html_path = get_asset_path("index.html")

        self.window = webview.create_window(
            title="DualSense AC Bridge",
            url=html_path,
            js_api=self.api,
            width=720,
            height=720,
            min_size=(720, 720),
            resizable=False,
            text_select=False,
            background_color='#09090b'
        )

        self.window.events.closing += self.on_window_closing
        webview.start(debug=False, private_mode=False)

    def quit_app(self):
        """Stop controller, telemetry receiver, tray icon, and terminate process."""
        if self._closing:
            return
        self._closing = True
        logger.info("Exiting DualSense AC Bridge...")

        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass

        try:
            self.controller.reset_effects()
            self.controller.stop()
        except Exception:
            pass

        try:
            self.receiver.stop()
        except Exception:
            pass

        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass

        os._exit(0)
