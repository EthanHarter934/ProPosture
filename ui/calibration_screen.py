"""
Calibration Panel Module

Embeddable 4-step calibration wizard frame. Guides the user through posture
education, live camera preview with stability tracking, baseline capture,
and confirmation. Designed to be embedded in the main window rather than
opened as a separate toplevel.
"""

import logging
import tkinter as tk
from typing import Any, Callable, Optional

import cv2
import customtkinter as ctk
import numpy as np
from PIL import Image, ImageTk

from constants import (
    ALL_MEASUREMENTS,
    CAMERA_FRAME_HEIGHT,
    CAMERA_FRAME_WIDTH,
    COLOR_ACCENT,
    COLOR_BAD,
    COLOR_GOOD,
    COLOR_WARNING,
    DEFAULT_CAMERA_INDEX,
    MEASUREMENT_DISPLAY_NAMES,
    STABILITY_THRESHOLD,
)
from core.calibration import CalibrationResult, CalibrationSession
from core.pose_detector import PoseDetector
from core.posture_analyzer import PostureAnalyzer

logger = logging.getLogger(__name__)


class CalibrationPanel(ctk.CTkFrame):
    """
    4-step calibration wizard embedded frame.

    Steps:
    1. Posture Education — explains good posture with canvas diagrams
    2. Camera Preview — live feed with landmarks and stability tracking
    3. Baseline Capture — 90-frame capture with progress bar
    4. Confirmation — review results with accept/recapture options
    """

    def __init__(
        self,
        parent: Any,
        camera_index: int = DEFAULT_CAMERA_INDEX,
        on_complete: Optional[Callable[[CalibrationResult], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the calibration panel.

        Args:
            parent: Parent widget.
            camera_index: Webcam device index.
            on_complete: Callback when calibration is accepted.
            on_cancel: Callback when calibration is cancelled/back pressed.
        """
        super().__init__(parent, **kwargs)

        self._camera_index = camera_index
        self._on_complete = on_complete
        self._on_cancel = on_cancel
        self._detector: Optional[PoseDetector] = None
        self._cap: Optional[cv2.VideoCapture] = None
        self._session = CalibrationSession()
        self._result: Optional[CalibrationResult] = None
        self._running = False
        self._current_step = 0

        self._step_frames: list[ctk.CTkFrame] = []
        self._build_steps()
        self._show_step(0)

    def set_camera_index(self, index: int) -> None:
        """
        Update the camera index for future captures.

        Args:
            index: New camera device index.
        """
        self._camera_index = index

    def _build_steps(self) -> None:
        """Build all four step frames."""
        self._step_frames = [
            self._build_education_step(),
            self._build_preview_step(),
            self._build_capture_step(),
            self._build_confirmation_step(),
        ]

    def _show_step(self, step: int) -> None:
        """
        Show the specified step and hide all others.

        Args:
            step: Step index (0-3).
        """
        for i, frame in enumerate(self._step_frames):
            if i == step:
                frame.pack(fill="both", expand=True, padx=10, pady=10)
            else:
                frame.pack_forget()

        self._current_step = step

        if step == 1:
            self._start_camera()
        elif step == 3:
            self._stop_camera()
            self._populate_confirmation()

    def reset_and_start(self) -> None:
        """Reset the calibration flow and show step 1."""
        self._stop_camera()
        self._session.reset()
        self._result = None
        self._show_step(0)

    # ═══════════════════════════════════════════
    # STEP 1: POSTURE EDUCATION
    # ═══════════════════════════════════════════

    def _build_education_step(self) -> ctk.CTkFrame:
        """Build the posture education frame with canvas diagrams."""
        frame = ctk.CTkFrame(self)

        # Header with cancel/back button
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=5, pady=(5, 0))
        ctk.CTkButton(
            header, text="←  Back to Dashboard", width=160,
            font=ctk.CTkFont(size=13), fg_color="#7f8c8d",
            hover_color="#95a5a6", command=self._on_back,
        ).pack(side="left")

        title = ctk.CTkLabel(
            frame, text="Understanding Good Posture",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title.pack(pady=(10, 5))

        subtitle = ctk.CTkLabel(
            frame,
            text="Before calibrating, let's make sure you know what good posture looks like.",
            font=ctk.CTkFont(size=13), text_color="gray",
        )
        subtitle.pack(pady=(0, 10))

        # Canvas for stick figures
        canvas_frame = ctk.CTkFrame(frame, fg_color="transparent")
        canvas_frame.pack(fill="x", padx=20, pady=5)

        self._education_canvas = tk.Canvas(
            canvas_frame, width=680, height=200,
            bg="#2b2b2b", highlightthickness=0,
        )
        self._education_canvas.pack()
        self._draw_posture_diagrams()

        # Education text
        tips = [
            "✓  Ears directly above your shoulders",
            "✓  Shoulders level and relaxed — not hunched up",
            "✓  Spine in a neutral position, sitting back in your chair",
            "✓  Screen at eye level so you don't look down",
            "✓  Feet flat on the floor",
        ]
        for tip in tips:
            ctk.CTkLabel(
                frame, text=tip,
                font=ctk.CTkFont(size=14), anchor="w",
            ).pack(fill="x", padx=40, pady=2)

        warning_text = (
            "⚠️  Take a moment to adjust your chair, monitor height, and keyboard "
            "position BEFORE continuing. The posture you hold during calibration "
            "is what the app will try to maintain."
        )
        ctk.CTkLabel(
            frame, text=warning_text,
            font=ctk.CTkFont(size=12), text_color="#f39c12",
            wraplength=620, justify="left",
        ).pack(fill="x", padx=40, pady=(15, 10))

        ctk.CTkButton(
            frame, text="I've adjusted my setup — Continue",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=45, fg_color=COLOR_ACCENT,
            command=lambda: self._show_step(1),
        ).pack(pady=(10, 5))

        return frame

    def _draw_posture_diagrams(self) -> None:
        """Draw good vs bad posture stick figures on the education canvas."""
        c = self._education_canvas
        self._draw_good_posture(c, 170, 180)
        self._draw_bad_posture(c, 510, 180)

        c.create_text(170, 15, text="✓ Good Posture",
                      fill="#2ecc71", font=("Arial", 13, "bold"))
        c.create_text(510, 15, text="✗ Bad Posture",
                      fill="#e74c3c", font=("Arial", 13, "bold"))

    @staticmethod
    def _draw_good_posture(c: tk.Canvas, cx: int, base_y: int) -> None:
        """Draw a stick figure with good posture."""
        color = "#2ecc71"
        c.create_oval(cx-12, base_y-155, cx+12, base_y-131, outline=color, width=2)
        c.create_line(cx, base_y-131, cx, base_y-60, fill=color, width=2)
        c.create_line(cx-30, base_y-115, cx+30, base_y-115, fill=color, width=2)
        c.create_oval(cx-17, base_y-148, cx-13, base_y-142, outline=color, width=2)
        c.create_oval(cx+13, base_y-148, cx+17, base_y-142, outline=color, width=2)
        c.create_line(cx, base_y-60, cx-20, base_y-10, fill=color, width=2)
        c.create_line(cx, base_y-60, cx+20, base_y-10, fill=color, width=2)
        c.create_line(cx-35, base_y-60, cx+35, base_y-60, fill="#555", width=1)
        c.create_line(cx+35, base_y-60, cx+35, base_y-130, fill="#555", width=1)

    @staticmethod
    def _draw_bad_posture(c: tk.Canvas, cx: int, base_y: int) -> None:
        """Draw a stick figure with bad posture (forward head, uneven shoulders)."""
        color = "#e74c3c"
        c.create_oval(cx+15, base_y-145, cx+39, base_y-121, outline=color, width=2)
        c.create_line(cx, base_y-60, cx+5, base_y-90,
                      cx+15, base_y-110, cx+27, base_y-121,
                      fill=color, width=2, smooth=True)
        c.create_line(cx-25, base_y-108, cx+30, base_y-115, fill=color, width=2)
        c.create_line(cx, base_y-60, cx-20, base_y-10, fill=color, width=2)
        c.create_line(cx, base_y-60, cx+20, base_y-10, fill=color, width=2)
        c.create_line(cx-35, base_y-60, cx+35, base_y-60, fill="#555", width=1)
        c.create_line(cx+35, base_y-60, cx+35, base_y-130, fill="#555", width=1)

    # ═══════════════════════════════════════════
    # STEP 2: CAMERA PREVIEW
    # ═══════════════════════════════════════════

    def _build_preview_step(self) -> ctk.CTkFrame:
        """Build the camera preview frame with landmark overlay."""
        frame = ctk.CTkFrame(self)

        title = ctk.CTkLabel(
            frame, text="Camera Preview — Hold Good Posture",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        title.pack(pady=(10, 5))

        self._camera_label = ctk.CTkLabel(frame, text="Starting camera...")
        self._camera_label.pack(pady=5)

        # Measurements readout
        self._measures_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self._measures_frame.pack(fill="x", padx=20, pady=5)

        self._measure_labels: dict[str, ctk.CTkLabel] = {}
        for name in ALL_MEASUREMENTS:
            row = ctk.CTkFrame(self._measures_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(
                row, text=f"{MEASUREMENT_DISPLAY_NAMES[name]}:",
                font=ctk.CTkFont(size=12), width=160, anchor="w",
            ).pack(side="left")
            lbl_val = ctk.CTkLabel(
                row, text="—", font=ctk.CTkFont(size=12, weight="bold"),
                width=100, anchor="w",
            )
            lbl_val.pack(side="left")
            self._measure_labels[name] = lbl_val

        # Stability bar
        stab_frame = ctk.CTkFrame(frame, fg_color="transparent")
        stab_frame.pack(fill="x", padx=20, pady=(5, 2))
        ctk.CTkLabel(stab_frame, text="Stability:",
                     font=ctk.CTkFont(size=13)).pack(side="left")
        self._stability_bar = ctk.CTkProgressBar(stab_frame, width=300)
        self._stability_bar.pack(side="left", padx=10)
        self._stability_bar.set(0)
        self._stability_label = ctk.CTkLabel(
            stab_frame, text="0%", font=ctk.CTkFont(size=12),
        )
        self._stability_label.pack(side="left")

        # Checklist
        checklist_items = [
            "Shoulders level and relaxed",
            "Ears directly above shoulders",
            "Screen at eye level",
            "Sitting back in chair (not perched on edge)",
            "Feet flat on floor",
        ]
        check_frame = ctk.CTkFrame(frame, fg_color="transparent")
        check_frame.pack(fill="x", padx=30, pady=5)
        for item in checklist_items:
            ctk.CTkLabel(
                check_frame, text=f"  ☐  {item}",
                font=ctk.CTkFont(size=11), anchor="w",
            ).pack(fill="x")

        self._capture_btn = ctk.CTkButton(
            frame, text="Capture Baseline",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=42, fg_color=COLOR_ACCENT,
            state="disabled", command=self._start_capture,
        )
        self._capture_btn.pack(pady=(8, 5))

        return frame

    # ═══════════════════════════════════════════
    # STEP 3: CAPTURE IN PROGRESS
    # ═══════════════════════════════════════════

    def _build_capture_step(self) -> ctk.CTkFrame:
        """Build the capture-in-progress frame."""
        frame = ctk.CTkFrame(self)

        ctk.CTkLabel(
            frame, text="Capturing Baseline...",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(30, 10))

        ctk.CTkLabel(
            frame, text="Hold still! Capturing 90 frames (3 seconds).",
            font=ctk.CTkFont(size=14), text_color="gray",
        ).pack(pady=(0, 20))

        self._capture_camera_label = ctk.CTkLabel(frame, text="")
        self._capture_camera_label.pack(pady=5)

        self._capture_progress = ctk.CTkProgressBar(frame, width=400)
        self._capture_progress.pack(pady=15)
        self._capture_progress.set(0)

        self._capture_percent = ctk.CTkLabel(
            frame, text="0%", font=ctk.CTkFont(size=16, weight="bold"),
        )
        self._capture_percent.pack()

        return frame

    # ═══════════════════════════════════════════
    # STEP 4: CONFIRMATION
    # ═══════════════════════════════════════════

    def _build_confirmation_step(self) -> ctk.CTkFrame:
        """Build the confirmation frame with quality report."""
        frame = ctk.CTkFrame(self)

        ctk.CTkLabel(
            frame, text="Calibration Complete",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(20, 10))

        self._quality_label = ctk.CTkLabel(
            frame, text="", font=ctk.CTkFont(size=14), wraplength=600,
        )
        self._quality_label.pack(pady=5)

        self._results_frame = ctk.CTkFrame(frame)
        self._results_frame.pack(fill="x", padx=30, pady=10)

        self._warning_label = ctk.CTkLabel(
            frame, text="", font=ctk.CTkFont(size=12),
            text_color=COLOR_WARNING, wraplength=600,
        )
        self._warning_label.pack(pady=5)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=15)

        ctk.CTkButton(
            btn_frame, text="Accept Baseline",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_GOOD, hover_color="#27ae60",
            width=160, height=40, command=self._accept,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame, text="Recapture",
            font=ctk.CTkFont(size=14),
            fg_color=COLOR_WARNING, hover_color="#e67e22",
            width=140, height=40, command=self._recapture,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame, text="Adjust & Recapture",
            font=ctk.CTkFont(size=14),
            fg_color="#7f8c8d", hover_color="#95a5a6",
            width=160, height=40,
            command=lambda: self._show_step(0),
        ).pack(side="left", padx=8)

        return frame

    def _populate_confirmation(self) -> None:
        """Fill the confirmation step with captured baseline data."""
        if self._result is None:
            return

        quality = self._result.quality
        if quality.is_acceptable:
            self._quality_label.configure(
                text="✅ Capture quality is good! Your baseline looks stable.",
                text_color=COLOR_GOOD,
            )
        else:
            self._quality_label.configure(
                text="⚠️ Some measurements had high variance. Consider recapturing.",
                text_color=COLOR_WARNING,
            )

        for widget in self._results_frame.winfo_children():
            widget.destroy()

        header = ctk.CTkFrame(self._results_frame, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(header, text="Measurement", width=180,
                     font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(side="left")
        ctk.CTkLabel(header, text="Mean", width=100,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        ctk.CTkLabel(header, text="Std Dev", width=100,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        ctk.CTkLabel(header, text="Quality", width=80,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")

        for name in ALL_MEASUREMENTS:
            mean, std, is_ok = quality.per_measurement[name]
            row = ctk.CTkFrame(self._results_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(row, text=MEASUREMENT_DISPLAY_NAMES[name],
                         width=180, anchor="w",
                         font=ctk.CTkFont(size=12)).pack(side="left")
            ctk.CTkLabel(row, text=f"{mean:.3f}", width=100,
                         font=ctk.CTkFont(size=12)).pack(side="left")
            ctk.CTkLabel(row, text=f"{std:.3f}", width=100,
                         font=ctk.CTkFont(size=12)).pack(side="left")
            status_text = "✓" if is_ok else "⚠"
            status_color = COLOR_GOOD if is_ok else COLOR_WARNING
            ctk.CTkLabel(row, text=status_text, width=80,
                         font=ctk.CTkFont(size=14),
                         text_color=status_color).pack(side="left")

        warnings_text = "\n".join(quality.warnings) if quality.warnings else ""
        self._warning_label.configure(text=warnings_text)

    # ═══════════════════════════════════════════
    # CAMERA MANAGEMENT
    # ═══════════════════════════════════════════

    def _start_camera(self) -> None:
        """Start the camera feed and detection loop."""
        if self._running:
            return

        try:
            import sys
            if sys.platform == "win32":
                self._cap = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
            else:
                self._cap = cv2.VideoCapture(self._camera_index)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_FRAME_WIDTH)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_FRAME_HEIGHT)
            self._detector = PoseDetector()
            self._session.reset()
            self._running = True
            self._update_camera()
            logger.info("Calibration camera started")
        except Exception:
            logger.exception("Failed to start calibration camera")

    def _stop_camera(self) -> None:
        """Stop the camera feed and release resources."""
        self._running = False
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        if self._detector is not None:
            self._detector.close()
            self._detector = None
        logger.info("Calibration camera stopped")

    def _update_camera(self) -> None:
        """Read a frame, process it, and schedule the next update."""
        if not self._running or self._cap is None:
            return

        ret, frame = self._cap.read()
        if not ret:
            self.after(5, self._update_camera)
            return

        frame = cv2.flip(frame, 1)
        landmarks = self._detector.detect(frame) if self._detector else None

        if landmarks is not None:
            frame = self._detector.draw_landmarks(frame, landmarks)
            measurements = PostureAnalyzer.compute_measurements(landmarks)
            self._session.add_frame(measurements)
            self._update_measurement_display(measurements)
            self._update_stability_display()

            if self._session.is_capturing and self._session.capture_complete:
                self._finish_capture()

        self._display_frame(frame)
        self.after(5, self._update_camera)

    def _display_frame(self, frame: np.ndarray) -> None:
        """Convert an OpenCV frame and display it in the appropriate label."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        photo = ctk.CTkImage(light_image=img, size=(480, 360))

        target_label = (
            self._capture_camera_label
            if self._current_step == 2
            else self._camera_label
        )
        target_label.configure(image=photo, text="")
        target_label._photo = photo  # Prevent garbage collection

    def _update_measurement_display(self, measurements: Any) -> None:
        """Update the measurement value labels."""
        values = measurements.to_dict()
        for name, label in self._measure_labels.items():
            label.configure(text=f"{values[name]:.3f}")

    def _update_stability_display(self) -> None:
        """Update the stability bar and capture button state."""
        score = self._session.get_stability_score()
        self._stability_bar.set(score)
        self._stability_label.configure(text=f"{int(score * 100)}%")

        if score >= STABILITY_THRESHOLD and not self._session.is_capturing:
            self._capture_btn.configure(state="normal")
        elif not self._session.is_capturing:
            self._capture_btn.configure(state="disabled")

    # ═══════════════════════════════════════════
    # CAPTURE FLOW
    # ═══════════════════════════════════════════

    def _start_capture(self) -> None:
        """Begin the 90-frame baseline capture."""
        self._session.start_capture()
        self._show_step(2)
        self._update_capture_progress()

    def _update_capture_progress(self) -> None:
        """Update the capture progress bar."""
        if not self._session.is_capturing:
            return

        progress = self._session.capture_progress
        self._capture_progress.set(progress)
        self._capture_percent.configure(text=f"{int(progress * 100)}%")

        if not self._session.capture_complete:
            self.after(100, self._update_capture_progress)

    def _finish_capture(self) -> None:
        """Complete the capture and show the confirmation step."""
        self._result = self._session.finish_capture()
        if self._result is not None:
            self._show_step(3)
        else:
            logger.error("Capture failed — not enough frames")
            self._show_step(1)

    def _accept(self) -> None:
        """Accept the calibration and return to dashboard."""
        if self._result is not None and self._on_complete:
            self._on_complete(self._result)
        self._stop_camera()

    def _recapture(self) -> None:
        """Return to the camera preview to recapture."""
        self._session.reset()
        self._result = None
        self._show_step(1)

    def _on_back(self) -> None:
        """Handle back button — return to dashboard."""
        self._stop_camera()
        if self._on_cancel:
            self._on_cancel()

    def cleanup(self) -> None:
        """Stop camera and release resources (call when hiding panel)."""
        self._stop_camera()
