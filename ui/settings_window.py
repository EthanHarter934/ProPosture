"""
Settings Panel Module

Embeddable settings frame that provides controls for coach personality,
sensitivity multipliers, alert timing, camera selection, appearance,
and startup configuration. Designed to be embedded in the main window
rather than opened as a separate toplevel. All changes persist immediately.
"""

import logging
from typing import Any, Callable, Optional

import customtkinter as ctk

from constants import (
    ALL_MEASUREMENTS,
    COACH_DRILL_SERGEANT,
    COACH_STANDARD,
    COLOR_ACCENT,
    COLOR_BAD,
    COLOR_WARNING,
    DEFAULT_ALERT_DELAY_SEC,
    DEFAULT_COOLDOWN_SEC,
    DEFAULT_SENSITIVITY_MULTIPLIER,
    MAX_ALERT_DELAY_SEC,
    MAX_COOLDOWN_SEC,
    MAX_SENSITIVITY_MULTIPLIER,
    MEASUREMENT_DISPLAY_NAMES,
    MIN_ALERT_DELAY_SEC,
    MIN_COOLDOWN_SEC,
    MIN_SENSITIVITY_MULTIPLIER,
)
from core.startup import (
    get_startup_label,
    is_startup_supported,
    set_launch_at_startup,
)
from data.profile_manager import AppSettings, CalibrationProfile

logger = logging.getLogger(__name__)


