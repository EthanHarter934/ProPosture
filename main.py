"""
ProPosture entry point.

Starts the Python posture backend, loads the React frontend in a native WebView,
configures the system tray, registers the global hotkey, and handles shutdown.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

# Suppress MediaPipe C++ warnings (like the NORM_RECT warning) before imports
os.environ["GLOG_minloglevel"] = "2"

import webview
from backend.controller import AppController
from backend.desktop_api import DesktopApi
from constants import (
    APP_DATA_DIR,
    DEFAULT_HOTKEY,
    LOG_DIR,
    LOG_RETENTION_DAYS,
)
from data.profile_manager import ProfileManager
from ui.tray_icon import TrayIcon


ROOT = Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", ROOT))
FRONTEND_INDEX = RESOURCE_ROOT / "frontend" / "dist" / "index.html"


def setup_logging() -> None:
    """Configure application logging to both file and console."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"proposture_{datetime.now().strftime('%Y-%m-%d')}.log"

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
    root_logger.handlers.clear()
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


def register_global_hotkey(
    controller: AppController,
    tray: TrayIcon,
    hotkey: str = DEFAULT_HOTKEY,
) -> None:
    """Register the global pause/resume hotkey where supported."""
    if sys.platform == "darwin":
        logging.info("Global hotkey disabled on macOS")
        return

    try:
        import keyboard

        def on_hotkey() -> None:
            state = controller.toggle_pause()
            tray.set_paused(bool(state["paused"]))

        keyboard.add_hotkey(hotkey, on_hotkey)
        logging.info("Global hotkey registered: %s", hotkey)
    except ImportError:
        logging.warning("keyboard library not available; global hotkey disabled")
    except Exception:
        logging.exception("Failed to register global hotkey; may need admin privileges")


def main() -> int:
    """Start the desktop app and block until the WebView exits."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("ProPosture starting up")

    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    profile_manager = ProfileManager()
    settings = profile_manager.load_settings()
    profile = profile_manager.load_profile()
    controller = AppController(profile_manager, settings, profile)

    if not FRONTEND_INDEX.exists():
        raise FileNotFoundError(
            f"React frontend build not found at {FRONTEND_INDEX}. "
            "Run npm install and npm run build."
        )

    desktop_api = DesktopApi(controller)
    app_window: Optional[Any] = None
    shutting_down = False

    def show_window() -> None:
        if app_window is None:
            return
        try:
            app_window.show()
            if hasattr(app_window, "restore"):
                app_window.restore()
        except Exception:
            logger.debug("Failed to show WebView window", exc_info=True)

    def shutdown() -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        logger.info("Application shutting down")
        controller.shutdown()
        if app_window is not None:
            try:
                app_window.destroy()
            except Exception:
                logger.debug("Failed to destroy WebView window", exc_info=True)

    tray = TrayIcon(
        on_open=show_window,
        on_pause=lambda: controller.snooze(),
        on_resume=lambda: controller.resume_alerts(),
        on_recalibrate=lambda: (controller.begin_calibration(), show_window()),
        on_quit=shutdown,
    )
    tray.start()
    register_global_hotkey(controller, tray, settings.hotkey or DEFAULT_HOTKEY)

    logger.info("ProPosture WebView loading %s", FRONTEND_INDEX)

    def handle_signal(signum: int, frame: object) -> None:
        shutdown()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    app_window = webview.create_window(
        "ProPosture",
        FRONTEND_INDEX.as_uri(),
        js_api=desktop_api,
        width=1024,
        height=760,
        min_size=(780, 640),
    )

    webview.start(debug=False)
    shutdown()
    tray.stop()
    logger.info("ProPosture shut down cleanly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
