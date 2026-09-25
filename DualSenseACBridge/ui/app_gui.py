"""
Modern Minimalist GUI for DualSense AC Bridge.
Features:
- Streamlined single-action Start / Stop control.
- Bilingual localization (Ukrainian / English) with interactive flag toggle in the top-right corner.
- Redesigned, categorized, and human-friendly Config tab (General, Triggers, Haptics, Gyroscope).
- Expandable info explanations (ℹ) for parameters.
- 'Advanced' toggle to reveal deep tuning parameters without overwhelming the user.
- System Tray integration.
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
from .i18n import (
    LANG_UK, LANG_EN, t, CONFIG_SECTIONS, CONFIG_ITEMS,
    get_item_label, get_item_info, get_section_title
)

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

        # Localization & state
        self.current_lang = self.config.get("language", LANG_UK)
        if self.current_lang not in (LANG_UK, LANG_EN):
            self.current_lang = LANG_UK

        self.is_active = True
        self.show_advanced = False
        self.tray_icon: pystray.Icon = None
        self._closing = False

        # Widget tracking for dynamic language updates
        self.config_vars = {}
        self.advanced_row_containers = []
        self.item_label_widgets = {}
        self.item_info_labels = {}
        self.info_boxes = {}
        self.section_title_labels = {}

        # Window setup
        self.title("DualSense AC Bridge")
        self.geometry("440x640")
        self.minsize(420, 580)
        self.resizable(True, True)

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

        # =========================================================================
        # Top Header Bar (Always Visible: App Title + Flag Language Switcher)
        # =========================================================================
        self.top_bar = ctk.CTkFrame(self.main_frame, fg_color="#18181B", height=42)
        self.top_bar.pack(fill="x", padx=14, pady=(8, 2))

        # Brand / App title
        self.header_title = ctk.CTkLabel(
            self.top_bar,
            text="🎮 DualSense AC Bridge",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#F4F4F5"
        )
        self.header_title.pack(side="left")

        # Flags container in top right corner
        self.flags_container = ctk.CTkFrame(self.top_bar, fg_color="#27272A", corner_radius=8)
        self.flags_container.pack(side="right")

        # Load flag images
        ua_flag_path = get_asset_path("flag_ua.png")
        en_flag_path = get_asset_path("flag_en.png")

        try:
            pil_ua = Image.open(ua_flag_path)
            self.img_flag_ua = ctk.CTkImage(light_image=pil_ua, dark_image=pil_ua, size=(24, 16))
        except Exception:
            self.img_flag_ua = None

        try:
            pil_en = Image.open(en_flag_path)
            self.img_flag_en = ctk.CTkImage(light_image=pil_en, dark_image=pil_en, size=(24, 16))
        except Exception:
            self.img_flag_en = None

        # Flag button: Ukrainian
        self.btn_flag_ua = ctk.CTkButton(
            self.flags_container,
            text="" if self.img_flag_ua else "🇺🇦 UA",
            image=self.img_flag_ua,
            width=36,
            height=26,
            corner_radius=6,
            command=lambda: self.set_language(LANG_UK)
        )
        self.btn_flag_ua.pack(side="left", padx=2, pady=2)

        # Flag button: English
        self.btn_flag_en = ctk.CTkButton(
            self.flags_container,
            text="" if self.img_flag_en else "🇬🇧 EN",
            image=self.img_flag_en,
            width=36,
            height=26,
            corner_radius=6,
            command=lambda: self.set_language(LANG_EN)
        )
        self.btn_flag_en.pack(side="left", padx=2, pady=2)

        self._update_flag_highlight()

        # =========================================================================
        # Tabview (Main & Config)
        # =========================================================================
        self.tabview = ctk.CTkTabview(self.main_frame, fg_color="transparent")
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        self.tab_main = self.tabview.add("main")
        self.tab_config = self.tabview.add("config")

        self._update_tab_headers()

        self._build_main_tab()
        self._build_config_tab()

    def _update_flag_highlight(self):
        """Highlights the active language flag button."""
        if self.current_lang == LANG_UK:
            self.btn_flag_ua.configure(
                fg_color="#2563EB",
                hover_color="#1D4ED8",
                border_width=1,
                border_color="#60A5FA"
            )
            self.btn_flag_en.configure(
                fg_color="transparent",
                hover_color="#3F3F46",
                border_width=0
            )
        else:
            self.btn_flag_en.configure(
                fg_color="#2563EB",
                hover_color="#1D4ED8",
                border_width=1,
                border_color="#60A5FA"
            )
            self.btn_flag_ua.configure(
                fg_color="transparent",
                hover_color="#3F3F46",
                border_width=0
            )

    def _update_tab_headers(self):
        """Updates text of tab buttons in CTkTabview."""
        try:
            btn_main = self.tabview._segmented_button._buttons_dict.get("main")
            btn_config = self.tabview._segmented_button._buttons_dict.get("config")
            if btn_main:
                btn_main.configure(text=f"📊  {t('tab_main', self.current_lang)}")
            if btn_config:
                btn_config.configure(text=f"⚙️  {t('tab_config', self.current_lang)}")
        except Exception as e:
            logger.debug(f"Could not update tab headers: {e}")

    def set_language(self, new_lang: str):
        """Switches the active language, updates UI, and persists to config."""
        if new_lang not in (LANG_UK, LANG_EN):
            return

        self.current_lang = new_lang
        self.config.set("language", new_lang)
        self._update_flag_highlight()
        self._update_tab_headers()

        # Update Main Tab Texts
        self.lbl_subtitle.configure(text=t("app_subtitle", self.current_lang))
        self.lbl_card_ctrl_title.configure(text=t("card_controller", self.current_lang))
        self.lbl_card_game_title.configure(text=t("card_game", self.current_lang))
        self.lbl_card_svc_title.configure(text=t("card_service", self.current_lang))
        self.lbl_hint.configure(text=t("tray_hint", self.current_lang))

        if self.is_active:
            self.btn_toggle.configure(text=t("btn_stop", self.current_lang))
            self.lbl_state.configure(text=t("service_running", self.current_lang))
        else:
            self.btn_toggle.configure(text=t("btn_start", self.current_lang))
            self.lbl_state.configure(text=t("service_stopped", self.current_lang))

        # Update Config Tab Texts
        self.lbl_cfg_lang_title.configure(text=t("cfg_lang_title", self.current_lang))
        self.lbl_cfg_lang_value.configure(text=t("cfg_lang_active", self.current_lang))
        self.lbl_cfg_lang_hint.configure(text=t("cfg_lang_hint", self.current_lang))
        self.btn_save_config.configure(text=t("cfg_btn_save", self.current_lang))

        if self.show_advanced:
            self.btn_adv_toggle.configure(text=t("cfg_btn_adv_hide", self.current_lang))
        else:
            self.btn_adv_toggle.configure(text=t("cfg_btn_adv_show", self.current_lang))

        # Update Section titles
        for sec in CONFIG_SECTIONS:
            sec_id = sec["id"]
            if sec_id in self.section_title_labels:
                self.section_title_labels[sec_id].configure(text=get_section_title(sec_id, self.current_lang))

        # Update Config Items Labels & Info Texts
        for item in CONFIG_ITEMS:
            key = item["key"]
            if key in self.item_label_widgets:
                self.item_label_widgets[key].configure(text=get_item_label(item, self.current_lang))
            if key in self.item_info_labels:
                self.item_info_labels[key].configure(text=get_item_info(item, self.current_lang))

        # Update Tray Menu
        self._rebuild_tray_menu()

    # =========================================================================
    # Main Tab UI
    # =========================================================================
    def _build_main_tab(self):
        # Top Banner / Splash Image
        icon_png = get_asset_path("icon_128.png")
        if not os.path.exists(icon_png):
            icon_png = get_asset_path("icon.png")

        if os.path.exists(icon_png):
            try:
                pil_img = Image.open(icon_png)
                self.banner_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(100, 100))
                self.banner_label = ctk.CTkLabel(self.tab_main, image=self.banner_img, text="")
                self.banner_label.pack(pady=(16, 4))
            except Exception as e:
                logger.debug(f"Could not load banner image: {e}")

        # Title & Subtitle
        self.lbl_title = ctk.CTkLabel(
            self.tab_main,
            text="DualSense AC Bridge",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#F4F4F5"
        )
        self.lbl_title.pack(pady=(0, 2))

        self.lbl_subtitle = ctk.CTkLabel(
            self.tab_main,
            text=t("app_subtitle", self.current_lang),
            font=ctk.CTkFont(size=12),
            text_color="#A1A1AA"
        )
        self.lbl_subtitle.pack(pady=(0, 16))

        # Status Card Box
        self.card = ctk.CTkFrame(self.tab_main, fg_color="#27272A", corner_radius=12)
        self.card.pack(fill="x", padx=24, pady=(0, 20))

        # Controller Status Row
        row1 = ctk.CTkFrame(self.card, fg_color="transparent")
        row1.pack(fill="x", padx=14, pady=(12, 6))
        self.lbl_card_ctrl_title = ctk.CTkLabel(row1, text=t("card_controller", self.current_lang), font=ctk.CTkFont(size=13, weight="bold"), text_color="#E4E4E7")
        self.lbl_card_ctrl_title.pack(side="left")
        self.lbl_ctrl = ctk.CTkLabel(row1, text=t("ctrl_searching", self.current_lang), font=ctk.CTkFont(size=13), text_color="#A1A1AA")
        self.lbl_ctrl.pack(side="right")

        # Game Status Row
        row2 = ctk.CTkFrame(self.card, fg_color="transparent")
        row2.pack(fill="x", padx=14, pady=6)
        self.lbl_card_game_title = ctk.CTkLabel(row2, text=t("card_game", self.current_lang), font=ctk.CTkFont(size=13, weight="bold"), text_color="#E4E4E7")
        self.lbl_card_game_title.pack(side="left")
        self.lbl_game = ctk.CTkLabel(row2, text=t("game_waiting", self.current_lang), font=ctk.CTkFont(size=13), text_color="#EAB308")
        self.lbl_game.pack(side="right")

        # Service State Row
        row3 = ctk.CTkFrame(self.card, fg_color="transparent")
        row3.pack(fill="x", padx=14, pady=(6, 12))
        self.lbl_card_svc_title = ctk.CTkLabel(row3, text=t("card_service", self.current_lang), font=ctk.CTkFont(size=13, weight="bold"), text_color="#E4E4E7")
        self.lbl_card_svc_title.pack(side="left")
        self.lbl_state = ctk.CTkLabel(row3, text=t("service_running", self.current_lang), font=ctk.CTkFont(size=13, weight="bold"), text_color="#22C55E")
        self.lbl_state.pack(side="right")

        # Primary Big Action Button: START / STOP
        self.btn_toggle = ctk.CTkButton(
            self.tab_main,
            text=t("btn_stop", self.current_lang),
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#DC2626",
            hover_color="#B91C1C",
            text_color="#FFFFFF",
            height=48,
            corner_radius=10,
            command=self.toggle_service
        )
        self.btn_toggle.pack(fill="x", padx=24, pady=(0, 14))

        # Bottom Hint (tray info)
        self.lbl_hint = ctk.CTkLabel(
            self.tab_main,
            text=t("tray_hint", self.current_lang),
            font=ctk.CTkFont(size=11),
            text_color="#71717A"
        )
        self.lbl_hint.pack(side="bottom", pady=(0, 12))

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
                text=t("btn_stop", self.current_lang),
                fg_color="#DC2626",
                hover_color="#B91C1C"
            )
            self.lbl_state.configure(text=t("service_running", self.current_lang), text_color="#22C55E")
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
                text=t("btn_start", self.current_lang),
                fg_color="#16A34A",
                hover_color="#15803D"
            )
            self.lbl_state.configure(text=t("service_stopped", self.current_lang), text_color="#EF4444")
            logger.info("Bridge service paused by user.")

    # =========================================================================
    # Config Tab UI
    # =========================================================================
    def _build_config_tab(self):
        # 1. Top Action & Info Header
        top_card = ctk.CTkFrame(self.tab_config, fg_color="#202023", corner_radius=10)
        top_card.pack(fill="x", padx=6, pady=(4, 8))

        # Language status row
        lang_row = ctk.CTkFrame(top_card, fg_color="transparent")
        lang_row.pack(fill="x", padx=12, pady=(10, 2))

        self.lbl_cfg_lang_title = ctk.CTkLabel(
            lang_row,
            text=t("cfg_lang_title", self.current_lang),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#E4E4E7"
        )
        self.lbl_cfg_lang_title.pack(side="left")

        self.lbl_cfg_lang_value = ctk.CTkLabel(
            lang_row,
            text=t("cfg_lang_active", self.current_lang),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38BDF8"
        )
        self.lbl_cfg_lang_value.pack(side="right")

        self.lbl_cfg_lang_hint = ctk.CTkLabel(
            top_card,
            text=t("cfg_lang_hint", self.current_lang),
            font=ctk.CTkFont(size=11),
            text_color="#71717A"
        )
        self.lbl_cfg_lang_hint.pack(padx=12, pady=(0, 8), anchor="w")

        # Action Buttons Row (Save + Advanced toggle)
        btn_row = ctk.CTkFrame(top_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 8))

        self.btn_save_config = ctk.CTkButton(
            btn_row,
            text=t("cfg_btn_save", self.current_lang),
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            height=34,
            corner_radius=8,
            command=self._save_config
        )
        self.btn_save_config.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.btn_adv_toggle = ctk.CTkButton(
            btn_row,
            text=t("cfg_btn_adv_show", self.current_lang),
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#27272A",
            hover_color="#3F3F46",
            border_width=1,
            border_color="#3F3F46",
            height=34,
            corner_radius=8,
            command=self._toggle_advanced
        )
        self.btn_adv_toggle.pack(side="right", expand=True, fill="x", padx=(4, 0))

        # Status feedback label below buttons
        self.lbl_save_status = ctk.CTkLabel(top_card, text="", font=ctk.CTkFont(size=12, weight="bold"), text_color="#22C55E")
        self.lbl_save_status.pack(pady=(0, 4))

        # 2. Scrollable Frame for Grouped Settings
        self.config_scroll = ctk.CTkScrollableFrame(self.tab_config, fg_color="transparent")
        self.config_scroll.pack(fill="both", expand=True, padx=2, pady=(0, 4))

        # Render sections
        for sec in CONFIG_SECTIONS:
            sec_id = sec["id"]
            sec_card = ctk.CTkFrame(self.config_scroll, fg_color="#202023", corner_radius=10)
            sec_card.pack(fill="x", padx=4, pady=6)

            # Section Title
            title_lbl = ctk.CTkLabel(
                sec_card,
                text=get_section_title(sec_id, self.current_lang),
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#60A5FA"
            )
            title_lbl.pack(anchor="w", padx=12, pady=(10, 6))
            self.section_title_labels[sec_id] = title_lbl

            # Section Items (Basic first, Advanced marked)
            sec_items = [it for it in CONFIG_ITEMS if it["section"] == sec_id]
            for item in sec_items:
                self._render_setting_item(sec_card, item)

    def _render_setting_item(self, parent, item: dict):
        key = item["key"]
        vtype = item["type"]
        is_adv = item["is_advanced"]
        raw_val = self.config.get(key)

        # Main item container
        row_container = ctk.CTkFrame(parent, fg_color="transparent")
        if is_adv:
            self.advanced_row_containers.append((row_container, parent))
            if not self.show_advanced:
                # Initially hidden if advanced
                pass
            else:
                row_container.pack(fill="x", padx=10, pady=3)
        else:
            row_container.pack(fill="x", padx=10, pady=3)

        # Control Row
        control_row = ctk.CTkFrame(row_container, fg_color="transparent")
        control_row.pack(fill="x", pady=2)

        # Left: Setting Label & INFO button
        left_box = ctk.CTkFrame(control_row, fg_color="transparent")
        left_box.pack(side="left", fill="x", expand=True)

        lbl = ctk.CTkLabel(
            left_box,
            text=get_item_label(item, self.current_lang),
            font=ctk.CTkFont(size=12),
            text_color="#E4E4E7",
            anchor="w"
        )
        lbl.pack(side="left", padx=(0, 6))
        self.item_label_widgets[key] = lbl

        # Info toggle button
        if item.get("info_uk"):
            btn_info = ctk.CTkButton(
                left_box,
                text="ℹ",
                width=22,
                height=22,
                corner_radius=11,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#27272A",
                hover_color="#3B82F6",
                text_color="#93C5FD",
                command=lambda k=key: self._toggle_info_card(k)
            )
            btn_info.pack(side="left")

        # Right: Value Widget (Switch or Entry)
        right_box = ctk.CTkFrame(control_row, fg_color="transparent")
        right_box.pack(side="right")

        if vtype == 'bool':
            bool_val = bool(raw_val) if raw_val is not None else False
            var = ctk.BooleanVar(value=bool_val)
            widget = ctk.CTkSwitch(
                right_box,
                text="",
                variable=var,
                width=38,
                switch_width=38,
                switch_height=20
            )
            widget.pack(side="right")
            self.config_vars[key] = ('bool', var)
        elif vtype in ('int', 'float'):
            str_val = str(raw_val) if raw_val is not None else "0"
            var = ctk.StringVar(value=str_val)
            widget = ctk.CTkEntry(
                right_box,
                textvariable=var,
                width=74,
                height=26,
                font=ctk.CTkFont(size=12),
                corner_radius=6,
                justify="center"
            )
            widget.pack(side="right")
            self.config_vars[key] = (vtype, var)
        else:
            str_val = str(raw_val) if raw_val is not None else ""
            var = ctk.StringVar(value=str_val)
            widget = ctk.CTkEntry(
                right_box,
                textvariable=var,
                width=90,
                height=26,
                font=ctk.CTkFont(size=12),
                corner_radius=6
            )
            widget.pack(side="right")
            self.config_vars[key] = ('str', var)

        # Expandable Info Box (initially hidden)
        if item.get("info_uk"):
            info_box = ctk.CTkFrame(row_container, fg_color="#18181B", border_width=1, border_color="#3B82F6", corner_radius=8)
            info_text = ctk.CTkLabel(
                info_box,
                text=get_item_info(item, self.current_lang),
                font=ctk.CTkFont(size=11),
                text_color="#CBD5E1",
                justify="left",
                wraplength=340
            )
            info_text.pack(fill="x", padx=10, pady=8)
            self.item_info_labels[key] = info_text
            self.info_boxes[key] = (info_box, False)  # (widget, is_visible)

    def _toggle_info_card(self, key: str):
        """Expands or collapses the explanation card for a specific setting."""
        if key not in self.info_boxes:
            return
        box, is_visible = self.info_boxes[key]
        if is_visible:
            box.pack_forget()
            self.info_boxes[key] = (box, False)
        else:
            box.pack(fill="x", padx=2, pady=(2, 6))
            self.info_boxes[key] = (box, True)

    def _toggle_advanced(self):
        """Toggles visibility of advanced settings across all sections."""
        self.show_advanced = not self.show_advanced
        if self.show_advanced:
            self.btn_adv_toggle.configure(text=t("cfg_btn_adv_hide", self.current_lang))
            for container, parent in self.advanced_row_containers:
                container.pack(fill="x", padx=10, pady=3)
        else:
            self.btn_adv_toggle.configure(text=t("cfg_btn_adv_show", self.current_lang))
            for container, parent in self.advanced_row_containers:
                container.pack_forget()

    def _save_config(self):
        """Saves current input values to config.json and immediately updates live hardware/services."""
        for key, (vtype, var) in self.config_vars.items():
            try:
                if vtype == 'bool':
                    self.config.data[key] = var.get()
                elif vtype == 'float':
                    self.config.data[key] = float(var.get())
                elif vtype == 'int':
                    self.config.data[key] = int(var.get())
                else:
                    self.config.data[key] = var.get().strip()
            except ValueError:
                pass  # Skip corrupted/incomplete numeric input

        # Save to disk
        self.config.save()

        # Apply settings to active runtime components immediately
        try:
            self.receiver.enable_triggers = self.config.get("enable_triggers", True)
            self.receiver.enable_audio_haptics = self.config.get("enable_audio_haptics", True)
            self.receiver.enable_rgb = self.config.get("enable_rgb", True)
            self.controller.enable_rgb = self.receiver.enable_rgb
            self.controller.enable_player_leds = self.config.get("enable_player_leds", True)

            # Gyroscope runtime updates
            self.controller.gyro.enabled = self.config.get("enable_gyro", True)
            self.controller.gyro.max_steer_angle = float(self.config.get("gyro_max_angle", 65.0))
            self.controller.gyro.deadzone = float(self.config.get("gyro_deadzone", 0.002))
            self.controller.gyro.ema_alpha = float(self.config.get("gyro_ema_alpha", 0.0))
            self.controller.gyro.gamma = float(self.config.get("gyro_gamma", 1.0))
            self.controller.gyro.invert_steer = bool(self.config.get("gyro_invert", False))
            self.controller.gyro.stick_override = bool(self.config.get("gyro_stick_override", True))
            self.controller.gyro.stick_override_threshold = float(self.config.get("gyro_stick_override_threshold", 0.20))
            self.controller.gyro.zero_offset = float(self.config.get("gyro_zero_offset", 0.0))
            self.controller.gyro.noise_threshold = float(self.config.get("gyro_noise_threshold", 0.0))
            self.controller.gyro.speed_sensitivity = float(self.config.get("gyro_speed_sensitivity", 0.15))
            self.controller.gyro.enable_speed_sensitivity = bool(self.config.get("gyro_enable_speed_sensitivity", True))
            self.controller.dpad_right_f10 = bool(self.config.get("dpad_right_f10", True))
            self.controller.dpad_right_gamepad = bool(self.config.get("dpad_right_gamepad", False))

            # Triggers & Haptics runtime updates
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

        # Feedback toast
        self.lbl_save_status.configure(text=t("cfg_saved", self.current_lang))
        self.after(2500, lambda: self.lbl_save_status.configure(text=""))

    # =========================================================================
    # Status Polling
    # =========================================================================
    def update_status(self):
        """Periodically updates status badges without UI freezes."""
        if self._closing:
            return

        try:
            # Controller status
            if self.controller.conn_type == CONN_USB:
                self.lbl_ctrl.configure(text=t("ctrl_usb", self.current_lang), text_color="#22C55E")
            elif self.controller.conn_type == CONN_BT:
                self.lbl_ctrl.configure(text=t("ctrl_bt", self.current_lang), text_color="#38BDF8")
            else:
                self.lbl_ctrl.configure(text=t("ctrl_disconnected", self.current_lang), text_color="#A1A1AA")

            # Game telemetry status
            now = time.time()
            udp_active = (now - self.receiver.last_udp_packet_time < 1.0) and (self.receiver.packet_count > 0)
            sm_active = self.receiver.sm.is_game_running()

            if udp_active:
                msg = t("game_active_udp", self.current_lang, rate=self.receiver.packets_per_second)
                self.lbl_game.configure(text=msg, text_color="#22C55E")
            elif sm_active:
                self.lbl_game.configure(text=t("game_active_sm", self.current_lang), text_color="#22C55E")
            else:
                self.lbl_game.configure(text=t("game_waiting", self.current_lang), text_color="#EAB308")

        except Exception as e:
            logger.debug(f"Status update error: {e}")

        # Refresh every 250ms
        self.after(250, self.update_status)

    # =========================================================================
    # System Tray Integration
    # =========================================================================
    def _setup_tray(self):
        """Creates the system tray icon."""
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
        """Builds localized tray menu."""
        return pystray.Menu(
            item(t("tray_show", self.current_lang), self._tray_show_window, default=True),
            item(t("tray_toggle", self.current_lang), self._tray_toggle),
            pystray.Menu.SEPARATOR,
            item(t("tray_quit", self.current_lang), self._tray_quit)
        )

    def _rebuild_tray_menu(self):
        """Updates tray menu items when language changes."""
        if self.tray_icon:
            try:
                self.tray_icon.menu = self._create_tray_menu()
            except Exception as e:
                logger.debug(f"Could not update tray menu: {e}")

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
