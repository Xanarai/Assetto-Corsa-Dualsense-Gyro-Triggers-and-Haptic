"""
Unified Telemetry Math Processor for Assetto Corsa Spatial Haptics.
Computes spatial haptic feedback (Left & Right separation) for:
- FFB Steering Load (physics.finalFF → proportional vibration)
- Kerb / Road Texture (Suspension velocity High-Pass filter)
- Wheel Lockup / ABS (Pulsating vibration per side)
- Oversteer / Drift (Low-frequency chassis slide rumble)
- Gear Shift Impulse (Short spike on gear change)

Written with cross-compatibility in mind (Python 3.3+ inside AC and Python 3.12+ in Bridge).
"""

import math
import time


def _clamp(val, min_val, max_val):
    if val < min_val:
        return min_val
    if val > max_val:
        return max_val
    return val


def _smoothstep(edge0, edge1, x):
    """Hermite smoothstep: smooth ramp from 0 to 1 between edge0 and edge1."""
    if x <= edge0:
        return 0.0
    if x >= edge1:
        return 1.0
    t = (x - edge0) / (edge1 - edge0)
    return t * t * (3.0 - 2.0 * t)


class HapticTelemetryState(object):
    """Encapsulates computed spatial haptic outputs for audio synthesis & HID rumble."""

    def __init__(
        self,
        left_amp=0.0,
        right_amp=0.0,
        left_freq=130.0,
        right_freq=130.0,
        kerb_l=0.0,
        kerb_r=0.0,
        lockup_l=0.0,
        lockup_r=0.0,
        drift=0.0,
        ffb=0.0,
        ffb_l=0.0,
        ffb_r=0.0,
        gear_shift=0.0,
    ):
        self.left_amp = float(_clamp(left_amp, 0.0, 1.0))
        self.right_amp = float(_clamp(right_amp, 0.0, 1.0))
        self.left_freq = float(left_freq)
        self.right_freq = float(right_freq)

        # Detailed breakdown for GUI visualization
        self.kerb_l = float(kerb_l)
        self.kerb_r = float(kerb_r)
        self.lockup_l = float(lockup_l)
        self.lockup_r = float(lockup_r)
        self.drift = float(drift)
        self.ffb = float(ffb)
        self.ffb_l = float(ffb_l)
        self.ffb_r = float(ffb_r)
        self.gear_shift = float(gear_shift)

        # Legacy aliases for receiver.py compatibility
        self.abs_l = self.lockup_l
        self.abs_r = self.lockup_r

    def to_dict(self):
        return {
            "left_amp": self.left_amp,
            "right_amp": self.right_amp,
            "left_freq": self.left_freq,
            "right_freq": self.right_freq,
            "kerb_l": self.kerb_l,
            "kerb_r": self.kerb_r,
            "lockup_l": self.lockup_l,
            "lockup_r": self.lockup_r,
            "drift": self.drift,
            "ffb": self.ffb,
            "ffb_l": self.ffb_l,
            "ffb_r": self.ffb_r,
            "gear_shift": self.gear_shift,
        }