class SettingsPanel(ctk.CTkFrame):
    """
    Embeddable settings frame.

    Provides controls for all user-adjustable settings including coach
    personality, sensitivity, timing, camera, appearance, and startup.
    Designed to sit inside the main window's content area.
    """

    def __init__(
        self,
        parent: Any,
        settings: AppSettings,
        profile: Optional[CalibrationProfile] = None,
        on_save: Optional[Callable[[AppSettings], None]] = None,
        on_profile_save: Optional[Callable[[CalibrationProfile], None]] = None,
        on_recalibrate: Optional[Callable[[], None]] = None,
        on_delete_calibration: Optional[Callable[[], None]] = None,
        on_test_voice: Optional[Callable[[str], None]] = None,
        on_back: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the settings panel.

        Args:
            parent: Parent widget.
            settings: Current application settings.
            profile: Current calibration profile (for sensitivity multipliers).
            on_save: Callback when settings change.
            on_profile_save: Callback when sensitivity multipliers change.
            on_recalibrate: Callback for recalibrate button.
            on_delete_calibration: Callback for delete calibration button.
            on_test_voice: Callback for test voice button.
            on_back: Callback to return to dashboard.
        """
        super().__init__(parent, **kwargs)

        self._settings = settings
        self._profile = profile
        self._on_save = on_save
        self._on_profile_save = on_profile_save
        self._on_recalibrate = on_recalibrate
        self._on_delete_calibration = on_delete_calibration
        self._on_test_voice = on_test_voice
        self._on_back = on_back

        self._sensitivity_sliders: dict[str, ctk.CTkSlider] = {}
        self._sensitivity_labels: dict[str, ctk.CTkLabel] = {}

        self._build_ui()

    def update_refs(
        self, settings: AppSettings, profile: Optional[CalibrationProfile]
    ) -> None:
        """
        Update the settings and profile references (called when re-shown).

        Args:
            settings: Current app settings.
            profile: Current calibration profile.
        """
        self._settings = settings
        self._profile = profile
        self._refresh_ui_values()

    def _refresh_ui_values(self) -> None:
        """Refresh all UI widget values from current settings."""
        self._coach_var.set(self._settings.coach_personality)
        self._delay_slider.set(self._settings.alert_delay_sec)
        self._delay_label.configure(text=f"{self._settings.alert_delay_sec:.0f}s")
        self._cooldown_slider.set(self._settings.cooldown_sec)
        self._cooldown_label.configure(text=f"{self._settings.cooldown_sec:.0f}s")
        self._camera_var.set(str(self._settings.camera_index))
        self._theme_var.set("Dark" if self._settings.dark_mode else "Light")
        self._startup_var.set(self._settings.launch_at_startup)

        if self._profile is not None:
            for name in ALL_MEASUREMENTS:
                val = self._profile.sensitivity_multipliers.get(
                    name, DEFAULT_SENSITIVITY_MULTIPLIER
                )
                if name in self._sensitivity_sliders:
                    self._sensitivity_sliders[name].set(val)
                if name in self._sensitivity_labels:
                    self._sensitivity_labels[name].configure(text=f"{val:.1f}")

    def _build_ui(self) -> None:
        """Build the full settings UI."""
        # Header with back button
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkButton(
            header, text="←  Back to Dashboard", width=160,
            font=ctk.CTkFont(size=13), fg_color="#7f8c8d",
            hover_color="#95a5a6", command=self._go_back,
        ).pack(side="left")

        ctk.CTkLabel(
            header, text="Settings",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(side="left", padx=15)

        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._build_coach_section(scroll)
        self._build_sensitivity_section(scroll)
        self._build_timing_section(scroll)
        self._build_camera_section(scroll)
        self._build_appearance_section(scroll)
        self._build_startup_section(scroll)
        self._build_actions_section(scroll)

    def _go_back(self) -> None:
        """Navigate back to the dashboard."""
        if self._on_back:
            self._on_back()

    # ═══════════════════════════════════════════
    # COACH PERSONALITY
    # ═══════════════════════════════════════════

    def _build_coach_section(self, parent: ctk.CTkFrame) -> None:
        """Build coach personality selector with test button."""
        section = self._make_section(parent, "🎙️  Coach Personality")

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", pady=5)

        self._coach_var = ctk.StringVar(value=self._settings.coach_personality)
        ctk.CTkOptionMenu(
            row, variable=self._coach_var,
            values=["standard", "drill_sergeant"],
            command=self._on_coach_change, width=200,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            row, text="Test Voice", width=100,
            fg_color=COLOR_ACCENT, command=self._test_voice,
        ).pack(side="left")

    def _on_coach_change(self, value: str) -> None:
        """Handle coach personality selection change."""
        self._settings.coach_personality = value
        self._save()

    def _test_voice(self) -> None:
        """Fire the test voice callback."""
        if self._on_test_voice:
            self._on_test_voice(self._coach_var.get())

    # ═══════════════════════════════════════════
    # SENSITIVITY SLIDERS
    # ═══════════════════════════════════════════

    def _build_sensitivity_section(self, parent: ctk.CTkFrame) -> None:
        """Build sensitivity multiplier sliders for each measurement."""
        section = self._make_section(parent, "🎚️  Sensitivity (Std Dev Multiplier)")

        ctk.CTkLabel(
            section,
            text="Lower = more sensitive (alerts sooner).  Range: 1.0 – 4.0",
            font=ctk.CTkFont(size=11), text_color="gray",
        ).pack(anchor="w", pady=(0, 5))

        for name in ALL_MEASUREMENTS:
            current_val = DEFAULT_SENSITIVITY_MULTIPLIER
            if self._profile is not None:
                current_val = self._profile.sensitivity_multipliers.get(
                    name, DEFAULT_SENSITIVITY_MULTIPLIER
                )
            self._build_slider_row(
                section, name, MEASUREMENT_DISPLAY_NAMES[name],
                MIN_SENSITIVITY_MULTIPLIER, MAX_SENSITIVITY_MULTIPLIER,
                current_val, self._on_sensitivity_change,
            )

    def _on_sensitivity_change(self, name: str, value: float) -> None:
        """Handle sensitivity slider change and persist to profile."""
        rounded = round(value, 1)
        if name in self._sensitivity_labels:
            self._sensitivity_labels[name].configure(text=f"{rounded:.1f}")

        # Update profile multipliers and save
        if self._profile is not None:
            self._profile.sensitivity_multipliers[name] = rounded
            if self._on_profile_save:
                self._on_profile_save(self._profile)

    # ═══════════════════════════════════════════
    # TIMING SLIDERS
    # ═══════════════════════════════════════════

    def _build_timing_section(self, parent: ctk.CTkFrame) -> None:
        """Build alert delay and cooldown sliders."""
        section = self._make_section(parent, "⏱️  Alert Timing")

        row_delay = ctk.CTkFrame(section, fg_color="transparent")
        row_delay.pack(fill="x", pady=5)
        ctk.CTkLabel(row_delay, text="Alert Delay (sec):", width=160,
                     anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")

        self._delay_label = ctk.CTkLabel(
            row_delay, text=f"{self._settings.alert_delay_sec:.0f}s",
            width=50, font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._delay_slider = ctk.CTkSlider(
            row_delay, from_=MIN_ALERT_DELAY_SEC, to=MAX_ALERT_DELAY_SEC,
            number_of_steps=int(MAX_ALERT_DELAY_SEC - MIN_ALERT_DELAY_SEC),
            command=self._on_delay_change, width=200,
        )
        self._delay_slider.set(self._settings.alert_delay_sec)
        self._delay_slider.pack(side="left", padx=5)
        self._delay_label.pack(side="left")

        row_cool = ctk.CTkFrame(section, fg_color="transparent")
        row_cool.pack(fill="x", pady=5)
        ctk.CTkLabel(row_cool, text="Cooldown (sec):", width=160,
                     anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")

        self._cooldown_label = ctk.CTkLabel(
            row_cool, text=f"{self._settings.cooldown_sec:.0f}s",
            width=50, font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._cooldown_slider = ctk.CTkSlider(
            row_cool, from_=MIN_COOLDOWN_SEC, to=MAX_COOLDOWN_SEC,
            number_of_steps=int((MAX_COOLDOWN_SEC - MIN_COOLDOWN_SEC) / 5),
            command=self._on_cooldown_change, width=200,
        )
        self._cooldown_slider.set(self._settings.cooldown_sec)
        self._cooldown_slider.pack(side="left", padx=5)
        self._cooldown_label.pack(side="left")

    def _on_delay_change(self, value: float) -> None:
        """Handle alert delay slider change."""
        val = int(round(value))
        self._delay_label.configure(text=f"{val}s")
        self._settings.alert_delay_sec = float(val)
        self._save()

    def _on_cooldown_change(self, value: float) -> None:
        """Handle cooldown slider change."""
        val = int(round(value))
        self._cooldown_label.configure(text=f"{val}s")
        self._settings.cooldown_sec = float(val)
        self._save()

    # ═══════════════════════════════════════════
    # CAMERA
    # ═══════════════════════════════════════════

    def _build_camera_section(self, parent: ctk.CTkFrame) -> None:
        """Build camera selector dropdown."""
        section = self._make_section(parent, "📷  Camera")

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text="Camera Index:", width=120,
                     anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")

        cam_values = [str(i) for i in range(5)]
        self._camera_var = ctk.StringVar(value=str(self._settings.camera_index))
        ctk.CTkOptionMenu(
            row, variable=self._camera_var,
            values=cam_values,
            command=self._on_camera_change, width=100,
        ).pack(side="left")

    def _on_camera_change(self, value: str) -> None:
        """Handle camera selection change."""
        self._settings.camera_index = int(value)
        self._save()

    # ═══════════════════════════════════════════
    # APPEARANCE
    # ═══════════════════════════════════════════

    def _build_appearance_section(self, parent: ctk.CTkFrame) -> None:
        """Build dark/light mode toggle."""
        section = self._make_section(parent, "🎨  Appearance")

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text="Theme:", width=120,
                     anchor="w", font=ctk.CTkFont(size=13)).pack(side="left")

        self._theme_var = ctk.StringVar(
            value="Dark" if self._settings.dark_mode else "Light"
        )
        ctk.CTkOptionMenu(
            row, variable=self._theme_var,
            values=["Dark", "Light"],
            command=self._on_theme_change, width=100,
        ).pack(side="left")

    def _on_theme_change(self, value: str) -> None:
        """Handle theme toggle."""
        self._settings.dark_mode = (value == "Dark")
        ctk.set_appearance_mode("dark" if self._settings.dark_mode else "light")
        self._save()

    # ═══════════════════════════════════════════
    # STARTUP
    # ═══════════════════════════════════════════

    def _build_startup_section(self, parent: ctk.CTkFrame) -> None:
        """Build launch at startup checkbox."""
        section = self._make_section(parent, "🚀  Startup")

        self._startup_var = ctk.BooleanVar(value=self._settings.launch_at_startup)
        ctk.CTkCheckBox(
            section,
            text=f"Launch at {get_startup_label()}",
            variable=self._startup_var,
            command=self._on_startup_change,
            font=ctk.CTkFont(size=13),
            state="normal" if is_startup_supported() else "disabled",
        ).pack(anchor="w", pady=5)

    def _on_startup_change(self) -> None:
        """Handle startup checkbox change."""
        enabled = self._startup_var.get()
        if not set_launch_at_startup(enabled):
            self._startup_var.set(False)
            enabled = False
        self._settings.launch_at_startup = enabled
        self._save()

    # ═══════════════════════════════════════════
    # ACTION BUTTONS
    # ═══════════════════════════════════════════

    def _build_actions_section(self, parent: ctk.CTkFrame) -> None:
        """Build reset/recalibrate action buttons."""
        section = self._make_section(parent, "⚙️  Actions")

        row1 = ctk.CTkFrame(section, fg_color="transparent")
        row1.pack(fill="x", pady=5)

        ctk.CTkButton(
            row1, text="Reset to Defaults", width=180,
            fg_color="#7f8c8d", hover_color="#95a5a6",
            command=self._reset_defaults,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            row1, text="Recalibrate", width=140,
            fg_color=COLOR_ACCENT, command=self._recalibrate,
        ).pack(side="left")

        row2 = ctk.CTkFrame(section, fg_color="transparent")
        row2.pack(fill="x", pady=5)

        ctk.CTkButton(
            row2, text="Delete Calibration & Recalibrate", width=280,
            fg_color=COLOR_BAD, hover_color="#c0392b",
            command=self._delete_and_recalibrate,
        ).pack(side="left")

    def _reset_defaults(self) -> None:
        """Reset all settings to defaults."""
        if self._settings.launch_at_startup:
            set_launch_at_startup(False)

        self._settings = AppSettings()
        self._refresh_ui_values()
        self._save()

    def _recalibrate(self) -> None:
        """Trigger recalibration."""
        if self._on_recalibrate:
            self._on_recalibrate()

    def _delete_and_recalibrate(self) -> None:
        """Delete calibration data and trigger recalibration."""
        if self._on_delete_calibration:
            self._on_delete_calibration()
        if self._on_recalibrate:
            self._on_recalibrate()

    # ═══════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════

    @staticmethod
    def _make_section(parent: ctk.CTkFrame, title: str) -> ctk.CTkFrame:
        """
        Create a labeled section frame.

        Args:
            parent: Parent frame.
            title: Section title text.

        Returns:
            The content frame inside the section.
        """
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", pady=(0, 10), padx=5)

        ctk.CTkLabel(
            frame, text=title,
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(8, 2))

        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.pack(fill="x", padx=15, pady=(0, 8))
        return content

    def _build_slider_row(
        self,
        parent: ctk.CTkFrame,
        name: str,
        display_name: str,
        min_val: float,
        max_val: float,
        current: float,
        callback: Callable,
    ) -> None:
        """
        Build a labeled slider row.

        Args:
            parent: Parent frame.
            name: Internal measurement name.
            display_name: Human-readable label.
            min_val: Slider minimum.
            max_val: Slider maximum.
            current: Current value.
            callback: Function to call on change.
        """
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=3)

        ctk.CTkLabel(row, text=f"{display_name}:", width=160,
                     anchor="w", font=ctk.CTkFont(size=12)).pack(side="left")

        val_label = ctk.CTkLabel(
            row, text=f"{current:.1f}", width=40,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._sensitivity_labels[name] = val_label

        slider = ctk.CTkSlider(
            row, from_=min_val, to=max_val,
            number_of_steps=int((max_val - min_val) * 10),
            command=lambda v, n=name: callback(n, v), width=180,
        )
        slider.set(current)
        self._sensitivity_sliders[name] = slider

        slider.pack(side="left", padx=5)
        val_label.pack(side="left")

    def _save(self) -> None:
        """Persist current settings via the save callback."""
        if self._on_save:
            self._on_save(self._settings)
