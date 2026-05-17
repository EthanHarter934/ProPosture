"""
Tray Icon Module

Sets up the system tray icon with a right-click menu for controlling
ProPosture while it runs in the background. Uses pystray on its own
thread as required by the library.
"""

import logging
import sys
import threading
from typing import Any, Callable, Optional

from PIL import Image
from pystray import Icon, Menu, MenuItem

from constants import ICON_PATH

logger = logging.getLogger(__name__)


class TrayIcon:
    """
    System tray icon with right-click context menu.

    Provides menu items to show the main window, pause/resume monitoring,
    recalibrate, and quit the application. Runs on a separate thread
    as required by pystray.
    """

    def __init__(
        self,
        on_open: Callable[[], None],
        on_pause: Callable[[], None],
        on_resume: Callable[[], None],
        on_recalibrate: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        """
        Initialize the tray icon.

        Args:
            on_open: Callback to open the main window.
            on_pause: Callback to pause/snooze monitoring.
            on_resume: Callback to resume monitoring.
            on_recalibrate: Callback to start recalibration.
            on_quit: Callback to quit the application.
        """
        self._on_open = on_open
        self._on_pause = on_pause
        self._on_resume = on_resume
        self._on_recalibrate = on_recalibrate
        self._on_quit = on_quit
        self._is_paused = False
        self._icon: Optional[Icon] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the tray icon on a background thread."""
        image = self._load_icon()
        menu = self._build_menu()

        self._icon = Icon(
            name="ProPosture",
            icon=image,
            title="ProPosture — Posture Monitor",
            menu=menu,
        )

        if sys.platform == "darwin":
            self._run_detached()
            return

        self._thread = threading.Thread(
            target=self._run,
            name="TrayIcon-Thread",
            daemon=True,
        )
        self._thread.start()
        logger.info("Tray icon started")

    def _run_detached(self) -> None:
        """Start pystray in a mode compatible with the macOS Tk mainloop."""
        try:
            if self._icon is not None:
                self._icon.run_detached()
                logger.info("Tray icon started in detached mode")
        except Exception:
            logger.exception("Tray icon error")

    def _run(self) -> None:
        """Run the tray icon (blocking, runs on its own thread)."""
        try:
            if self._icon is not None:
                self._icon.run()
        except Exception:
            logger.exception("Tray icon error")

    @staticmethod
    def _load_icon() -> Image.Image:
        """
        Load the application icon image.

        Returns:
            PIL Image for the tray icon.
        """
        try:
            img = Image.open(str(ICON_PATH))
            img = img.resize((64, 64), Image.Resampling.LANCZOS)
            return img
        except Exception:
            logger.warning("Could not load icon from %s, using fallback", ICON_PATH)
            return TrayIcon._create_fallback_icon()

    @staticmethod
    def _create_fallback_icon() -> Image.Image:
        """
        Create a simple fallback icon if the file is missing.

        Returns:
            A simple colored square PIL Image.
        """
        img = Image.new("RGB", (64, 64), color=(74, 158, 255))
        return img

    def _build_menu(self) -> Menu:
        """
        Build the right-click context menu.

        Returns:
            pystray Menu with all items.
        """
        return Menu(
            MenuItem("Open ProPosture", self._handle_open, default=True),
            Menu.SEPARATOR,
            MenuItem(
                "Pause Monitoring (15 min)",
                self._handle_pause,
                visible=lambda item: not self._is_paused,
            ),
            MenuItem(
                "Resume Monitoring",
                self._handle_resume,
                visible=lambda item: self._is_paused,
            ),
            Menu.SEPARATOR,
            MenuItem("Recalibrate", self._handle_recalibrate),
            Menu.SEPARATOR,
            MenuItem("Quit", self._handle_quit),
        )

    def _handle_open(self, icon: Any, item: Any) -> None:
        """Handle 'Open ProPosture' menu click."""
        self._on_open()

    def _handle_pause(self, icon: Any, item: Any) -> None:
        """Handle 'Pause Monitoring' menu click."""
        self._is_paused = True
        self._on_pause()
        self._update_menu()

    def _handle_resume(self, icon: Any, item: Any) -> None:
        """Handle 'Resume Monitoring' menu click."""
        self._is_paused = False
        self._on_resume()
        self._update_menu()

    def _handle_recalibrate(self, icon: Any, item: Any) -> None:
        """Handle 'Recalibrate' menu click."""
        self._on_recalibrate()

    def _handle_quit(self, icon: Any, item: Any) -> None:
        """Handle 'Quit' menu click."""
        self.stop()
        self._on_quit()

    def _update_menu(self) -> None:
        """Force menu update to reflect pause/resume state."""
        if self._icon is not None:
            self._icon.update_menu()

    def stop(self) -> None:
        """Stop and remove the tray icon."""
        try:
            if self._icon is not None:
                self._icon.stop()
                logger.info("Tray icon stopped")
        except Exception:
            logger.exception("Error stopping tray icon")

    def set_paused(self, paused: bool) -> None:
        """
        Update the tray's pause state (called from hotkey handler).

        Args:
            paused: Whether monitoring is paused.
        """
        self._is_paused = paused
        self._update_menu()
