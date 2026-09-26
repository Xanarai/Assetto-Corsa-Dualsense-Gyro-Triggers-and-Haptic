# DualSense AC Bridge

[![GitHub Release](https://img.shields.io/badge/Assetto%20Corsa-DualSense%20Bridge-red?logo=playstation)](https://github.com/Xanarai/Assetto-Corsa-Dualsense-Gyro-Triggers-and-Haptic)
[![ViGEmBus](https://img.shields.io/badge/Driver-ViGEmBus-blue)](https://vigembusdriver.com/)
[![UI](https://img.shields.io/badge/Interface-PyWebView%20%7C%20Bilingual-success)](#)
[![Haptics](https://img.shields.io/badge/Haptics-Voice--Coil%20HD-purple)](#)

> [!NOTE]
> **Language / Мова:**  
> [English Version](#english-version) | [Українська версія](#українська-версія)

---

# English Version

## About the Project

**DualSense AC Bridge** is a Windows companion application designed to unlock the full hardware potential of the **Sony PlayStation 5 DualSense** controller in **Assetto Corsa**.

It bridges vehicle physics and telemetry directly into the gamepad, enabling steering wheel simulation via motion gyro, progressive adaptive resistance on triggers, and true high-definition voice-coil haptics.

---

## Features

* **Precision Gyroscope Steering**:
  * Steer your car smoothly by rotating the gamepad in your hands like a real racing wheel.
  * Jitter filtering with smooth deadzone transitions (no center snapping).
  * Speed sensitivity scaling to keep the vehicle calm and stable on high-speed straights.
  * **Stick Override**: instant counter-steering recovery using the physical left thumbstick whenever you need to catch a slide!
* **Adaptive Triggers (L2 / R2)**:
  * **Brake Resistance (L2)**: progressive hydraulic pedal firmness with a solid resistance wall.
  * **ABS Vibration**: distinct tactile kicking pulsations when anti-lock brakes engage.
  * **Throttle Spring (R2)**: realistic accelerator spring return force for optimal throttle modulation.
* **True Voice-Coil HD Haptics**:
  * DualSense audio actuators reproduce detailed road physics:
  * **Kerbs & bumps**: physical road texture and kerb impact sensations.
  * **Wheel lockup**: high-frequency tire judder under heavy braking.
  * **Drift & lateral slip**: real-time sensation of rear-end breakaway and tire scrub.
  * **Gear shift thump**: crisp mechanical impulse delivered through the controller body on gear changes.
* **Telemetry Lighting (RGB & LEDs)**:
  * Dynamic lightbar color transitions reflecting engine RPM and flashing on wheel lockup.
  * 5 white player LEDs beneath the touchpad indicate the current gear.
* **Modern Interface**:
  * Dark aesthetic UI with full English and Ukrainian localization.
  * 1-Click interactive Audio Setup Wizard.
  * Integrated Testing & Diagnostics panel for triggers and gyro calibration.
  * Seamlessly minimizes to the Windows system tray during races.

---

## Requirements & Setup Guide

### 1. Install ViGEmBus Driver (Mandatory)
The bridge creates a virtual Xbox 360 controller via the ViGEmBus system driver so Assetto Corsa can read smooth motion steering axes. Without this driver, the game will not detect input.
* **Download:** [ViGEmBus Driver Website](https://vigembusdriver.com/)
* Download and run `ViGEmBus_Setup_...exe` to complete the installation.

### 2. Connect via USB Cable ONLY
> [!IMPORTANT]
> **Why is a USB cable required?**  
> True HD voice-coil haptics require 4-channel audio output to the controller's internal actuators.  
> **Windows only exposes the 4-channel Quadraphonic audio interface over a wired USB connection.**  
> *(Bluetooth only supports trigger resistance and basic rumble, but not HD haptics).*

### 3. Disable Conflicting Software
* **DS4Windows**: If installed, **fully close DS4Windows** to avoid double-input conflicts and exclusive device locks.
* **Steam Input**:
  1. Open **Steam** -> Library.
  2. Right-click **Assetto Corsa** -> **Properties**.
  3. Select the **Controller** tab.
  4. Set the dropdown override to **«Disable Steam Input»**.

---

## Windows Audio Configuration for DualSense

DualSense haptics utilize the gamepad's secondary audio channels (voice-coil actuators).

### Option A: Built-in Setup Wizard (Recommended)
1. Plug your DualSense in via USB and launch **DualSense AC Bridge**.
2. Click **«Setup»** on the haptic status banner.
3. The wizard will automatically configure 4-channel quadraphonic audio and set device volume to 100%.
4. Accept the Windows UAC administrator prompt when requested.

---

### Option B: Manual Configuration
1. Press `Win + R`, type `mmsys.cpl` and press **Enter** (opens classic Sound Control Panel).
2. Find **«Wireless Controller»** (DualSense):
   * If disabled, right-click -> **Enable**.
3. **CRITICAL:** Do **NOT** set Wireless Controller as your *Default Playback Device*. Keep your normal speakers/headphones as Default so game audio or music doesn't blast into the haptic motors.
4. Right-click «Wireless Controller» -> **Properties** -> **Levels** -> set volume to **100%** (essential for maximum haptic power).
5. Select «Wireless Controller» and click **Configure** (bottom-left):
   * Select **Quadraphonic (4 channels)** and complete the wizard.

---

## Assetto Corsa / Content Manager Configuration

1. Launch **Content Manager** (or standard Assetto Corsa settings).
2. Navigate to: **Settings** -> **Assetto Corsa** -> **Controls**.
3. Select **Game Controller / Gamepad**.
4. Verify that buttons, triggers, and steering axes respond to your DualSense (gyro tilts the virtual left thumbstick).
5. Telemetry (kerbs, ABS, tire slip, gears) is gathered automatically via native Assetto Corsa Shared Memory — no extra plugins required!

---

## Quick Launch Steps

1. Plug in your DualSense controller via USB.
2. Launch **DualSense AC Bridge**.
3. Check Dashboard statuses:
   * **Controller:** `DualSense (USB)` [Connected]
   * **ViGEmBus Driver:** `Installed` [OK]
   * **Haptics:** `Active` [OK]
4. (Optional) Open **«Testing»** modal to verify trigger resistance and gyro steering angles.
5. Launch **Assetto Corsa** and hit the track!

---

## Settings & Tips

* **Max Steering Angle**: In the Settings tab, you can adjust the gyro steering lock angle (default 65°–90°). 65° is great for fast counter-steering in drift, while 80°–90° gives high precision in GT/formula racing.
* **Stick Override**: If you lose control or spin out, you don't need to contort your wrists — simply push the physical left thumbstick, and control immediately defaults to the stick.
* **System Tray**: Clicking the window close button minimizes the application to the Windows notification tray so it stays out of your way during gameplay. To exit completely, right-click the tray icon -> Exit.

---
---

# Українська версія

## Про проєкт

**DualSense AC Bridge** — це спеціальна програма для Windows, яка розкриває всі можливості геймпада **Sony PlayStation 5 DualSense** в автосимуляторі **Assetto Corsa**. 

Вона перетворює звичайний геймпад на точне віртуальне кермо завдяки гіроскопу, а також передає фізику автомобіля через фірмові адаптивні курки та справжню HD-вібрацію (Voice-Coil Haptics).

---

## Що дає програма

* **Кермування гіроскопом (Gyro Steering)**:
  * Повертайте геймпад у руках, як справжнє спортивне кермо.
  * Плавна фільтрація природного тремтіння рук (мертва зона без ривків).
  * Динамічне зниження чутливості на високій швидкості, щоб машина не втрачала стабільність на прямих.
  * **Stick Override**: якщо машину зірвало в занос, просто відхиліть лівий стік — керування миттєво перехоплюється стіком для швидкого вирівнювання!
* **Адаптивні тригери (L2 / R2)**:
  * **Курковий опір гальма (L2)**: імітація жорсткості педалі гальма зі справжнім упором.
  * **Пульсація ABS**: курок L2 відчутно б'є в палець у момент спрацювання антиблокувальної системи.
  * **Пружність педалі газу (R2)**: реалістичний опір акселератора для точного дозування газу на виході з поворотів.
* **Справжня HD-вібрація (Voice-Coil Haptics)**:
  * Вібромотори DualSense працюють як динаміки високої чіткості:
  * **Поребрики та нерівності**: відчуття кожного удару колеса об бордюр або тріщину асфальту.
  * **Блокування коліс**: характерне тертя та дрібне тремтіння при перегальмовуванні.
  * **Знос та занос (Drift)**: тактильне відчуття ковзання шин під час бокового зриву осі.
  * **Перемикання передач**: чіткий механічний поштовх у долоні в момент зміни ступеня КПП.
* **Телеметрія на діодах (RGB & LEDs)**:
  * Світлодіодна смуга динамічно змінює колір залежно від обертів двигуна (RPM) та блимає при блокуванні коліс.
  * 5 білих діодів під тачпадом показують номер поточної передачі.
* **Зручний інтерфейс**:
  * Стильний сучасний інтерфейс українською та англійською мовами.
  * Вбудований майстер налаштування звуку в 1 клік.
  * Розділ "Тестування" для швидкої перевірки роботи тригерів та кута нахилу гіроскопа.
  * Згортання в системний трей Windows під час гри.

---

## Важливі вимоги перед початком

### 1. Обов'язково встановіть системний драйвер ViGEmBus
Програма емулює віртуальний геймпад Xbox 360, щоб Assetto Corsa бачила плавні осі керма від гіроскопа. Без драйвера гра не розпізнає ввід.
* **Завантажити:** [Офіційний сайт драйвера ViGEmBus](https://vigembusdriver.com/)
* Завантажте файл `ViGEmBus_Setup_...exe`, запустіть його та завершіть встановлення.

### 2. Підключайте геймпад ТІЛЬКИ по USB-кабелю
> [!IMPORTANT]
> **Чому потрібен кабель?**  
> Повноцінна високоточна тактильна віддача (True HD Haptics) працює через внутрішні звукові котушки геймпада (4-канальний звук).  
> **Windows підтримує 4-канальний звук DualSense виключно при підключенні через USB-кабель.**  
> *(По Bluetooth підтримуються лише опір тригерів та базовий rumble, але не HD-гаптика).*

### 3. Вимкніть конфліктні програми
* **DS4Windows**: Якщо ви користуєтеся цією програмою — **повністю закрийте її**. Інакше виникне конфлікт подвійного вводу та блокування геймпада.
* **Steam Input**:
  1. Відкрийте **Steam** -> Бібліотека.
  2. Натисніть правою кнопкою миші на **Assetto Corsa** -> **Властивості (Properties)**.
  3. Перейдіть у вкладку **Контролер (Controller)**.
  4. У випадаючому списку виберіть **«Вимкнути систему вводу Steam» (Disable Steam Input)**.

---

## Налаштування звуку у Windows для геймпада

Щоб працювала HD-вібрація, Windows має правильно взаємодіяти з аудіочипом DualSense.

### Варіант А: Автоматично через програму (Рекомендовано)
1. Підключіть DualSense через USB-кабель і запустіть **DualSense AC Bridge**.
2. Якщо звук геймпада ще не налаштовано, у додатку з'явиться банер або повідомлення.
3. Натисніть **«Налаштувати»** (або запустіть майстер налаштування).
4. Програма автоматично:
   * Активує 4-канальний режим (квадрофонія).
   * Виставить гучність пристрою DualSense на 100% (необхідно для максимальної сили вібрації).
5. Підтвердіть запит прав адміністратора Windows (UAC), якщо він з'явиться.

---

### Варіант Б: Вручну через Панель керування Windows
Якщо ви бажаєте перевірити або налаштувати вручну:
1. Натисніть клавіші `Win + R`, введіть `mmsys.cpl` і натисніть **Enter** (відкриється класична панель звуку).
2. Знайдіть пристрій **«Wireless Controller»** (або DualSense):
   * Якщо пристрій вимкнено — натисніть правою кнопкою миші -> **«Увімкнути» (Enable)**.
3. **ГОЛОВНЕ ПРАВИЛО:** Переконайтеся, що геймпад **НЕ** вибрано як *«Пристрій за замовчуванням»* (Default Device)! Вашим основним звуковим пристроєм мають залишатися ваші колонки або навушники, інакше звуки Windows та музика гратимуть у вібромотори геймпада.
4. Натисніть правою кнопкою миші на «Wireless Controller» -> **«Властивості» (Properties)** -> вкладка **«Рівні» (Levels)** -> встановіть повзунок гучності на **100%**.
5. Виділіть «Wireless Controller» та внизу натисніть кнопку **«Настроїти» (Configure)**:
   * Оберіть конфігурацію **«Квадрофонічна» (Quadraphonic / 4 канали)** та завершіть майстер кнопкою «Далі» -> «Готово».

---

## Налаштування в Assetto Corsa / Content Manager

1. Відкрийте **Content Manager** (або стандартні налаштування гри).
2. Перейдіть у розділ: **Налаштування (Settings)** -> **Assetto Corsa** -> **Керування (Controls)**.
3. У верхній вкладці виберіть тип вводу: **Геймпад / Контролер (Game Controller)**.
4. Переконайтеся, що гра реагує на кнопки, газ (R2), гальмо (L2) та поворот керма (гіроскоп відхиляє вісь лівого стіка віртуального геймпада).
5. Телеметрія (поребрики, ABS, знос коліс, передачі) надходить у програму автоматично через штатну пам'ять Assetto Corsa (Shared Memory) — ніяких додаткових плагінів встановлювати не потрібно!

---

## Порядок запуску перед грою

1. Підключіть геймпад до ПК кабелем USB.
2. Запустіть **DualSense AC Bridge**.
3. Переконайтеся, що на головній панелі світиться:
   * **Геймпад:** `DualSense (USB)` [Підключено]
   * **Драйвер ViGEmBus:** `Встановлено` [OK]
   * **Тактильний відгук:** `Активний` [OK]
4. За бажанням відкрийте вікно **«Тестування»**:
   * Натисніть L2 та R2 — ви відчуєте наростаючий опір тригерів та вібрацію.
   * Покрутіть геймпад як кермо — шкала кута повороту покаже градуси та відхилення осі.
5. Запустіть **Assetto Corsa** і виїжджайте на трасу!

---

## Корисні налаштування та підказки

* **Максимальний кут керма**: У вкладці «Налаштування» можна змінити максимальний кут нахилу гіроскопа (за замовчуванням 65°–90°). 65° зручно для динамічного дрифту, 80°–90° — для точних кільцевих гонок.
* **Підрулювання стіком (Stick Override)**: Якщо ви втратили зчеплення або розвернулися, вам не потрібно ламати зап'ястя — просто рухніть лівий стік, і керування миттєво повернеться на класичний стік.
* **Згортання в трей**: При натисканні на хрестик вікно програми згортається в область сповіщень біля годинника (системний трей), щоб не заважати під час гри. Для повного закриття натисніть правою кнопкою миші на іконку в треї -> «Вихід».
