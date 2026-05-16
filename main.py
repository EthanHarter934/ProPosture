"""
ProPosture — Main Entry Point

Launches the ProPosture application: configures logging, loads user profile
and settings, sets up the system tray icon, registers the global hotkey,
and starts the main window. Handles graceful shutdown on exit.
"""

import logging
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import customtkinter as ctk

from constants import (
    APP_DATA_DIR,
    APP_NAME,
    DEFAULT_HOTKEY,
    ICON_PATH,
    LOG_DIR,
    LOG_RETENTION_DAYS,
    SNOOZE_DURATION_SEC,
)
from data.profile_manager import ProfileManager
from ui.main_window import MainWindow
from ui.tray_icon import TrayIcon


def setup_logging() -> None:
    """
    Configure application logging to both file and console.

    Log files are written to %LOCALAPPDATA%/ProPosture/logs/ with
    daily rotation. Old logs beyond LOG_RETENTION_DAYS are cleaned up.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_filename = f"proposture_{datetime.now().strftime('%Y-%m-%d')}.log"
    log_path = LOG_DIR / log_filename

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)-25s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    cleanup_old_logs()


def cleanup_old_logs() -> None:
    """Remove log files older than LOG_RETENTION_DAYS."""
    try:
        cutoff = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
        for log_file in LOG_DIR.glob("proposture_*.log"):
            if log_file.stat().st_mtime < cutoff.timestamp():
                log_file.unlink()
                logging.debug("Deleted old log: %s", log_file.name)
    except Exception:
        logging.exception("Error cleaning up old logs")


def register_global_hotkey(main_window: MainWindow, tray: TrayIcon) -> None:
    """
    Register the global hotkey for toggling pause/resume.

    Uses the `keyboard` library. Falls back gracefully if registration
    fails (e.g., due to insufficient privileges).

    Args:
        main_window: Main window instance for the toggle callback.
        tray: Tray icon to update pause state.
    """
    try:
        import keyboard

        def on_hotkey() -> None:
            """Handle global hotkey press."""
            main_window.after(0, main_window.toggle_pause)
            is_paused = main_window._alert_engine.is_paused
            tray.set_paused(is_paused)

        keyboard.add_hotkey(DEFAULT_HOTKEY, on_hotkey)
        logging.info("Global hotkey registered: %s", DEFAULT_HOTKEY)
    except ImportError:
        logging.warning("keyboard library not available — global hotkey disabled")
    except Exception:
        logging.exception("Failed to register global hotkey — may need admin privileges")


def main() -> None:
    """
    Application entry point.

    Sets up logging, loads user data, creates the UI, registers the tray
    icon and hotkey, then runs the main event loop.
    """
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("ProPosture starting up")

    # Ensure AppData directory
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Load profile and settings
    pm = ProfileManager()
    settings = pm.load_settings()
    profile = pm.load_profile()

    # Set appearance mode
    ctk.set_appearance_mode("dark" if settings.dark_mode else "light")
    ctk.set_default_color_theme("blue")

    # Create main window
    app = MainWindow(
        profile_manager=pm,
        settings=settings,
        profile=profile,
    )

    # Set up tray icon
    tray = TrayIcon(
        on_open=lambda: app.after(0, app.show_window),
        on_pause=lambda: app.after(0, app.snooze),
        on_resume=lambda: app.after(0, app.toggle_pause),
        on_recalibrate=lambda: app.after(0, app.open_calibration),
        on_quit=lambda: app.after(0, app.quit_app),
    )
    tray.start()
    app.tray_icon = tray

    # Register global hotkey
    register_global_hotkey(app, tray)

    # Minimize to tray on window close (not quit)
    app.protocol("WM_DELETE_WINDOW", app.on_closing)

    # If no calibration exists, open calibration wizard on first launch
    if not pm.has_calibration():
        logger.info("No calibration found — launching calibration wizard")
        app.after(500, app.open_calibration)

    logger.info("ProPosture ready — entering main loop")
    app.mainloop()

    logger.info("ProPosture shut down cleanly")


if __name__ == "__main__":
    main()
