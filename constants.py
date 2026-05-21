"""
ProPosture Constants Module

Central repository for all application constants, default values, file paths,
coach personality dialogue lines, and MediaPipe landmark indices. No other
module should contain hardcoded values — import them from here.
"""

import os
import sys
from pathlib import Path

# ═══════════════════════════════════════════════
# APPLICATION METADATA
# ═══════════════════════════════════════════════

APP_NAME: str = "ProPosture"
APP_VERSION: str = "1.0.0"

# ═══════════════════════════════════════════════
# FILE PATHS
# ═══════════════════════════════════════════════

def _get_app_data_dir() -> Path:
    """Return the platform-appropriate writable application data directory."""
    if sys.platform == "win32":
        base_dir = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base_dir:
            return Path(base_dir) / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_NAME

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    base_dir = os.environ.get("XDG_DATA_HOME")
    if base_dir:
        return Path(base_dir) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def _get_resource_dir() -> Path:
    """Return source root in development or PyInstaller's extraction dir."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


APP_DATA_DIR: Path = _get_app_data_dir()
LOG_DIR: Path = APP_DATA_DIR / "logs"
PROFILE_PATH: Path = APP_DATA_DIR / "profile.json"
SETTINGS_PATH: Path = APP_DATA_DIR / "settings.json"
TTS_CACHE_DIR: Path = APP_DATA_DIR / "tts_cache"
RESOURCE_DIR: Path = _get_resource_dir()
ASSETS_DIR: Path = RESOURCE_DIR / "assets"
ICON_PATH: Path = ASSETS_DIR / "icon.png"
POSE_LANDMARKER_MODEL_PATH: Path = ASSETS_DIR / "pose_landmarker_lite.task"

# ═══════════════════════════════════════════════
# LOG RETENTION
# ═══════════════════════════════════════════════

LOG_RETENTION_DAYS: int = 7

# ═══════════════════════════════════════════════
# MEDIAPIPE LANDMARK INDICES
# (from mediapipe.solutions.pose.PoseLandmark)
# ═══════════════════════════════════════════════

LANDMARK_NOSE: int = 0
LANDMARK_LEFT_EAR: int = 7
LANDMARK_RIGHT_EAR: int = 8
LANDMARK_LEFT_SHOULDER: int = 11
LANDMARK_RIGHT_SHOULDER: int = 12

REQUIRED_LANDMARKS: list[int] = [
    LANDMARK_NOSE,
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_RIGHT_SHOULDER,
]

# ═══════════════════════════════════════════════
# VISIBILITY & DETECTION
# ═══════════════════════════════════════════════

MIN_LANDMARK_VISIBILITY: float = 0.6
POSE_MIN_DETECTION_CONFIDENCE: float = 0.5
POSE_MIN_TRACKING_CONFIDENCE: float = 0.5

# ═══════════════════════════════════════════════
# CAMERA
# ═══════════════════════════════════════════════

DEFAULT_CAMERA_INDEX: int = 0
CAMERA_FRAME_WIDTH: int = 640
CAMERA_FRAME_HEIGHT: int = 480
TARGET_FPS: int = 30

# ═══════════════════════════════════════════════
# CALIBRATION
# ═══════════════════════════════════════════════

CALIBRATION_VERSION: int = 3
CALIBRATION_CAPTURE_FRAMES: int = 90  # 3 seconds at 30 fps
STABILITY_WINDOW_FRAMES: int = 30  # 1 second of frames for stability check
STABILITY_THRESHOLD: float = 0.55  # 0.0–1.0 to consider user "stable"

# ═══════════════════════════════════════════════
# SENSITIVITY DEFAULTS (std dev multipliers)
# ═══════════════════════════════════════════════

DEFAULT_SENSITIVITY_MULTIPLIER: float = 2.0
MIN_SENSITIVITY_MULTIPLIER: float = 1.0
MAX_SENSITIVITY_MULTIPLIER: float = 4.0

# ═══════════════════════════════════════════════
# ALERT ENGINE
# ═══════════════════════════════════════════════

DEFAULT_ALERT_DELAY_SEC: float = 10.0  # Bad posture must persist this long
MIN_ALERT_DELAY_SEC: float = 5.0
MAX_ALERT_DELAY_SEC: float = 60.0

DEFAULT_COOLDOWN_SEC: float = 60.0  # Minimum gap between alerts
MIN_COOLDOWN_SEC: float = 15.0
MAX_COOLDOWN_SEC: float = 300.0

# ═══════════════════════════════════════════════
# SNOOZE
# ═══════════════════════════════════════════════

SNOOZE_DURATION_SEC: float = 15 * 60  # 15 minutes

# ═══════════════════════════════════════════════
# GLOBAL HOTKEY
# ═══════════════════════════════════════════════

DEFAULT_HOTKEY: str = "ctrl+shift+p"

# ═══════════════════════════════════════════════
# TTS / VOICE
# ═══════════════════════════════════════════════

STANDARD_SPEECH_RATE: int = 175  # words per minute
STANDARD_VOLUME: float = 0.9

COACH_STANDARD: str = "standard"
COACH_LABELS: dict[str, str] = {
    COACH_STANDARD: "Standard",
}

# ── Voice Mode ──────────────────────────────────
# "standard" = gTTS voices, "custom" = VoxCPM2 server with user description
VOICE_MODE_STANDARD: str = "standard"
VOICE_MODE_CUSTOM: str = "custom"
VOICE_MODE_LABELS: dict[str, str] = {
    VOICE_MODE_STANDARD: "Standard TTS",
    VOICE_MODE_CUSTOM: "Custom Voice (VoxCPM2)",
}
DEFAULT_VOICE_MODE: str = VOICE_MODE_STANDARD

DEFAULT_TTS_VOICE: str = "us"
DEFAULT_VOLUME: float = 1.0
TTS_VOICE_OPTIONS: dict[str, dict[str, str]] = {
    "us": {"label": "US English", "lang": "en", "tld": "com"},
    "uk": {"label": "UK English", "lang": "en", "tld": "co.uk"},
    "australia": {"label": "Australian English", "lang": "en", "tld": "com.au"},
    "canada": {"label": "Canadian English", "lang": "en", "tld": "ca"},
    "india": {"label": "Indian English", "lang": "en", "tld": "co.in"},
}
TTS_VOICE_LABELS: dict[str, str] = {
    key: config["label"] for key, config in TTS_VOICE_OPTIONS.items()
}

# ── VoxCPM2 Voice Server ────────────────────────
DEFAULT_VOICE_SERVER_URL: str = "http://localhost:5123"
CUSTOM_VOICE_CACHE_DIR: Path = APP_DATA_DIR / "custom_voice_cache"
DEFAULT_VOICE_DESCRIPTION: str = ""

# ═══════════════════════════════════════════════
# MEASUREMENT NAMES (used as dict keys everywhere)
# ═══════════════════════════════════════════════

MEASURE_NOSE_SHOULDER_VERTICAL_GAP: str = "nose_shoulder_vertical_gap"
MEASURE_SHOULDER_SCREEN_Y: str = "shoulder_screen_y"

ALL_MEASUREMENTS: list[str] = [
    MEASURE_NOSE_SHOULDER_VERTICAL_GAP,
    MEASURE_SHOULDER_SCREEN_Y,
]

MEASUREMENT_DISPLAY_NAMES: dict[str, str] = {
    MEASURE_NOSE_SHOULDER_VERTICAL_GAP: "Nose-Shoulder Gap",
    MEASURE_SHOULDER_SCREEN_Y: "Shoulder Height",
}

# Minimum tolerances for posture classification at the default sensitivity.
# These prevent very stable calibrations from creating near-zero thresholds
# that classify ordinary landmark jitter as bad posture.
# Values are fractions of the calibrated nose-to-shoulder vertical distance.
POSTURE_TOLERANCE_FLOORS: dict[str, float] = {
    MEASURE_NOSE_SHOULDER_VERTICAL_GAP: 0.16,
    MEASURE_SHOULDER_SCREEN_Y: 0.16,
}

# Maximum acceptable raw jitter during calibration capture.
# Values are fractions of the calibrated nose-to-shoulder vertical distance.
CALIBRATION_VARIANCE_LIMITS: dict[str, float] = {
    MEASURE_NOSE_SHOULDER_VERTICAL_GAP: 0.08,
    MEASURE_SHOULDER_SCREEN_Y: 0.08,
}

# ═══════════════════════════════════════════════
# POSTURE STATUS
# ═══════════════════════════════════════════════

STATUS_GOOD: str = "Good"
STATUS_WARNING: str = "Warning"
STATUS_BAD: str = "Bad"
STATUS_NO_DETECTION: str = "No Detection"

# Warning is issued at 70% of the alert threshold
WARNING_THRESHOLD_RATIO: float = 0.7

# ═══════════════════════════════════════════════
# COACH PERSONALITY LINES
# ═══════════════════════════════════════════════

COACH_LINES: dict[str, dict[str, list[str]]] = {
    COACH_STANDARD: {
        MEASURE_NOSE_SHOULDER_VERTICAL_GAP: [
            "Lift your head a bit higher.",
            "Raise your head slightly and look straight ahead.",
            "Bring your chin up a little and keep your head tall.",
        ],
        MEASURE_SHOULDER_SCREEN_Y: [
            "Sit up straighter.",
            "Lift your chest and bring your shoulders back to your usual height.",
            "Straighten your spine and return your shoulders to your calibrated position.",
        ],
    },
}

CAMERA_THUMBNAIL_WIDTH: int = 480
CAMERA_THUMBNAIL_HEIGHT: int = 360

PRIVACY_NOTE: str = (
    "🔒 Camera feed is processed locally. "
    "Nothing is recorded or transmitted."
)

# Colors
COLOR_GOOD: str = "#2ecc71"
COLOR_WARNING: str = "#f39c12"
COLOR_BAD: str = "#e74c3c"
COLOR_INACTIVE: str = "#95a5a6"

# ═══════════════════════════════════════════════
# WINDOWS STARTUP REGISTRY
# ═══════════════════════════════════════════════

STARTUP_REGISTRY_KEY: str = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_REGISTRY_NAME: str = APP_NAME
