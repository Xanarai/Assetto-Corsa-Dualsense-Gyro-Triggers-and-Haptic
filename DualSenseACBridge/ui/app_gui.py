"""
Modern Minimalist GUI for DualSense AC Bridge.
Features:
- Streamlined single-action Start / Stop control.
- System Tray integration (minimizes to tray on close).
- Clean visual status card and Assetto Corsa telemetry monitor.
"""

import os
import sys
import time
import threading
import logging
import customtkinter as ctk
from PIL import Image
import pystray
from pystray import MenuItem as item

from ..controller.dualsense import DualSenseController, CONN_USB, CONN_BT
from ..ac_integration.receiver import TelemetryReceiver
from ..config import Config

logger = logging.getLogger("DualSenseACBridge.AppGUI")

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def get_asset_path(filename: str) -> str:
    """Finds asset path for both dev mode and PyInstaller onedir/onefile."""
    candidates = []
    # PyInstaller temp folder or exe folder
    if hasattr(sys, '_MEIPASS'):
        candidates.append(os.path.join(sys._MEIPASS, "assets", filename))
        candidates.append(os.path.join(sys._MEIPASS, filename))
    if hasattr(sys, 'executable'):
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "assets", filename))
        candidates.append(os.path.join(exe_dir, filename))

    # Current bridge directory
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates.append(os.path.join(current_dir, "assets", filename))
    candidates.append(os.path.join(current_dir, filename))

    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]