class HapticTelemetryProcessor(object):
    """
    Stateful processor converting Assetto Corsa physics telemetry
    into precise, balanced, spatial tactile feedback signals.

    Effects:
    1. FFB Steering Load — abs(finalFF) mapped to constant vibration amplitude
    2. Kerb — suspension travel derivative (delta velocity) → high-freq bursts
    3. Lockup — wheel slip under braking → pulsating vibration
    4. Drift — body slip angle from velocity vector → deep rumble
    5. Gear Shift — one-shot impulse on gear change
    """

    def __init__(self):
        # ── User-Tunable Gains (0.0 = off, 1.0 = default, 2.0 = double) ──
        self.master_gain = 1.0
        self.ffb_gain = 0.7       # FFB steering load → vibration intensity
        self.kerb_gain = 1.0      # Kerb rumble strips
        self.lockup_gain = 1.0    # Wheel lockup / ABS
        self.drift_gain = 0.85    # Oversteer / body slip
        self.gearshift_gain = 0.8 # Gear shift impulse

        # ── Physical Thresholds ──
        # Kerb: suspension velocity thresholds (m/s)
        # Flat road in AC produces ~0.02–0.08 m/s noise. Kerbs produce 0.15+ m/s.
        self.kerb_threshold_low = 0.06   # Спрацьовує навіть на плоских поребриках
        self.kerb_threshold_high = 0.35  # Раніше досягає 100% потужності

        # Lockup: wheel slip ratio thresholds (negative = locked wheel)
        self.lockup_slip_threshold = -0.12   # Start sensing lockup
        self.lockup_slip_max = -0.50         # Full lockup intensity

        # Drift: body slip angle thresholds (radians)
        self.drift_threshold_rad = 0.18   # ~10° — below this, no drift feel
        self.drift_max_rad = 0.52         # ~30° — maximum drift intensity

        # FFB: finalFF deadzone (ignore tiny forces on straights)
        self.ffb_deadzone = 0.06
        self.ffb_max = 0.85  # FFB value at which vibration reaches max

        # Gear shift impulse duration (seconds)
        self.gearshift_impulse_duration = 0.06  # 60ms pulse

        # ── State Memory ──
        self.last_time = None
        self.prev_suspension_travel = None  # FL, FR, RL, RR (None on init to prevent 1st frame kerb spike)
        self.prev_suspension_vel = [0.0, 0.0, 0.0, 0.0]
        self.prev_gear = 0
        self.gearshift_timer = 0.0  # Countdown for gear shift impulse
        self.last_state = HapticTelemetryState()

    def reset(self):
        self.last_time = None
        self.prev_suspension_travel = None
        self.prev_suspension_vel = [0.0, 0.0, 0.0, 0.0]
        self.prev_gear = 0
        self.gearshift_timer = 0.0
        self.last_state = HapticTelemetryState()

    def process(self, physics_obj, delta_t=None, in_kerb_l=0.0, in_kerb_r=0.0):
        """
        Process one frame of AC physics telemetry and return a HapticTelemetryState.

        Args:
            physics_obj: Assetto Corsa physics shared memory struct (or sim_info.physics)
            delta_t: Frame delta time in seconds (None = auto-calculate)

        Returns:
            HapticTelemetryState with computed haptic amplitudes and frequencies
        """
        now = time.time()
        if delta_t is None:
            if self.last_time is None:
                dt = 0.016
            else:
                dt = now - self.last_time
        else:
            dt = delta_t

        dt = _clamp(dt, 0.001, 0.1)
        self.last_time = now

        if physics_obj is None:
            self.last_state = HapticTelemetryState()
            return self.last_state

        # ── Read telemetry values safely ──
        try:
            speed_kmh = float(getattr(physics_obj, "speedKmh", 0.0))
            brake = float(getattr(physics_obj, "brake", 0.0))
            gear = int(getattr(physics_obj, "gear", 0))
            final_ff = float(getattr(physics_obj, "finalFF", 0.0))
            abs_sys = float(getattr(physics_obj, "abs", 0.0))

            raw_travel = list(getattr(physics_obj, "suspensionTravel", [0.0, 0.0, 0.0, 0.0]))
            raw_slips = list(getattr(physics_obj, "wheelSlip", [0.0, 0.0, 0.0, 0.0]))
            # Prefer localVelocity for drift, fallback to velocity
            raw_vel = list(getattr(physics_obj, "localVelocity", getattr(physics_obj, "velocity", [0.0, 0.0, 0.0])))
        except Exception:
            return self.last_state

        # Ensure arrays have correct length
        if len(raw_travel) < 4:
            raw_travel = [0.0, 0.0, 0.0, 0.0]
        if len(raw_slips) < 4:
            raw_slips = [0.0, 0.0, 0.0, 0.0]
        if len(raw_vel) < 3:
            raw_vel = [0.0, 0.0, 0.0]

        if self.prev_suspension_travel is None:
            self.prev_suspension_travel = list(raw_travel)

        # ── Dead zone: no vibration when standing still ──
        if speed_kmh < 3.0:
            self.prev_suspension_travel = list(raw_travel)
            self.prev_gear = gear
            self.last_state = HapticTelemetryState()
            return self.last_state

        # ═══════════════════════════════════════════════════════
        # 1. FFB STEERING LOAD → proportional haptic vibration
        # ═══════════════════════════════════════════════════════
        ffb_raw = abs(final_ff)
        ffb_intensity = 0.0
        if ffb_raw > self.ffb_deadzone:
            # Smooth ramp using cubic smoothstep & saturation
            x = min(1.0, (ffb_raw - self.ffb_deadzone) / max(0.001, (self.ffb_max - self.ffb_deadzone)))
            ff_soft = x * x * (3.0 - 2.0 * x)
            ffb_intensity = math.tanh(ff_soft * 1.85) * self.ffb_gain

            # Understeer detection & grip drop-off:
            # When front tyres scrub beyond optimum slip, resistance drops significantly
            f_slips = raw_slips if len(raw_slips) >= 2 else [0.0, 0.0]
            avg_front_slip = (abs(f_slips[0]) + abs(f_slips[1])) * 0.5
            optimal_slip = 0.13
            max_slip = 0.38
            if avg_front_slip > optimal_slip:
                slip_ratio = min(1.0, (avg_front_slip - optimal_slip) / (max_slip - optimal_slip))
                grip_factor = 1.0 - (slip_ratio * 0.45)
                ffb_intensity *= grip_factor

        # Spatial weighting: FFB sign indicates steering rack self-aligning torque
        # final_ff > 0: turning right -> outside (left) hand loaded
        # final_ff < 0: turning left  -> outside (right) hand loaded
        if final_ff >= 0:
            ffb_l = ffb_intensity
            ffb_r = ffb_intensity * 0.35  # Lighter on inside hand
        else:
            ffb_r = ffb_intensity
            ffb_l = ffb_intensity * 0.35

        # ═══════════════════════════════════════════════════════
        # 2. KERB / RUMBLE STRIPS → sharp suspension velocity spikes
        # ═══════════════════════════════════════════════════════
        susp_vel = [0.0, 0.0, 0.0, 0.0]
        for i in range(4):
            susp_vel[i] = (raw_travel[i] - self.prev_suspension_travel[i]) / dt
        self.prev_suspension_travel = list(raw_travel)

        # EMA smoothing (α=0.70 new, 0.30 old) для швидкої реакції на удари
        for i in range(4):
            susp_vel[i] = susp_vel[i] * 0.70 + self.prev_suspension_vel[i] * 0.30
        self.prev_suspension_vel = list(susp_vel)

        # Left side = max(FL, RL), Right side = max(FR, RR)
        left_susp_shock = max(abs(susp_vel[0]), abs(susp_vel[2]))
        right_susp_shock = max(abs(susp_vel[1]), abs(susp_vel[3]))

        kerb_l = max(_smoothstep(self.kerb_threshold_low, self.kerb_threshold_high, left_susp_shock) * self.kerb_gain, float(in_kerb_l) * self.kerb_gain)
        kerb_r = max(_smoothstep(self.kerb_threshold_low, self.kerb_threshold_high, right_susp_shock) * self.kerb_gain, float(in_kerb_r) * self.kerb_gain)

        # ═══════════════════════════════════════════════════════
        # 3. WHEEL LOCKUP / ABS → pulsating vibration under braking
        # ═══════════════════════════════════════════════════════
        lockup_l = 0.0
        lockup_r = 0.0

        if brake > 0.05 and speed_kmh > 5.0:
            # Per-side lockup: FL+RL (left), FR+RR (right)
            min_left_slip = min(raw_slips[0], raw_slips[2])
            min_right_slip = min(raw_slips[1], raw_slips[3])

            abs_bonus = 0.05 if abs_sys > 0.0 else 0.0  # Lower threshold when ABS is active

            left_locked = min_left_slip < (self.lockup_slip_threshold + abs_bonus)
            right_locked = min_right_slip < (self.lockup_slip_threshold + abs_bonus)

            if left_locked:
                severity = _smoothstep(
                    abs(self.lockup_slip_threshold + abs_bonus),
                    abs(self.lockup_slip_max),
                    abs(min_left_slip)
                )
                lockup_l = severity * self.lockup_gain

            if right_locked:
                severity = _smoothstep(
                    abs(self.lockup_slip_threshold + abs_bonus),
                    abs(self.lockup_slip_max),
                    abs(min_right_slip)
                )
                lockup_r = severity * self.lockup_gain

        # ═══════════════════════════════════════════════════════
        # 4. DRIFT / OVERSTEER → body slip angle from velocity vector
        # ═══════════════════════════════════════════════════════
        drift_amp = 0.0
        drift_l = 0.0
        drift_r = 0.0

        # In AC: velocity[0] = lateral (X), velocity[2] = longitudinal (Z)
        vx = raw_vel[0]
        vz = raw_vel[2]

        if abs(vz) > 3.0:  # Only compute when moving meaningfully forward
            beta = abs(math.atan2(vx, abs(vz)))
            if beta > self.drift_threshold_rad:
                drift_amp = _smoothstep(
                    self.drift_threshold_rad,
                    self.drift_max_rad,
                    beta
                ) * self.drift_gain

                # Spatial: drift direction
                if vx > 0.0:
                    drift_l = drift_amp * 1.0
                    drift_r = drift_amp * 0.35
                else:
                    drift_r = drift_amp * 1.0
                    drift_l = drift_amp * 0.35

        # ═══════════════════════════════════════════════════════
        # 5. GEAR SHIFT IMPULSE → short spike on gear change
        # ═══════════════════════════════════════════════════════
        gear_shift_amp = 0.0

        if gear != self.prev_gear and self.prev_gear != 0 and gear != 0:
            # Gear just changed — start impulse timer
            self.gearshift_timer = self.gearshift_impulse_duration
        self.prev_gear = gear

        if self.gearshift_timer > 0.0:
            # Linear decay over impulse duration
            gear_shift_amp = (self.gearshift_timer / self.gearshift_impulse_duration) * self.gearshift_gain
            self.gearshift_timer -= dt
            if self.gearshift_timer < 0.0:
                self.gearshift_timer = 0.0

        # ═══════════════════════════════════════════════════════
        # CHANNEL SUMMATION
        # ═══════════════════════════════════════════════════════
        # Each effect contributes to left/right channels.
        # Kerbs and lockup are high-frequency events (150–200 Hz)
        # Drift and FFB are lower-frequency (80–130 Hz)
        # Gear shift is a broadband impulse

        total_left = _clamp(
            ffb_l * 0.50 +          # FFB: moderate constant presence
            kerb_l * 0.90 +         # Kerbs: very noticeable
            lockup_l * 0.85 +       # Lockup: strong pulsation
            drift_l * 0.65 +        # Drift: medium rumble
            gear_shift_amp * 1.0,   # Gear shift: full impulse
            0.0, 1.0
        ) * self.master_gain

        total_right = _clamp(
            ffb_r * 0.50 +
            kerb_r * 0.90 +
            lockup_r * 0.85 +
            drift_r * 0.65 +
            gear_shift_amp * 1.0,
            0.0, 1.0
        ) * self.master_gain

        # ── Determine dominant frequency per channel ──
        # Priority: Kerb (high-freq) > Lockup (mid) > Drift (low) > FFB (mid-low)
        freq_l = 135.0
        freq_r = 135.0

        if kerb_l > 0.15:
            freq_l = 180.0  # Sharp kerb texture
        elif lockup_l > 0.15:
            freq_l = 145.0  # ABS pulse feel
        elif drift_l > 0.15:
            freq_l = 85.0   # Deep chassis rumble
        elif ffb_l > 0.05:
            freq_l = 120.0  # Steering load

        if kerb_r > 0.15:
            freq_r = 180.0
        elif lockup_r > 0.15:
            freq_r = 145.0
        elif drift_r > 0.15:
            freq_r = 85.0
        elif ffb_r > 0.05:
            freq_r = 120.0

        self.last_state = HapticTelemetryState(
            left_amp=total_left,
            right_amp=total_right,
            left_freq=freq_l,
            right_freq=freq_r,
            kerb_l=kerb_l,
            kerb_r=kerb_r,
            lockup_l=lockup_l,
            lockup_r=lockup_r,
            drift=drift_amp,
            ffb=ffb_intensity,
            ffb_l=ffb_l,
            ffb_r=ffb_r,
            gear_shift=gear_shift_amp,
        )
        return self.last_state
