"""
=============================================================================
EXPERIMENTAL MODULE: Steering Resistance Simulation via DualSense Vibration
=============================================================================
Notice: This module is experimental and is intentionally NOT hooked into the
main telemetry loop until verified in hands-on testing.

Concept:
Simulates mechanical steering resistance / tire grip for gyroscope steering by
modulating dense vibration (130-150 Hz) non-linearly:
1. Center Softening: Cubic curve at low angles eliminates nervous tremor on straights.
2. Pacejka Saturation: Progressive buildup matching lateral tire load in corners.
3. Understeer Drop-off: When front tires scrub beyond optimum slip, resistance
   drops by ~45%, communicating front-end grip loss.
4. Spatial Weighting: Weight shifts to the loaded outside hand in turns.
=============================================================================
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
        Calculates tactile resistance forces.
        Returns:
            (left_resistance, right_resistance, grip_factor)
            where resistances are in range [0.0, 1.0].
        """
        if speed_kmh < self.min_speed_kmh:
            return 0.0, 0.0, 1.0

        # 1. Base FFB signal
        raw_ff = abs(float(final_ff))

        # 2. Smooth Center Curve (Cubic Smoothstep)
        if raw_ff <= self.deadzone:
            ff_soft = 0.0
        else:
            x = min(1.0, (raw_ff - self.deadzone) / (1.0 - self.deadzone))
            ff_soft = x * x * (3.0 - 2.0 * x)

        # 3. Saturation Curve (Tire grip buildup via tanh)
        ff_sat = math.tanh(ff_soft * self.saturation_gain)

        # 4. Understeer Detection & Grip Drop-off
        f_slips = front_slips if len(front_slips) >= 2 else [0.0, 0.0]
        avg_front_slip = (abs(f_slips[0]) + abs(f_slips[1])) * 0.5

        if avg_front_slip <= self.optimal_slip:
            grip_factor = 1.0
        else:
            slip_ratio = min(1.0, (avg_front_slip - self.optimal_slip) / (self.max_slip - self.optimal_slip))
            grip_factor = 1.0 - (slip_ratio * self.understeer_drop)

        total_resistance = ff_sat * grip_factor

        # 5. Spatial Weighting (outside hand takes load)
        # steer_norm > 0: Turning Right -> Left hand loaded
        # steer_norm < 0: Turning Left  -> Right hand loaded
        bias = max(-1.0, min(1.0, float(steer_norm)))
        if bias >= 0:
            left_weight = total_resistance
            right_weight = total_resistance * (0.30 + 0.70 * (1.0 - bias))
        else:
            right_weight = total_resistance
            left_weight = total_resistance * (0.30 + 0.70 * (1.0 + bias))

        return left_weight, right_weight, grip_factor
