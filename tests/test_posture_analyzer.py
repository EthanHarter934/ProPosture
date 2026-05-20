import unittest

from constants import (
    ALL_MEASUREMENTS,
    DEFAULT_SENSITIVITY_MULTIPLIER,
    MEASURE_NOSE_SHOULDER_VERTICAL_GAP,
    MEASURE_SHOULDER_SCREEN_Y,
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
            nose_shoulder_vertical_gap=0.29,
            shoulder_screen_y=0.56,
        )

        status = PostureAnalyzer.compare_to_baseline(
            measurements,
            _baseline(
                **{
                    MEASURE_NOSE_SHOULDER_VERTICAL_GAP: 0.30,
                    MEASURE_SHOULDER_SCREEN_Y: 0.55,
                }
            ),
            _stds(0.001),
            _multipliers(),
        )

        self.assertEqual(status.overall_status, STATUS_GOOD)

    def test_vertical_measurements_only_penalize_worse_direction(self) -> None:
        measurements = PostureMeasurements(
            nose_shoulder_vertical_gap=0.35,
            shoulder_screen_y=0.54,
        )

        status = PostureAnalyzer.compare_to_baseline(
            measurements,
            _baseline(
                **{
                    MEASURE_NOSE_SHOULDER_VERTICAL_GAP: 0.30,
                    MEASURE_SHOULDER_SCREEN_Y: 0.55,
                }
            ),
            _stds(0.001),
            _multipliers(),
        )

        ratios = {dev.measurement_name: dev.deviation_ratio for dev in status.deviations}
        self.assertEqual(ratios[MEASURE_NOSE_SHOULDER_VERTICAL_GAP], 0.0)
        self.assertEqual(ratios[MEASURE_SHOULDER_SCREEN_Y], 0.0)
        self.assertEqual(status.overall_status, STATUS_GOOD)

    def test_meaningful_head_drop_classifies_as_bad(self) -> None:
        measurements = PostureMeasurements(
            nose_shoulder_vertical_gap=0.23,
            shoulder_screen_y=0.55,
        )

        status = PostureAnalyzer.compare_to_baseline(
            measurements,
            _baseline(
                **{
                    MEASURE_NOSE_SHOULDER_VERTICAL_GAP: 0.30,
                    MEASURE_SHOULDER_SCREEN_Y: 0.55,
                }
            ),
            _stds(0.001),
            _multipliers(),
        )

        self.assertEqual(status.overall_status, STATUS_BAD)
        self.assertEqual(status.worst_measurement, MEASURE_NOSE_SHOULDER_VERTICAL_GAP)

    def test_sensitivity_multiplier_scales_tolerance_floor(self) -> None:
        measurements = PostureMeasurements(
            nose_shoulder_vertical_gap=0.30,
            shoulder_screen_y=0.59,
        )
        baseline = _baseline(
            **{
                MEASURE_NOSE_SHOULDER_VERTICAL_GAP: 0.30,
                MEASURE_SHOULDER_SCREEN_Y: 0.55,
            }
        )

        sensitive = PostureAnalyzer.compare_to_baseline(
            measurements,
            baseline,
            _stds(0.001),
            _multipliers(1.0),
        )
        lenient = PostureAnalyzer.compare_to_baseline(
            measurements,
            baseline,
            _stds(0.001),
            _multipliers(4.0),
        )

        self.assertEqual(sensitive.overall_status, STATUS_BAD)
        self.assertEqual(sensitive.worst_measurement, MEASURE_SHOULDER_SCREEN_Y)
        self.assertEqual(lenient.overall_status, STATUS_GOOD)


if __name__ == "__main__":
    unittest.main()
