import unittest

from constants import (
    ALL_MEASUREMENTS,
    DEFAULT_SENSITIVITY_MULTIPLIER,
    MEASURE_FORWARD_HEAD_RATIO,
    MEASURE_HEAD_TILT_ANGLE,
    MEASURE_NECK_ANGLE,
    MEASURE_SHOULDER_ANGLE,
    STATUS_BAD,
    STATUS_GOOD,
)
from core.posture_analyzer import PostureAnalyzer, PostureMeasurements


def _baseline(**overrides: float) -> dict[str, float]:
    values = {name: 0.0 for name in ALL_MEASUREMENTS}
    values.update(overrides)
    return values


def _stds(value: float) -> dict[str, float]:
    return {name: value for name in ALL_MEASUREMENTS}


def _multipliers(value: float = DEFAULT_SENSITIVITY_MULTIPLIER) -> dict[str, float]:
    return {name: value for name in ALL_MEASUREMENTS}


class PostureAnalyzerTests(unittest.TestCase):
    def test_tiny_calibration_jitter_does_not_make_normal_motion_bad(self) -> None:
        measurements = PostureMeasurements(
            shoulder_angle=1.0,
            forward_head_ratio=0.02,
            head_tilt_angle=1.0,
            neck_angle=1.0,
        )

        status = PostureAnalyzer.compare_to_baseline(
            measurements,
            _baseline(),
            _stds(0.01),
            _multipliers(),
        )

        self.assertEqual(status.overall_status, STATUS_GOOD)

    def test_forward_head_and_neck_only_penalize_worse_direction(self) -> None:
        measurements = PostureMeasurements(
            shoulder_angle=0.0,
            forward_head_ratio=0.05,
            head_tilt_angle=0.0,
            neck_angle=82.0,
        )

        status = PostureAnalyzer.compare_to_baseline(
            measurements,
            _baseline(
                **{
                    MEASURE_FORWARD_HEAD_RATIO: 0.10,
                    MEASURE_NECK_ANGLE: 90.0,
                }
            ),
            _stds(0.01),
            _multipliers(),
        )

        ratios = {dev.measurement_name: dev.deviation_ratio for dev in status.deviations}
        self.assertEqual(ratios[MEASURE_FORWARD_HEAD_RATIO], 0.0)
        self.assertEqual(ratios[MEASURE_NECK_ANGLE], 0.0)
        self.assertEqual(status.overall_status, STATUS_GOOD)

    def test_meaningful_head_tilt_still_classifies_as_bad(self) -> None:
        measurements = PostureMeasurements(
            shoulder_angle=0.0,
            forward_head_ratio=0.0,
            head_tilt_angle=8.5,
            neck_angle=0.0,
        )

        status = PostureAnalyzer.compare_to_baseline(
            measurements,
            _baseline(),
            _stds(0.01),
            _multipliers(),
        )

        self.assertEqual(status.overall_status, STATUS_BAD)
        self.assertEqual(status.worst_measurement, MEASURE_HEAD_TILT_ANGLE)

    def test_sensitivity_multiplier_scales_tolerance_floor(self) -> None:
        measurements = PostureMeasurements(
            shoulder_angle=3.0,
            forward_head_ratio=0.0,
            head_tilt_angle=0.0,
            neck_angle=0.0,
        )

        sensitive = PostureAnalyzer.compare_to_baseline(
            measurements,
            _baseline(),
            _stds(0.01),
            _multipliers(1.0),
        )
        lenient = PostureAnalyzer.compare_to_baseline(
            measurements,
            _baseline(),
            _stds(0.01),
            _multipliers(4.0),
        )

        self.assertEqual(sensitive.overall_status, STATUS_BAD)
        self.assertEqual(sensitive.worst_measurement, MEASURE_SHOULDER_ANGLE)
        self.assertEqual(lenient.overall_status, STATUS_GOOD)


if __name__ == "__main__":
    unittest.main()
