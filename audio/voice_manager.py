"""
Voice Manager Module

Manages text-to-speech output for coach personalities using pyttsx3.
Runs the TTS engine on its own dedicated daemon thread to avoid blocking
the UI or detection threads. Prevents overlapping speech and selects
random lines from the coach personality pool.
"""

import logging
import queue
import random
import threading
from typing import Optional

import pyttsx3

from constants import (
    COACH_DRILL_SERGEANT,
    COACH_LINES,
    COACH_STANDARD,
    DRILL_SERGEANT_SPEECH_RATE,
    DRILL_SERGEANT_VOLUME,
    STANDARD_SPEECH_RATE,
    STANDARD_VOLUME,
)
from core.alert_engine import Alert

logger = logging.getLogger(__name__)


class VoiceManager:
    """
    Manages TTS output with configurable coach personalities.

    Runs pyttsx3 on a dedicated daemon thread since the engine is not
    thread-safe. Speech requests are enqueued and processed sequentially.
    Overlapping requests are dropped to prevent audio pile-up.
    """

    def __init__(self, personality: str = COACH_STANDARD) -> None:
        """
        Initialize the voice manager.

        Args:
            personality: Initial coach personality key.
        """
        self._personality = personality
        self._speech_queue: queue.Queue[Optional[str]] = queue.Queue(maxsize=5)
        self._is_speaking = threading.Event()
        self._shutdown = threading.Event()
        self._last_lines: dict[str, str] = {}  # Avoid repeats per measurement
        self._lock = threading.Lock()

        self._thread = threading.Thread(
            target=self._speech_loop,
            name="VoiceManager-Thread",
            daemon=True,
        )
        self._thread.start()
        logger.info("VoiceManager initialized with personality=%s", personality)

    @property
    def personality(self) -> str:
        """Current coach personality."""
        with self._lock:
            return self._personality

    @personality.setter
    def personality(self, value: str) -> None:
        """Set the coach personality."""
        with self._lock:
            self._personality = value
        logger.info("Coach personality changed to %s", value)

    @property
    def is_speaking(self) -> bool:
        """Whether speech is currently in progress."""
        return self._is_speaking.is_set()

    def speak_alert(self, alert: Alert) -> bool:
        """
        Queue a spoken alert for the given posture issue.

        Selects a random line from the current personality's pool for the
        triggered measurement. Avoids repeating the same line consecutively.

        Args:
            alert: The Alert to speak.

        Returns:
            True if the alert was queued, False if speech is busy or queue full.
        """
        if self._is_speaking.is_set():
            logger.debug("Speech busy, skipping alert for %s", alert.measurement_name)
            return False

        line = self._select_line(alert.measurement_name)
        if line is None:
            logger.warning("No lines found for %s/%s",
                           self._personality, alert.measurement_name)
            return False

        try:
            self._speech_queue.put_nowait(line)
            return True
        except queue.Full:
            logger.debug("Speech queue full, dropping alert")
            return False

    def _select_line(self, measurement_name: str) -> Optional[str]:
        """
        Select a random line for the given measurement, avoiding repeats.

        Args:
            measurement_name: The measurement key (e.g. "shoulder_angle").

        Returns:
            A coach line string, or None if no lines are defined.
        """
        with self._lock:
            personality = self._personality

        lines_pool = COACH_LINES.get(personality, {}).get(measurement_name, [])
        if not lines_pool:
            return None

        last_used = self._last_lines.get(measurement_name)
        available = [l for l in lines_pool if l != last_used]

        if not available:
            available = lines_pool

        chosen = random.choice(available)
        self._last_lines[measurement_name] = chosen
        return chosen

    def speak_text(self, text: str) -> bool:
        """
        Queue arbitrary text for speech (used by test voice button).

        Args:
            text: The text to speak.

        Returns:
            True if queued, False if queue is full.
        """
        try:
            self._speech_queue.put_nowait(text)
            return True
        except queue.Full:
            return False

    def _speech_loop(self) -> None:
        """
        Main loop for the speech daemon thread.

        Initializes pyttsx3 on this thread (required by the library) and
        processes speech requests from the queue until shutdown.
        """
        engine = self._init_engine()
        if engine is None:
            return

        while not self._shutdown.is_set():
            try:
                text = self._speech_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if text is None:  # Poison pill for shutdown
                break

            self._speak_one(engine, text)

        self._cleanup_engine(engine)

    def _init_engine(self) -> Optional[pyttsx3.Engine]:
        """
        Initialize the pyttsx3 engine on the current thread.

        Returns:
            The initialized engine, or None on failure.
        """
        try:
            engine = pyttsx3.init()
            logger.info("pyttsx3 engine initialized")
            return engine
        except Exception:
            logger.exception("Failed to initialize pyttsx3 engine")
            return None

    def _speak_one(self, engine: pyttsx3.Engine, text: str) -> None:
        """
        Speak a single text string using the TTS engine.

        Configures the engine for the current personality before speaking.

        Args:
            engine: The pyttsx3 engine instance.
            text: The text to speak.
        """
        self._is_speaking.set()
        try:
            self._configure_engine(engine)
            engine.say(text)
            engine.runAndWait()
            logger.debug("Spoke: %s", text[:60])
        except Exception:
            logger.exception("Error during speech")
        finally:
            self._is_speaking.clear()

    def _configure_engine(self, engine: pyttsx3.Engine) -> None:
        """
        Configure TTS engine properties for the current personality.

        Args:
            engine: The pyttsx3 engine to configure.
        """
        with self._lock:
            personality = self._personality

        if personality == COACH_DRILL_SERGEANT:
            engine.setProperty("rate", DRILL_SERGEANT_SPEECH_RATE)
            engine.setProperty("volume", DRILL_SERGEANT_VOLUME)
        else:
            engine.setProperty("rate", STANDARD_SPEECH_RATE)
            engine.setProperty("volume", STANDARD_VOLUME)

    @staticmethod
    def _cleanup_engine(engine: pyttsx3.Engine) -> None:
        """
        Clean up the TTS engine.

        Args:
            engine: The engine to stop and clean up.
        """
        try:
            engine.stop()
        except Exception:
            logger.exception("Error stopping pyttsx3 engine")
        logger.info("VoiceManager speech loop exited")

    def shutdown(self) -> None:
        """Signal the speech thread to shut down gracefully."""
        self._shutdown.set()
        try:
            self._speech_queue.put_nowait(None)  # Poison pill
        except queue.Full:
            pass
        logger.info("VoiceManager shutdown signal sent")
