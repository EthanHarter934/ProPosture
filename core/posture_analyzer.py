"""
Posture Analyzer Module

Pure-math module that computes the four posture measurements from detected
landmarks and compares them against a calibrated baseline. Contains no state
and no I/O — only geometry calculations.
"""

import logging
import math
from dataclasses import dataclass
from typing import Optional

from constants import (
    ALL_MEASUREMENTS,
    MEASURE_FORWARD_HEAD_RATIO,
    MEASURE_HEAD_TILT_ANGLE,
    MEASURE_NECK_ANGLE,
    MEASURE_SHOULDER_ANGLE,
    STATUS_BAD,
    STATUS_GOOD,
    STATUS_WARNING,
    WARNING_THRESHOLD_RATIO,
)
from core.pose_detector import DetectedLandmarks, LandmarkPoint

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PostureMeasurements:
    """
    The four computed posture measurements from a single frame.

    Attributes:
        shoulder_angle: Angle of shoulder line vs horizontal (degrees).
        forward_head_ratio: Horizontal nose offset / shoulder width (unitless).
        head_tilt_angle: Angle of ear line vs horizontal (degrees).
        neck_angle: Angle at nose in shoulder-nose triangle (degrees).
    """

    shoulder_angle: float
    forward_head_ratio: float
    head_tilt_angle: float
    neck_angle: float

    def to_dict(self) -> dict[str, float]:
        """Convert measurements to a dictionary keyed by measurement names."""
        return {
            MEASURE_SHOULDER_ANGLE: self.shoulder_angle,
            MEASURE_FORWARD_HEAD_RATIO: self.forward_head_ratio,
            MEASURE_HEAD_TILT_ANGLE: self.head_tilt_angle,
            MEASURE_NECK_ANGLE: self.neck_angle,
        }


