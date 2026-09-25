"""
Configuration manager for DualSense AC Bridge.
Loads and saves settings to config.json.
Automatically locates config.json in bridge root or package directory.
"""

import json
import os
import logging

logger = logging.getLogger("DualSenseACBridge.Config")

DEFAULT_CONFIG = {
    "language": "uk",
    "udp_port": 6969,
    "udp_host": "0.0.0.0",
    "left_trigger_scale": 1.0,
    "right_trigger_scale": 1.0,
    "brake_wall_pos": 7,
    "brake_wall_force": 6,
    "throttle_spring_force": 3,
    "rgb_brightness_scale": 1.0,
    "enable_triggers": True,
    "enable_rgb": True,
    "enable_player_leds": True,
    "enable_audio_haptics": True,
    "haptic_master_gain": 0.45,
    "haptic_ffb_gain": 0.35,
    "haptic_kerb_gain": 0.5,
    "haptic_lockup_gain": 1.0,
    "haptic_drift_gain": 1.0,
    "haptic_gearshift_gain": 0.8,
    "brake_gamma": 2.4,
    "throttle_gamma": 1.4,
    "minimize_to_tray": False,
    "auto_connect": True,
    "enable_gyro": True,
    "gyro_max_angle": 90.0,
    "gyro_deadzone": 0.002,
    "gyro_ema_alpha": 1.0,
    "gyro_filter_beta": 0.98,
    "gyro_gamma": 1.0,
    "gyro_invert": False,
    "gyro_speed_sensitivity": 0.15,
    "gyro_enable_speed_sensitivity": False,
    "gyro_stick_override": True,
    "gyro_stick_override_threshold": 0.2,
    "gyro_axis": "y",
    "gyro_scale": 16.384,
    "gyro_rate_invert": False,
    "gyro_zero_offset": 0.0,
    "gyro_noise_threshold": 0.08,
    "dpad_right_f10": True,
    "dpad_right_gamepad": False,
    "auto_exit_on_game_close": True
}


class Config:
    def __init__(self, config_path: str = None):
        if config_path is None:
            cur_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(cur_dir)

            local_cfg = os.path.join(cur_dir, "config.json")
            parent_cfg = os.path.join(parent_dir, "config.json")

            # Якщо config.json лежить у bridge/ -> беремо його, інакше в DualSenseACBridge/
            if os.path.exists(parent_cfg):
                config_path = parent_cfg
            elif os.path.exists(local_cfg):
                config_path = local_cfg
            else:
                # Пріоритет створення нового файлу - папка bridge/
                config_path = parent_cfg

        self.config_path = config_path
        self.data = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data.update(saved)
                print(f"[CONFIG] Завантажено конфіг: {self.config_path}")
                logger.info(f"Loaded config from {self.config_path}")
            except Exception as e:
                print(f"[CONFIG ERROR] Не вдалося завантажити {self.config_path}: {e}")
                logger.warning(f"Could not load config: {e}")
        else:
            print(f"[CONFIG] Файл не знайдено, створюємо новий: {self.config_path}")
            self.save()

    def save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
            logger.info(f"Saved config to {self.config_path}")
        except Exception as e:
            print(f"[CONFIG ERROR] Не вдалося зберегти {self.config_path}: {e}")
            logger.warning(f"Could not save config: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()