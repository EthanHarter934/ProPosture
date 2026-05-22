"""
Application controller for the React UI.

This module owns the runtime behavior behind the React desktop interface:
monitoring, calibration, settings persistence, voice tests, and frame previews.
The posture, calibration, profile, audio, and startup logic remain in the
existing Python backend modules.
"""

from __future__ import annotations

import base64
import logging
import sys
import threading
import time
from typing import Any, Optional

import cv2
import numpy as np

from audio.voice_manager import VoiceManager
from constants import (
    ALL_MEASUREMENTS,
    CAMERA_FRAME_HEIGHT,
    CAMERA_FRAME_WIDTH,
    CAMERA_THUMBNAIL_HEIGHT,
    CAMERA_THUMBNAIL_WIDTH,
    COACH_LABELS,
    COACH_LINES,
    COLOR_BAD,
    COLOR_GOOD,
    COLOR_INACTIVE,
    COLOR_WARNING,
    CUSTOM_VOICE_CACHE_DIR,
    DEFAULT_ALERT_DELAY_SEC,
    DEFAULT_COOLDOWN_SEC,
    DEFAULT_SENSITIVITY_MULTIPLIER,
    DEFAULT_VOICE_SERVER_URL,
    MAX_ALERT_DELAY_SEC,
    MAX_COOLDOWN_SEC,
    MAX_SENSITIVITY_MULTIPLIER,
    MEASUREMENT_DISPLAY_NAMES,
    MEASURE_NOSE_SHOULDER_VERTICAL_GAP,
    MEASURE_SHOULDER_SCREEN_Y,
    MIN_ALERT_DELAY_SEC,
    MIN_COOLDOWN_SEC,
    MIN_SENSITIVITY_MULTIPLIER,
    PRIVACY_NOTE,
    SNOOZE_DURATION_SEC,
    STATUS_BAD,
    STATUS_GOOD,
    STATUS_NO_DETECTION,
    STATUS_WARNING,
    STABILITY_THRESHOLD,
    TARGET_FPS,
    TTS_VOICE_LABELS,
    VOICE_MODE_CUSTOM,
    VOICE_MODE_LABELS,
    VOICE_MODE_STANDARD,
)
from core.alert_engine import AlertEngine
from core.calibration import CalibrationResult, CalibrationSession
from core.pose_detector import PoseDetector
from core.posture_analyzer import PostureAnalyzer, PostureStatus
from core.startup import (
    get_startup_label,
    is_startup_supported,
    set_launch_at_startup,
)
from data.profile_manager import AppSettings, CalibrationProfile, ProfileManager

logger = logging.getLogger(__name__)

VIEW_DASHBOARD = "dashboard"
VIEW_CALIBRATION = "calibration"
VIEW_SETTINGS = "settings"
FRAME_DELAY_SEC = 1.0 / TARGET_FPS


