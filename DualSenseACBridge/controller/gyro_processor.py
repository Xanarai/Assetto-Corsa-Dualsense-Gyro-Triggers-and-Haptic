"""
Precision IMU Steering Processor for Assetto Corsa.
Processes raw 6-axis IMU telemetry (accelerometer + gyroscope) into normalized steering output.

Features:
- Dynamic tau complementary filter (gyro-dominant in turns, gravity-referenced on straights)
- DualSense IMU axis orientation and sign reconciliation
- Continuous deadzone remapping without step discontinuities
- Non-linear gamma steering curve
- High-speed steering angle attenuation
"""

import math
import time
import logging
from typing import Optional

from ..config import Config

logger = logging.getLogger("DualSenseACBridge.GyroProcessor")

ACCEL_SCALE_G = 8192.0
GYRO_SCALE_DPS = 16.384


class GyroProcessor:
    """Transforms raw DualSense accelerometer and gyroscope registers into racing steering input."""

    def __init__(self):
        cfg = Config()

        self.enabled: bool = cfg.get("enable_gyro", True)
        self.max_steer_angle: float = float(cfg.get("gyro_max_angle", 65.0))
        self.deadzone: float = float(cfg.get("gyro_deadzone", 0.02))
        self.gamma: float = float(cfg.get("gyro_gamma", 1.15))
        self.invert_steer: bool = cfg.get("gyro_invert", False)
        self.stick_override: bool = cfg.get("gyro_stick_override", True)
        self.stick_override_threshold: float = float(cfg.get("gyro_stick_override_threshold", 0.20))
        self.speed_sensitivity: float = float(cfg.get("gyro_speed_sensitivity", 0.15))
        self.enable_speed_sensitivity: bool = cfg.get("gyro_enable_speed_sensitivity", True)
        self.gyro_axis: str = str(cfg.get("gyro_axis", "y")).lower()
        self.gyro_scale: float = float(cfg.get("gyro_scale", GYRO_SCALE_DPS))
        self.gyro_rate_invert: bool = bool(cfg.get("gyro_rate_invert", False))

        self.filtered_angle: float = 0.0        # Computed tilt angle in degrees
        self.final_output: float = 0.0          # Normalized steering signal in [-1.0, 1.0]

        self.raw_accel_angle: float = 0.0
        self.current_angle: float = 0.0         # Fused state angle
        self.is_initialized: bool = False
        self.touchpad_pressed_prev: bool = False
        self.last_time: float = time.perf_counter()

    def reset(self):
        """Resets internal state angles and timing counters."""
        self.filtered_angle = 0.0
        self.final_output = 0.0
        self.current_angle = 0.0
        self.is_initialized = False
        self.last_time = time.perf_counter()

    def process_imu(
        self,
        ax_raw: int,
        ay_raw: int,
        az_raw: int,
        gx_raw: int,
        gy_raw: int,
        gz_raw: int,
        speed_kmh: float = 0.0,
        touchpad_clicked: bool = False
    ) -> float:
        """
        Fuses 6-axis raw IMU registers into a normalized steering command.

        Returns:
            Normalized steering value in range [-1.0, 1.0].
        """
        self.touchpad_pressed_prev = touchpad_clicked

        if not self.enabled:
            self.final_output = 0.0
            return 0.0

        now = time.perf_counter()
        dt = now - self.last_time
        if dt <= 0.0 or dt > 0.1:
            dt = 0.004  # Fallback to nominal 250 Hz interval to prevent startup delta spikes
        self.last_time = now

        ax = float(ax_raw)
        ay = float(ay_raw)
        az = float(az_raw)

        # Compute absolute roll angle from gravity vector
        yz_magnitude = math.sqrt(ay * ay + az * az)
        if yz_magnitude > 10.0:
            accel_angle = -math.degrees(math.atan2(ax, yz_magnitude))
        else:
            accel_angle = -90.0 if ax > 0 else 90.0

        self.raw_accel_angle = accel_angle

        # Angular rate conversion from raw register value to degrees/second
        if self.gyro_axis == 'x':
            gyro_rate = float(gx_raw) / self.gyro_scale
        elif self.gyro_axis == 'z':
            gyro_rate = float(gz_raw) / self.gyro_scale
        else:
            gyro_rate = float(gy_raw) / self.gyro_scale
            
        # Invert gyro rate if needed. DualSense hardware registers default to opposite signs
        # between accelerometer roll and gyroscope angular velocity.
        if not self.gyro_rate_invert:
            gyro_rate = -gyro_rate
            
        gyro_angle_change = gyro_rate * dt

        if not self.is_initialized:
            self.current_angle = accel_angle
            self.is_initialized = True

        # Adaptive complementary filter:
        # Dynamically scale filter time constant (tau) based on angular rate.
        # High angular rates rely predominantly on gyro (tau = 2.5s) for instant response and curb rejection.
        # Low rates allow accelerometer correction (tau = 0.25s) to eliminate gyro drift on straights.
        movement_intensity = min(1.0, abs(gyro_rate) / 20.0)
        tau = 0.25 + (movement_intensity * 2.25)
        
        alpha = tau / (tau + dt)
        self.current_angle = alpha * (self.current_angle + gyro_angle_change) + (1.0 - alpha) * accel_angle

        # Pass through fused angle directly without artificial smoothing lag
        self.filtered_angle = self.current_angle

        # Normalize angle against configured steering lock
        max_angle = max(10.0, self.max_steer_angle)
        norm_val = self.filtered_angle / max_angle
        norm_val = max(-1.0, min(1.0, norm_val))

        # Continuous deadzone mapping (smooth ramp without step discontinuities)
        dz = max(0.0, min(0.3, self.deadzone))
        abs_val = abs(norm_val)

        if abs_val <= dz:
            deadzoned = 0.0
        else:
            sign = 1.0 if norm_val > 0.0 else -1.0
            deadzoned = sign * ((abs_val - dz) / (1.0 - dz))

        # Non-linear gamma curve
        if abs(deadzoned) > 1e-5 and self.gamma != 1.0:
            sign = 1.0 if deadzoned > 0.0 else -1.0
            curved = sign * (abs(deadzoned) ** self.gamma)
        else:
            curved = deadzoned

        # Dynamic speed sensitivity: progressively damp steering ratio at speeds > 30 km/h
        if self.enable_speed_sensitivity and speed_kmh > 30.0:
            speed_factor = 1.0 / (1.0 + (speed_kmh - 30.0) * (self.speed_sensitivity * 0.01))
            curved *= max(0.25, speed_factor)

        if self.invert_steer:
            curved = -curved

        self.final_output = max(-1.0, min(1.0, curved))
        return self.final_output