@dataclass
class MeasurementDeviation:
    """
    Deviation of a single measurement from its baseline.

    Attributes:
        measurement_name: Which measurement this deviation is for.
        current_value: The current frame's value.
        baseline_mean: The calibrated baseline mean.
        baseline_std: The calibrated baseline std dev.
        multiplier: The user's sensitivity multiplier.
        deviation_ratio: How many "threshold units" the value deviates.
            0.0 = at baseline, 1.0 = at alert threshold.
    """

    measurement_name: str
    current_value: float
    baseline_mean: float
    baseline_std: float
    multiplier: float
    deviation_ratio: float


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
        Compute all four posture measurements from detected landmarks.

        Args:
            landmarks: The five detected landmark positions (normalized 0–1).

        Returns:
            PostureMeasurements containing all four values.
        """
        shoulder_angle = PostureAnalyzer._compute_shoulder_angle(
            landmarks.left_shoulder, landmarks.right_shoulder
        )
        forward_head_ratio = PostureAnalyzer._compute_forward_head_ratio(
            landmarks.nose, landmarks.left_shoulder, landmarks.right_shoulder
        )
        head_tilt_angle = PostureAnalyzer._compute_head_tilt_angle(
            landmarks.left_ear, landmarks.right_ear
        )
        neck_angle = PostureAnalyzer._compute_neck_angle(
            landmarks.nose, landmarks.left_shoulder, landmarks.right_shoulder
        )

        return PostureMeasurements(
            shoulder_angle=shoulder_angle,
            forward_head_ratio=forward_head_ratio,
            head_tilt_angle=head_tilt_angle,
            neck_angle=neck_angle,
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
            std_devs: Dict of measurement name → baseline std dev.
            multipliers: Dict of measurement name → sensitivity multiplier.

        Returns:
            PostureStatus with overall status and per-measurement deviations.
        """
        current_dict = current.to_dict()
        deviations: list[MeasurementDeviation] = []

        for name in ALL_MEASUREMENTS:
            deviation = PostureAnalyzer._compute_deviation(
                name, current_dict[name], baseline[name],
                std_devs[name], multipliers[name],
            )
            deviations.append(deviation)

        return PostureAnalyzer._build_status(deviations)

    @staticmethod
    def _compute_deviation(
        name: str, current: float, mean: float,
        std: float, multiplier: float,
    ) -> MeasurementDeviation:
        """
        Compute how far a single measurement deviates from its baseline.

        Args:
            name: Measurement name.
            current: Current frame's value.
            mean: Baseline mean.
            std: Baseline standard deviation.
            multiplier: User's sensitivity multiplier.

        Returns:
            MeasurementDeviation with computed deviation ratio.
        """
        threshold = std * multiplier
        if threshold < 1e-6:
            threshold = 1e-6  # Avoid division by zero

        absolute_deviation = abs(current - mean)
        ratio = absolute_deviation / threshold

        return MeasurementDeviation(
            measurement_name=name,
            current_value=current,
            baseline_mean=mean,
            baseline_std=std,
            multiplier=multiplier,
            deviation_ratio=ratio,
        )

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
    def _compute_shoulder_angle(
        left: LandmarkPoint, right: LandmarkPoint
    ) -> float:
        """
        Compute the angle of the shoulder line relative to horizontal.

        A perfectly level pair of shoulders yields 0 degrees.

        Args:
            left: Left shoulder landmark.
            right: Right shoulder landmark.

        Returns:
            Angle in degrees (positive = left shoulder higher).
        """
        dx = right.x - left.x
        dy = right.y - left.y
        return math.degrees(math.atan2(dy, dx))

    @staticmethod
    def _compute_forward_head_ratio(
        nose: LandmarkPoint, left_s: LandmarkPoint, right_s: LandmarkPoint
    ) -> float:
        """
        Compute the forward head ratio (scale-independent).

        Measures how far the nose is horizontally offset from the midpoint
        of both shoulders, normalized by shoulder width.

        Args:
            nose: Nose landmark.
            left_s: Left shoulder landmark.
            right_s: Right shoulder landmark.

        Returns:
            Ratio (unitless). Higher = head further forward / to one side.
        """
        mid_x = (left_s.x + right_s.x) / 2.0
        shoulder_width = PostureAnalyzer._distance_2d(left_s, right_s)

        if shoulder_width < 1e-6:
            return 0.0

        horizontal_offset = abs(nose.x - mid_x)
        return horizontal_offset / shoulder_width

    @staticmethod
    def _compute_head_tilt_angle(
        left_ear: LandmarkPoint, right_ear: LandmarkPoint
    ) -> float:
        """
        Compute the head tilt angle from the ear line vs horizontal.

        Args:
            left_ear: Left ear landmark.
            right_ear: Right ear landmark.

        Returns:
            Angle in degrees (positive = left ear higher).
        """
        dx = right_ear.x - left_ear.x
        dy = right_ear.y - left_ear.y
        return math.degrees(math.atan2(dy, dx))

    @staticmethod
    def _compute_neck_angle(
        nose: LandmarkPoint, left_s: LandmarkPoint, right_s: LandmarkPoint
    ) -> float:
        """
        Compute the neck angle: angle at the nose in the triangle
        formed by left_shoulder, nose, right_shoulder.

        A wider angle indicates the head is closer to the shoulder line
        (more forward flexion).

        Args:
            nose: Nose landmark.
            left_s: Left shoulder landmark.
            right_s: Right shoulder landmark.

        Returns:
            Angle in degrees at the nose vertex.
        """
        vec_to_left = (left_s.x - nose.x, left_s.y - nose.y)
        vec_to_right = (right_s.x - nose.x, right_s.y - nose.y)

        dot = vec_to_left[0] * vec_to_right[0] + vec_to_left[1] * vec_to_right[1]
        mag_left = math.sqrt(vec_to_left[0] ** 2 + vec_to_left[1] ** 2)
        mag_right = math.sqrt(vec_to_right[0] ** 2 + vec_to_right[1] ** 2)

        if mag_left < 1e-6 or mag_right < 1e-6:
            return 0.0

        cos_angle = max(-1.0, min(1.0, dot / (mag_left * mag_right)))
        return math.degrees(math.acos(cos_angle))

    @staticmethod
    def _distance_2d(p1: LandmarkPoint, p2: LandmarkPoint) -> float:
        """
        Compute 2D Euclidean distance between two landmarks.

        Args:
            p1: First landmark point.
            p2: Second landmark point.

        Returns:
            Distance in normalized coordinate space.
        """
        return math.sqrt((p2.x - p1.x) ** 2 + (p2.y - p1.y) ** 2)
