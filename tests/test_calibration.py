import unittest

from constants import (
    ALL_MEASUREMENTS,
    MEASURE_HEAD_TILT_ANGLE,
    MEASURE_SHOULDER_ANGLE,
)
from core.calibration import CalibrationSession


def _frame(**overrides: float) -> dict[str, float]:
    values = {name: 0.0 for name in ALL_MEASUREMENTS}
    values.update(overrides)
    return values


class CalibrationSessionTests(unittest.TestCase):
    def test_baseline_uses_robust_center_not_outlier_sensitive_mean(self) -> None:
        frames = [
            _frame(**{MEASURE_SHOULDER_ANGLE: 2.0})
            for _ in range(9)
        ]
        frames.append(_frame(**{MEASURE_SHOULDER_ANGLE: 50.0}))

        baseline = CalibrationSession._compute_baseline(frames)

        self.assertEqual(baseline.means[MEASURE_SHOULDER_ANGLE], 2.0)

    def test_quality_assessment_uses_measurement_specific_limits(self) -> None:
        frames = [
            _frame(**{MEASURE_HEAD_TILT_ANGLE: -10.0}),
            _frame(**{MEASURE_HEAD_TILT_ANGLE: 10.0}),
        ]
        baseline = CalibrationSession._compute_baseline(frames)

        quality = CalibrationSession._assess_quality(frames, baseline)

        self.assertFalse(quality.is_acceptable)
        self.assertFalse(quality.per_measurement[MEASURE_HEAD_TILT_ANGLE][2])


if __name__ == "__main__":
    unittest.main()