class AppController:
    """Thread-safe controller used by the desktop bridge and tray callbacks."""

    def __init__(
        self,
        profile_manager: ProfileManager,
        settings: AppSettings,
        profile: Optional[CalibrationProfile],
    ) -> None:
        self._pm = profile_manager
        self._settings = settings
        self._profile = profile

        self._analyzer = PostureAnalyzer()
        self._alert_engine = AlertEngine(
            alert_delay=settings.alert_delay_sec,
            cooldown=settings.cooldown_sec,
        )
        self._voice_manager = VoiceManager(
            personality=settings.coach_personality,
            voice=settings.tts_voice,
            volume=settings.volume,
            voice_mode=settings.voice_mode,
            voice_description=settings.voice_description,
            voice_server_url=settings.voice_server_url,
            cloned_voice_ref_path=getattr(settings, 'cloned_voice_ref_path', ''),
        )

        self._lock = threading.RLock()
        self._monitoring = False
        self._monitor_stop = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_cap: Optional[cv2.VideoCapture] = None
        self._current_status = STATUS_NO_DETECTION
        self._current_posture_reason = ""
        self._current_monitor_jpeg: Optional[bytes] = None
        self._session_start = 0.0
        self._alert_count = 0
        self._good_streak_start = 0.0
        self._longest_good_streak = 0.0

        self._calibration_step = 0
        self._calibration_session = CalibrationSession()
        self._calibration_result: Optional[CalibrationResult] = None
        self._calibration_running = False
        self._calibration_stop = threading.Event()
        self._calibration_thread: Optional[threading.Thread] = None
        self._calibration_cap: Optional[cv2.VideoCapture] = None
        self._calibration_detector: Optional[PoseDetector] = None
        self._current_calibration_jpeg: Optional[bytes] = None
        self._calibration_measurements: dict[str, float] = {}
        self._calibration_stability = 0.0

        self._is_generating_voice = False
        self._active_view = VIEW_CALIBRATION if profile is None else VIEW_DASHBOARD

    def state(self) -> dict[str, Any]:
        """Return a serializable snapshot for the React app."""
        with self._lock:
            elapsed = time.time() - self._session_start if self._session_start else 0.0
            return {
                "view": self._active_view,
                "needsCalibration": self._profile is None,
                "monitoring": self._monitoring,
                "paused": self._alert_engine.is_paused,
                "snoozed": self._alert_engine.is_snoozed,
                "headerStatus": self._header_status(),
                "postureStatus": self._current_status,
                "postureDetail": self._posture_detail(
                    self._current_status,
                    self._current_posture_reason,
                ),
                "isGeneratingVoice": self._is_generating_voice,
                "voiceManagerSpeaking": self._voice_manager.is_speaking,
                "session": {
                    "elapsed": elapsed,
                    "elapsedLabel": self._format_duration(elapsed),
                    "alerts": self._alert_count,
                    "bestStreak": self._longest_good_streak,
                    "bestStreakLabel": self._format_duration(self._longest_good_streak),
                },
                "settings": self._settings_payload(),
                "profile": self._profile_payload(),
                "calibration": self._calibration_payload(),
                "constants": self.constants_payload(),
            }

    def constants_payload(self) -> dict[str, Any]:
        """Return UI constants that come from the Python backend."""
        return {
            "measurements": ALL_MEASUREMENTS,
            "measurementLabels": MEASUREMENT_DISPLAY_NAMES,
            "coachLabels": COACH_LABELS,
            "voices": TTS_VOICE_LABELS,
            "voiceModes": VOICE_MODE_LABELS,
            "ranges": {
                "sensitivity": {
                    "min": MIN_SENSITIVITY_MULTIPLIER,
                    "max": MAX_SENSITIVITY_MULTIPLIER,
                    "step": 0.1,
                    "default": DEFAULT_SENSITIVITY_MULTIPLIER,
                },
                "alertDelay": {
                    "min": MIN_ALERT_DELAY_SEC,
                    "max": MAX_ALERT_DELAY_SEC,
                    "step": 1,
                    "default": DEFAULT_ALERT_DELAY_SEC,
                },
                "cooldown": {
                    "min": MIN_COOLDOWN_SEC,
                    "max": MAX_COOLDOWN_SEC,
                    "step": 5,
                    "default": DEFAULT_COOLDOWN_SEC,
                },
                "volume": {
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "default": 1.0,
                },
            },
            "cameraIndexes": [0, 1, 2, 3, 4],
            "stabilityThreshold": STABILITY_THRESHOLD,
            "startupSupported": is_startup_supported(),
            "startupLabel": get_startup_label(),
            "privacyNote": PRIVACY_NOTE,
            "colors": {
                STATUS_GOOD: COLOR_GOOD,
                STATUS_WARNING: COLOR_WARNING,
                STATUS_BAD: COLOR_BAD,
                STATUS_NO_DETECTION: COLOR_INACTIVE,
            },
        }

    def set_view(self, view: str) -> dict[str, Any]:
        """Set the active frontend view."""
        if view not in {VIEW_DASHBOARD, VIEW_CALIBRATION, VIEW_SETTINGS}:
            raise ValueError("Unknown view")
        if view != VIEW_CALIBRATION:
            self.stop_calibration_camera()
        with self._lock:
            self._active_view = view
        return self.state()

    def start_monitoring(self) -> dict[str, Any]:
        """Start posture monitoring."""
        with self._lock:
            if self._profile is None:
                self._active_view = VIEW_CALIBRATION
                return self.state()
            if self._monitoring or self._is_generating_voice:
                return self.state()

        self.stop_calibration_camera()

        with self._lock:
            if self._monitoring:
                return self.state()
            self._monitor_stop.clear()
            self._monitoring = True
            self._session_start = time.time()
            self._alert_count = 0
            self._good_streak_start = time.time()
            self._longest_good_streak = 0.0
            self._current_posture_reason = ""

        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="Monitoring-Thread",
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info("Monitoring started")
        return self.state()

    def stop_monitoring(self) -> dict[str, Any]:
        """Stop posture monitoring."""
        self._monitor_stop.set()
        with self._lock:
            self._monitoring = False
            self._current_status = STATUS_NO_DETECTION
            self._current_posture_reason = ""

        thread = self._monitor_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.5)

        if thread is None or not thread.is_alive():
            self._monitor_thread = None
            if self._monitor_cap is not None:
                self._monitor_cap.release()
                self._monitor_cap = None

        logger.info("Monitoring stopped")
        return self.state()

    def toggle_monitoring(self) -> dict[str, Any]:
        """Toggle monitoring on or off."""
        return self.stop_monitoring() if self._monitoring else self.start_monitoring()

    def snooze(self) -> dict[str, Any]:
        """Snooze alerts for the configured duration."""
        self._alert_engine.snooze(SNOOZE_DURATION_SEC)
        logger.info("Monitoring snoozed for 15 minutes")
        return self.state()

    def toggle_pause(self) -> dict[str, Any]:
        """Pause or resume alert evaluation."""
        if self._alert_engine.is_paused:
            self._alert_engine.resume()
        else:
            self._alert_engine.pause()
        return self.state()

    def resume_alerts(self) -> dict[str, Any]:
        """Resume alerts immediately, clearing any active snooze."""
        self._alert_engine.reset()
        return self.state()

    def save_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Persist and apply settings updates from the React app."""
        with self._lock:
            # Handle audio file upload if present
            if "audio_file_data" in updates and updates.get("audio_file_data"):
                try:
                    audio_data_base64 = updates["audio_file_data"]
                    audio_file_name = updates.get("audio_file_name", "cloned_voice.wav")

                    if isinstance(audio_data_base64, str) and audio_data_base64.startswith("data:"):
                        # Extract base64 from data URL if needed
                        audio_data_base64 = audio_data_base64.split(",", 1)[1]

                    audio_bytes = base64.b64decode(audio_data_base64)

                    # Save to custom voice cache directory with a fixed name for voice cloning reference
                    CUSTOM_VOICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    cloned_voice_ref_path = CUSTOM_VOICE_CACHE_DIR / "cloned_voice_reference.wav"
                    cloned_voice_ref_path.write_bytes(audio_bytes)

                    logger.info("Saved cloned voice reference audio file: %s", cloned_voice_ref_path)
                    self._settings.cloned_voice_ref_path = str(cloned_voice_ref_path)
                except Exception:
                    logger.exception("Failed to save audio file")

            for key, value in updates.items():
                if key == "audio_file_data":
                    # Don't persist raw audio data in settings
                    continue
                if not hasattr(self._settings, key):
                    continue
                setattr(self._settings, key, value)

            self._settings.alert_delay_sec = float(self._settings.alert_delay_sec)
            self._settings.cooldown_sec = float(self._settings.cooldown_sec)
            self._settings.camera_index = int(self._settings.camera_index)
            self._settings.dark_mode = bool(self._settings.dark_mode)
            self._settings.launch_at_startup = bool(self._settings.launch_at_startup)
            self._settings.show_camera_preview = bool(self._settings.show_camera_preview)
            self._settings.volume = max(0.0, min(1.0, float(self._settings.volume)))

            if "launch_at_startup" in updates:
                enabled = self._settings.launch_at_startup
                if not set_launch_at_startup(enabled):
                    self._settings.launch_at_startup = False

            self._pm.save_settings(self._settings)
            self._alert_engine.alert_delay = self._settings.alert_delay_sec
            self._alert_engine.cooldown = self._settings.cooldown_sec
            self._voice_manager.personality = self._settings.coach_personality
            self._voice_manager.voice = self._settings.tts_voice
            self._voice_manager.volume = self._settings.volume
            self._voice_manager.voice_mode = self._settings.voice_mode
            self._voice_manager.voice_description = self._settings.voice_description or self._settings.character_description
            self._voice_manager.voice_server_url = self._settings.voice_server_url
            if hasattr(self._settings, 'cloned_voice_ref_path'):
                self._voice_manager.cloned_voice_ref_path = self._settings.cloned_voice_ref_path

        logger.debug("Settings saved and applied")
        return self.state()

    def reset_settings(self) -> dict[str, Any]:
        """Reset application settings to defaults."""
        if self._settings.launch_at_startup:
            set_launch_at_startup(False)
        with self._lock:
            if self._profile is not None:
                for name in ALL_MEASUREMENTS:
                    self._profile.sensitivity_multipliers[name] = DEFAULT_SENSITIVITY_MULTIPLIER
                self._pm.save_profile(self._profile)
        return self.save_settings(AppSettings().__dict__)

    def save_sensitivity(self, measurement: str, value: float) -> dict[str, Any]:
        """Persist a sensitivity multiplier for the current profile."""
        if measurement not in ALL_MEASUREMENTS:
            raise ValueError("Unknown measurement")
        with self._lock:
            if self._profile is not None:
                self._profile.sensitivity_multipliers[measurement] = round(float(value), 1)
                self._pm.save_profile(self._profile)
        return self.state()

    def test_voice(self, personality: str, voice: str) -> dict[str, Any]:
        """Play the selected test voice without permanently changing settings."""
        old_personality = self._voice_manager.personality
        old_voice = self._voice_manager.voice
        self._voice_manager.personality = personality
        self._voice_manager.voice = voice
        self._voice_manager.speak_text("This is how I'll sound when I coach you.")
        self._voice_manager.personality = old_personality
        self._voice_manager.voice = old_voice
        return self.state()

    def generate_custom_voice_test(self, voice_description: str, voice_server_url: str) -> dict[str, Any]:
        """Test the custom voice by playing a single line."""
        old_desc = self._voice_manager.voice_description
        old_url = self._voice_manager.voice_server_url
        old_mode = self._voice_manager.voice_mode
        old_ref = self._voice_manager.cloned_voice_ref_path

        self._voice_manager.voice_description = voice_description
        self._voice_manager.voice_server_url = voice_server_url
        self._voice_manager.voice_mode = VOICE_MODE_CUSTOM
        self._voice_manager.cloned_voice_ref_path = ""
        self._voice_manager.speak_text("This is a preview of my voice. I will be monitoring your posture closely to help you stay aligned and healthy throughout your day.")
        self._voice_manager.voice_description = old_desc
        self._voice_manager.voice_server_url = old_url
        self._voice_manager.voice_mode = old_mode
        self._voice_manager.cloned_voice_ref_path = old_ref
        return self.state()

    def test_cloned_voice(self, character_description: str, voice_server_url: str) -> dict[str, Any]:
        """Test a cloned voice from uploaded audio."""
        old_desc = self._voice_manager.voice_description
        old_url = self._voice_manager.voice_server_url
        old_mode = self._voice_manager.voice_mode
        old_ref = self._voice_manager.cloned_voice_ref_path

        cloned_voice_ref_path = getattr(self._settings, 'cloned_voice_ref_path', '')

        self._voice_manager.voice_description = character_description
        self._voice_manager.voice_server_url = voice_server_url
        self._voice_manager.voice_mode = VOICE_MODE_CUSTOM
        self._voice_manager.cloned_voice_ref_path = cloned_voice_ref_path
        self._voice_manager.speak_text("This is a preview of my voice. I will be monitoring your posture closely to help you stay aligned and healthy throughout your day.")

        self._voice_manager.voice_description = old_desc
        self._voice_manager.voice_server_url = old_url
        self._voice_manager.voice_mode = old_mode
        self._voice_manager.cloned_voice_ref_path = old_ref
        return self.state()

    def generate_custom_voice(self, voice_description: str, voice_server_url: str) -> dict[str, Any]:
        """
        Pre-generate all coach lines using the VoxCPM2 server in the background.
        """
        import hashlib
        import json
        import urllib.request
        import zipfile
        import io
        import tempfile

        if not voice_description.strip():
            return {**self.state(), "voiceGeneration": {"error": "Voice description is empty"}}

        if not voice_server_url.strip():
            voice_server_url = DEFAULT_VOICE_SERVER_URL

        with self._lock:
            if self._is_generating_voice:
                return self.state()
            self._is_generating_voice = True
            voice_source_type = getattr(self._settings, 'voice_source_type', 'description')
            cloned_voice_ref_path = getattr(self._settings, 'cloned_voice_ref_path', '') if voice_source_type == 'audio' else ''

        def _bg_generate() -> None:
            try:
                # Collect all unique coach lines
                all_prompts: dict[str, str] = {}
                for personality_lines in COACH_LINES.values():
                    for measurement, lines in personality_lines.items():
                        for i, line in enumerate(lines):
                            key = hashlib.sha256(
                                f"{voice_description}\0{line}".encode("utf-8")
                            ).hexdigest()[:16]
                            all_prompts[key] = line

                # Check which are already cached
                CUSTOM_VOICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                needed: dict[str, str] = {}
                for key, text in all_prompts.items():
                    cache_key = hashlib.sha256(
                        f"{voice_description}\0{text}".encode("utf-8")
                    ).hexdigest()
                    cached_path = CUSTOM_VOICE_CACHE_DIR / f"{cache_key}.wav"
                    if not (cached_path.exists() and cached_path.stat().st_size > 0):
                        needed[key] = text

                if not needed:
                    logger.info("All custom voice lines already cached")
                    return

                # Generate via voice server batch endpoint
                url = f"{voice_server_url.rstrip('/')}/generate"
                payload_dict = {
                    "voice_description": voice_description,
                    "prompts": needed,
                }
                # For audio upload mode, pass the reference. For text description,
                # the server will auto-detect the cached test audio.
                if voice_source_type == 'audio' and cloned_voice_ref_path:
                    payload_dict["reference_audio_path"] = cloned_voice_ref_path

                payload = json.dumps(payload_dict).encode("utf-8")

                generation_mode = "voice cloning" if (voice_source_type == 'audio' and cloned_voice_ref_path) else "auto-detected reference"
                logger.info("Requesting %d custom voice lines from %s using %s mode",
                           len(needed), url, generation_mode)

                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=600) as response:
                    zip_data = response.read()

                # Extract WAV files from ZIP and save to cache
                generated_count = 0
                with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                    for name in zf.namelist():
                        if not name.endswith(".wav"):
                            continue
                        zip_key = name[:-4]  # Strip .wav
                        text = needed.get(zip_key, "")
                        if not text:
                            continue
                        cache_key = hashlib.sha256(
                            f"{voice_description}\0{text}".encode("utf-8")
                        ).hexdigest()
                        cached_path = CUSTOM_VOICE_CACHE_DIR / f"{cache_key}.wav"
                        cached_path.write_bytes(zf.read(name))
                        generated_count += 1

                logger.info("Generated %d custom voice lines in background", generated_count)
            except Exception:
                logger.exception("Failed to generate custom voice in background")
            finally:
                with self._lock:
                    self._is_generating_voice = False

        threading.Thread(target=_bg_generate, name="VoiceGen-Thread", daemon=True).start()
        return self.state()

    def begin_calibration(self) -> dict[str, Any]:
        """Reset the calibration flow to the education step."""
        self.stop_monitoring()
        self.stop_calibration_camera()
        with self._lock:
            self._active_view = VIEW_CALIBRATION
            self._calibration_step = 0
            self._calibration_session.reset()
            self._calibration_result = None
            self._calibration_measurements = {}
            self._calibration_stability = 0.0
            self._current_calibration_jpeg = None
        return self.state()

    def start_calibration_preview(self) -> dict[str, Any]:
        """Move to the live calibration preview step and start camera capture."""
        self.stop_monitoring()
        with self._lock:
            self._active_view = VIEW_CALIBRATION
            self._calibration_step = 1
            self._calibration_session.reset()
            self._calibration_result = None
            self._calibration_stop.clear()
        self._ensure_calibration_camera()
        return self.state()

    def start_calibration_capture(self) -> dict[str, Any]:
        """Begin the 90-frame baseline capture."""
        with self._lock:
            self._calibration_step = 2
            self._calibration_session.start_capture()
        self._ensure_calibration_camera()
        return self.state()

    def recapture(self) -> dict[str, Any]:
        """Return to calibration preview from the confirmation step."""
        return self.start_calibration_preview()

    def accept_calibration(self) -> dict[str, Any]:
        """Persist the captured baseline and return to the dashboard."""
        with self._lock:
            result = self._calibration_result
        if result is None:
            return self.state()

        profile = CalibrationProfile(
            captured_at=result.captured_at,
            baseline_means=result.baseline.means,
            baseline_stds=result.baseline.std_devs,
            sensitivity_multipliers={name: DEFAULT_SENSITIVITY_MULTIPLIER for name in ALL_MEASUREMENTS},
        )
        self._pm.save_profile(profile)
        self.stop_calibration_camera()
        with self._lock:
            self._profile = profile
            self._active_view = VIEW_DASHBOARD
        logger.info("Calibration saved")
        return self.state()

    def cancel_calibration(self) -> dict[str, Any]:
        """Cancel calibration and return to the dashboard."""
        self.stop_calibration_camera()
        with self._lock:
            self._active_view = VIEW_DASHBOARD
        return self.state()

    def delete_calibration(self) -> dict[str, Any]:
        """Delete stored calibration data."""
        self._pm.delete_calibration()
        self.stop_monitoring()
        with self._lock:
            self._profile = None
            self._active_view = VIEW_CALIBRATION
        return self.state()

    def latest_monitor_jpeg(self) -> Optional[bytes]:
        """Return the latest monitoring preview frame."""
        with self._lock:
            return self._current_monitor_jpeg

    def latest_calibration_jpeg(self) -> Optional[bytes]:
        """Return the latest calibration preview frame."""
        with self._lock:
            return self._current_calibration_jpeg

    def latest_monitor_frame_data_url(self) -> Optional[str]:
        """Return the latest monitoring preview as a browser-ready data URL."""
        return self._data_url(self.latest_monitor_jpeg())

    def latest_calibration_frame_data_url(self) -> Optional[str]:
        """Return the latest calibration preview as a browser-ready data URL."""
        return self._data_url(self.latest_calibration_jpeg())

    def shutdown(self) -> None:
        """Release all background resources."""
        self.stop_monitoring()
        self.stop_calibration_camera()
        self._voice_manager.shutdown()

    def _monitor_loop(self) -> None:
        detector: Optional[PoseDetector] = None
        try:
            self._monitor_cap = self._open_camera(self._settings.camera_index)
            detector = PoseDetector()
            while not self._monitor_stop.is_set():
                if self._monitor_cap is None or not self._monitor_cap.isOpened():
                    break
                ret, frame = self._monitor_cap.read()
                if not ret:
                    time.sleep(FRAME_DELAY_SEC)
                    continue
                self._process_monitor_frame(detector, cv2.flip(frame, 1))
                time.sleep(FRAME_DELAY_SEC)
        except Exception:
            logger.exception("Monitoring loop error")
        finally:
            if detector is not None:
                detector.close()
            if self._monitor_cap is not None:
                self._monitor_cap.release()
                self._monitor_cap = None
            with self._lock:
                self._monitoring = False
                self._monitor_thread = None

    def _process_monitor_frame(self, detector: PoseDetector, frame: np.ndarray) -> None:
        landmarks = detector.detect(frame)
        if landmarks is not None:
            frame = detector.draw_landmarks(frame, landmarks)
            measurements = self._analyzer.compute_measurements(landmarks)
            status = self._evaluate_posture(measurements)
            self._process_alerts(status)
        else:
            with self._lock:
                self._current_status = STATUS_NO_DETECTION
                self._current_posture_reason = ""

        jpeg = self._encode_jpeg(frame, CAMERA_THUMBNAIL_WIDTH, CAMERA_THUMBNAIL_HEIGHT)
        with self._lock:
            self._current_monitor_jpeg = jpeg

    def _evaluate_posture(self, measurements: Any) -> PostureStatus:
        with self._lock:
            profile = self._profile
        if profile is None:
            with self._lock:
                self._current_status = STATUS_NO_DETECTION
                self._current_posture_reason = ""
            return PostureStatus(STATUS_GOOD, [], None)

        status = self._analyzer.compare_to_baseline(
            measurements,
            profile.baseline_means,
            profile.baseline_stds,
            profile.sensitivity_multipliers,
        )
        with self._lock:
            self._current_status = status.overall_status
            self._current_posture_reason = self._posture_reason(status)
        return status

    def _process_alerts(self, status: PostureStatus) -> None:
        alert = self._alert_engine.check(status)
        with self._lock:
            if alert is not None:
                self._voice_manager.speak_alert(alert)
                self._alert_count += 1

            if status.overall_status == STATUS_GOOD:
                streak = time.time() - self._good_streak_start
                self._longest_good_streak = max(self._longest_good_streak, streak)
            else:
                self._good_streak_start = time.time()

    def _ensure_calibration_camera(self) -> None:
        with self._lock:
            if self._calibration_running:
                return
            self._calibration_running = True
            self._calibration_stop.clear()

        self._calibration_thread = threading.Thread(
            target=self._calibration_loop,
            name="Calibration-Thread",
            daemon=True,
        )
        self._calibration_thread.start()

    def _calibration_loop(self) -> None:
        try:
            self._calibration_cap = self._open_camera(self._settings.camera_index)
            self._calibration_detector = PoseDetector()
            while not self._calibration_stop.is_set():
                if self._calibration_cap is None or not self._calibration_cap.isOpened():
                    break
                ret, frame = self._calibration_cap.read()
                if not ret:
                    time.sleep(FRAME_DELAY_SEC)
                    continue
                self._process_calibration_frame(cv2.flip(frame, 1))
                time.sleep(FRAME_DELAY_SEC)
        except Exception:
            logger.exception("Calibration loop error")
        finally:
            self._release_calibration_resources()

    def _process_calibration_frame(self, frame: np.ndarray) -> None:
        detector = self._calibration_detector
        if detector is None:
            return
        landmarks = detector.detect(frame)
        if landmarks is not None:
            frame = detector.draw_landmarks(frame, landmarks)
            measurements = PostureAnalyzer.compute_measurements(landmarks)
            self._calibration_session.add_frame(measurements)
            with self._lock:
                self._calibration_measurements = measurements.to_dict()
                self._calibration_stability = self._calibration_session.get_stability_score()

            if (
                self._calibration_session.is_capturing
                and self._calibration_session.capture_complete
            ):
                result = self._calibration_session.finish_capture()
                with self._lock:
                    self._calibration_result = result
                    self._calibration_step = 3 if result is not None else 1
                self._calibration_stop.set()

        jpeg = self._encode_jpeg(frame, 420, 315)
        with self._lock:
            self._current_calibration_jpeg = jpeg

    def stop_calibration_camera(self) -> None:
        self._calibration_stop.set()

        thread = self._calibration_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.5)

        if thread is None or not thread.is_alive():
            self._release_calibration_resources()

    def _release_calibration_resources(self) -> None:
        with self._lock:
            self._calibration_running = False
            self._calibration_thread = None
        if self._calibration_cap is not None:
            self._calibration_cap.release()
            self._calibration_cap = None
        if self._calibration_detector is not None:
            self._calibration_detector.close()
            self._calibration_detector = None

    def _settings_payload(self) -> dict[str, Any]:
        return {
            "coach_personality": self._settings.coach_personality,
            "tts_voice": self._settings.tts_voice,
            "voice_mode": self._settings.voice_mode,
            "voice_description": self._settings.voice_description,
            "voice_source_type": self._settings.voice_source_type,
            "character_description": self._settings.character_description,
            "audio_file_name": self._settings.audio_file_name,
            "voice_server_url": self._settings.voice_server_url,
            "alert_delay_sec": self._settings.alert_delay_sec,
            "cooldown_sec": self._settings.cooldown_sec,
            "camera_index": self._settings.camera_index,
            "dark_mode": self._settings.dark_mode,
            "launch_at_startup": self._settings.launch_at_startup,
            "show_camera_preview": self._settings.show_camera_preview,
            "hotkey": self._settings.hotkey,
            "volume": self._settings.volume,
        }

    def _profile_payload(self) -> Optional[dict[str, Any]]:
        if self._profile is None:
            return None
        return {
            "captured_at": self._profile.captured_at,
            "baseline_means": self._profile.baseline_means,
            "baseline_stds": self._profile.baseline_stds,
            "sensitivity_multipliers": self._profile.sensitivity_multipliers,
        }

    def _calibration_payload(self) -> dict[str, Any]:
        result = self._calibration_result
        quality = None
        if result is not None:
            quality = {
                "isAcceptable": result.quality.is_acceptable,
                "warnings": result.quality.warnings,
                "perMeasurement": {
                    name: {"mean": mean, "std": std, "ok": ok}
                    for name, (mean, std, ok) in result.quality.per_measurement.items()
                },
            }
        return {
            "step": self._calibration_step,
            "running": self._calibration_running,
            "stability": self._calibration_stability,
            "measurements": self._calibration_measurements,
            "captureProgress": self._calibration_session.capture_progress,
            "captureComplete": self._calibration_session.capture_complete,
            "quality": quality,
        }

    def _header_status(self) -> dict[str, str]:
        if self._alert_engine.is_snoozed:
            return {"text": "Snoozed", "color": COLOR_WARNING}
        if self._alert_engine.is_paused:
            return {"text": "Paused", "color": COLOR_WARNING}
        if self._monitoring:
            return {"text": "Active", "color": COLOR_GOOD}
        return {"text": "Inactive", "color": COLOR_INACTIVE}

    @staticmethod
    def _posture_reason(status: PostureStatus) -> str:
        if status.overall_status == STATUS_GOOD:
            return ""
        return {
            MEASURE_NOSE_SHOULDER_VERTICAL_GAP: "Lift your head a bit higher.",
            MEASURE_SHOULDER_SCREEN_Y: "Sit up straighter.",
        }.get(status.worst_measurement or "", "")

    @staticmethod
    def _posture_detail(status: str, reason: str = "") -> str:
        if reason:
            return reason
        return {
            STATUS_GOOD: "Your posture looks great. Keep it up.",
            STATUS_WARNING: "Minor deviation detected. Adjust slightly.",
            STATUS_BAD: "Bad posture detected. Correct your position.",
            STATUS_NO_DETECTION: "No pose detected. Check camera.",
        }.get(status, "")

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total = int(seconds)
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    @staticmethod
    def _encode_jpeg(frame: np.ndarray, width: int, height: int) -> Optional[bytes]:
        try:
            h, w = frame.shape[:2]
            ratio = min(width / w, height / h)
            new_w = max(1, int(w * ratio))
            new_h = max(1, int(h * ratio))
            resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            ok, buffer = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            return buffer.tobytes() if ok else None
        except Exception:
            logger.debug("Failed to encode preview frame", exc_info=True)
            return None

    @staticmethod
    def _open_camera(index: int) -> cv2.VideoCapture:
        if sys.platform == "win32":
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_FRAME_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
        return cap

    @staticmethod
    def _data_url(jpeg: Optional[bytes]) -> Optional[str]:
        if jpeg is None:
            return None
        encoded = base64.b64encode(jpeg).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
