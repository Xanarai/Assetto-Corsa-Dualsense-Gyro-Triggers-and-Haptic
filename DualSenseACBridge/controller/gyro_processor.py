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

        self.centering_tau: float = 0.06
        raw_tau = cfg.get("gyro_centering_tau", 0.06)
        try:
            self.set_centering_tau(raw_tau)
        except ValueError as e:
            logger.error(f"[CONFIG ERROR] Invalid 'gyro_centering_tau' in configuration: {e}. Defaulting to 0.06s.")
            self.centering_tau = 0.06

        self.filtered_angle: float = 0.0        # Computed tilt angle in degrees
        self.final_output: float = 0.0          # Normalized steering signal in [-1.0, 1.0]

        self.raw_accel_angle: float = 0.0
        self.current_angle: float = 0.0         # Fused state angle
        self.total_g: float = 1.0               # Instantaneous 3D acceleration magnitude in G's
        self.gravity_weight: float = 1.0        # Gravity confidence factor [0.0, 1.0]
        self.is_initialized: bool = False
        self.touchpad_pressed_prev: bool = False
        self.last_time: float = time.perf_counter()

    @staticmethod
    def compute_gravity_weight(total_g: float) -> float:
        """
        Gravity shock rejection filter.
        The accelerometer only measures the true gravity vector when total acceleration
        magnitude is approximately 1.0G (+/- 15%).
        During mechanical vibration (gear shift kicks, haptic audio resonance, kerb strikes),
        dynamic acceleration spikes or drops sharply.
        
        Returns:
            1.0 if within nominal [0.85G, 1.15G] window.
            0.0 if deviating by more than 0.25G (<= 0.75G or >= 1.25G).
            Linear interpolation between 0.15G and 0.25G delta for smooth transition.
        """
        g_delta = abs(total_g - 1.0)
        if g_delta <= 0.15:
            return 1.0
        elif g_delta >= 0.25:
            return 0.0
        else:
            return (0.25 - g_delta) / 0.10

    def set_centering_tau(self, val: float):
        """
        Sets the centering time constant (tau) in seconds.
        Safe range: [0.01, 0.30] seconds.
        Raises ValueError if val is invalid or outside the safe range.
        """
        try:
            fval = float(val)
            if math.isnan(fval) or math.isinf(fval) or not (0.01 <= fval <= 0.30):
                raise ValueError(f"Value {fval} is outside allowed range [0.01, 0.30]")
            self.centering_tau = fval
        except (ValueError, TypeError) as e:
            err_msg = f"Invalid 'gyro_centering_tau' value '{val}': {e}. Must be a number between 0.01 and 0.30 seconds."
            logger.error(err_msg)
            raise ValueError(err_msg) from e

    def reset(self):
        """Resets internal state angles and timing counters."""
        self.filtered_angle = 0.0
        self.final_output = 0.0
        self.current_angle = 0.0
        self.total_g = 1.0
        self.gravity_weight = 1.0
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
        if touchpad_clicked and not self.touchpad_pressed_prev:
            self.current_angle = 0.0
            self.filtered_angle = 0.0
            logger.info("Touchpad clicked -> Recalibrated steering center to 0.0°")
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

        # 3D acceleration vector magnitude in G's & gravity confidence factor
        total_accel_raw = math.sqrt(ax * ax + ay * ay + az * az)
        self.total_g = total_accel_raw / ACCEL_SCALE_G
        self.gravity_weight = self.compute_gravity_weight(self.total_g)

        # Compute absolute roll angle from gravity vector
        yz_magnitude = math.sqrt(ay * ay + az * az)
        if yz_magnitude > 10.0:
            raw_accel_angle = -math.degrees(math.atan2(ax, yz_magnitude))
        else:
            raw_accel_angle = -90.0 if ax > 0 else 90.0

        self.raw_accel_angle = raw_accel_angle

        # Continuous quadrant unwrapping beyond 90 degrees:
        # Since sqrt(ay^2 + az^2) is strictly positive, raw atan2 reflects at 90° (e.g. 100° becomes 80°).
        # We unwrap the accelerometer angle using the current fused gyro state.
        if self.current_angle > 90.0 and raw_accel_angle > 0.0:
            accel_angle = 180.0 - raw_accel_angle
        elif self.current_angle < -90.0 and raw_accel_angle < 0.0:
            accel_angle = -180.0 - raw_accel_angle
        else:
            accel_angle = raw_accel_angle

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
            if self.gravity_weight > 0.0:
                self.current_angle = accel_angle
                self.is_initialized = True
            else:
                self.current_angle = 0.0

        # Adaptive complementary filter with high-speed zero centering:
        # Near center (|angle| < 12°), tau drops to user-configured centering_tau (default 0.06s) for snappy, immediate centering.
        # High angular rates rely predominantly on gyro for instant response and curb rejection.
        abs_angle = abs(self.current_angle)
        if abs_angle < 12.0:
            min_tau = self.centering_tau
            max_tau = max(min_tau, 0.90)
        elif abs_angle < 25.0:
            min_tau = 0.10
            max_tau = 1.60
        else:
            min_tau = 0.18
            max_tau = 2.50

        movement_intensity = min(1.0, abs(gyro_rate) / 40.0)
        tau = min_tau + (movement_intensity * (max_tau - min_tau))
        base_alpha = tau / (tau + dt)

        # Fade out accelerometer correction at high roll angles (>= 65° towards 80°):
        # Around and beyond 90°, the gravity vector projection becomes degenerate.
        # At steep tilt, rely 100% on gyro integration to prevent inversion or center drift.
        if abs_angle <= 65.0:
            angle_weight = 1.0
        elif abs_angle >= 80.0:
            angle_weight = 0.0
        else:
            angle_weight = (80.0 - abs_angle) / 15.0

        # Gravity Shock Rejection:
        # Decouple accelerometer when total G vector deviates from nominal gravity
        # (e.g. during gear shift haptics, road bumps, or motor vibrations).
        accel_weight = angle_weight * self.gravity_weight

        effective_alpha = 1.0 - (1.0 - base_alpha) * accel_weight
        self.current_angle = effective_alpha * (self.current_angle + gyro_angle_change) + (1.0 - effective_alpha) * accel_angle

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