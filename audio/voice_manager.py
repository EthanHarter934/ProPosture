"""
Voice Manager Module

Manages text-to-speech output for coach personalities using either gTTS
(standard mode) or VoxCPM2 server (custom voice mode). Speech requests run
on a dedicated daemon thread so network generation and audio playback do
not block the UI or detection threads.
"""

import hashlib
import logging
import queue
import random
import shutil
import subprocess
import sys
import threading
import ctypes
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from gtts import gTTS

from constants import (
    COACH_LINES,
    COACH_STANDARD,
    CUSTOM_VOICE_CACHE_DIR,
    DEFAULT_TTS_VOICE,
    DEFAULT_VOICE_MODE,
    DEFAULT_VOICE_SERVER_URL,
    TTS_CACHE_DIR,
    TTS_VOICE_OPTIONS,
    VOICE_MODE_CUSTOM,
    VOICE_MODE_STANDARD,
)
from core.alert_engine import Alert

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpeechRequest:
    """A queued speech item with the voice captured at enqueue time."""

    text: str
    voice: str
    volume: float = 1.0
    voice_mode: str = VOICE_MODE_STANDARD
    voice_description: str = ""
    voice_server_url: str = DEFAULT_VOICE_SERVER_URL


class VoiceManager:
    """
    Manages TTS output with configurable coach personalities and voices.

    Supports two voice modes:
    - "standard": Uses gTTS for text-to-speech.
    - "custom": Calls the VoxCPM2 server to generate audio with a user-
      defined voice description, then caches and plays the resulting WAV.
    """

    def __init__(
        self,
        personality: str = COACH_STANDARD,
        voice: str = DEFAULT_TTS_VOICE,
        volume: float = 1.0,
        voice_mode: str = DEFAULT_VOICE_MODE,
        voice_description: str = "",
        voice_server_url: str = DEFAULT_VOICE_SERVER_URL,
    ) -> None:
        """
        Initialize the voice manager.

        Args:
            personality: Initial coach personality key.
            voice: Initial gTTS voice/accent key.
            volume: Audio volume (0.0 to 1.0).
            voice_mode: "standard" or "custom".
            voice_description: Natural language voice description for VoxCPM2.
            voice_server_url: URL of the VoxCPM2 voice server.
        """
        self._personality = personality
        self._voice = self._normalize_voice(voice)
        self._volume = max(0.0, min(1.0, volume))
        self._voice_mode = voice_mode
        self._voice_description = voice_description
        self._voice_server_url = voice_server_url
        self._speech_queue: queue.Queue[Optional[SpeechRequest]] = queue.Queue(maxsize=5)
        self._is_speaking = threading.Event()
        self._shutdown = threading.Event()
        self._last_lines: dict[str, str] = {}
        self._lock = threading.Lock()

        TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CUSTOM_VOICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self._thread = threading.Thread(
            target=self._speech_loop,
            name="VoiceManager-Thread",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "VoiceManager initialized with personality=%s, voice=%s, "
            "volume=%.2f, voice_mode=%s",
            personality,
            self._voice,
            self._volume,
            self._voice_mode,
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
    def volume(self) -> float:
        """Current audio volume (0.0 to 1.0)."""
        with self._lock:
            return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        """Set the audio volume (0.0 to 1.0)."""
        clamped = max(0.0, min(1.0, value))
        with self._lock:
            self._volume = clamped
        logger.info("Volume changed to %.2f", clamped)

    @property
    def voice_mode(self) -> str:
        """Current voice mode ('standard' or 'custom')."""
        with self._lock:
            return self._voice_mode

    @voice_mode.setter
    def voice_mode(self, value: str) -> None:
        """Set the voice mode."""
        with self._lock:
            self._voice_mode = value
        logger.info("Voice mode changed to %s", value)

    @property
    def voice_description(self) -> str:
        """Current custom voice description for VoxCPM2."""
        with self._lock:
            return self._voice_description

    @voice_description.setter
    def voice_description(self, value: str) -> None:
        """Set the custom voice description."""
        with self._lock:
            self._voice_description = value
        logger.info("Voice description updated")

    @property
    def voice_server_url(self) -> str:
        """Current VoxCPM2 voice server URL."""
        with self._lock:
            return self._voice_server_url

    @voice_server_url.setter
    def voice_server_url(self, value: str) -> None:
        """Set the VoxCPM2 voice server URL."""
        with self._lock:
            self._voice_server_url = value.rstrip("/")
        logger.info("Voice server URL changed to %s", value)

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
            measurement_name: The measurement key.

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
        """Queue text with the current voice settings captured immediately."""
        with self._lock:
            request = SpeechRequest(
                text=text,
                voice=self._voice,
                volume=self._volume,
                voice_mode=self._voice_mode,
                voice_description=self._voice_description,
                voice_server_url=self._voice_server_url,
            )

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
        """Generate audio and play it synchronously."""
        self._is_speaking.set()
        try:
            if request.voice_mode == VOICE_MODE_CUSTOM and request.voice_description:
                audio_path = self._get_or_create_custom_audio(request)
            else:
                audio_path = self._get_or_create_audio(request)
            self._play_audio(audio_path, request.volume)
            logger.debug("Spoke using %s: %s", request.voice_mode, request.text[:60])
        except Exception:
            logger.exception("Error during speech")
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

    def _get_or_create_custom_audio(self, request: SpeechRequest) -> Path:
        """
        Return a cached WAV path, generating via the VoxCPM2 server if needed.

        Calls the voice server's /generate_single endpoint to produce a WAV
        file with the user's custom voice description applied to the text.
        """
        import urllib.request
        import json

        cache_key = hashlib.sha256(
            f"{request.voice_description}\0{request.text}".encode("utf-8")
        ).hexdigest()
        path = CUSTOM_VOICE_CACHE_DIR / f"{cache_key}.wav"

        if path.exists() and path.stat().st_size > 0:
            return path

        url = f"{request.voice_server_url}/generate_single"
        payload = json.dumps({
            "voice_description": request.voice_description,
            "text": request.text,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        logger.info("Requesting custom voice audio from %s", url)
        with urllib.request.urlopen(req, timeout=120) as response:
            wav_data = response.read()

        path.write_bytes(wav_data)
        logger.info("Custom voice audio cached: %s (%d bytes)", path.name, len(wav_data))
        return path

    @staticmethod
    def _play_audio(path: Path, volume: float) -> None:
        """Play an audio file using the local platform's available player."""
        if sys.platform == "darwin":
            subprocess.run(["afplay", "-v", str(volume), str(path)], check=True)
            return

        if sys.platform == "win32":
            VoiceManager._play_audio_windows(path, volume)
            return

        for command in ("ffplay", "mpg123", "mpg321"):
            player = shutil.which(command)
            if player is None:
                continue
            if command == "ffplay":
                args = [player, "-volume", str(int(volume * 100)), "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]
            elif command == "mpg123":
                args = [player, "-f", str(int(volume * 32768)), "-q", str(path)]
            else:
                args = [player, "-q", str(path)]
            subprocess.run(args, check=True)
            return

        raise RuntimeError("No supported audio playback command found")

    @staticmethod
    def _play_audio_windows(path: Path, volume: float) -> None:
        """Play an audio file on Windows using MCI."""
        path_str = str(path)
        mci = ctypes.windll.winmm.mciSendStringW
        
        alias = "proposture_tts"
        open_cmd = f'open "{path_str}" alias {alias}'
        
        res = mci(open_cmd, None, 0, 0)
        if res != 0:
            logger.error("Failed to open audio file via MCI (code %d): %s", res, path_str)
            return
            
        try:
            mci(f'setaudio {alias} volume to {int(volume * 1000)}', None, 0, 0)
            play_res = mci(f'play {alias} wait', None, 0, 0)
            if play_res != 0:
                logger.error("Failed to play audio file via MCI (code %d)", play_res)
        finally:
            mci(f'close {alias}', None, 0, 0)

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
