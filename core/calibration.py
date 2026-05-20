"""
Calibration Module

Manages the calibration session: accumulates frames to assess stability,
captures a 90-frame baseline window, computes robust center/jitter values for
each measurement, and evaluates capture quality. This is the heart of
ProPosture — all posture detection is relative to the values produced here.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from constants import (
    ALL_MEASUREMENTS,
    CALIBRATION_CAPTURE_FRAMES,
    CALIBRATION_VARIANCE_LIMITS,
    CALIBRATION_VERSION,
    MEASURE_NOSE_SHOULDER_VERTICAL_GAP,
    MEASURE_SHOULDER_SCREEN_Y,
    STABILITY_WINDOW_FRAMES,
)
from core.posture_analyzer import PostureMeasurements

logger = logging.getLogger(__name__)


@dataclass
class BaselineValues:
    """
    Computed baseline: center and jitter estimate for each measurement.

    Attributes:
        means: Dict of measurement name → robust center value.
        std_devs: Dict of measurement name → robust jitter estimate.
    """

    means: dict[str, float]
    std_devs: dict[str, float]


@dataclass
class QualityReport:
    """
    Quality assessment of a calibration capture.

    Attributes:
        is_acceptable: True if all std devs are within tolerance.
        warnings: List of human-readable warnings for high-variance measurements.
        per_measurement: Dict of measurement name → (mean, std, is_ok).
    """

    is_acceptable: bool
    warnings: list[str]
    per_measurement: dict[str, tuple[float, float, bool]]


@dataclass
class CalibrationResult:
    """
    Full result of a calibration capture.

    Attributes:
        baseline: The computed baseline values.
        quality: Quality assessment of the capture.
        captured_at: ISO timestamp of capture.
        frame_count: Number of frames captured.
    """

    baseline: BaselineValues
    quality: QualityReport
    captured_at: str
    frame_count: int


class CalibrationSession:
    """
    Manages a single calibration session.

    Accumulates posture measurements frame by frame, tracks stability
    over a sliding window, and captures the final baseline when triggered.
    """

    def __init__(self) -> None:
        """Initialize an empty calibration session."""
        self._buffer: deque[dict[str, float]] = deque(
            maxlen=STABILITY_WINDOW_FRAMES * 2
        )
        self._capture_buffer: list[dict[str, float]] = []
        self._is_capturing: bool = False
        logger.info("CalibrationSession initialized")

    def add_frame(self, measurements: PostureMeasurements) -> None:
        """
        Add a single frame's measurements to the session buffer.

        Args:
            measurements: The computed posture measurements for this frame.
        """
        measurement_dict = measurements.to_dict()
        self._buffer.append(measurement_dict)

        if self._is_capturing:
            self._capture_buffer.append(measurement_dict)

    @property
    def is_capturing(self) -> bool:
        """Whether a baseline capture is currently in progress."""
        return self._is_capturing

    @property
    def capture_progress(self) -> float:
        """
        Progress of the current capture as a ratio (0.0 to 1.0).

        Returns:
            0.0 if not capturing, otherwise frames_captured / total_needed.
        """
        if not self._is_capturing:
            return 0.0
        return min(1.0, len(self._capture_buffer) / CALIBRATION_CAPTURE_FRAMES)

    @property
    def capture_complete(self) -> bool:
        """Whether enough frames have been captured for a baseline."""
        return (
            self._is_capturing
            and len(self._capture_buffer) >= CALIBRATION_CAPTURE_FRAMES
        )

    def get_stability_score(self) -> float:
        """
        Compute how stable the user's posture has been over the recent window.

        Uses absolute jitter of each measurement over the last
        STABILITY_WINDOW_FRAMES frames. Lower jitter means more stable.
        The score is inverted and normalized to 0.0–1.0.

        Returns:
            Stability score from 0.0 (unstable) to 1.0 (very stable).
        """
        if len(self._buffer) < STABILITY_WINDOW_FRAMES:
            return 0.0

        recent = list(self._buffer)[-STABILITY_WINDOW_FRAMES:]
        return self._compute_stability(recent)

    @staticmethod
    def _compute_stability(frames: list[dict[str, float]]) -> float:
        """
        Compute stability from a window of measurement frames.

        Uses absolute standard deviation with per-measurement thresholds.
        More lenient than CV-based approach — only requires the user to
        be reasonably still, not perfectly motionless.

        Args:
            frames: List of measurement dictionaries.

        Returns:
            Stability score 0.0–1.0.
        """
        # Per-measurement "acceptable jitter" thresholds.
        # These are generous — even with natural body sway you should pass.
        jitter_thresholds = {
            MEASURE_NOSE_SHOULDER_VERTICAL_GAP: 0.02,
            MEASURE_SHOULDER_SCREEN_Y: 0.02,
        }

        scores: list[float] = []
        for name in ALL_MEASUREMENTS:
            values = np.array([f[name] for f in frames])
            std = float(np.std(values))
            threshold = jitter_thresholds.get(name, 0.02)

            # Score: 1.0 if std < threshold/2, linear drop to 0.0 at 2*threshold
            ratio = std / threshold
            score = max(0.0, min(1.0, 1.0 - ratio))
            scores.append(score)

        return sum(scores) / max(len(scores), 1)

    def start_capture(self) -> None:
        """Begin capturing frames for baseline computation."""
        self._capture_buffer.clear()
        self._is_capturing = True
        logger.info("Baseline capture started")

    def cancel_capture(self) -> None:
        """Cancel an in-progress capture."""
        self._is_capturing = False
        self._capture_buffer.clear()
        logger.info("Baseline capture cancelled")

    def finish_capture(self) -> Optional[CalibrationResult]:
        """
        Finish the capture and compute the baseline.

        Returns:
            CalibrationResult if enough frames were captured, else None.
        """
        self._is_capturing = False

        if len(self._capture_buffer) < CALIBRATION_CAPTURE_FRAMES:
            logger.warning(
                "Capture incomplete: %d/%d frames",
                len(self._capture_buffer),
                CALIBRATION_CAPTURE_FRAMES,
            )
            return None

        # Use exactly the required number of frames
        frames = self._capture_buffer[:CALIBRATION_CAPTURE_FRAMES]
        baseline = self._compute_baseline(frames)
        quality = self._assess_quality(frames, baseline)
        captured_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")

        result = CalibrationResult(
            baseline=baseline,
            quality=quality,
            captured_at=captured_at,
            frame_count=len(frames),
        )

        logger.info("Baseline captured: %d frames, acceptable=%s",
                     len(frames), quality.is_acceptable)
        return result

    @staticmethod
    def _compute_baseline(frames: list[dict[str, float]]) -> BaselineValues:
        """
        Compute robust center and jitter for each measurement across frames.

        Args:
            frames: List of measurement dictionaries.

        Returns:
            BaselineValues with robust center and jitter estimates.
        """
        means: dict[str, float] = {}
        std_devs: dict[str, float] = {}

        for name in ALL_MEASUREMENTS:
            values = np.array([f[name] for f in frames])
            center = float(np.median(values))
            deviations = np.abs(values - center)
            robust_std = float(np.median(deviations) * 1.4826)

            means[name] = center
            std_devs[name] = robust_std

        return BaselineValues(means=means, std_devs=std_devs)

    @staticmethod
    def _assess_quality(
        frames: list[dict[str, float]],
        baseline: BaselineValues,
    ) -> QualityReport:
        """
        Assess the quality of the captured baseline.

        Flags measurements with unusually high std dev, indicating
        the user was moving during capture.

        Args:
            frames: Raw captured measurement frames.
            baseline: Computed baseline values.

        Returns:
            QualityReport with warnings for problematic measurements.
        """
        warnings: list[str] = []
        per_measurement: dict[str, tuple[float, float, bool]] = {}
        reference_distance = max(
            abs(baseline.means.get(MEASURE_NOSE_SHOULDER_VERTICAL_GAP, 0.0)),
            1e-6,
        )

        for name in ALL_MEASUREMENTS:
            mean = baseline.means[name]
            values = np.array([f[name] for f in frames])
            std = float(np.std(values))
            limit = CALIBRATION_VARIANCE_LIMITS.get(name, 0.08) * reference_distance
            is_ok = std < limit

            if not is_ok:
                display = name.replace("_", " ").title()
                warnings.append(
                    f"{display}: high variance detected (std={std:.2f}, "
                    f"limit={limit:.2f}). "
                    f"You may have been moving during capture."
                )

            per_measurement[name] = (mean, std, is_ok)

        return QualityReport(
            is_acceptable=len(warnings) == 0,
            warnings=warnings,
            per_measurement=per_measurement,
        )

    def reset(self) -> None:
        """Reset the session, clearing all buffers."""
        self._buffer.clear()
        self._capture_buffer.clear()
        self._is_capturing = False
        logger.info("CalibrationSession reset")