class BridgeApp(ctk.CTk):
    def __init__(self, controller: DualSenseController, receiver: TelemetryReceiver, config: Config):
        super().__init__()

        self.controller = controller
        self.receiver = receiver
        self.config = config

        self.is_active = True
        self.tray_icon: pystray.Icon = None
        self._closing = False

        # Window setup
        self.title("DualSense AC Bridge")
        self.geometry("380x520")
        self.resizable(False, False)

        # Set window icon if available
        ico_path = get_asset_path("icon.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception as e:
                logger.debug(f"Could not set window iconbitmap: {e}")

        # Intercept window close (X) to minimize to tray
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

        # Setup UI
        self._build_ui()

        # Setup System Tray Icon
        self._setup_tray()

        # Periodic status refresh
        self.update_status()

    def _build_ui(self):
        # Main background container
        self.main_frame = ctk.CTkFrame(self, fg_color="#18181B", corner_radius=0)
        self.main_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Top Banner / Splash Image
        icon_png = get_asset_path("icon_128.png")
        if not os.path.exists(icon_png):
            icon_png = get_asset_path("icon.png")

        if os.path.exists(icon_png):
            try:
                pil_img = Image.open(icon_png)
                self.banner_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(110, 110))
                self.banner_label = ctk.CTkLabel(self.main_frame, image=self.banner_img, text="")
                self.banner_label.pack(pady=(20, 6))
            except Exception as e:
                logger.debug(f"Could not load banner image: {e}")

        # Title & Subtitle
        self.lbl_title = ctk.CTkLabel(
            self.main_frame,
            text="DualSense AC Bridge",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#F4F4F5"
        )
        self.lbl_title.pack(pady=(0, 2))

        self.lbl_subtitle = ctk.CTkLabel(
            self.main_frame,
            text="Assetto Corsa • Adaptive Triggers & Haptics",
            font=ctk.CTkFont(size=12),
            text_color="#A1A1AA"
        )
        self.lbl_subtitle.pack(pady=(0, 16))

        # Status Card Box
        self.card = ctk.CTkFrame(self.main_frame, fg_color="#27272A", corner_radius=12)
        self.card.pack(fill="x", padx=24, pady=(0, 20))

        # Controller Status Row
        row1 = ctk.CTkFrame(self.card, fg_color="transparent")
        row1.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(row1, text="Геймпад:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#E4E4E7").pack(side="left")
        self.lbl_ctrl = ctk.CTkLabel(row1, text="Пошук...", font=ctk.CTkFont(size=13), text_color="#A1A1AA")
        self.lbl_ctrl.pack(side="right")

        # Game Status Row
        row2 = ctk.CTkFrame(self.card, fg_color="transparent")
        row2.pack(fill="x", padx=14, pady=6)
        ctk.CTkLabel(row2, text="Assetto Corsa:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#E4E4E7").pack(side="left")
        self.lbl_game = ctk.CTkLabel(row2, text="Очікування гри", font=ctk.CTkFont(size=13), text_color="#EAB308")
        self.lbl_game.pack(side="right")

        # Service State Row
        row3 = ctk.CTkFrame(self.card, fg_color="transparent")
        row3.pack(fill="x", padx=14, pady=(6, 12))
        ctk.CTkLabel(row3, text="Стан сервісу:", font=ctk.CTkFont(size=13, weight="bold"), text_color="#E4E4E7").pack(side="left")
        self.lbl_state = ctk.CTkLabel(row3, text="🟢 Працює", font=ctk.CTkFont(size=13, weight="bold"), text_color="#22C55E")
        self.lbl_state.pack(side="right")

        # Primary Big Action Button: START / STOP
        self.btn_toggle = ctk.CTkButton(
            self.main_frame,
            text="⏹️  ЗУПИНИТИ",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#DC2626",
            hover_color="#B91C1C",
            text_color="#FFFFFF",
            height=50,
            corner_radius=10,
            command=self.toggle_service
        )
        self.btn_toggle.pack(fill="x", padx=24, pady=(0, 14))

        # Bottom Hint (tray info)
        self.lbl_hint = ctk.CTkLabel(
            self.main_frame,
            text="💡 При закритті вікна програма згортається в трей",
            font=ctk.CTkFont(size=11),
            text_color="#71717A"
        )
        self.lbl_hint.pack(side="bottom", pady=(0, 14))

    def toggle_service(self):
        """Toggles between Running and Stopped state."""
        self.is_active = not self.is_active
        if self.is_active:
            # Resume active operation
            self.receiver.enable_triggers = self.config.get("enable_triggers", True)
            self.receiver.enable_audio_haptics = self.config.get("enable_audio_haptics", True)
            self.receiver.enable_rgb = self.config.get("enable_rgb", True)
            self.controller.enable_rgb = self.receiver.enable_rgb
            self.controller.gyro.enabled = self.config.get("enable_gyro", True)

            self.btn_toggle.configure(
                text="⏹️  ЗУПИНИТИ",
                fg_color="#DC2626",
                hover_color="#B91C1C"
            )
            self.lbl_state.configure(text="🟢 Працює", text_color="#22C55E")
            logger.info("Bridge service resumed by user.")
        else:
            # Stop / Pause active operation & reset triggers
            self.receiver.enable_triggers = False
            self.receiver.enable_audio_haptics = False
            self.receiver.enable_rgb = False
            self.controller.enable_rgb = False
            self.controller.gyro.enabled = False

            # Reset controller effects to neutral immediately
            self.controller.reset_effects()
            if self.receiver.audio_engine and self.receiver.audio_engine.is_active:
                self.receiver.audio_engine.update_layers(0, 0, 0, 0, 0, 0, 0, 0)

            self.btn_toggle.configure(
                text="▶️  ЗАПУСТИТИ",
                fg_color="#16A34A",
                hover_color="#15803D"
            )
            self.lbl_state.configure(text="⏸️ Зупинено", text_color="#EF4444")
            logger.info("Bridge service paused by user.")

    def update_status(self):
        """Periodically updates status badges without UI freezes."""
        if self._closing:
            return

        try:
            # Controller status
            if self.controller.conn_type == CONN_USB:
                self.lbl_ctrl.configure(text="DualSense (USB)", text_color="#22C55E")
            elif self.controller.conn_type == CONN_BT:
                self.lbl_ctrl.configure(text="DualSense (Bluetooth)", text_color="#38BDF8")
            else:
                self.lbl_ctrl.configure(text="Не підключено", text_color="#A1A1AA")

            # Game telemetry status
            now = time.time()
            udp_active = (now - self.receiver.last_udp_packet_time < 1.0) and (self.receiver.packet_count > 0)
            sm_active = self.receiver.sm.is_game_running()

            if udp_active:
                self.lbl_game.configure(text=f"Активна ({self.receiver.packets_per_second:.0f} Hz)", text_color="#22C55E")
            elif sm_active:
                self.lbl_game.configure(text="Активна (Shared Memory)", text_color="#22C55E")
            else:
                self.lbl_game.configure(text="Очікування гри...", text_color="#EAB308")

        except Exception as e:
            logger.debug(f"Status update error: {e}")

        # Refresh every 250ms
        self.after(250, self.update_status)

    def _setup_tray(self):
        """Creates the system tray icon."""
        icon_path = get_asset_path("icon_64.png")
        if not os.path.exists(icon_path):
            icon_path = get_asset_path("icon.png")

        try:
            tray_img = Image.open(icon_path)
        except Exception:
            tray_img = Image.new('RGB', (64, 64), color=(30, 30, 30))

        menu = pystray.Menu(
            item("Розгорнути вікно", self._tray_show_window, default=True),
            item("Старт / Стоп", self._tray_toggle),
            pystray.Menu.SEPARATOR,
            item("Вихід", self._tray_quit)
        )

        self.tray_icon = pystray.Icon("DualSenseACBridge", tray_img, "DualSense AC Bridge", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def on_window_close(self):
        """Minimizes window to tray instead of exiting."""
        self.withdraw()

    def show_window(self):
        """Brings the window back from tray to foreground."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def _tray_show_window(self, icon, item_obj):
        self.after(0, self.show_window)

    def _tray_toggle(self, icon, item_obj):
        self.after(0, self.toggle_service)

    def _tray_quit(self, icon, item_obj):
        self.after(0, self.quit_app)

    def quit_app(self):
        """Clean shutdown of all components."""
        if self._closing:
            return
        self._closing = True
        logger.info("Exiting DualSense AC Bridge...")

        # Stop system tray icon
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass

        # Reset and stop hardware
        try:
            self.controller.reset_effects()
            self.controller.stop()
        except Exception:
            pass

        try:
            self.receiver.stop()
        except Exception:
            pass

        try:
            self.destroy()
        except Exception:
            pass

        # Force terminate any remaining threads
        os._exit(0)
