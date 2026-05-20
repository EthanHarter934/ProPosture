import unittest

from constants import (
    ALL_MEASUREMENTS,
    MEASURE_NOSE_SHOULDER_VERTICAL_GAP,
    MEASURE_SHOULDER_SCREEN_Y,
)
from core.calibration import CalibrationSession


def _frame(**overrides: float) -> dict[str, float]:
    values = {name: 0.0 for name in ALL_MEASUREMENTS}
    values[MEASURE_NOSE_SHOULDER_VERTICAL_GAP] = 0.30
    values[MEASURE_SHOULDER_SCREEN_Y] = 0.55
    values.update(overrides)
    return values


class CalibrationSessionTests(unittest.TestCase):
    def test_baseline_uses_robust_center_not_outlier_sensitive_mean(self) -> None:
        frames = [
            _frame(**{MEASURE_SHOULDER_SCREEN_Y: 0.55})
            for _ in range(9)
        ]
        frames.append(_frame(**{MEASURE_SHOULDER_SCREEN_Y: 0.85}))

        baseline = CalibrationSession._compute_baseline(frames)

        self.assertEqual(baseline.means[MEASURE_SHOULDER_SCREEN_Y], 0.55)

    def test_quality_assessment_uses_measurement_specific_limits(self) -> None:
        frames = [
            _frame(**{MEASURE_SHOULDER_SCREEN_Y: 0.50}),
            _frame(**{MEASURE_SHOULDER_SCREEN_Y: 0.60}),
        ]
        baseline = CalibrationSession._compute_baseline(frames)

        quality = CalibrationSession._assess_quality(frames, baseline)

        self.assertFalse(quality.is_acceptable)
        self.assertFalse(quality.per_measurement[MEASURE_SHOULDER_SCREEN_Y][2])


if __name__ == "__main__":
    unittest.main()
