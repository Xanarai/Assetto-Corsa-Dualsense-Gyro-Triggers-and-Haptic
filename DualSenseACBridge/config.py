"""
Configuration manager for DualSense AC Bridge.
Loads, validates, and persists user settings in config.json.
"""

import json
import os
import logging

logger = logging.getLogger("DualSenseACBridge.Config")

DEFAULT_CONFIG = {
    "language": "en",
    "udp_port": 6969,
    "udp_host": "127.0.0.1",
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
    "haptic_kerb_gain": 0.5,
    "haptic_lockup_gain": 1.0,
    "haptic_drift_gain": 1.0,
    "haptic_gearshift_gain": 0.8,
    "haptic_ffb_gain": 1.0,
    "brake_gamma": 2.4,
    "throttle_gamma": 1.4,
    "enable_gyro": True,
    "gyro_max_angle": 90.0,
    "gyro_deadzone": 0.002,
    "gyro_gamma": 1.0,
    "gyro_invert": False,
    "gyro_speed_sensitivity": 0.15,
    "gyro_enable_speed_sensitivity": False,
    "gyro_stick_override": True,
    "gyro_stick_override_threshold": 0.2,
    "gyro_axis": "y",
    "gyro_scale": 16.384,
    "gyro_rate_invert": False,
    "auto_exit_on_game_close": True,
    "controller_mode": "xinput",
    "key_binds": {}
}


class Config:
    """Manages application settings persistence to disk."""

    def __init__(self, config_path: str = None):
        if config_path is None:
            cur_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(cur_dir)

            local_cfg = os.path.join(cur_dir, "config.json")
            parent_cfg = os.path.join(parent_dir, "config.json")

            # Prefer root directory config over package directory
            if os.path.exists(parent_cfg):
                config_path = parent_cfg
            elif os.path.exists(local_cfg):
                config_path = local_cfg
            else:
                # Default new configuration file to project root
                config_path = parent_cfg

        self.config_path = config_path
        self.data = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        """Loads configuration from JSON file or initializes defaults if not found."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data.update(saved)
                print(f"[CONFIG] Loaded config: {self.config_path}")
                logger.info(f"Loaded config from {self.config_path}")
            except Exception as e:
                print(f"[CONFIG ERROR] Failed to load {self.config_path}: {e}")
                logger.warning(f"Could not load config: {e}")
        else:
            print(f"[CONFIG] File not found, creating new: {self.config_path}")
            self.save()

    def save(self):
        """Persists current in-memory configuration to disk."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
            logger.info(f"Saved config to {self.config_path}")
        except Exception as e:
            print(f"[CONFIG ERROR] Failed to save {self.config_path}: {e}")
            logger.warning(f"Could not save config: {e}")

    def get(self, key, default=None):
        """Retrieves a configuration value by key."""
        return self.data.get(key, default)

    def set(self, key, value):
        """Updates a configuration key and immediately persists changes."""
        self.data[key] = value
        self.save()