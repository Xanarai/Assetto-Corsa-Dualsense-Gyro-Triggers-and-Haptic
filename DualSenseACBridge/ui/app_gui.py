"""
Modern Minimalist GUI for DualSense AC Bridge.
Features:
- Streamlined single-action Start / Stop control.
- Bilingual localization (English / Ukrainian) with interactive flag buttons in the top-right header.
- Redesigned, categorized Config tab (General, Triggers, Haptics, Gyroscope).
- Interactive Sliders with live value readouts for all gain, force, angle, and sensitivity parameters.
- Prominently styled Master Enable/Disable switches that automatically disable dependent child settings.
- Hover-based adaptive INFO tooltips that never overflow the window.
- One-click Undo (Відкат) button and Ctrl+Z keyboard shortcut for settings changes.
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
    LANG_UK, LANG_EN, DEFAULT_LANG, t, CONFIG_SECTIONS, CONFIG_ITEMS,
    get_item_label, get_item_info, get_section_title
)

logger = logging.getLogger("DualSenseACBridge.AppGUI")

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def get_asset_path(filename: str) -> str:
    """Robustly resolves asset paths across all package structures and frozen exe modes."""
    candidates = []

    # 1. PyInstaller temp folder or exe folder
    if hasattr(sys, '_MEIPASS'):
        candidates.append(os.path.join(sys._MEIPASS, "assets", filename))
        candidates.append(os.path.join(sys._MEIPASS, filename))
    if hasattr(sys, 'executable'):
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "assets", filename))
        candidates.append(os.path.join(exe_dir, filename))

    # 2. Traverse up from this file's directory (ui -> DualSenseACBridge -> root)
    cur_path = os.path.abspath(__file__)
    for _ in range(5):
        cur_path = os.path.dirname(cur_path)
        candidates.append(os.path.join(cur_path, "assets", filename))
        candidates.append(os.path.join(cur_path, "DualSenseACBridge", "assets", filename))
        candidates.append(os.path.join(cur_path, filename))

    # 3. Current working directory
    cwd = os.getcwd()
    candidates.append(os.path.join(cwd, "assets", filename))
    candidates.append(os.path.join(cwd, "DualSenseACBridge", "assets", filename))

    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)

    return os.path.abspath(candidates[0])


class BridgeApp(ctk.CTk):
    def __init__(self, controller: DualSenseController, receiver: TelemetryReceiver, config: Config):
        super().__init__()

        self.controller = controller
        self.receiver = receiver
        self.config = config

        # Localization & default language (English by default)
        self.current_lang = self.config.get("language", DEFAULT_LANG)
        if self.current_lang not in (LANG_UK, LANG_EN):
            self.current_lang = DEFAULT_LANG

        self.is_active = True
        self.show_advanced = False
        self.tray_icon: pystray.Icon = None
        self._closing = False

        # Undo stack & state tracking
        self.undo_stack = []
        self._slider_start_val = {}

        # Widget tracking for dynamic language updates & dependency disabling
        self.config_vars = {}
        self.slider_widgets = {}
        self.slider_labels = {}
        self.master_switch_widgets = {}
        self.master_card_frames = {}
        self.child_widgets_by_master = {}
        self.child_labels_by_master = {}
        self.advanced_row_containers = []
        self.item_label_widgets = {}
        self.section_title_labels = {}

        # Window setup
        self.title("DualSense AC Bridge")
        self.geometry("450x660")
        self.minsize(430, 600)
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

        # Keyboard shortcut for Undo (Ctrl+Z)
        self.bind("<Control-z>", lambda e: self.undo_last_change())
        self.bind("<Control-Z>", lambda e: self.undo_last_change())

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
        # Top Header Bar (Always Visible: App Title + Country Flag Switcher)
        # =========================================================================
        self.top_bar = ctk.CTkFrame(self.main_frame, fg_color="#18181B", height=42)
        self.top_bar.pack(fill="x", padx=14, pady=(8, 2))

        # Brand / App title
        self.header_title = ctk.CTkLabel(
            self.top_bar,
            text="DualSense AC Bridge",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#F4F4F5"
        )
        self.header_title.pack(side="left")

        # Flags container in top right corner
        self.flags_container = ctk.CTkFrame(self.top_bar, fg_color="#27272A", corner_radius=8)
        self.flags_container.pack(side="right")

        # Load country flag images
        ua_flag_path = get_asset_path("flag_ua.png")
        en_flag_path = get_asset_path("flag_en.png")

        try:
            pil_ua = Image.open(ua_flag_path)
            self.img_flag_ua = ctk.CTkImage(light_image=pil_ua, dark_image=pil_ua, size=(28, 18))
        except Exception as e:
            logger.warning(f"Could not load Ukrainian flag from {ua_flag_path}: {e}")
            self.img_flag_ua = None

        try:
            pil_en = Image.open(en_flag_path)
            self.img_flag_en = ctk.CTkImage(light_image=pil_en, dark_image=pil_en, size=(28, 18))
        except Exception as e:
            logger.warning(f"Could not load English flag from {en_flag_path}: {e}")
            self.img_flag_en = None

        # Flag button: Ukrainian
        self.btn_flag_ua = ctk.CTkButton(
            self.flags_container,
            text="" if self.img_flag_ua else "UA",
            image=self.img_flag_ua,
            width=38,
            height=26,
            corner_radius=6,
            command=lambda: self.set_language(LANG_UK)
        )
        self.btn_flag_ua.pack(side="left", padx=2, pady=2)

        # Flag button: English
        self.btn_flag_en = ctk.CTkButton(
            self.flags_container,
            text="" if self.img_flag_en else "EN",
            image=self.img_flag_en,
            width=38,
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

        # Setup Floating Adaptive Tooltip
        self._setup_floating_tooltip()

    def _setup_floating_tooltip(self):
        """Creates an adaptive, non-clipped floating tooltip overlay."""
        self.tooltip_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color="#18181B",
            border_width=1,
            border_color="#3B82F6",
            corner_radius=8
        )
        self.tooltip_title = ctk.CTkLabel(
            self.tooltip_frame,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#60A5FA",
            anchor="w"
        )
        self.tooltip_title.pack(fill="x", padx=10, pady=(8, 2))

        self.tooltip_text = ctk.CTkLabel(
            self.tooltip_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#E2E8F0",
            justify="left",
            anchor="w"
        )
        self.tooltip_text.pack(fill="x", padx=10, pady=(0, 8))

    def _on_info_enter(self, event, item: dict):
        """Shows floating adaptive explanation when hovering over the info button."""
        name = get_item_label(item, self.current_lang)
        info = get_item_info(item, self.current_lang)
        if not info:
            return

        self.tooltip_title.configure(text=name)

        # Responsive wrap length based on window size
        win_w = self.main_frame.winfo_width()
        win_h = self.main_frame.winfo_height()
        max_wrap = max(220, min(360, win_w - 48))
        self.tooltip_text.configure(text=info, wraplength=max_wrap)
        self.tooltip_frame.update_idletasks()

        tw = self.tooltip_frame.winfo_reqwidth()
        th = self.tooltip_frame.winfo_reqheight()

        # Coordinates relative to main_frame
        px = event.x_root - self.main_frame.winfo_rootx()
        py = event.y_root - self.main_frame.winfo_rooty()

        # Horizontal clamping: stay strictly inside window margins
        pos_x = max(12, min(px - 20, win_w - tw - 12))

        # Vertical clamping: flip above cursor if near bottom of window
        if py + th + 28 > win_h:
            pos_y = max(10, py - th - 10)
        else:
            pos_y = py + 20

        self.tooltip_frame.place(x=pos_x, y=pos_y)
        self.tooltip_frame.lift()

    def _on_info_leave(self, event):
        """Hides floating tooltip when mouse leaves info button."""
        self.tooltip_frame.place_forget()

    def _update_flag_highlight(self):
        """Highlights the active country flag button."""
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
                btn_main.configure(text=t('tab_main', self.current_lang))
            if btn_config:
                btn_config.configure(text=t('tab_config', self.current_lang))
        except Exception as e:
            logger.debug(f"Could not update tab headers: {e}")

    def set_language(self, new_lang: str):
        """Switches active language, updates all UI text, and persists to config."""
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
        self.btn_undo.configure(text=t("cfg_btn_undo", self.current_lang))

        if self.show_advanced:
            self.btn_adv_toggle.configure(text=t("cfg_btn_adv_hide", self.current_lang))
        else:
            self.btn_adv_toggle.configure(text=t("cfg_btn_adv_show", self.current_lang))

        # Update Section titles
        for sec in CONFIG_SECTIONS:
            sec_id = sec["id"]
            if sec_id in self.section_title_labels:
                self.section_title_labels[sec_id].configure(text=get_section_title(sec_id, self.current_lang))

        # Update Config Item Labels
        for item in CONFIG_ITEMS:
            key = item["key"]
            if key in self.item_label_widgets:
                self.item_label_widgets[key].configure(text=get_item_label(item, self.current_lang))

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
        # 1. Top Action & Info Header Card
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

        # Action Buttons Row: Save, Undo, Advanced
        btn_row = ctk.CTkFrame(top_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 8))

        self.btn_save_config = ctk.CTkButton(
            btn_row,
            text=t("cfg_btn_save", self.current_lang),
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            height=32,
            corner_radius=8,
            command=self._save_config
        )
        self.btn_save_config.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.btn_undo = ctk.CTkButton(
            btn_row,
            text=t("cfg_btn_undo", self.current_lang),
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1F2937",
            hover_color="#374151",
            text_color="#6B7280",
            height=32,
            corner_radius=8,
            state="disabled",
            command=self.undo_last_change
        )
        self.btn_undo.pack(side="left", expand=True, fill="x", padx=4)

        self.btn_adv_toggle = ctk.CTkButton(
            btn_row,
            text=t("cfg_btn_adv_show", self.current_lang),
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#27272A",
            hover_color="#3F3F46",
            border_width=1,
            border_color="#3F3F46",
            height=32,
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

            # Section Items: render Master switch first, then remaining basic, then advanced
            sec_items = [it for it in CONFIG_ITEMS if it["section"] == sec_id]
            master_item = next((it for it in sec_items if it.get("is_master")), None)
            other_items = [it for it in sec_items if not it.get("is_master")]

            if master_item:
                self._render_master_switch(sec_card, master_item)

            for item in other_items:
                self._render_setting_item(sec_card, item)

        # Initialize all dependency states
        for item in CONFIG_ITEMS:
            if item.get("is_master"):
                k = item["key"]
                is_on = bool(self.config.get(k, True))
                self._update_master_dependency(k, is_on)

    def _render_master_switch(self, parent, item: dict):
        """Renders an accented Master Enable/Disable card with prominent status."""
        key = item["key"]
        raw_val = self.config.get(key, True)
        is_on = bool(raw_val)

        master_frame = ctk.CTkFrame(
            parent,
            fg_color="#27272A",
            border_width=1,
            border_color="#3B82F6" if is_on else "#3F3F46",
            corner_radius=8
        )
        master_frame.pack(fill="x", padx=8, pady=(2, 8))
        self.master_card_frames[key] = master_frame

        row = ctk.CTkFrame(master_frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=8)

        # Left: Title + Info button
        left_box = ctk.CTkFrame(row, fg_color="transparent")
        left_box.pack(side="left", fill="x", expand=True)

        lbl = ctk.CTkLabel(
            left_box,
            text=get_item_label(item, self.current_lang),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#F4F4F5",
            anchor="w"
        )
        lbl.pack(side="left", padx=(0, 6))
        self.item_label_widgets[key] = lbl

        if item.get("info_uk"):
            btn_info = ctk.CTkButton(
                left_box,
                text="i",
                width=22,
                height=22,
                corner_radius=11,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#334155",
                hover_color="#2563EB",
                text_color="#93C5FD"
            )
            btn_info.pack(side="left")
            btn_info.bind("<Enter>", lambda e, it=item: self._on_info_enter(e, it))
            btn_info.bind("<Leave>", self._on_info_leave)

        # Right: Master Switch
        var = ctk.BooleanVar(value=is_on)
        switch = ctk.CTkSwitch(
            row,
            text="",
            variable=var,
            width=44,
            switch_width=44,
            switch_height=22,
            progress_color="#2563EB",
            command=lambda k=key, v=var: self._on_master_toggle(k, v)
        )
        switch.pack(side="right")
        self.config_vars[key] = ('bool', var)
        self.master_switch_widgets[key] = switch

    def _on_master_toggle(self, key: str, var: ctk.BooleanVar):
        """Called when a Master switch is toggled."""
        new_val = var.get()
        old_val = not new_val
        self._record_undo(key, old_val, new_val)

        # Update border highlight
        if key in self.master_card_frames:
            self.master_card_frames[key].configure(
                border_color="#3B82F6" if new_val else "#3F3F46"
            )

        # Update dependent child controls
        self._update_master_dependency(key, new_val)

    def _update_master_dependency(self, master_key: str, is_enabled: bool):
        """Enables or disables child controls dependent on this master switch."""
        if master_key in self.child_widgets_by_master:
            for widget in self.child_widgets_by_master[master_key]:
                try:
                    widget.configure(state="normal" if is_enabled else "disabled")
                except Exception:
                    pass

        if master_key in self.child_labels_by_master:
            for lbl in self.child_labels_by_master[master_key]:
                try:
                    lbl.configure(text_color="#E4E4E7" if is_enabled else "#52525B")
                except Exception:
                    pass

    def _render_setting_item(self, parent, item: dict):
        key = item["key"]
        vtype = item["type"]
        widget_type = item.get("widget", "entry")
        is_adv = item["is_advanced"]
        raw_val = self.config.get(key)
        master_key = item.get("master_key")

        # Container
        row_container = ctk.CTkFrame(parent, fg_color="transparent")
        if is_adv:
            self.advanced_row_containers.append((row_container, parent))
            if self.show_advanced:
                row_container.pack(fill="x", padx=10, pady=3)
        else:
            row_container.pack(fill="x", padx=10, pady=3)

        # Control Row
        control_row = ctk.CTkFrame(row_container, fg_color="transparent")
        control_row.pack(fill="x", pady=2)

        # Left: Setting Label & INFO Hover Button
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

        if master_key:
            self.child_labels_by_master.setdefault(master_key, []).append(lbl)

        # Info Hover Button
        if item.get("info_uk"):
            btn_info = ctk.CTkButton(
                left_box,
                text="i",
                width=22,
                height=22,
                corner_radius=11,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#27272A",
                hover_color="#3B82F6",
                text_color="#93C5FD"
            )
            btn_info.pack(side="left")
            btn_info.bind("<Enter>", lambda e, it=item: self._on_info_enter(e, it))
            btn_info.bind("<Leave>", self._on_info_leave)

        # Right: Value Control (Slider, Switch, or Entry)
        right_box = ctk.CTkFrame(control_row, fg_color="transparent")
        right_box.pack(side="right")

        if widget_type == "slider":
            min_v = item.get("min_val", 0.0)
            max_v = item.get("max_val", 1.0)
            step_v = item.get("step", 0.05)
            fmt = item.get("format", "{:.2f}")

            try:
                curr_val = float(raw_val) if raw_val is not None else min_v
            except (ValueError, TypeError):
                curr_val = min_v

            # Range steps
            num_steps = max(1, int(round((max_v - min_v) / step_v)))

            # Live numerical value readout label
            val_lbl = ctk.CTkLabel(
                right_box,
                text=fmt.format(int(curr_val) if vtype == "int" else curr_val),
                width=46,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#38BDF8",
                anchor="e"
            )

            # Slider
            slider = ctk.CTkSlider(
                right_box,
                from_=min_v,
                to=max_v,
                number_of_steps=num_steps,
                width=115,
                height=16,
                progress_color="#2563EB",
                button_color="#38BDF8",
                button_hover_color="#60A5FA"
            )
            slider.set(curr_val)

            # Drag callback updates live readout
            def on_slide(val, k=key, f=fmt, vt=vtype, lbl=val_lbl):
                typed_val = int(round(val)) if vt == "int" else float(val)
                lbl.configure(text=f.format(typed_val))

            slider.configure(command=on_slide)

            # Undo tracking on mouse press and release
            slider.bind("<ButtonPress-1>", lambda e, k=key, s=slider: self._on_slider_press(k, s))
            slider.bind("<ButtonRelease-1>", lambda e, k=key, s=slider, vt=vtype: self._on_slider_release(k, s, vt))

            slider.pack(side="left", padx=(0, 6))
            val_lbl.pack(side="right")

            self.slider_widgets[key] = slider
            self.slider_labels[key] = (val_lbl, fmt, vtype)
            self.config_vars[key] = ('slider', (vtype, slider))

            if master_key:
                self.child_widgets_by_master.setdefault(master_key, []).append(slider)

        elif widget_type == "switch":
            bool_val = bool(raw_val) if raw_val is not None else False
            var = ctk.BooleanVar(value=bool_val)
            switch = ctk.CTkSwitch(
                right_box,
                text="",
                variable=var,
                width=38,
                switch_width=38,
                switch_height=20,
                command=lambda k=key, v=var: self._on_switch_toggle(k, v)
            )
            switch.pack(side="right")
            self.config_vars[key] = ('bool', var)

            if master_key:
                self.child_widgets_by_master.setdefault(master_key, []).append(switch)

        else:
            str_val = str(raw_val) if raw_val is not None else ""
            var = ctk.StringVar(value=str_val)
            entry = ctk.CTkEntry(
                right_box,
                textvariable=var,
                width=80 if vtype != "str" else 96,
                height=26,
                font=ctk.CTkFont(size=12),
                corner_radius=6,
                justify="center" if vtype != "str" else "left"
            )
            entry.bind("<FocusIn>", lambda e, k=key, v=var: self._on_entry_focus_in(k, v))
            entry.bind("<FocusOut>", lambda e, k=key, v=var: self._on_entry_focus_out(k, v))
            entry.pack(side="right")
            self.config_vars[key] = (vtype, var)

            if master_key:
                self.child_widgets_by_master.setdefault(master_key, []).append(entry)

    # =========================================================================
    # Undo / Redo Mechanism
    # =========================================================================
    def _on_slider_press(self, key: str, slider: ctk.CTkSlider):
        self._slider_start_val[key] = slider.get()

    def _on_slider_release(self, key: str, slider: ctk.CTkSlider, vtype: str):
        old_val = self._slider_start_val.get(key)
        new_val = int(round(slider.get())) if vtype == "int" else float(slider.get())
        if old_val is not None and abs(new_val - old_val) > 1e-4:
            old_typed = int(round(old_val)) if vtype == "int" else float(old_val)
            self._record_undo(key, old_typed, new_val)

    def _on_switch_toggle(self, key: str, var: ctk.BooleanVar):
        new_val = var.get()
        old_val = not new_val
        self._record_undo(key, old_val, new_val)

    def _on_entry_focus_in(self, key: str, var: ctk.StringVar):
        self._slider_start_val[key] = var.get()

    def _on_entry_focus_out(self, key: str, var: ctk.StringVar):
        old_val = self._slider_start_val.get(key)
        new_val = var.get()
        if old_val is not None and old_val != new_val:
            self._record_undo(key, old_val, new_val)

    def _record_undo(self, key: str, old_val, new_val):
        """Pushes previous value to undo stack and enables Undo button."""
        self.undo_stack.append((key, old_val))
        self.btn_undo.configure(
            state="normal",
            fg_color="#374151",
            text_color="#F3F4F6",
            hover_color="#4B5563"
        )

    def undo_last_change(self):
        """Reverts the last configuration edit (Ctrl+Z)."""
        if not self.undo_stack:
            self.lbl_save_status.configure(
                text=t("cfg_undo_empty", self.current_lang),
                text_color="#A1A1AA"
            )
            self.after(1500, lambda: self.lbl_save_status.configure(text=""))
            return

        key, prev_val = self.undo_stack.pop()

        # Restore widget state
        if key in self.config_vars:
            vtype, target = self.config_vars[key]
            if vtype == 'slider':
                val_type, slider = target
                slider.set(prev_val)
                if key in self.slider_labels:
                    val_lbl, fmt, vt = self.slider_labels[key]
                    val_lbl.configure(text=fmt.format(prev_val))
            elif vtype == 'bool':
                target.set(bool(prev_val))
                if key in self.master_card_frames:
                    self.master_card_frames[key].configure(
                        border_color="#3B82F6" if prev_val else "#3F3F46"
                    )
                    self._update_master_dependency(key, bool(prev_val))
            else:
                target.set(str(prev_val))

        # Save to active config
        self.config.data[key] = prev_val
        self.config.save()

        # Update button state
        if not self.undo_stack:
            self.btn_undo.configure(
                state="disabled",
                fg_color="#1F2937",
                text_color="#6B7280"
            )

        # Notify user
        item_obj = next((it for it in CONFIG_ITEMS if it["key"] == key), None)
        lbl_name = get_item_label(item_obj, self.current_lang) if item_obj else key
        self.lbl_save_status.configure(
            text=t("cfg_undo_done", self.current_lang, name=lbl_name),
            text_color="#38BDF8"
        )
        self.after(2000, lambda: self.lbl_save_status.configure(text=""))

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
        for key, (vtype, target) in self.config_vars.items():
            try:
                if vtype == 'slider':
                    val_type, slider = target
                    val = slider.get()
                    self.config.data[key] = int(round(val)) if val_type == 'int' else float(val)
                elif vtype == 'bool':
                    self.config.data[key] = target.get()
                elif vtype == 'float':
                    self.config.data[key] = float(target.get())
                elif vtype == 'int':
                    self.config.data[key] = int(target.get())
                else:
                    self.config.data[key] = target.get().strip()
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
        self.lbl_save_status.configure(
            text=t("cfg_saved", self.current_lang),
            text_color="#22C55E"
        )
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
