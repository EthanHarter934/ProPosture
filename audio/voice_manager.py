"""
Voice Manager Module

Manages text-to-speech output for coach personalities using gTTS. Speech
requests run on a dedicated daemon thread so network generation and audio
playback do not block the UI or detection threads.
"""

import hashlib
import logging
import queue
import random
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from gtts import gTTS

from constants import (
    COACH_LINES,
    COACH_STANDARD,
    DEFAULT_TTS_VOICE,
    TTS_CACHE_DIR,
    TTS_VOICE_OPTIONS,
)
from core.alert_engine import Alert

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpeechRequest:
    """A queued speech item with the voice captured at enqueue time."""

    text: str
    voice: str


class VoiceManager:
    """
    Manages gTTS output with configurable coach personalities and voices.

    Alert text is selected from the current personality's pool. The selected
    gTTS voice is stored with each queued item, preventing later settings
    changes from affecting already queued test lines or alerts.
    """

    def __init__(
        self,
        personality: str = COACH_STANDARD,
        voice: str = DEFAULT_TTS_VOICE,
    ) -> None:
        """
        Initialize the voice manager.

        Args:
            personality: Initial coach personality key.
            voice: Initial gTTS voice/accent key.
        """
        self._personality = personality
        self._voice = self._normalize_voice(voice)
        self._speech_queue: queue.Queue[Optional[SpeechRequest]] = queue.Queue(maxsize=5)
        self._is_speaking = threading.Event()
        self._shutdown = threading.Event()
        self._last_lines: dict[str, str] = {}
        self._lock = threading.Lock()

        TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self._thread = threading.Thread(
            target=self._speech_loop,
            name="VoiceManager-Thread",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "VoiceManager initialized with personality=%s, voice=%s",
            personality,
            self._voice,
        )

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
    def voice(self) -> str:
        """Current gTTS voice/accent key."""
        with self._lock:
            return self._voice

    @voice.setter
    def voice(self, value: str) -> None:
        """Set the gTTS voice/accent key."""
        normalized = self._normalize_voice(value)
        with self._lock:
            self._voice = normalized
        logger.info("gTTS voice changed to %s", normalized)

    @property
    def is_speaking(self) -> bool:
        """Whether speech is currently in progress."""
        return self._is_speaking.is_set()

    def speak_alert(self, alert: Alert) -> bool:
        """
        Queue a spoken alert for the given posture issue.

        Selects a random line from the current personality's pool for the
        triggered measurement. Avoids repeating the same line consecutively.
        """
        if self._is_speaking.is_set():
            logger.debug("Speech busy, skipping alert for %s", alert.measurement_name)
            return False

        line = self._select_line(alert.measurement_name)
        if line is None:
            logger.warning("No lines found for %s/%s",
                           self._personality, alert.measurement_name)
            return False

        return self._enqueue(line)

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
        available = [line for line in lines_pool if line != last_used]
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
            True if queued, False if speech is busy or the queue is full.
        """
        if self._is_speaking.is_set():
            logger.debug("Speech busy, skipping test voice")
            return False
        return self._enqueue(text)

    def _enqueue(self, text: str) -> bool:
        """Queue text with the current voice captured immediately."""
        with self._lock:
            request = SpeechRequest(text=text, voice=self._voice)

        try:
            self._speech_queue.put_nowait(request)
            return True
        except queue.Full:
            logger.debug("Speech queue full, dropping request")
            return False

    def _speech_loop(self) -> None:
        """Process speech requests until shutdown."""
        while not self._shutdown.is_set():
            try:
                request = self._speech_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if request is None:
                break

            self._speak_one(request)

        logger.info("VoiceManager speech loop exited")

    def _speak_one(self, request: SpeechRequest) -> None:
        """Generate cached gTTS audio and play it synchronously."""
        self._is_speaking.set()
        try:
            audio_path = self._get_or_create_audio(request)
            self._play_audio(audio_path)
            logger.debug("Spoke using %s: %s", request.voice, request.text[:60])
        except Exception:
            logger.exception("Error during gTTS speech")
        finally:
            self._is_speaking.clear()

    def _get_or_create_audio(self, request: SpeechRequest) -> Path:
        """Return a cached MP3 path, generating it with gTTS if needed."""
        voice_config = TTS_VOICE_OPTIONS[self._normalize_voice(request.voice)]
        cache_key = hashlib.sha256(
            f"{request.voice}\0{request.text}".encode("utf-8")
        ).hexdigest()
        path = TTS_CACHE_DIR / f"{cache_key}.mp3"

        if path.exists() and path.stat().st_size > 0:
            return path

        tts = gTTS(
            text=request.text,
            lang=voice_config["lang"],
            tld=voice_config["tld"],
            slow=False,
        )
        tts.save(str(path))
        return path

    @staticmethod
    def _play_audio(path: Path) -> None:
        """Play an MP3 file using the local platform's available player."""
        if sys.platform == "darwin":
            subprocess.run(["afplay", str(path)], check=True)
            return

        if sys.platform == "win32":
            escaped = str(path).replace("'", "''")
            script = (
                "$player = New-Object -ComObject WMPlayer.OCX;"
                f"$player.URL = '{escaped}';"
                "$player.controls.play();"
                "Start-Sleep -Milliseconds 200;"
                "while ($player.playState -eq 3) { Start-Sleep -Milliseconds 100 }"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                check=True,
            )
            return

        for command in ("ffplay", "mpg123", "mpg321"):
            player = shutil.which(command)
            if player is None:
                continue
            if command == "ffplay":
                args = [player, "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]
            else:
                args = [player, "-q", str(path)]
            subprocess.run(args, check=True)
            return

        raise RuntimeError("No supported MP3 playback command found")

    @staticmethod
    def _normalize_voice(value: str) -> str:
        """Return a supported voice key, falling back to the default."""
        if value in TTS_VOICE_OPTIONS:
            return value
        return DEFAULT_TTS_VOICE

    def shutdown(self) -> None:
        """Signal the speech thread to shut down gracefully."""
        self._shutdown.set()
        try:
            self._speech_queue.put_nowait(None)
        except queue.Full:
            pass
        logger.info("VoiceManager shutdown signal sent")
