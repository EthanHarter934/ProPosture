"""
Calibration Module

Manages the calibration session: accumulates frames to assess stability,
captures a 90-frame baseline window, computes mean/std for each measurement,
and evaluates capture quality. This is the heart of ProPosture — all posture
detection is relative to the values produced here.
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
    CALIBRATION_VERSION,
    HIGH_VARIANCE_THRESHOLD,
    STABILITY_WINDOW_FRAMES,
)
from core.posture_analyzer import PostureMeasurements

logger = logging.getLogger(__name__)


@dataclass
class BaselineValues:
    """
    Computed baseline: mean and standard deviation for each measurement.

    Attributes:
        means: Dict of measurement name → mean value.
        std_devs: Dict of measurement name → standard deviation.
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

        Uses the coefficient of variation (std/mean) of each measurement
        over the last STABILITY_WINDOW_FRAMES frames. A lower CV means
        more stable. The score is inverted and normalized to 0.0–1.0.

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

        Args:
            frames: List of measurement dictionaries.

        Returns:
            Stability score 0.0–1.0.
        """
        total_cv = 0.0
        count = 0

        for name in ALL_MEASUREMENTS:
            values = np.array([f[name] for f in frames])
            std = float(np.std(values))
            mean = float(np.mean(np.abs(values)))

            if mean < 1e-6:
                cv = std  # Use raw std when mean is near zero
            else:
                cv = std / mean

            total_cv += cv
            count += 1

        avg_cv = total_cv / max(count, 1)
        # Map CV to stability: CV=0 → score=1.0, CV≥0.3 → score=0.0
        score = max(0.0, min(1.0, 1.0 - (avg_cv / 0.3)))
        return score

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
        quality = self._assess_quality(baseline)
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
        Compute mean and std dev for each measurement across frames.

        Args:
            frames: List of measurement dictionaries.

        Returns:
            BaselineValues with means and std_devs.
        """
        means: dict[str, float] = {}
        std_devs: dict[str, float] = {}

        for name in ALL_MEASUREMENTS:
            values = np.array([f[name] for f in frames])
            means[name] = float(np.mean(values))
            std_devs[name] = float(np.std(values))

        return BaselineValues(means=means, std_devs=std_devs)

    @staticmethod
    def _assess_quality(baseline: BaselineValues) -> QualityReport:
        """
        Assess the quality of the captured baseline.

        Flags measurements with unusually high std dev, indicating
        the user was moving during capture.

        Args:
            baseline: Computed baseline values.

        Returns:
            QualityReport with warnings for problematic measurements.
        """
        warnings: list[str] = []
        per_measurement: dict[str, tuple[float, float, bool]] = {}

        for name in ALL_MEASUREMENTS:
            mean = baseline.means[name]
            std = baseline.std_devs[name]
            is_ok = std < HIGH_VARIANCE_THRESHOLD

            if not is_ok:
                display = name.replace("_", " ").title()
                warnings.append(
                    f"{display}: high variance detected (std={std:.2f}). "
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
