"""
Alert Engine Module

Runs threshold checks against the calibrated baseline, tracks how long
bad posture has persisted, enforces cooldown between alerts, and fires
alerts with specific reasons. Thread-safe via internal locks.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

from constants import (
    ALL_MEASUREMENTS,
    DEFAULT_ALERT_DELAY_SEC,
    DEFAULT_COOLDOWN_SEC,
    MEASUREMENT_DISPLAY_NAMES,
    STATUS_BAD,
)
from core.posture_analyzer import PostureStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Alert:
    """
    A posture alert ready to be spoken.

    Attributes:
        reason: Human-readable description of the issue.
        measurement_name: The measurement key that triggered it.
        severity: How far beyond threshold (1.0 = at threshold, 2.0 = 2x).
    """

    reason: str
    measurement_name: str
    severity: float


class AlertEngine:
    """
    Monitors posture status and fires alerts when bad posture persists.

    Tracks continuous bad-posture duration per measurement, enforces a
    configurable delay before the first alert, and enforces a cooldown
    between subsequent alerts. All methods are thread-safe.
    """

    def __init__(
        self,
        alert_delay: float = DEFAULT_ALERT_DELAY_SEC,
        cooldown: float = DEFAULT_COOLDOWN_SEC,
    ) -> None:
        """
        Initialize the alert engine.

        Args:
            alert_delay: Seconds of continuous bad posture before alerting.
            cooldown: Minimum seconds between consecutive alerts.
        """
        self._lock = threading.Lock()
        self._alert_delay = alert_delay
        self._cooldown = cooldown
        self._bad_start_times: dict[str, Optional[float]] = {
            m: None for m in ALL_MEASUREMENTS
        }
        self._last_alert_time: float = 0.0
        self._paused = threading.Event()
        self._paused.set()  # Start in "not paused" state (set = active)
        self._snooze_until: float = 0.0
        logger.info(
            "AlertEngine initialized: delay=%.1fs, cooldown=%.1fs",
            alert_delay, cooldown,
        )

    @property
    def alert_delay(self) -> float:
        """Current alert delay in seconds."""
        with self._lock:
            return self._alert_delay

    @alert_delay.setter
    def alert_delay(self, value: float) -> None:
        """Set the alert delay in seconds."""
        with self._lock:
            self._alert_delay = value

    @property
    def cooldown(self) -> float:
        """Current cooldown in seconds."""
        with self._lock:
            return self._cooldown

    @cooldown.setter
    def cooldown(self, value: float) -> None:
        """Set the cooldown in seconds."""
        with self._lock:
            self._cooldown = value

    def check(self, status: PostureStatus) -> Optional[Alert]:
        """
        Check if an alert should be fired based on the current posture status.

        Args:
            status: The current PostureStatus from the analyzer.

        Returns:
            An Alert if bad posture has persisted long enough and cooldown
            has elapsed, otherwise None.
        """
        if not self._is_active():
            return None

        with self._lock:
            now = time.time()
            self._update_bad_timers(status, now)

            if not self._cooldown_elapsed(now):
                return None

            return self._find_triggered_alert(now)

    def _is_active(self) -> bool:
        """
        Check if the engine is active (not paused and not snoozed).

        Returns:
            True if alerts should be evaluated.
        """
        if not self._paused.is_set():
            return False

        with self._lock:
            if time.time() < self._snooze_until:
                return False

        return True

    def _update_bad_timers(self, status: PostureStatus, now: float) -> None:
        """
        Update the per-measurement bad-posture timers.

        Args:
            status: Current posture status.
            now: Current timestamp.
        """
        for dev in status.deviations:
            name = dev.measurement_name
            if dev.deviation_ratio >= 1.0:
                # Bad posture for this measurement
                if self._bad_start_times[name] is None:
                    self._bad_start_times[name] = now
            else:
                # Good posture — reset timer
                self._bad_start_times[name] = None

    def _cooldown_elapsed(self, now: float) -> bool:
        """
        Check if enough time has passed since the last alert.

        Args:
            now: Current timestamp.

        Returns:
            True if cooldown has elapsed.
        """
        return (now - self._last_alert_time) >= self._cooldown

    def _find_triggered_alert(self, now: float) -> Optional[Alert]:
        """
        Find the measurement that has been bad longest past the delay.

        Args:
            now: Current timestamp.

        Returns:
            Alert for the worst measurement, or None if nothing triggers.
        """
        worst_name: Optional[str] = None
        worst_duration: float = 0.0
        worst_severity: float = 0.0

        for name in ALL_MEASUREMENTS:
            start = self._bad_start_times[name]
            if start is None:
                continue

            duration = now - start
            if duration >= self._alert_delay and duration > worst_duration:
                worst_name = name
                worst_duration = duration

        if worst_name is None:
            return None

        # Record alert time and reset the timer for this measurement
        self._last_alert_time = now
        self._bad_start_times[worst_name] = None

        display_name = MEASUREMENT_DISPLAY_NAMES.get(worst_name, worst_name)
        reason = self._build_reason(worst_name)

        alert = Alert(
            reason=reason,
            measurement_name=worst_name,
            severity=max(1.0, worst_duration / self._alert_delay),
        )

        logger.info("Alert fired: %s (duration=%.1fs)", worst_name, worst_duration)
        return alert

    @staticmethod
    def _build_reason(measurement_name: str) -> str:
        """
        Build a human-readable reason string for the alert.

        Args:
            measurement_name: The measurement key that triggered.

        Returns:
            A short description of the posture issue.
        """
        reasons = {
            "shoulder_angle": "shoulders uneven",
            "forward_head_ratio": "head too far forward",
            "head_tilt_angle": "head tilting sideways",
            "neck_angle": "neck flexion detected",
        }
        return reasons.get(measurement_name, "poor posture detected")

    def pause(self) -> None:
        """Pause alert evaluation."""
        self._paused.clear()
        self._reset_timers()
        logger.info("AlertEngine paused")

    def resume(self) -> None:
        """Resume alert evaluation."""
        self._paused.set()
        self._reset_timers()
        logger.info("AlertEngine resumed")

    @property
    def is_paused(self) -> bool:
        """Whether the engine is currently paused."""
        return not self._paused.is_set()

    def snooze(self, duration_sec: float) -> None:
        """
        Snooze alerts for a specified duration.

        Args:
            duration_sec: Number of seconds to snooze.
        """
        with self._lock:
            self._snooze_until = time.time() + duration_sec
            self._reset_timers_unlocked()
        logger.info("AlertEngine snoozed for %.0f seconds", duration_sec)

    @property
    def is_snoozed(self) -> bool:
        """Whether the engine is currently snoozed."""
        with self._lock:
            return time.time() < self._snooze_until

    def _reset_timers(self) -> None:
        """Reset all bad-posture timers (acquires lock)."""
        with self._lock:
            self._reset_timers_unlocked()

    def _reset_timers_unlocked(self) -> None:
        """Reset all bad-posture timers (caller must hold lock)."""
        for name in ALL_MEASUREMENTS:
            self._bad_start_times[name] = None

    def reset(self) -> None:
        """Fully reset the engine state."""
        with self._lock:
            self._reset_timers_unlocked()
            self._last_alert_time = 0.0
            self._snooze_until = 0.0
        self._paused.set()
        logger.info("AlertEngine reset")
