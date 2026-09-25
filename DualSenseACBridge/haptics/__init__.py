"""
Spatial Haptic Feedback and Telemetry Math Package for DualSense AC Bridge.
"""

from .telemetry_math import HapticTelemetryProcessor, HapticTelemetryState
from .audio_engine import HapticAudioEngine

__all__ = [
    "HapticTelemetryProcessor",
    "HapticTelemetryState",
    "HapticAudioEngine",
]
