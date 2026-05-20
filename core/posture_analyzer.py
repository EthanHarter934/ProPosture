"""
Posture Analyzer Module

Pure-math module that computes posture measurements from detected landmarks
and classifies them against a calibrated baseline. Contains no state and no
I/O — only geometry calculations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from constants import (
    ALL_MEASUREMENTS,
    DEFAULT_SENSITIVITY_MULTIPLIER,
    MEASURE_NOSE_SHOULDER_VERTICAL_GAP,
    MEASURE_SHOULDER_SCREEN_Y,
    POSTURE_TOLERANCE_FLOORS,
    STATUS_BAD,
    STATUS_GOOD,
    STATUS_WARNING,
    WARNING_THRESHOLD_RATIO,
)

if TYPE_CHECKING:
    from core.pose_detector import DetectedLandmarks, LandmarkPoint

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PostureMeasurements:
    """
    The computed posture measurements from a single frame.

    Attributes:
        nose_shoulder_vertical_gap: Vertical distance from the nose to the
            shoulder line in normalized screen coordinates. Larger means the
            nose is higher above the shoulders.
        shoulder_screen_y: Shoulder midpoint y in normalized screen
            coordinates. Larger means lower on screen.
    """

    nose_shoulder_vertical_gap: float
    shoulder_screen_y: float

    def to_dict(self) -> dict[str, float]:
        """Convert measurements to a dictionary keyed by measurement names."""
        return {
            MEASURE_NOSE_SHOULDER_VERTICAL_GAP: self.nose_shoulder_vertical_gap,
            MEASURE_SHOULDER_SCREEN_Y: self.shoulder_screen_y,
        }


@dataclass
class MeasurementDeviation:
    """
    Deviation of a single measurement from its baseline.

    Attributes:
        measurement_name: Which measurement this deviation is for.
        current_value: The current frame's value.
        baseline_mean: The calibrated baseline mean.
        baseline_std: The calibrated baseline jitter estimate.
        multiplier: The user's sensitivity multiplier.
        tolerance: The effective allowed deviation before bad posture.
        deviation_ratio: How many "threshold units" the value deviates.
            0.0 = at baseline, 1.0 = at alert threshold.
        raw_delta: Signed current - baseline difference.
        relevant_delta: The portion of raw_delta considered posturally worse.
    """

    measurement_name: str
    current_value: float
    baseline_mean: float
    baseline_std: float
    multiplier: float
    tolerance: float
    deviation_ratio: float
    raw_delta: float
    relevant_delta: float


@dataclass
class PostureStatus:
    """
    Overall posture assessment for a single frame.

    Attributes:
        overall_status: One of STATUS_GOOD, STATUS_WARNING, STATUS_BAD.
        deviations: List of per-measurement deviations.
        worst_measurement: Name of the most-deviated measurement, or None.
    """

    overall_status: str
    deviations: list[MeasurementDeviation]
    worst_measurement: Optional[str]


class PostureAnalyzer:
    """
    Computes posture measurements from landmarks and compares them
    against a calibrated baseline to produce a PostureStatus.
    """

    @staticmethod
    def compute_measurements(landmarks: DetectedLandmarks) -> PostureMeasurements:
        """
        Compute posture measurements from detected landmarks.

        Args:
            landmarks: The five detected landmark positions (normalized 0–1).

        Returns:
            PostureMeasurements containing the vertical posture values.
        """
        nose_shoulder_vertical_gap = PostureAnalyzer._compute_nose_shoulder_vertical_gap(
            landmarks.nose, landmarks.left_shoulder, landmarks.right_shoulder
        )
        shoulder_screen_y = PostureAnalyzer._compute_shoulder_screen_y(
            landmarks.left_shoulder, landmarks.right_shoulder
        )

        return PostureMeasurements(
            nose_shoulder_vertical_gap=nose_shoulder_vertical_gap,
            shoulder_screen_y=shoulder_screen_y,
        )

    @staticmethod
    def compare_to_baseline(
        current: PostureMeasurements,
        baseline: dict[str, float],
        std_devs: dict[str, float],
        multipliers: dict[str, float],
    ) -> PostureStatus:
        """
        Compare current measurements against the calibrated baseline.

        Args:
            current: Current frame's posture measurements.
            baseline: Dict of measurement name → baseline mean.
            std_devs: Dict of measurement name → baseline jitter estimate.
            multipliers: Dict of measurement name → sensitivity multiplier.

        Returns:
            PostureStatus with overall status and per-measurement deviations.
        """
        current_dict = current.to_dict()
        deviations: list[MeasurementDeviation] = []

        for name in ALL_MEASUREMENTS:
            deviation = PostureAnalyzer._compute_deviation(
                name,
                current_dict[name],
                baseline[name],
                std_devs[name],
                multipliers[name],
                baseline,
            )
            deviations.append(deviation)

        return PostureAnalyzer._build_status(deviations)

    @staticmethod
    def _compute_deviation(
        name: str, current: float, mean: float,
        std: float, multiplier: float, baseline: dict[str, float],
    ) -> MeasurementDeviation:
        """
        Compute how far a single measurement deviates from its baseline.

        Args:
            name: Measurement name.
            current: Current frame's value.
            mean: Baseline mean.
            std: Baseline standard deviation or robust jitter estimate.
            multiplier: User's sensitivity multiplier.

        Returns:
            MeasurementDeviation with computed deviation ratio.
        """
        tolerance = PostureAnalyzer._compute_tolerance(name, std, multiplier, baseline)
        raw_delta = current - mean
        relevant_delta = PostureAnalyzer._compute_relevant_delta(name, raw_delta)
        ratio = relevant_delta / tolerance

        return MeasurementDeviation(
            measurement_name=name,
            current_value=current,
            baseline_mean=mean,
            baseline_std=std,
            multiplier=multiplier,
            tolerance=tolerance,
            deviation_ratio=ratio,
            raw_delta=raw_delta,
            relevant_delta=relevant_delta,
        )

    @staticmethod
    def _compute_tolerance(
        name: str,
        std: float,
        multiplier: float,
        baseline: dict[str, float],
    ) -> float:
        """
        Compute the effective deviation tolerance for a measurement.

        Tolerance floors are percentages of the calibrated vertical distance
        between the nose and the shoulder line. This keeps classification
        person- and camera-relative while still preserving the user's
        sensitivity control.

        Args:
            name: Measurement name.
            std: Calibrated standard deviation or robust jitter estimate.
            multiplier: User's sensitivity multiplier.

        Returns:
            Effective tolerance in the measurement's native units.
        """
        sensitivity_scale = multiplier / DEFAULT_SENSITIVITY_MULTIPLIER
        reference_distance = max(
            abs(baseline.get(MEASURE_NOSE_SHOULDER_VERTICAL_GAP, 0.0)),
            1e-6,
        )
        floor = (
            POSTURE_TOLERANCE_FLOORS.get(name, 0.1)
            * reference_distance
            * sensitivity_scale
        )
        std_based = max(0.0, std) * multiplier
        return max(floor, std_based, 1e-6)

    @staticmethod
    def _compute_relevant_delta(name: str, raw_delta: float) -> float:
        """
        Return only the part of a measurement change that indicates worse posture.

        The head is bad when the calibrated nose-to-shoulder vertical gap
        shrinks, which means the nose dropped toward the shoulder line.
        Shoulders are bad when their screen y increases, which means they are
        lower than the calibrated position.

        Args:
            name: Measurement name.
            raw_delta: current - baseline value.

        Returns:
            Non-negative deviation to compare against tolerance.
        """
        if name == MEASURE_NOSE_SHOULDER_VERTICAL_GAP:
            return max(0.0, -raw_delta)
        if name == MEASURE_SHOULDER_SCREEN_Y:
            return max(0.0, raw_delta)
        return abs(raw_delta)

    @staticmethod
    def _build_status(deviations: list[MeasurementDeviation]) -> PostureStatus:
        """
        Determine overall status from individual measurement deviations.

        Args:
            deviations: List of per-measurement deviations.

        Returns:
            PostureStatus with the worst overall status.
        """
        worst_ratio = 0.0
        worst_name: Optional[str] = None

        for dev in deviations:
            if dev.deviation_ratio > worst_ratio:
                worst_ratio = dev.deviation_ratio
                worst_name = dev.measurement_name

        if worst_ratio >= 1.0:
            overall = STATUS_BAD
        elif worst_ratio >= WARNING_THRESHOLD_RATIO:
            overall = STATUS_WARNING
        else:
            overall = STATUS_GOOD

        return PostureStatus(
            overall_status=overall,
            deviations=deviations,
            worst_measurement=worst_name if worst_ratio >= WARNING_THRESHOLD_RATIO else None,
        )

    @staticmethod
    def _compute_nose_shoulder_vertical_gap(
        nose: LandmarkPoint, left_s: LandmarkPoint, right_s: LandmarkPoint
    ) -> float:
        """
        Compute vertical distance from the nose to the shoulder line.

        Args:
            nose: Nose landmark.
            left_s: Left shoulder landmark.
            right_s: Right shoulder landmark.

        Returns:
            Normalized screen distance. Higher = nose higher above shoulders.
        """
        shoulder_y = PostureAnalyzer._compute_shoulder_screen_y(left_s, right_s)
        return shoulder_y - nose.y

    @staticmethod
    def _compute_shoulder_screen_y(
        left_s: LandmarkPoint, right_s: LandmarkPoint
    ) -> float:
        """
        Compute the average shoulder height in normalized screen coordinates.

        Args:
            left_s: Left shoulder landmark.
            right_s: Right shoulder landmark.

        Returns:
            Normalized screen y. Higher value = lower on screen.
        """
        return (left_s.y + right_s.y) / 2.0
