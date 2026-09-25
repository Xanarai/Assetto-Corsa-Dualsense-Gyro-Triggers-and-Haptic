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
    LANG_UK, LANG_EN, DEFAULT_LANG, t, CONFIG_SECTIONS, CONFIG_ITEMS
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


class BridgeAPI:
    """JS-accessible API exposing configuration and status telemetry."""
    def __init__(self, app):
        self._app = app

    def get_initial_data(self):
        """Return configuration, localized strings, and status for frontend boot."""
        return {
            "config": self._app.config.data,
            "lang": self._app.current_lang,
            "sections": CONFIG_SECTIONS,
            "items": CONFIG_ITEMS,
            "texts": {
                LANG_UK: self._app.get_translations(LANG_UK),
                LANG_EN: self._app.get_translations(LANG_EN)
            },
            "is_active": self._app.is_active
        }

    def set_language(self, lang: str):
        """Update active language and persist to config."""
        self._app.set_language(lang)

    def save_config(self, config_dict: dict):
        """Save configuration dictionary and apply immediately to active devices."""
        for k, v in config_dict.items():
            self._app.config.data[k] = v
        self._app.config.save()
        self._app.apply_live_config()
        return {"success": True}

    def save_single_key(self, key: str, value):
        """Save a single configuration key and apply live."""
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

        return {
            "ctrl_conn": conn_str,
            "udp_active": udp_active,
            "sm_active": sm_active,
            "packet_rate": self._app.receiver.packets_per_second,
            "is_active": self._app.is_active
        }


class WebBridgeApp:
    def __init__(self, controller: DualSenseController, receiver: TelemetryReceiver, config: Config):
        self.controller = controller
        self.receiver = receiver
        self.config = config

        self.current_lang = self.config.get("language", DEFAULT_LANG)
        if self.current_lang not in (LANG_UK, LANG_EN):
            self.current_lang = DEFAULT_LANG

        self.is_active = True
        self._closing = False
        self.tray_icon = None
        self.window = None

        self.api = BridgeAPI(self)
        self._setup_tray()

    def get_translations(self, lang: str):
        """Return translation dictionary for the requested language."""
        from .i18n import TEXTS
        return TEXTS.get(lang, TEXTS[DEFAULT_LANG])

    def set_language(self, lang: str):
        """Update language preference and rebuild tray menu."""
        self.current_lang = lang
        self.config.set("language", lang)
        self._rebuild_tray_menu()

    def toggle_service(self) -> bool:
        """Toggle telemetry processing and reset hardware states when pausing."""
        self.is_active = not self.is_active
        if self.is_active:
            self.receiver.enable_triggers = self.config.get("enable_triggers", True)
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
                self.receiver.audio_engine.update_layers(0, 0, 0, 0, 0, 0, 0, 0)
            logger.info("Bridge service paused by user.")
        return self.is_active

    def apply_live_config(self):
        """Synchronize in-memory config values with active controller and receiver modules."""
        try:
            self.receiver.enable_triggers = self.config.get("enable_triggers", True)
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

            self.receiver.left_trigger_scale = float(self.config.get("left_trigger_scale", 1.0))
            self.receiver.right_trigger_scale = float(self.config.get("right_trigger_scale", 1.0))
            self.receiver.rgb_brightness_scale = float(self.config.get("rgb_brightness_scale", 1.0))
            self.receiver.haptic_processor.master_gain = float(self.config.get("haptic_master_gain", 1.8))
            self.receiver.haptic_processor.ffb_gain = float(self.config.get("haptic_ffb_gain", 0.15))
            self.receiver.haptic_processor.kerb_gain = float(self.config.get("haptic_kerb_gain", 1.6))
            self.receiver.haptic_processor.lockup_gain = float(self.config.get("haptic_lockup_gain", 1.5))
            self.receiver.haptic_processor.drift_gain = float(self.config.get("haptic_drift_gain", 1.2))
            self.receiver.haptic_processor.gearshift_gain = float(self.config.get("haptic_gearshift_gain", 1.5))
            self.receiver.auto_exit_on_game_close = bool(self.config.get("auto_exit_on_game_close", False))
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
            width=460,
            height=680,
            min_size=(420, 580),
            resizable=True,
            text_select=False,
            background_color='#09090b'
        )

        self.window.events.closing += self.on_window_closing
        webview.start(debug=False)

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
