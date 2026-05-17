"""
Profile Manager Module

Handles loading and saving user calibration profiles and application settings
to JSON files in the user's platform-specific ProPosture data directory. Uses
atomic writes (temp file + rename) for crash safety and provides schema
validation with sensible defaults for missing keys.
"""

import json
import logging
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from constants import (
    ALL_MEASUREMENTS,
    APP_DATA_DIR,
    CALIBRATION_VERSION,
    COACH_STANDARD,
    DEFAULT_ALERT_DELAY_SEC,
    DEFAULT_CAMERA_INDEX,
    DEFAULT_COOLDOWN_SEC,
    DEFAULT_HOTKEY,
    DEFAULT_SENSITIVITY_MULTIPLIER,
    DEFAULT_TTS_VOICE,
    PROFILE_PATH,
    SETTINGS_PATH,
    TTS_VOICE_OPTIONS,
)

logger = logging.getLogger(__name__)


@dataclass
class CalibrationProfile:
    """
    Stored calibration data.

    Attributes:
        calibration_version: Schema version for future migrations.
        captured_at: ISO timestamp of when calibration was captured.
        baseline_means: Dict of measurement name → baseline mean.
        baseline_stds: Dict of measurement name → baseline jitter estimate.
        sensitivity_multipliers: Dict of measurement name → multiplier.
    """

    calibration_version: int = CALIBRATION_VERSION
    captured_at: str = ""
    baseline_means: dict[str, float] = field(default_factory=dict)
    baseline_stds: dict[str, float] = field(default_factory=dict)
    sensitivity_multipliers: dict[str, float] = field(default_factory=dict)


@dataclass
class AppSettings:
    """
    Application settings.

    Attributes:
        coach_personality: Current coach personality key.
        tts_voice: Current gTTS voice/accent key.
        alert_delay_sec: Seconds of bad posture before alert.
        cooldown_sec: Minimum seconds between alerts.
        camera_index: Webcam device index.
        dark_mode: Whether dark mode is enabled.
        launch_at_startup: Whether to launch at OS startup/login.
        show_camera_preview: Whether to show live camera in dashboard.
        hotkey: Global hotkey string for pause/resume.
    """

    coach_personality: str = COACH_STANDARD
    tts_voice: str = DEFAULT_TTS_VOICE
    alert_delay_sec: float = DEFAULT_ALERT_DELAY_SEC
    cooldown_sec: float = DEFAULT_COOLDOWN_SEC
    camera_index: int = DEFAULT_CAMERA_INDEX
    dark_mode: bool = True
    launch_at_startup: bool = False
    show_camera_preview: bool = False
    hotkey: str = DEFAULT_HOTKEY


