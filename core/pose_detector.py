"""
Pose Detector Module

Wraps MediaPipe Pose to extract the specific landmarks needed for posture
analysis. Handles frame preprocessing, landmark extraction with visibility
filtering, and provides a drawing helper for UI overlay rendering.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np
import time
from pathlib import Path
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from constants import (
    LANDMARK_LEFT_EAR,
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_NOSE,
    LANDMARK_RIGHT_EAR,
    LANDMARK_RIGHT_SHOULDER,
    MIN_LANDMARK_VISIBILITY,
    POSE_MIN_DETECTION_CONFIDENCE,
    POSE_MIN_TRACKING_CONFIDENCE,
    POSE_MODEL_COMPLEXITY,
    REQUIRED_LANDMARKS,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LandmarkPoint:
    """A single detected landmark with 2D coordinates and visibility score."""

    x: float
    y: float
    visibility: float


@dataclass(frozen=True)
class DetectedLandmarks:
    """Container for all posture-relevant landmarks from a single frame."""

    nose: LandmarkPoint
    left_ear: LandmarkPoint
    right_ear: LandmarkPoint
    left_shoulder: LandmarkPoint
    right_shoulder: LandmarkPoint


class PoseDetector:
    """
    Detects human pose landmarks in video frames using MediaPipe Pose.

    Extracts only the five landmarks relevant to seated posture analysis:
    nose, left/right ears, and left/right shoulders. Filters out frames
    where any required landmark has insufficient visibility.
    """

    def __init__(self) -> None:
        """Initialize MediaPipe Pose with configured parameters."""
        model_path = str(Path(__file__).parent.parent / "assets" / "pose_landmarker_lite.task")
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            min_pose_detection_confidence=POSE_MIN_DETECTION_CONFIDENCE,
            min_pose_presence_confidence=POSE_MIN_TRACKING_CONFIDENCE,
            min_tracking_confidence=POSE_MIN_TRACKING_CONFIDENCE,
            num_poses=1,
        )
        self._pose = vision.PoseLandmarker.create_from_options(options)
        logger.info("PoseDetector initialized with tasks API")

    def detect(self, frame: np.ndarray) -> Optional[DetectedLandmarks]:
        """
        Process a BGR frame and extract posture-relevant landmarks.

        Args:
            frame: A BGR image (numpy array) from the webcam.

        Returns:
            DetectedLandmarks if all required landmarks have sufficient
            visibility, otherwise None.
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        timestamp_ms = time.time_ns() // 1_000_000
        results = self._pose.detect_for_video(mp_image, timestamp_ms)

        if not results.pose_landmarks:
            return None

        return self._extract_landmarks(results.pose_landmarks[0])

    def _extract_landmarks(
        self, landmarks: list
    ) -> Optional[DetectedLandmarks]:
        """
        Extract and validate the five required landmarks.

        Args:
            landmarks: Full list of MediaPipe pose landmarks.

        Returns:
            DetectedLandmarks if all pass visibility threshold, else None.
        """
        if not self._check_visibility(landmarks):
            return None

        return DetectedLandmarks(
            nose=self._to_point(landmarks[LANDMARK_NOSE]),
            left_ear=self._to_point(landmarks[LANDMARK_LEFT_EAR]),
            right_ear=self._to_point(landmarks[LANDMARK_RIGHT_EAR]),
            left_shoulder=self._to_point(landmarks[LANDMARK_LEFT_SHOULDER]),
            right_shoulder=self._to_point(landmarks[LANDMARK_RIGHT_SHOULDER]),
        )

    def _check_visibility(self, landmarks: list) -> bool:
        """
        Verify all required landmarks exceed the visibility threshold.

        Args:
            landmarks: Full list of MediaPipe pose landmarks.

        Returns:
            True if all required landmarks are sufficiently visible.
        """
        for idx in REQUIRED_LANDMARKS:
            if landmarks[idx].visibility < MIN_LANDMARK_VISIBILITY:
                return False
        return True

    @staticmethod
    def _to_point(landmark) -> LandmarkPoint:
        """
        Convert a MediaPipe landmark to a LandmarkPoint dataclass.

        Args:
            landmark: A MediaPipe NormalizedLandmark.

        Returns:
            LandmarkPoint with x, y, and visibility.
        """
        return LandmarkPoint(
            x=landmark.x,
            y=landmark.y,
            visibility=landmark.visibility,
        )

    def draw_landmarks(
        self, frame: np.ndarray, landmarks: DetectedLandmarks
    ) -> np.ndarray:
        """
        Draw posture-relevant landmarks and connection lines on the frame.

        Draws circles at each landmark position and lines connecting
        shoulders, ears, and nose-to-shoulder-midpoint.

        Args:
            frame: BGR image to draw on (will be modified in place).
            landmarks: The detected landmark positions.

        Returns:
            The frame with landmarks drawn on it.
        """
        h, w = frame.shape[:2]
        points = self._landmarks_to_pixel_coords(landmarks, w, h)

        self._draw_landmark_circles(frame, points)
        self._draw_connection_lines(frame, points)

        return frame

    def _landmarks_to_pixel_coords(
        self, landmarks: DetectedLandmarks, w: int, h: int
    ) -> dict[str, tuple[int, int]]:
        """
        Convert normalized landmark coordinates to pixel coordinates.

        Args:
            landmarks: Normalized landmark positions.
            w: Frame width in pixels.
            h: Frame height in pixels.

        Returns:
            Dictionary mapping landmark names to (x, y) pixel tuples.
        """
        return {
            "nose": (int(landmarks.nose.x * w), int(landmarks.nose.y * h)),
            "left_ear": (int(landmarks.left_ear.x * w), int(landmarks.left_ear.y * h)),
            "right_ear": (int(landmarks.right_ear.x * w), int(landmarks.right_ear.y * h)),
            "left_shoulder": (int(landmarks.left_shoulder.x * w), int(landmarks.left_shoulder.y * h)),
            "right_shoulder": (int(landmarks.right_shoulder.x * w), int(landmarks.right_shoulder.y * h)),
        }

    @staticmethod
    def _draw_landmark_circles(
        frame: np.ndarray, points: dict[str, tuple[int, int]]
    ) -> None:
        """
        Draw filled circles at each landmark position.

        Args:
            frame: BGR image to draw on.
            points: Mapping of landmark names to pixel coordinates.
        """
        colors = {
            "nose": (0, 255, 255),
            "left_ear": (255, 200, 0),
            "right_ear": (255, 200, 0),
            "left_shoulder": (0, 255, 0),
            "right_shoulder": (0, 255, 0),
        }
        for name, pt in points.items():
            cv2.circle(frame, pt, 6, colors[name], -1)
            cv2.circle(frame, pt, 8, (255, 255, 255), 1)

    @staticmethod
    def _draw_connection_lines(
        frame: np.ndarray, points: dict[str, tuple[int, int]]
    ) -> None:
        """
        Draw connection lines between landmarks for visual feedback.

        Draws: shoulder line, ear line, and nose-to-shoulder-midpoint line.

        Args:
            frame: BGR image to draw on.
            points: Mapping of landmark names to pixel coordinates.
        """
        # Shoulder line
        cv2.line(frame, points["left_shoulder"], points["right_shoulder"], (0, 255, 0), 2)
        # Ear line
        cv2.line(frame, points["left_ear"], points["right_ear"], (255, 200, 0), 2)
        # Nose to shoulder midpoint
        mid_x = (points["left_shoulder"][0] + points["right_shoulder"][0]) // 2
        mid_y = (points["left_shoulder"][1] + points["right_shoulder"][1]) // 2
        cv2.line(frame, points["nose"], (mid_x, mid_y), (0, 255, 255), 2)

    def close(self) -> None:
        """Release MediaPipe resources."""
        self._pose.close()
        logger.info("PoseDetector resources released")
