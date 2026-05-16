"""
ProPosture Constants Module

Central repository for all application constants, default values, file paths,
coach personality dialogue lines, and MediaPipe landmark indices. No other
module should contain hardcoded values — import them from here.
"""

from pathlib import Path
import os

# ═══════════════════════════════════════════════
# APPLICATION METADATA
# ═══════════════════════════════════════════════

APP_NAME: str = "ProPosture"
APP_VERSION: str = "1.0.0"

# ═══════════════════════════════════════════════
# FILE PATHS
# ═══════════════════════════════════════════════

APP_DATA_DIR: Path = Path(os.environ.get("LOCALAPPDATA", "")) / APP_NAME
LOG_DIR: Path = APP_DATA_DIR / "logs"
PROFILE_PATH: Path = APP_DATA_DIR / "profile.json"
SETTINGS_PATH: Path = APP_DATA_DIR / "settings.json"
ASSETS_DIR: Path = Path(__file__).parent / "assets"
ICON_PATH: Path = ASSETS_DIR / "icon.png"

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
    LANDMARK_LEFT_EAR,
    LANDMARK_RIGHT_EAR,
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_RIGHT_SHOULDER,
]

# ═══════════════════════════════════════════════
# VISIBILITY & DETECTION
# ═══════════════════════════════════════════════

MIN_LANDMARK_VISIBILITY: float = 0.6
POSE_MODEL_COMPLEXITY: int = 1
POSE_MIN_DETECTION_CONFIDENCE: float = 0.5
POSE_MIN_TRACKING_CONFIDENCE: float = 0.5

# ═══════════════════════════════════════════════
# CAMERA
# ═══════════════════════════════════════════════

DEFAULT_CAMERA_INDEX: int = 0
CAMERA_FRAME_WIDTH: int = 640
CAMERA_FRAME_HEIGHT: int = 480
TARGET_FPS: int = 30
FRAME_INTERVAL_MS: int = 1000 // TARGET_FPS  # ~33ms

# ═══════════════════════════════════════════════
# CALIBRATION
# ═══════════════════════════════════════════════

CALIBRATION_VERSION: int = 1
CALIBRATION_CAPTURE_FRAMES: int = 90  # 3 seconds at 30 fps
STABILITY_WINDOW_FRAMES: int = 30  # 1 second of frames for stability check
STABILITY_THRESHOLD: float = 0.55  # 0.0–1.0 to consider user "stable"
HIGH_VARIANCE_THRESHOLD: float = 5.0  # Flag quality warning if std > this

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
DRILL_SERGEANT_SPEECH_RATE: int = 220
STANDARD_VOLUME: float = 0.9
DRILL_SERGEANT_VOLUME: float = 1.0

COACH_STANDARD: str = "standard"
COACH_DRILL_SERGEANT: str = "drill_sergeant"

# ═══════════════════════════════════════════════
# MEASUREMENT NAMES (used as dict keys everywhere)
# ═══════════════════════════════════════════════

MEASURE_SHOULDER_ANGLE: str = "shoulder_angle"
MEASURE_FORWARD_HEAD_RATIO: str = "forward_head_ratio"
MEASURE_HEAD_TILT_ANGLE: str = "head_tilt_angle"
MEASURE_NECK_ANGLE: str = "neck_angle"

ALL_MEASUREMENTS: list[str] = [
    MEASURE_SHOULDER_ANGLE,
    MEASURE_FORWARD_HEAD_RATIO,
    MEASURE_HEAD_TILT_ANGLE,
    MEASURE_NECK_ANGLE,
]