class ProfileManager:
    """
    Manages loading and saving calibration profiles and app settings.

    Files are stored as JSON in the platform-specific app data directory. All
    writes are atomic (write to temp file, then rename) to prevent corruption.
    """

    def __init__(self) -> None:
        """Initialize the profile manager and ensure directories exist."""
        self._ensure_directories()
        logger.info("ProfileManager initialized at %s", APP_DATA_DIR)

    @staticmethod
    def _ensure_directories() -> None:
        """Create the app data directory structure if it doesn't exist."""
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured directory: %s", APP_DATA_DIR)

    def has_calibration(self) -> bool:
        """
        Check if a calibration profile exists.

        Returns:
            True if a profile file exists and contains valid calibration.
        """
        if not PROFILE_PATH.exists():
            return False

        profile = self.load_profile()
        return profile is not None and len(profile.baseline_means) > 0

    def load_profile(self) -> Optional[CalibrationProfile]:
        """
        Load the calibration profile from disk.

        Returns:
            CalibrationProfile if valid data exists, else None.
        """
        data = self._read_json(PROFILE_PATH)
        if data is None:
            return None

        return self._parse_profile(data)

    @staticmethod
    def _parse_profile(data: dict[str, Any]) -> CalibrationProfile:
        """
        Parse a raw JSON dict into a CalibrationProfile.

        Args:
            data: The raw deserialized JSON dictionary.

        Returns:
            A populated CalibrationProfile with defaults for missing keys.
        """
        baseline = data.get("baseline", {})
        sensitivity = data.get("sensitivity", {})

        means: dict[str, float] = {}
        stds: dict[str, float] = {}
        multipliers: dict[str, float] = {}

        for name in ALL_MEASUREMENTS:
            means[name] = baseline.get(f"{name}_mean", 0.0)
            stds[name] = baseline.get(f"{name}_std", 1.0)
            multipliers[name] = sensitivity.get(
                f"{name}_multiplier", DEFAULT_SENSITIVITY_MULTIPLIER
            )

        return CalibrationProfile(
            calibration_version=data.get("calibration_version", CALIBRATION_VERSION),
            captured_at=data.get("captured_at", ""),
            baseline_means=means,
            baseline_stds=stds,
            sensitivity_multipliers=multipliers,
        )

    def save_profile(self, profile: CalibrationProfile) -> bool:
        """
        Save the calibration profile to disk.

        Args:
            profile: The calibration data to save.

        Returns:
            True if saved successfully.
        """
        data = self._serialize_profile(profile)
        return self._write_json(PROFILE_PATH, data)

    @staticmethod
    def _serialize_profile(profile: CalibrationProfile) -> dict[str, Any]:
        """
        Serialize a CalibrationProfile to a JSON-compatible dict.

        Args:
            profile: The profile to serialize.

        Returns:
            A dictionary matching the expected JSON schema.
        """
        baseline: dict[str, float] = {}
        sensitivity: dict[str, float] = {}

        for name in ALL_MEASUREMENTS:
            baseline[f"{name}_mean"] = profile.baseline_means.get(name, 0.0)
            baseline[f"{name}_std"] = profile.baseline_stds.get(name, 1.0)
            sensitivity[f"{name}_multiplier"] = profile.sensitivity_multipliers.get(
                name, DEFAULT_SENSITIVITY_MULTIPLIER
            )

        return {
            "calibration_version": profile.calibration_version,
            "captured_at": profile.captured_at,
            "baseline": baseline,
            "sensitivity": sensitivity,
        }

    def load_settings(self) -> AppSettings:
        """
        Load application settings from disk.

        Returns:
            AppSettings populated from file, or defaults if file is missing.
        """
        data = self._read_json(SETTINGS_PATH)
        if data is None:
            return AppSettings()

        return self._parse_settings(data)

    @staticmethod
    def _parse_settings(data: dict[str, Any]) -> AppSettings:
        """
        Parse raw JSON into AppSettings with defaults for missing keys.

        Args:
            data: Raw deserialized JSON dictionary.

        Returns:
            Populated AppSettings.
        """
        defaults = AppSettings()
        tts_voice = data.get("tts_voice", defaults.tts_voice)
        if tts_voice not in TTS_VOICE_OPTIONS:
            tts_voice = defaults.tts_voice

        return AppSettings(
            coach_personality=data.get("coach_personality", defaults.coach_personality),
            tts_voice=tts_voice,
            alert_delay_sec=data.get("alert_delay_sec", defaults.alert_delay_sec),
            cooldown_sec=data.get("cooldown_sec", defaults.cooldown_sec),
            camera_index=data.get("camera_index", defaults.camera_index),
            dark_mode=data.get("dark_mode", defaults.dark_mode),
            launch_at_startup=data.get("launch_at_startup", defaults.launch_at_startup),
            show_camera_preview=data.get("show_camera_preview", defaults.show_camera_preview),
            hotkey=data.get("hotkey", defaults.hotkey),
        )

    def save_settings(self, settings: AppSettings) -> bool:
        """
        Save application settings to disk.

        Args:
            settings: The settings to save.

        Returns:
            True if saved successfully.
        """
        data = {
            "coach_personality": settings.coach_personality,
            "tts_voice": settings.tts_voice,
            "alert_delay_sec": settings.alert_delay_sec,
            "cooldown_sec": settings.cooldown_sec,
            "camera_index": settings.camera_index,
            "dark_mode": settings.dark_mode,
            "launch_at_startup": settings.launch_at_startup,
            "show_camera_preview": settings.show_camera_preview,
            "hotkey": settings.hotkey,
        }
        return self._write_json(SETTINGS_PATH, data)

    def delete_calibration(self) -> bool:
        """
        Delete the calibration profile file.

        Returns:
            True if deleted or already absent.
        """
        try:
            if PROFILE_PATH.exists():
                PROFILE_PATH.unlink()
                logger.info("Calibration profile deleted")
            return True
        except Exception:
            logger.exception("Failed to delete calibration profile")
            return False

    @staticmethod
    def _read_json(path: Path) -> Optional[dict[str, Any]]:
        """
        Read and parse a JSON file.

        Args:
            path: Path to the JSON file.

        Returns:
            Parsed dictionary, or None on failure.
        """
        try:
            if not path.exists():
                return None

            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            logger.exception("Failed to read JSON from %s", path)
            return None

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> bool:
        """
        Atomically write data to a JSON file.

        Writes to a temporary file first, then renames to the target path
        to prevent corruption from interrupted writes.

        Args:
            path: Target file path.
            data: Dictionary to serialize.

        Returns:
            True if written successfully.
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_fd, temp_path = tempfile.mkstemp(
                dir=str(path.parent),
                suffix=".tmp",
            )
            temp_file = Path(temp_path)

            try:
                with open(temp_fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                temp_file.replace(path)
                logger.debug("Wrote JSON to %s", path)
                return True
            except Exception:
                temp_file.unlink(missing_ok=True)
                raise
        except Exception:
            logger.exception("Failed to write JSON to %s", path)
            return False
