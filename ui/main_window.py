"""
Main Window Module

Primary dashboard showing monitoring status, live posture reading, session
statistics, and quick-access controls. Manages the detection loop on a
background thread and coordinates with the alert engine and voice manager.
"""

import logging
import threading
import time
from typing import Any, Optional

import cv2
import customtkinter as ctk
import numpy as np
from PIL import Image, ImageTk

from constants import (
    ALL_MEASUREMENTS,
    CAMERA_FRAME_HEIGHT,
    CAMERA_FRAME_WIDTH,
    CAMERA_THUMBNAIL_HEIGHT,
    CAMERA_THUMBNAIL_WIDTH,
    COLOR_ACCENT,
    COLOR_BAD,
    COLOR_GOOD,
    COLOR_INACTIVE,
    COLOR_WARNING,
    MAIN_WINDOW_HEIGHT,
    MAIN_WINDOW_WIDTH,
    MEASURE_FORWARD_HEAD_RATIO,
    PRIVACY_NOTE,
    SNOOZE_DURATION_SEC,
    STATUS_BAD,
    STATUS_GOOD,
    STATUS_NO_DETECTION,
    STATUS_WARNING,
    WINDOW_TITLE,
)
from core.alert_engine import AlertEngine
from core.pose_detector import PoseDetector
from core.posture_analyzer import PostureAnalyzer, PostureStatus
from audio.voice_manager import VoiceManager
from data.profile_manager import AppSettings, CalibrationProfile, ProfileManager

logger = logging.getLogger(__name__)


