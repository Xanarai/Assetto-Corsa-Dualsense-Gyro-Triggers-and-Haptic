"""
Internationalization (i18n) and Configuration Metadata for DualSense AC Bridge.
Provides Ukrainian (uk) and English (en) translations for all GUI elements,
setting names, and interactive info tooltips.
"""

LANG_UK = "uk"
LANG_EN = "en"

# General UI text translations
TEXTS = {
    LANG_UK: {
        "app_title": "DualSense AC Bridge",
        "app_subtitle": "Assetto Corsa • Адаптивні тригери та вібрація",
        "tab_main": "Головна",
        "tab_config": "Налаштування",
        
        # Status Card
        "card_controller": "Геймпад:",
        "card_game": "Assetto Corsa:",
        "card_service": "Стан сервісу:",
        "ctrl_searching": "Пошук...",
        "ctrl_usb": "DualSense (USB)",
        "ctrl_bt": "DualSense (Bluetooth)",
        "ctrl_disconnected": "Не підключено",
        "game_waiting": "Очікування гри...",
        "game_active_udp": "Активна ({rate:.0f} Гц)",
        "game_active_sm": "Активна (Shared Memory)",
        "service_running": "Працює",
        "service_stopped": "Зупинено",
        
        # Action Buttons
        "btn_stop": "ЗУПИНИТИ",
        "btn_start": "ЗАПУСТИТИ",
        "tray_hint": "При закритті вікна програма згортається в системний трей",
        
        # Tray Menu
        "tray_show": "Розгорнути вікно",
        "tray_toggle": "Старт / Стоп",
        "tray_quit": "Вихід",
        
        # Config Tab Header & Controls
        "cfg_lang_title": "Мова інтерфейсу / Language",
        "cfg_lang_active": "Українська",
        "cfg_lang_hint": "Змінити мову можна прапорцями у верхньому кутку вікна",
        "cfg_btn_save": "Зберегти налаштування",
        "cfg_saved": "Збережено та застосовано!",
        "cfg_btn_adv_show": "Показати додаткові налаштування ▼",
        "cfg_btn_adv_hide": "Сховати додаткові налаштування ▲",
        "cfg_filter_hint": "Розширені параметри для точного тюнінгу",
        
        # Tooltip / Info popup
        "info_title": "Пояснення параметра",
        "close": "Зрозуміло",
    },
    LANG_EN: {
        "app_title": "DualSense AC Bridge",
        "app_subtitle": "Assetto Corsa • Adaptive Triggers & Haptics",
        "tab_main": "Dashboard",
        "tab_config": "Settings",
        
        # Status Card
        "card_controller": "Controller:",
        "card_game": "Assetto Corsa:",
        "card_service": "Service State:",
        "ctrl_searching": "Searching...",
        "ctrl_usb": "DualSense (USB)",
        "ctrl_bt": "DualSense (Bluetooth)",
        "ctrl_disconnected": "Disconnected",
        "game_waiting": "Waiting for game...",
        "game_active_udp": "Active ({rate:.0f} Hz)",
        "game_active_sm": "Active (Shared Memory)",
        "service_running": "Running",
        "service_stopped": "Stopped",
        
        # Action Buttons
        "btn_stop": "STOP",
        "btn_start": "START",
        "tray_hint": "Closing the window minimizes the app to system tray",
        
        # Tray Menu
        "tray_show": "Show Window",
        "tray_toggle": "Start / Stop",
        "tray_quit": "Exit",
        
        # Config Tab Header & Controls
        "cfg_lang_title": "Interface Language / Мова",
        "cfg_lang_active": "English",
        "cfg_lang_hint": "Switch language anytime via the flag icons in the top-right header",
        "cfg_btn_save": "Save Settings",
        "cfg_saved": "Saved & Applied!",
        "cfg_btn_adv_show": "Show Advanced Settings ▼",
        "cfg_btn_adv_hide": "Hide Advanced Settings ▲",
        "cfg_filter_hint": "Advanced parameters for fine-tuning physics & sensors",
        
        # Tooltip / Info popup
        "info_title": "Parameter Info",
        "close": "Got it",
    }
}


