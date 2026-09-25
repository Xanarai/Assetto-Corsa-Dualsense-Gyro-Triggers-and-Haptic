"""
Main entry point for DualSense AC Bridge.
Runs GUI or CLI mode.
"""

import sys
import os
import time
import argparse
import logging
import signal

# Ensure working directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from DualSenseACBridge.controller.dualsense import DualSenseController
from DualSenseACBridge.ac_integration.receiver import TelemetryReceiver
from DualSenseACBridge.config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("DualSenseACBridge.Main")


def run_cli(controller: DualSenseController, receiver: TelemetryReceiver):
    logger.info("Running in CLI mode. Press Ctrl+C to stop.")
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        print("\nStopping DualSense AC Bridge...")
        running = False

    def on_game_closed():
        nonlocal running
        print("\nAssetto Corsa closed. Stopping DualSense AC Bridge...")
        running = False

    receiver.on_game_closed = on_game_closed
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while running:
            now = time.time()
            telemetry_active = (now - receiver.last_packet_time < 1.0) and (receiver.packet_count > 0)
            ctrl_status = f"{controller.product_name} ({'USB' if controller.conn_type == 1 else 'BT' if controller.conn_type == 2 else 'DISCONNECTED'})"
            telemetry_status = f"LIVE ({receiver.packets_per_second:.0f} Hz, {receiver.packet_count} pkts)" if telemetry_active else "WAITING"
            lt = receiver.last_lt_info
            rt = receiver.last_rt_info
            gyro_str = f"{controller.gyro.filtered_angle:+.1f}° ({controller.gyro.final_output * 100:+.0f}%)" if controller.gyro.enabled else "OFF"
            print(
                f"\r[Ctrl: {ctrl_status}] [Gyro: {gyro_str}] [AC: {telemetry_status}] [L2 ABS: {lt.get('strength', 0)}/8] [R2: {rt.get('strength', 0)}/8]",
                end="",
                flush=True
            )
            time.sleep(0.05)
    finally:
        print("\nShutting down...")
        controller.reset_effects()
        controller.stop()
        receiver.stop()
        print("Done.")


def main():
    parser = argparse.ArgumentParser(description="DualSense AC Bridge for Steam Input & Assetto Corsa")
    parser.add_argument("--cli", action="store_true", help="Run in headless console CLI mode without GUI")
    parser.add_argument("--port", type=int, default=None, help="UDP port override (default from config: 6969)")
    args = parser.parse_args()

    config = Config(os.path.join(BASE_DIR, "config.json"))
    port = args.port or config.get("udp_port", 6969)
    host = config.get("udp_host", "0.0.0.0")

    controller = DualSenseController()
    receiver = TelemetryReceiver(controller, host=host, port=port)
    receiver.left_trigger_scale = config.get("left_trigger_scale", 1.0)
    receiver.right_trigger_scale = config.get("right_trigger_scale", 1.0)
    receiver.rgb_brightness_scale = config.get("rgb_brightness_scale", 1.0)
    receiver.enable_triggers = config.get("enable_triggers", True)
    receiver.enable_rgb = config.get("enable_rgb", True)
    receiver.enable_audio_haptics = config.get("enable_audio_haptics", True)
    receiver.haptic_processor.master_gain = float(config.get("haptic_master_gain", 1.0))
    receiver.haptic_processor.ffb_gain = float(config.get("haptic_ffb_gain", 0.7))
    receiver.haptic_processor.kerb_gain = float(config.get("haptic_kerb_gain", 1.0))
    receiver.haptic_processor.lockup_gain = float(config.get("haptic_lockup_gain", 1.0))
    receiver.haptic_processor.drift_gain = float(config.get("haptic_drift_gain", 0.85))
    receiver.haptic_processor.gearshift_gain = float(config.get("haptic_gearshift_gain", 0.8))
    receiver.auto_exit_on_game_close = bool(config.get("auto_exit_on_game_close", True))
    started = receiver.start()
    if not started:
        logger.info(f"Port {port} is already active (another instance running). Exiting cleanly.")
        sys.exit(0)

    controller.enable_rumble = False
    controller.enable_rgb = config.get("enable_rgb", True)
    controller.enable_player_leds = config.get("enable_player_leds", True)

    # Initialize Gyroscope configuration
    controller.gyro.enabled = config.get("enable_gyro", True)
    controller.gyro.max_steer_angle = float(config.get("gyro_max_angle", 65.0))
    controller.gyro.deadzone = float(config.get("gyro_deadzone", 0.002))
    controller.gyro.ema_alpha = float(config.get("gyro_ema_alpha", 0.0))
    controller.gyro.gamma = float(config.get("gyro_gamma", 1.0))
    controller.gyro.invert_steer = bool(config.get("gyro_invert", False))
    controller.gyro.stick_override = bool(config.get("gyro_stick_override", True))
    controller.gyro.stick_override_threshold = float(config.get("gyro_stick_override_threshold", 0.20))
    controller.gyro.zero_offset = float(config.get("gyro_zero_offset", 0.0))
    controller.gyro.noise_threshold = float(config.get("gyro_noise_threshold", 0.0))
    controller.gyro.speed_sensitivity = float(config.get("gyro_speed_sensitivity", 0.15))
    controller.gyro.enable_speed_sensitivity = bool(config.get("gyro_enable_speed_sensitivity", True))

    # Initialize Keybindings configuration
    controller.dpad_right_f10 = bool(config.get("dpad_right_f10", True))
    controller.dpad_right_gamepad = bool(config.get("dpad_right_gamepad", False))

    controller.start()

    if args.cli:
        run_cli(controller, receiver)
    else:
        try:
            # Outdated GUI has been moved to DualSenseACBridge.app_gui_outdated:
            # from DualSenseACBridge.app_gui_outdated import BridgeApp as OutdatedBridgeApp
            # Using new streamlined minimal GUI with Start/Stop and System Tray:
            from DualSenseACBridge.ui.app_gui import BridgeApp
            try:
                import pyi_splash
                if pyi_splash.is_alive():
                    pyi_splash.close()
            except Exception:
                pass
            app = BridgeApp(controller, receiver, config)
            app.mainloop()
        except Exception as e:
            logger.error(f"Failed to start GUI: {e}, falling back to CLI mode")
            run_cli(controller, receiver)


if __name__ == "__main__":
    main()
