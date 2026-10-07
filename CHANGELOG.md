# Changelog

All notable changes to this project will be documented in this file.

## [1.2.0] - 2026-10-07

### What's New

#### Refined Gyroscope Steering and Expanded Range
Expanded motion steering options for greater control fidelity and responsiveness.

* **Wider Steering Angle:** You can now set the maximum steering angle up to 180 degrees in Settings, giving you full flexibility for tight hairpins and drift angles.
* **Adjustable Auto-Centering:** Tune how naturally the steering returns to center with the new "Auto-Centering Time Constant" option in Gyro Settings.
* **Smooth Recentering Transition:** Motion steering feels more natural and stable both on high-speed straights and during sudden counter-steering maneuvers.

#### Immediate Brake Trigger Resistance
* **Eliminated Initial Travel Deadzone:** The L2 brake pedal resistance now engages the moment you begin pressing the trigger, providing consistent and authentic hydraulic pedal feel without any loose initial play.

#### Seamless Keybind Input Isolation
* **Conflict-Free Button Binding:** Assigning a controller button to a keyboard key now cleanly blocks the original gamepad input, preventing duplicate simultaneous actions in games and system overlays.

#### Audio and Haptic Performance Improvements
* **Clear and Consistent Haptics:** Overhauled real-time tactile synthesis, eliminating audio stutter, pops, and delayed vibrations for smooth, continuous road texture and kerb effects.

---

## [1.1.1] - 2026-09-28

### What's New

#### Improved Brake ABS and Lockup Feedback
Enhanced the brake pedal tactile response to deliver more accurate and realistic physical feedback during hard braking.

* **Accurate Lockup Detection:** The L2 brake pedal vibration now activates strictly during actual tire lockup and ABS intervention, eliminating unintended pulsing during normal braking.
* **Independent ABS Vibration Toggle:** You can now enable or disable brake trigger vibration independently without affecting the hydraulic brake resistance wall.
* **Trigger Settings Control:** Easily toggle this option on or off in Settings under the Triggers section via "ABS / Lockup Vibration (L2)".

---

## [1.1.0] - 2026-09-27

### What's New

#### DirectInput Mode and Force Feedback Support
You can now switch between standard Gamepad emulation (XInput) and Steering Wheel emulation (DirectInput).

* **Steering Wheel Mode in Assetto Corsa:** By switching to DirectInput mode in General Settings and selecting Wheel controls in Assetto Corsa, you can experience true Force Feedback directly through your DualSense controller.
* **Physics-Driven Steering Resistance:** Feel the realistic mechanical weight of the steering rack build up as you turn through corners, and instantly notice when front tires lose grip.
* **Distinct Road and Kerb Sensations:** Experience separated tactile effects for kerb strikes, asphalt textures, tire slip, and braking lockups without constant background vibration on straights.
* **Adaptive Trigger Feedback:** The L2 brake pedal and R2 throttle pedal now feature subtle tactile responses when driving over heavy kerbs, in addition to progressive resistance and ABS pulsing.
* **Mode Selection in Settings:** Switch between XInput and DirectInput in General Settings. The app automatically reminds you to restart the bridge and the game to apply the change.

---

## [1.0.1] - 2026-09-27

### What's New

#### Keyboard Binds
You can now bind any DualSense controller button to any keyboard key (such as F10, Space, Enter, Shift, etc.).

* **Dual Functionality:** Bound buttons trigger the assigned keyboard key while still working as regular gamepad buttons.
* **Global Support:** Works globally across Windows and all games, not just in Assetto Corsa.
* **Visual Setup:** Open Settings -> Keyboard Binds to easily assign keys using an interactive DualSense layout and on-screen keyboard (or simply press the desired key on your physical keyboard).

---

## [1.0.0] - 2026-09-27

### Initial Release
* Initial unstable release of DualSense AC Bridge.
* Basic motion steering via gyro, adaptive triggers telemetry, and HD haptic feedback.
* Ongoing work on overall application and connection stability.
