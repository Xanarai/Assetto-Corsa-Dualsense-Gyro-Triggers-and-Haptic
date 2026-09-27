# DualSense AC Bridge

[![GitHub Release](https://img.shields.io/badge/Assetto%20Corsa-DualSense%20Bridge-red?logo=playstation)](https://github.com/Xanarai/Assetto-Corsa-Dualsense-Gyro-Triggers-and-Haptic)
[![ViGEmBus](https://img.shields.io/badge/Driver-ViGEmBus-blue)](https://vigembusdriver.com/)
[![UI](https://img.shields.io/badge/Interface-PyWebView-success)](#)
[![Haptics](https://img.shields.io/badge/Haptics-Voice--Coil%20HD-purple)](#)

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
  * Modern dark aesthetic UI.
  * 1-Click interactive Audio Setup Wizard.
  * Integrated Testing & Diagnostics panel for triggers and gyro calibration.
  * Seamlessly minimizes to the Windows system tray during races.

---

## Requirements & Setup Guide

### 1. Download the Application
* Go to the [Releases](https://github.com/Xanarai/Assetto-Corsa-Dualsense-Gyro-Triggers-and-Haptic/releases/latest) page on GitHub.
* Download the latest `.zip` archive.
* Extract the archive to any folder on your PC (e.g., your Desktop or Documents).

### 2. Install ViGEmBus Driver (Mandatory)
The bridge creates a virtual Xbox 360 controller via the ViGEmBus system driver so Assetto Corsa can read smooth motion steering axes. Without this driver, the game will not detect input.
* **Download:** [ViGEmBus Driver Website](https://vigembusdriver.com/)
* Download and run `ViGEmBus_Setup_...exe` to complete the installation.

### 3. Connect via USB Cable ONLY
> [!IMPORTANT]
> **Why is a USB cable required?**  
> True HD voice-coil haptics require 4-channel audio output to the controller's internal actuators.  
> **Windows only exposes the 4-channel Quadraphonic audio interface over a wired USB connection.**  
> *(Bluetooth only supports trigger resistance and basic rumble, but not HD haptics).*

### 4. Disable Conflicting Software
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

