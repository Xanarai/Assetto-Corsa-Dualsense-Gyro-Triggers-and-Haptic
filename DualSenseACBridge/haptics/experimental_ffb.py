"""
Experimental steering resistance model using voice-coil haptics (130-150 Hz).

Modulates high-frequency resistance based on lateral tire load:
- Deadzone smoothing (smoothstep) around center.
- Tanh saturation modeling tire grip buildup.
- Front slip angle monitoring with drop-off on understeer to emulate grip loss.
- Asymmetric weighting toward the outside hand in cornering.
"""

import math
from typing import Tuple, List


class ExperimentalFFBResistanceModel:
    def __init__(self):
        self.deadzone: float = 0.04
        self.saturation_gain: float = 1.85
        self.optimal_slip: float = 0.13
        self.max_slip: float = 0.38
        self.understeer_drop: float = 0.45
        self.min_speed_kmh: float = 4.0

    def compute(
        self,
        final_ff: float,
        steer_norm: float,
        front_slips: List[float],
        speed_kmh: float = 50.0
    ) -> Tuple[float, float, float]:
        """
        Compute tactile resistance forces for left and right channels.

        Returns:
            Tuple of (left_resistance, right_resistance, grip_factor) in range [0.0, 1.0].
        """
        if speed_kmh < self.min_speed_kmh:
            return 0.0, 0.0, 1.0

        raw_ff = abs(float(final_ff))

        # Smoothstep deadzone transition
        if raw_ff <= self.deadzone:
            ff_soft = 0.0
        else:
            x = min(1.0, (raw_ff - self.deadzone) / (1.0 - self.deadzone))
            ff_soft = x * x * (3.0 - 2.0 * x)

        # Tanh saturation for progressive tire load buildup
        ff_sat = math.tanh(ff_soft * self.saturation_gain)

        # Attenuate resistance when slip exceeds optimal angle (understeer grip loss)
        f_slips = front_slips if len(front_slips) >= 2 else [0.0, 0.0]
        avg_front_slip = (abs(f_slips[0]) + abs(f_slips[1])) * 0.5

        if avg_front_slip <= self.optimal_slip:
            grip_factor = 1.0
        else:
            slip_ratio = min(1.0, (avg_front_slip - self.optimal_slip) / (self.max_slip - self.optimal_slip))
            grip_factor = 1.0 - (slip_ratio * self.understeer_drop)

        total_resistance = ff_sat * grip_factor

        # Bias resistance toward outside hand (steer > 0 is turning right, loading left hand)
        bias = max(-1.0, min(1.0, float(steer_norm)))
        if bias >= 0:
            left_weight = total_resistance
            right_weight = total_resistance * (0.30 + 0.70 * (1.0 - bias))
        else:
            right_weight = total_resistance
            left_weight = total_resistance * (0.30 + 0.70 * (1.0 + bias))

        return left_weight, right_weight, grip_factor