MEASUREMENT_DISPLAY_NAMES: dict[str, str] = {
    MEASURE_SHOULDER_ANGLE: "Shoulder Angle",
    MEASURE_FORWARD_HEAD_RATIO: "Forward Head Ratio",
    MEASURE_HEAD_TILT_ANGLE: "Head Tilt Angle",
    MEASURE_NECK_ANGLE: "Neck Angle",
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
        MEASURE_FORWARD_HEAD_RATIO: [
            "Your head is drifting forward. Bring your ears back over your shoulders.",
            "Try to imagine a string pulling the top of your head toward the ceiling.",
            "Your neck will thank you — pull your chin back slightly and sit tall.",
        ],
        MEASURE_SHOULDER_ANGLE: [
            "Your shoulders are uneven. Take a breath and let them drop and level out.",
            "Check your shoulders — try to make them symmetrical and relaxed.",
            "Your shoulders seem lopsided. Roll them back and settle them evenly.",
        ],
        MEASURE_HEAD_TILT_ANGLE: [
            "Your head is tilting to one side. Center it gently over your spine.",
            "Try to level your head — imagine balancing a book on top of it.",
            "Your head is leaning sideways. Straighten up and look ahead.",
        ],
        MEASURE_NECK_ANGLE: [
            "Your neck is flexing forward. Lift your chin and lengthen your spine.",
            "Bring your head back — your neck is bending too far forward.",
            "Straighten your neck gently. Think tall, think aligned.",
        ],
    },
    COACH_DRILL_SERGEANT: {
        MEASURE_FORWARD_HEAD_RATIO: [
            "YOUR HEAD IS THREE FEET IN FRONT OF YOUR BODY. GET IT BACK. NOW.",
            "What is that, a turkey neck?! Chin back, soldier! IMMEDIATELY.",
            "Your monitor is not a feeding trough! SIT UP STRAIGHT!",
        ],
        MEASURE_SHOULDER_ANGLE: [
            "Are you a HUNCHBACK? Level those shoulders out RIGHT NOW!",
            "One shoulder up, one shoulder down — you look like a broken coat hanger! FIX IT!",
            "Those shoulders are a DISASTER! Square them up, recruit!",
        ],
        MEASURE_HEAD_TILT_ANGLE: [
            "WHY IS YOUR HEAD SIDEWAYS? Are you a confused golden retriever? LEVEL IT OUT!",
            "Your head is tilting like a sinking ship! STRAIGHTEN UP!",
            "HEAD STRAIGHT, eyes forward! This is not a nap, soldier!",
        ],
        MEASURE_NECK_ANGLE: [
            "Your neck looks like a GOOSENECK LAMP! Pull it back NOW!",
            "NECK STRAIGHT, chin UP! You are NOT a vulture!",
            "What are you looking at down there?! HEAD UP, SOLDIER!",
        ],
    },
}

# ═══════════════════════════════════════════════
# UI CONSTANTS
# ═══════════════════════════════════════════════

WINDOW_TITLE: str = f"{APP_NAME} v{APP_VERSION}"
MAIN_WINDOW_WIDTH: int = 780
MAIN_WINDOW_HEIGHT: int = 750
SETTINGS_WINDOW_WIDTH: int = 500
SETTINGS_WINDOW_HEIGHT: int = 700
CALIBRATION_WINDOW_WIDTH: int = 750
CALIBRATION_WINDOW_HEIGHT: int = 700

CAMERA_THUMBNAIL_WIDTH: int = 320
CAMERA_THUMBNAIL_HEIGHT: int = 240

PRIVACY_NOTE: str = (
    "🔒 Camera feed is processed locally. "
    "Nothing is recorded or transmitted."
)

# Colors
COLOR_GOOD: str = "#2ecc71"
COLOR_WARNING: str = "#f39c12"
COLOR_BAD: str = "#e74c3c"
COLOR_INACTIVE: str = "#95a5a6"
COLOR_ACCENT: str = "#4a9eff"
COLOR_BG_DARK: str = "#1a1a2e"
COLOR_BG_CARD: str = "#16213e"

# ═══════════════════════════════════════════════
# WINDOWS STARTUP REGISTRY
# ═══════════════════════════════════════════════

STARTUP_REGISTRY_KEY: str = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_REGISTRY_NAME: str = APP_NAME