class MainWindow(ctk.CTk):
    """
    Primary application dashboard window.

    Displays monitoring status, posture reading, session stats, and camera
    preview. Runs the detection pipeline on a background thread.
    """

    def __init__(
        self,
        profile_manager: ProfileManager,
        settings: AppSettings,
        profile: Optional[CalibrationProfile],
    ) -> None:
        """
        Initialize the main window.

        Args:
            profile_manager: For loading/saving profiles and settings.
            settings: Current application settings.
            profile: Calibration profile (None if not yet calibrated).
        """
        super().__init__()
        self.title(WINDOW_TITLE)
        self.geometry(f"{MAIN_WINDOW_WIDTH}x{MAIN_WINDOW_HEIGHT}")
        self.resizable(False, False)

        self._pm = profile_manager
        self._settings = settings
        self._profile = profile

        # Core components (initialized later)
        self._detector: Optional[PoseDetector] = None
        self._analyzer = PostureAnalyzer()
        self._alert_engine = AlertEngine(
            alert_delay=settings.alert_delay_sec,
            cooldown=settings.cooldown_sec,
        )
        self._voice_manager = VoiceManager(personality=settings.coach_personality)

        # State
        self._monitoring = False
        self._stop_event = threading.Event()
        self._detection_thread: Optional[threading.Thread] = None
        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()
        self._current_status: str = STATUS_NO_DETECTION
        self._current_frame: Optional[np.ndarray] = None
        self._show_preview = settings.show_camera_preview

        # Session stats
        self._session_start: float = 0.0
        self._alert_count: int = 0
        self._good_streak_start: float = 0.0
        self._longest_good_streak: float = 0.0

        # Tray icon reference (set externally)
        self.tray_icon: Any = None

        # Callbacks for tray
        self.on_quit_callback: Optional[Any] = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the dashboard UI layout."""
        self._build_header()
        self._build_status_section()
        self._build_camera_section()
        self._build_stats_section()
        self._build_controls()
        self._build_footer()

    # ═══════════════════════════════════════════
    # HEADER
    # ═══════════════════════════════════════════

    def _build_header(self) -> None:
        """Build the app header with title."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 5))

        ctk.CTkLabel(
            header, text="ProPosture",
            font=ctk.CTkFont(size=28, weight="bold"),
        ).pack(side="left")

        self._status_dot = ctk.CTkLabel(
            header, text="●", font=ctk.CTkFont(size=22),
            text_color=COLOR_INACTIVE,
        )
        self._status_dot.pack(side="right", padx=5)

        self._status_text = ctk.CTkLabel(
            header, text="Inactive",
            font=ctk.CTkFont(size=14), text_color="gray",
        )
        self._status_text.pack(side="right")

    # ═══════════════════════════════════════════
    # STATUS SECTION
    # ═══════════════════════════════════════════

    def _build_status_section(self) -> None:
        """Build the posture status display."""
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(
            frame, text="Current Posture",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=(10, 2))

        self._posture_label = ctk.CTkLabel(
            frame, text="—",
            font=ctk.CTkFont(size=36, weight="bold"),
            text_color=COLOR_INACTIVE,
        )
        self._posture_label.pack(pady=(0, 5))

        self._posture_detail = ctk.CTkLabel(
            frame, text="Start monitoring to see your posture status",
            font=ctk.CTkFont(size=12), text_color="gray",
        )
        self._posture_detail.pack(pady=(0, 10))

    # ═══════════════════════════════════════════
    # CAMERA PREVIEW
    # ═══════════════════════════════════════════

    def _build_camera_section(self) -> None:
        """Build the optional camera preview section."""
        self._camera_frame = ctk.CTkFrame(self)

        self._preview_toggle = ctk.CTkSwitch(
            self._camera_frame, text="Show Camera Preview",
            command=self._toggle_preview,
            font=ctk.CTkFont(size=12),
        )
        self._preview_toggle.pack(pady=(8, 4))

        self._camera_label = ctk.CTkLabel(
            self._camera_frame, text="Camera preview off",
            width=CAMERA_THUMBNAIL_WIDTH,
            height=CAMERA_THUMBNAIL_HEIGHT,
        )

        self._camera_frame.pack(fill="x", padx=20, pady=5)

        if self._show_preview:
            self._preview_toggle.select()
            self._camera_label.pack(pady=5)

    def _toggle_preview(self) -> None:
        """Toggle the camera preview visibility."""
        self._show_preview = not self._show_preview
        if self._show_preview:
            self._camera_label.pack(pady=5)
        else:
            self._camera_label.pack_forget()
            self._camera_label.configure(image=None, text="Camera preview off")

    # ═══════════════════════════════════════════
    # SESSION STATS
    # ═══════════════════════════════════════════

    def _build_stats_section(self) -> None:
        """Build session statistics display."""
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(
            frame, text="Session Statistics",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=(10, 5))

        stats_grid = ctk.CTkFrame(frame, fg_color="transparent")
        stats_grid.pack(fill="x", padx=15, pady=(0, 10))

        self._time_label = self._make_stat(stats_grid, "Time Monitored", "0:00", 0, 0)
        self._alerts_label = self._make_stat(stats_grid, "Alerts", "0", 0, 1)
        self._streak_label = self._make_stat(stats_grid, "Best Streak", "0:00", 0, 2)

    @staticmethod
    def _make_stat(
        parent: ctk.CTkFrame, title: str, value: str, row: int, col: int
    ) -> ctk.CTkLabel:
        """
        Create a stat display widget.

        Args:
            parent: Parent frame.
            title: Stat title.
            value: Initial value text.
            row: Grid row.
            col: Grid column.

        Returns:
            The value label for later updates.
        """
        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=row, column=col, padx=20, pady=5, sticky="nsew")
        parent.columnconfigure(col, weight=1)

        ctk.CTkLabel(
            cell, text=title,
            font=ctk.CTkFont(size=11), text_color="gray",
        ).pack()

        val_lbl = ctk.CTkLabel(
            cell, text=value,
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        val_lbl.pack()
        return val_lbl

    # ═══════════════════════════════════════════
    # CONTROLS
    # ═══════════════════════════════════════════

    def _build_controls(self) -> None:
        """Build the quick-access control buttons."""
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=8)

        self._monitor_btn = ctk.CTkButton(
            frame, text="▶  Start Monitoring",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40, fg_color=COLOR_GOOD, hover_color="#27ae60",
            command=self.toggle_monitoring,
        )
        self._monitor_btn.pack(fill="x", pady=3)

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=3)

        self._pause_btn = ctk.CTkButton(
            btn_row, text="⏸  Pause (15 min)",
            font=ctk.CTkFont(size=12), height=35,
            fg_color=COLOR_WARNING, hover_color="#e67e22",
            width=150, command=self.snooze,
        )
        self._pause_btn.pack(side="left", expand=True, fill="x", padx=(0, 3))

        ctk.CTkButton(
            btn_row, text="⚙  Settings",
            font=ctk.CTkFont(size=12), height=35,
            fg_color="#7f8c8d", hover_color="#95a5a6",
            width=120, command=self.open_settings,
        ).pack(side="left", expand=True, fill="x", padx=3)

        ctk.CTkButton(
            btn_row, text="🎯  Recalibrate",
            font=ctk.CTkFont(size=12), height=35,
            fg_color=COLOR_ACCENT,
            width=120, command=self.open_calibration,
        ).pack(side="left", expand=True, fill="x", padx=(3, 0))

    # ═══════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════

    def _build_footer(self) -> None:
        """Build the privacy notice footer."""
        ctk.CTkLabel(
            self, text=PRIVACY_NOTE,
            font=ctk.CTkFont(size=10), text_color="gray",
        ).pack(side="bottom", pady=8)

    # ═══════════════════════════════════════════
    # MONITORING LIFECYCLE
    # ═══════════════════════════════════════════

    def toggle_monitoring(self) -> None:
        """Toggle posture monitoring on/off."""
        if self._monitoring:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self) -> None:
        """Start the detection thread and begin monitoring."""
        if self._profile is None:
            self.open_calibration()
            return

        if self._monitoring:
            return

        self._stop_event.clear()
        self._monitoring = True
        self._session_start = time.time()
        self._alert_count = 0
        self._good_streak_start = time.time()
        self._longest_good_streak = 0.0

        self._detection_thread = threading.Thread(
            target=self._detection_loop,
            name="Detection-Thread",
            daemon=True,
        )
        self._detection_thread.start()

        self._monitor_btn.configure(
            text="⏹  Stop Monitoring",
            fg_color=COLOR_BAD, hover_color="#c0392b",
        )
        self._update_header_status("Active", COLOR_GOOD)
        self._schedule_ui_update()
        logger.info("Monitoring started")

    def stop_monitoring(self) -> None:
        """Stop the detection thread."""
        self._stop_event.set()
        self._monitoring = False

        if self._cap is not None:
            self._cap.release()
            self._cap = None

        self._monitor_btn.configure(
            text="▶  Start Monitoring",
            fg_color=COLOR_GOOD, hover_color="#27ae60",
        )
        self._update_header_status("Inactive", COLOR_INACTIVE)
        logger.info("Monitoring stopped")

    def _detection_loop(self) -> None:
        """
        Background detection loop.

        Captures frames, detects landmarks, analyzes posture, and checks
        for alerts. Runs until _stop_event is set.
        """
        try:
            self._cap = cv2.VideoCapture(self._settings.camera_index)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_FRAME_WIDTH)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_FRAME_HEIGHT)
            detector = PoseDetector()
        except Exception:
            logger.exception("Failed to start detection")
            self._monitoring = False
            return

        try:
            self._run_detection(detector)
        except Exception:
            logger.exception("Detection loop error")
        finally:
            detector.close()
            if self._cap is not None:
                self._cap.release()
                self._cap = None

    def _run_detection(self, detector: PoseDetector) -> None:
        """
        Core detection loop body.

        Args:
            detector: Initialized PoseDetector instance.
        """
        while not self._stop_event.is_set():
            if self._cap is None or not self._cap.isOpened():
                break

            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.033)
                continue

            frame = cv2.flip(frame, 1)
            landmarks = detector.detect(frame)

            if landmarks is not None:
                frame = detector.draw_landmarks(frame, landmarks)
                measurements = self._analyzer.compute_measurements(landmarks)
                status = self._evaluate_posture(measurements)
                self._process_alerts(status)
            else:
                with self._lock:
                    self._current_status = STATUS_NO_DETECTION

            with self._lock:
                self._current_frame = frame.copy()

            time.sleep(0.033)

    def _evaluate_posture(self, measurements: Any) -> PostureStatus:
        """
        Evaluate posture against the calibrated baseline.

        Args:
            measurements: Current frame's PostureMeasurements.

        Returns:
            PostureStatus with deviations.
        """
        if self._profile is None:
            with self._lock:
                self._current_status = STATUS_NO_DETECTION
            return PostureStatus(STATUS_GOOD, [], None)

        status = self._analyzer.compare_to_baseline(
            measurements,
            self._profile.baseline_means,
            self._profile.baseline_stds,
            self._profile.sensitivity_multipliers,
        )

        with self._lock:
            self._current_status = status.overall_status

        return status

    def _process_alerts(self, status: PostureStatus) -> None:
        """
        Check for and fire alerts based on posture status.

        Args:
            status: Current posture evaluation.
        """
        alert = self._alert_engine.check(status)
        if alert is not None:
            self._voice_manager.speak_alert(alert)
            self._alert_count += 1

        # Track good posture streak
        if status.overall_status == STATUS_GOOD:
            streak = time.time() - self._good_streak_start
            if streak > self._longest_good_streak:
                self._longest_good_streak = streak
        else:
            self._good_streak_start = time.time()

    # ═══════════════════════════════════════════
    # UI UPDATE LOOP
    # ═══════════════════════════════════════════

    def _schedule_ui_update(self) -> None:
        """Schedule periodic UI updates on the main thread."""
        if not self._monitoring:
            return
        self._update_ui()
        self.after(500, self._schedule_ui_update)

    def _update_ui(self) -> None:
        """Update all dashboard UI elements from current state."""
        with self._lock:
            status = self._current_status
            frame = self._current_frame

        self._update_posture_display(status)
        self._update_stats()

        if self._show_preview and frame is not None:
            self._update_camera_preview(frame)

    def _update_posture_display(self, status: str) -> None:
        """
        Update the posture status indicator.

        Args:
            status: Current posture status string.
        """
        color_map = {
            STATUS_GOOD: COLOR_GOOD,
            STATUS_WARNING: COLOR_WARNING,
            STATUS_BAD: COLOR_BAD,
            STATUS_NO_DETECTION: COLOR_INACTIVE,
        }
        color = color_map.get(status, COLOR_INACTIVE)
        self._posture_label.configure(text=status, text_color=color)

        detail_map = {
            STATUS_GOOD: "Your posture looks great! Keep it up.",
            STATUS_WARNING: "Minor deviation detected. Adjust slightly.",
            STATUS_BAD: "Bad posture detected! Correct your position.",
            STATUS_NO_DETECTION: "No pose detected. Check camera.",
        }
        self._posture_detail.configure(text=detail_map.get(status, ""))

    def _update_stats(self) -> None:
        """Update session statistics labels."""
        if self._session_start > 0:
            elapsed = time.time() - self._session_start
            self._time_label.configure(text=self._format_duration(elapsed))

        self._alerts_label.configure(text=str(self._alert_count))
        self._streak_label.configure(
            text=self._format_duration(self._longest_good_streak)
        )

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """
        Format seconds into M:SS or H:MM:SS string.

        Args:
            seconds: Duration in seconds.

        Returns:
            Formatted time string.
        """
        total = int(seconds)
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def _update_camera_preview(self, frame: np.ndarray) -> None:
        """
        Update the camera preview label with the current frame.

        Args:
            frame: BGR image from the detection thread.
        """
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            img = img.resize(
                (CAMERA_THUMBNAIL_WIDTH, CAMERA_THUMBNAIL_HEIGHT),
                Image.Resampling.LANCZOS,
            )
            photo = ImageTk.PhotoImage(img)
            self._camera_label.configure(image=photo, text="")
            self._camera_label._photo = photo
        except Exception:
            logger.debug("Failed to update camera preview")

    def _update_header_status(self, text: str, color: str) -> None:
        """
        Update the header status indicator.

        Args:
            text: Status text (e.g. "Active", "Paused").
            color: Color for the status dot.
        """
        self._status_text.configure(text=text)
        self._status_dot.configure(text_color=color)

    # ═══════════════════════════════════════════
    # PUBLIC ACTIONS
    # ═══════════════════════════════════════════

    def snooze(self) -> None:
        """Snooze monitoring for 15 minutes."""
        self._alert_engine.snooze(SNOOZE_DURATION_SEC)
        self._update_header_status("Snoozed", COLOR_WARNING)
        logger.info("Monitoring snoozed for 15 minutes")

    def toggle_pause(self) -> None:
        """Toggle pause/resume (used by global hotkey)."""
        if self._alert_engine.is_paused:
            self._alert_engine.resume()
            self._update_header_status("Active", COLOR_GOOD)
        else:
            self._alert_engine.pause()
            self._update_header_status("Paused", COLOR_WARNING)

    def open_settings(self) -> None:
        """Open the settings window."""
        from ui.settings_window import SettingsWindow
        SettingsWindow(
            self,
            settings=self._settings,
            on_save=self._on_settings_saved,
            on_recalibrate=self.open_calibration,
            on_delete_calibration=self._delete_calibration,
            on_test_voice=self._test_voice,
        )

    def open_calibration(self) -> None:
        """Open the calibration wizard."""
        from ui.calibration_screen import CalibrationScreen
        was_monitoring = self._monitoring
        if was_monitoring:
            self.stop_monitoring()

        CalibrationScreen(
            self,
            camera_index=self._settings.camera_index,
            on_complete=lambda result: self._on_calibration_complete(result, was_monitoring),
            on_cancel=lambda: self._on_calibration_cancel(was_monitoring),
        )

    def _on_calibration_complete(self, result: Any, resume: bool) -> None:
        """
        Handle calibration completion.

        Args:
            result: CalibrationResult from the calibration session.
            resume: Whether to resume monitoring after calibration.
        """
        from data.profile_manager import CalibrationProfile

        profile = CalibrationProfile(
            captured_at=result.captured_at,
            baseline_means=result.baseline.means,
            baseline_stds=result.baseline.std_devs,
            sensitivity_multipliers={
                name: 2.0 for name in ALL_MEASUREMENTS
            },
        )

        self._pm.save_profile(profile)
        self._profile = profile
        logger.info("Calibration saved")

        if resume:
            self.start_monitoring()

    def _on_calibration_cancel(self, resume: bool) -> None:
        """
        Handle calibration cancellation.

        Args:
            resume: Whether to resume monitoring.
        """
        if resume and self._profile is not None:
            self.start_monitoring()

    def _on_settings_saved(self, settings: Any) -> None:
        """
        Handle settings save.

        Args:
            settings: Updated AppSettings.
        """
        self._settings = settings
        self._pm.save_settings(settings)
        self._alert_engine.alert_delay = settings.alert_delay_sec
        self._alert_engine.cooldown = settings.cooldown_sec
        self._voice_manager.personality = settings.coach_personality

    def _delete_calibration(self) -> None:
        """Delete calibration data."""
        self._pm.delete_calibration()
        self._profile = None
        self.stop_monitoring()

    def _test_voice(self, personality: str) -> None:
        """
        Test the selected voice personality.

        Args:
            personality: Coach personality key to test.
        """
        old = self._voice_manager.personality
        self._voice_manager.personality = personality
        self._voice_manager.speak_text(
            "This is how I'll sound when I coach you."
        )
        self._voice_manager.personality = old

    # ═══════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════

    def on_closing(self) -> None:
        """Handle window close — minimize to tray instead of quitting."""
        self.withdraw()
        logger.info("Main window hidden to tray")

    def show_window(self) -> None:
        """Show the main window (called from tray icon)."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def quit_app(self) -> None:
        """Fully quit the application."""
        logger.info("Application shutting down")
        self.stop_monitoring()
        self._voice_manager.shutdown()

        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass

        self.destroy()