def t(key: str, lang: str = LANG_UK, **kwargs) -> str:
    """Retrieves localized string by key."""
    lang_dict = TEXTS.get(lang, TEXTS[LANG_UK])
    text = lang_dict.get(key, TEXTS[LANG_UK].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


CONFIG_SECTIONS = [
    {
        "id": "general",
        "title_uk": "Основні налаштування",
        "title_en": "General Settings",
    },
    {
        "id": "triggers",
        "title_uk": "Адаптивні тригери (L2 / R2)",
        "title_en": "Adaptive Triggers (L2 / R2)",
    },
    {
        "id": "haptics",
        "title_uk": "Тактильний відгук (Haptics)",
        "title_en": "Haptic Feedback",
    },
    {
        "id": "gyro",
        "title_uk": "Кермування гіроскопом",
        "title_en": "Gyroscope Steering",
    },
]

# Comprehensive metadata, grouping and clear explanations for all configuration keys
CONFIG_ITEMS = [
    # ==================== GENERAL (Основні налаштування) ====================
    {
        "key": "auto_connect",
        "section": "general",
        "type": "bool",
        "is_advanced": False,
        "name_uk": "Автоматичне підключення",
        "name_en": "Auto-Connect on Launch",
        "info_uk": "Автоматично підключатися до геймпада DualSense та гри Assetto Corsa при запуску програми.",
        "info_en": "Automatically connect to the DualSense controller and Assetto Corsa when the application starts.",
    },
    {
        "key": "minimize_to_tray",
        "section": "general",
        "type": "bool",
        "is_advanced": False,
        "name_uk": "Згортати в трей при закритті",
        "name_en": "Minimize to Tray on Close",
        "info_uk": "При натисканні на хрестик ховати вікно програми в системний трей біля годинника замість повного виходу.",
        "info_en": "Minimizes the bridge window to system tray instead of exiting when clicking the close button.",
    },
    {
        "key": "auto_exit_on_game_close",
        "section": "general",
        "type": "bool",
        "is_advanced": False,
        "name_uk": "Закривати при виході з гри",
        "name_en": "Exit When Game Closes",
        "info_uk": "Автоматично завершувати роботу мосту, коли гру Assetto Corsa закрито.",
        "info_en": "Automatically shut down the bridge application when Assetto Corsa stops running.",
    },
    {
        "key": "enable_rgb",
        "section": "general",
        "type": "bool",
        "is_advanced": False,
        "name_uk": "RGB підсвічування (Lightbar)",
        "name_en": "Enable RGB Lightbar",
        "info_uk": "Динамічна зміна кольору світлодіодної смуги DualSense (індикація обертів двигуна RPM, блокування коліс, тощо).",
        "info_en": "Dynamic RGB lightbar coloring based on engine RPM, wheel lockup alerts, and telemetry.",
    },
    {
        "key": "rgb_brightness_scale",
        "section": "general",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Яскравість RGB підсвічування",
        "name_en": "RGB Brightness Scale",
        "info_uk": "Загальна яскравість світлодіодної панелі геймпада (від 0.0 до 1.0).",
        "info_en": "Global brightness multiplier for the DualSense lightbar LEDs (0.0 to 1.0).",
    },
    {
        "key": "enable_player_leds",
        "section": "general",
        "type": "bool",
        "is_advanced": True,
        "name_uk": "Світлодіоди передач (Player LEDs)",
        "name_en": "Player LEDs (Gear Indicator)",
        "info_uk": "Відображення номера поточної передачі на 5 білих світлодіодних індикаторах під тачпадом.",
        "info_en": "Show current gear or connection status on the 5 white LED dots below the touchpad.",
    },
    {
        "key": "udp_port",
        "section": "general",
        "type": "int",
        "is_advanced": True,
        "name_uk": "UDP порт телеметрії",
        "name_en": "UDP Telemetry Port",
        "info_uk": "Мережевий UDP порт, на який Assetto Corsa передає пакети телеметрії (за замовчуванням 6969).",
        "info_en": "Network UDP port where Assetto Corsa sends telemetry data (default: 6969).",
    },
    {
        "key": "udp_host",
        "section": "general",
        "type": "str",
        "is_advanced": True,
        "name_uk": "UDP адреса прослуховування",
        "name_en": "UDP Host Address",
        "info_uk": "IP-адреса для прослуховування вхідних UDP пакетів (0.0.0.0 слухає всі мережеві інтерфейси).",
        "info_en": "IP address to listen on for UDP packets (0.0.0.0 listens across all interfaces).",
    },

    # ==================== ADAPTIVE TRIGGERS (Адаптивні тригери) ====================
    {
        "key": "enable_triggers",
        "section": "triggers",
        "type": "bool",
        "is_advanced": False,
        "name_uk": "Увімкнути адаптивні тригери",
        "name_en": "Enable Adaptive Triggers",
        "info_uk": "Увімкнути фізичний опір та вібраційні ефекти на курках L2 (гальмо/ABS) та R2 (газ).",
        "info_en": "Enable dynamic resistance and vibration feedback on L2 (brake/ABS) and R2 (throttle).",
    },
    {
        "key": "brake_wall_force",
        "section": "triggers",
        "type": "int",
        "is_advanced": False,
        "name_uk": "Сила опору гальма (ABS)",
        "name_en": "Brake Wall Resistance Force",
        "info_uk": "Жорсткість фізичного упору курка L2 під час гальмування та спрацювання ABS (від 1 до 8).",
        "info_en": "Resistance firmness felt on trigger L2 when braking or triggering ABS (range: 1 to 8).",
    },
    {
        "key": "brake_wall_pos",
        "section": "triggers",
        "type": "int",
        "is_advanced": False,
        "name_uk": "Позиція спрацювання ABS",
        "name_en": "ABS Activation Travel Position",
        "info_uk": "Глибина натискання курка L2, де з'являється упор та вібрація ABS (0 = на самому початку, 9 = наприкінці ходу).",
        "info_en": "Trigger depression depth on L2 where the ABS barrier kicks in (0 = immediate start, 9 = bottom).",
    },
    {
        "key": "throttle_spring_force",
        "section": "triggers",
        "type": "int",
        "is_advanced": False,
        "name_uk": "Пружність педалі газу (R2)",
        "name_en": "Throttle Spring Tension",
        "info_uk": "Сила пружинного повернення курка газу R2, що імітує пружність реальної педалі акселератора (від 0 до 8).",
        "info_en": "Spring return force applied to trigger R2 to simulate accelerator pedal resistance (0 to 8).",
    },
    {
        "key": "left_trigger_scale",
        "section": "triggers",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Масштаб чутливості L2",
        "name_en": "Left Trigger Force Multiplier",
        "info_uk": "Загальний коефіцієнт масштабування сили ефектів для курка гальма L2.",
        "info_en": "Global scaling factor for adaptive trigger feedback on the left brake trigger.",
    },
    {
        "key": "right_trigger_scale",
        "section": "triggers",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Масштаб чутливості R2",
        "name_en": "Right Trigger Force Multiplier",
        "info_uk": "Загальний коефіцієнт масштабування сили ефектів для курка газу R2.",
        "info_en": "Global scaling factor for adaptive trigger feedback on the right throttle trigger.",
    },
    {
        "key": "brake_gamma",
        "section": "triggers",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Гамма крива гальма",
        "name_en": "Brake Gamma Curve",
        "info_uk": "Нелінійна крива опору гальма (>1.0 забезпечує плавний легкий хід спочатку і жорсткий опір в кінці).",
        "info_en": "Non-linear trigger resistance calculation curve (>1.0 gives a softer start and firm lockup).",
    },
    {
        "key": "throttle_gamma",
        "section": "triggers",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Гамма крива газу",
        "name_en": "Throttle Gamma Curve",
        "info_uk": "Нелінійна крива опору педалі газу для точного дозування прискорення.",
        "info_en": "Non-linear response curve for throttle pedal resistance.",
    },

    # ==================== HAPTICS (Тактильний відгук) ====================
    {
        "key": "enable_audio_haptics",
        "section": "haptics",
        "type": "bool",
        "is_advanced": False,
        "name_uk": "Увімкнути тактильний відгук",
        "name_en": "Enable Haptic Feedback",
        "info_uk": "Увімкнути високоточну вібрацію через звукові котушки DualSense (поребрики, фактура асфальту, FFB).",
        "info_en": "Enable HD haptic feedback through DualSense voice-coil actuators (kerbs, road surface, FFB).",
    },
    {
        "key": "haptic_master_gain",
        "section": "haptics",
        "type": "float",
        "is_advanced": False,
        "name_uk": "Загальна потужність вібрації",
        "name_en": "Master Haptic Gain",
        "info_uk": "Головна гучність та інтенсивність усіх тактильних ефектів геймпада разом (за замовчуванням 1.0 - 1.8).",
        "info_en": "Master volume and intensity multiplier for all tactile feedback effects combined.",
    },
    {
        "key": "haptic_kerb_gain",
        "section": "haptics",
        "type": "float",
        "is_advanced": False,
        "name_uk": "Вібрація поребриків (Kerbs)",
        "name_en": "Kerb Vibration Gain",
        "info_uk": "Інтенсивність удару та вібрації в руках під час наїзду колесами на бордюри та нерівності траси.",
        "info_en": "Vibration intensity when driving over kerbs, rumble strips, and road undulations.",
    },
    {
        "key": "haptic_ffb_gain",
        "section": "haptics",
        "type": "float",
        "is_advanced": False,
        "name_uk": "Текстура дороги та FFB",
        "name_en": "Road Texture & FFB Gain",
        "info_uk": "Передача мікровібрацій зчеплення шин з асфальтом та зусилля на кермі від фізичного рушія гри.",
        "info_en": "Transfers asphalt roughness, tire friction micro-vibrations, and steering rack forces.",
    },
    {
        "key": "haptic_lockup_gain",
        "section": "haptics",
        "type": "float",
        "is_advanced": False,
        "name_uk": "Блокування коліс (Lockup)",
        "name_en": "Wheel Lockup Haptics",
        "info_uk": "Характерне тремтіння та вібрація в геймпаді при блокуванні шин під час занадто різкого гальмування.",
        "info_en": "Distinct judder and shudder felt when tires lock up under heavy braking.",
    },
    {
        "key": "haptic_drift_gain",
        "section": "haptics",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Ковзання та занос (Drift)",
        "name_en": "Drift & Tire Slip Gain",
        "info_uk": "Відчуття бічного ковзання шин під час зносу або зриву задньої осі в занос.",
        "info_en": "Tactile feeling of lateral tire slip and slide during drift and oversteer.",
    },
    {
        "key": "haptic_gearshift_gain",
        "section": "haptics",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Удар перемикання передач",
        "name_en": "Gear Shift Kick Gain",
        "info_uk": "Чіткий механічний поштовх у руки в момент перемикання передачі.",
        "info_en": "Crisp tactile thump impulse transmitted through the controller body when shifting gears.",
    },

    # ==================== GYROSCOPE (Кермування гіроскопом) ====================
    {
        "key": "enable_gyro",
        "section": "gyro",
        "type": "bool",
        "is_advanced": False,
        "name_uk": "Кермування гіроскопом",
        "name_en": "Gyroscope Steering",
        "info_uk": "Керування автомобілем нахилом самого геймпада як віртуальним кермом замість лівого стіка.",
        "info_en": "Steer the vehicle by physically tilting the controller like a steering wheel.",
    },
    {
        "key": "gyro_max_angle",
        "section": "gyro",
        "type": "float",
        "is_advanced": False,
        "name_uk": "Максимальний кут нахилу (°)",
        "name_en": "Max Steering Angle (°)",
        "info_uk": "Кут нахилу геймпада в градусах, який відповідає 100% вивороту віртуального керма (наприклад, 65° або 90°).",
        "info_en": "Physical tilt angle in degrees required for 100% full lock steering (e.g. 65° or 90°).",
    },
    {
        "key": "gyro_invert",
        "section": "gyro",
        "type": "bool",
        "is_advanced": False,
        "name_uk": "Інвертувати напрямок повороту",
        "name_en": "Invert Steering Axis",
        "info_uk": "Змінює напрямок повороту на протилежний (якщо при нахилі вправо машина повертає вліво).",
        "info_en": "Invert steering direction if tilting right steers left.",
    },
    {
        "key": "gyro_enable_speed_sensitivity",
        "section": "gyro",
        "type": "bool",
        "is_advanced": False,
        "name_uk": "Зниження чутливості на швидкості",
        "name_en": "Speed Sensitivity Scaling",
        "info_uk": "Автоматично зменшує різкість кермування на високій швидкості для стабільного контролю машини.",
        "info_en": "Dynamically reduces steering sensitivity at high speeds for smooth, stable car control.",
    },
    {
        "key": "gyro_speed_sensitivity",
        "section": "gyro",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Коефіцієнт чутливості швидкості",
        "name_en": "Speed Sensitivity Factor",
        "info_uk": "Ступінь зменшення кута на швидкості (більше значення = спокійніше та стабільніше кермо на прямих).",
        "info_en": "Rate of steering reduction at speed (higher = calmer, less twitchy car on straights).",
    },
    {
        "key": "gyro_stick_override",
        "section": "gyro",
        "type": "bool",
        "is_advanced": False,
        "name_uk": "Перехоплення лівим стіком",
        "name_en": "Stick Override",
        "info_uk": "Якщо ви відхиляєте лівий стік, він миттєво замінює гіроскоп (дуже зручно для швидкого вирівнювання з заносу).",
        "info_en": "Moving the left thumbstick temporarily overrides gyro input for quick countersteering.",
    },
    {
        "key": "gyro_deadzone",
        "section": "gyro",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Мертва зона центру",
        "name_en": "Center Deadzone",
        "info_uk": "Зона навколо нульового положення, в якій дрібне природне тремтіння рук повністю ігнорується.",
        "info_en": "Deadband around zero tilt where minor natural hand jitter is ignored.",
    },
    {
        "key": "gyro_gamma",
        "section": "gyro",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Гамма чутливості (Нелінійність)",
        "name_en": "Steering Response Gamma",
        "info_uk": "Крива реакції керма: 1.0 = лінійно, >1.0 = висока точність у центрі та швидкий поворот на краях.",
        "info_en": "Steering response curve: 1.0 is linear, >1.0 provides fine control around center.",
    },
    {
        "key": "gyro_filter_beta",
        "section": "gyro",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Коефіцієнт фільтра (Beta)",
        "name_en": "Filter Smoothing Beta",
        "info_uk": "Параметр фільтра злиття даних акселерометра та гіроскопа (баланс між швидкістю та стабільністю горизонту).",
        "info_en": "Sensor fusion filter parameter balancing gyroscope rate and accelerometer gravity.",
    },
    {
        "key": "gyro_ema_alpha",
        "section": "gyro",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Згладжування шуму (EMA Alpha)",
        "name_en": "EMA Noise Smoothing Alpha",
        "info_uk": "Експоненційне згладжування (0 = без затримки / чистий сигнал, 0.1-0.2 = плавніший рух).",
        "info_en": "Exponential smoothing factor (0 = zero latency raw, 0.1-0.2 = extra smooth).",
    },
    {
        "key": "gyro_axis",
        "section": "gyro",
        "type": "str",
        "is_advanced": True,
        "name_uk": "Робоча вісь нахилу",
        "name_en": "Gyroscope Sensor Axis",
        "info_uk": "Вісь сенсора DualSense, що визначає поворот: 'y' (обертання у площині керма) або 'z'.",
        "info_en": "Internal sensor axis used for steering: 'y' (steering wheel rotation) or 'z'.",
    },
    {
        "key": "gyro_zero_offset",
        "section": "gyro",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Калібрувальний зсув нуля",
        "name_en": "Zero Calibration Offset",
        "info_uk": "Постійне зміщення кута, якщо геймпад у нейтральному положенні має невелике відхилення.",
        "info_en": "Static angular calibration offset if controller rests slightly off-center.",
    },
    {
        "key": "gyro_noise_threshold",
        "section": "gyro",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Поріг відсікання шумів",
        "name_en": "Noise Cutoff Threshold",
        "info_uk": "Мінімальна кутова швидкість (рад/с), нижче якої сенсор вважається нерухомим.",
        "info_en": "Minimum angular rate threshold below which sensor jitter is filtered out.",
    },
    {
        "key": "gyro_stick_override_threshold",
        "section": "gyro",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Поріг спрацювання стіка",
        "name_en": "Stick Override Threshold",
        "info_uk": "Наскільки потрібно відхилити лівий стік (від 0.0 до 1.0), щоб перехопити керування у гіроскопа.",
        "info_en": "Thumbstick deflection threshold (0.0 to 1.0) needed to trigger gyro override.",
    },
    {
        "key": "gyro_scale",
        "section": "gyro",
        "type": "float",
        "is_advanced": True,
        "name_uk": "Внутрішній масштаб сенсора",
        "name_en": "Sensor Raw Scale",
        "info_uk": "Технічний масштаб конвертації сирих даних IMU DualSense у градуси/секунду.",
        "info_en": "Raw IMU scale conversion factor for DualSense gyroscope registers.",
    },
    {
        "key": "gyro_rate_invert",
        "section": "gyro",
        "type": "bool",
        "is_advanced": True,
        "name_uk": "Інверсія кутової швидкості",
        "name_en": "Invert Angular Rate",
        "info_uk": "Технічна інверсія знака кутової швидкості гіроскопа.",
        "info_en": "Technical inversion of the raw gyro angular velocity register.",
    },
    {
        "key": "dpad_right_f10",
        "section": "gyro",
        "type": "bool",
        "is_advanced": True,
        "name_uk": "D-Pad Вправо = F10 (Центрування)",
        "name_en": "D-Pad Right = F10 (Center)",
        "info_uk": "Натискання хрестовини вправо емулює клавішу F10 або калібрує центр керма прямо під час заїзду.",
        "info_en": "Pressing D-Pad Right emits F10 or re-calibrates steering center point on-the-fly.",
    },
    {
        "key": "dpad_right_gamepad",
        "section": "gyro",
        "type": "bool",
        "is_advanced": True,
        "name_uk": "Пропускати D-Pad Вправо у гру",
        "name_en": "Pass D-Pad Right to Game",
        "info_uk": "Чи передавати сигнал кнопки D-Pad Вправо у стандартний віртуальний геймпад гри.",
        "info_en": "Whether to pass the D-Pad Right button event to the virtual gamepad.",
    },
]


def get_item_label(item: dict, lang: str = LANG_UK) -> str:
    """Returns the localized display name for a setting item."""
    if lang == LANG_EN:
        return item.get("name_en", item.get("name_uk", item["key"]))
    return item.get("name_uk", item.get("name_en", item["key"]))


def get_item_info(item: dict, lang: str = LANG_UK) -> str:
    """Returns the localized explanation text for a setting item."""
    if lang == LANG_EN:
        return item.get("info_en", item.get("info_uk", ""))
    return item.get("info_uk", item.get("info_en", ""))


def get_section_title(section_id: str, lang: str = LANG_UK) -> str:
    """Returns localized section header title."""
    for sec in CONFIG_SECTIONS:
        if sec["id"] == section_id:
            return sec["title_en"] if lang == LANG_EN else sec["title_uk"]
    return section_id.capitalize()
