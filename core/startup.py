"""
Platform startup integration.

Windows uses the current user's Run registry key. macOS uses a LaunchAgent
plist in ~/Library/LaunchAgents. Unsupported platforms fail gracefully.
"""

from __future__ import annotations

import logging
import plistlib
import subprocess
import sys
from pathlib import Path

from constants import APP_NAME, STARTUP_REGISTRY_KEY, STARTUP_REGISTRY_NAME

logger = logging.getLogger(__name__)

MACOS_LAUNCH_AGENT_LABEL = "com.proposture.app"
MACOS_LAUNCH_AGENT_PATH = (
    Path.home() / "Library" / "LaunchAgents" / f"{MACOS_LAUNCH_AGENT_LABEL}.plist"
)


def is_startup_supported() -> bool:
    """Return whether this platform supports app-managed startup."""
    return sys.platform in {"win32", "darwin"}


def get_startup_label() -> str:
    """Return a user-facing startup target label for the current platform."""
    if sys.platform == "win32":
        return "Windows startup"
    if sys.platform == "darwin":
        return "macOS login"
    return "system startup"


def set_launch_at_startup(enabled: bool) -> bool:
    """
    Enable or disable launching ProPosture at OS startup/login.

    Args:
        enabled: Whether startup launch should be enabled.

    Returns:
        True if the startup setting was applied or was already absent.
    """
    if sys.platform == "win32":
        return _set_windows_startup(enabled)
    if sys.platform == "darwin":
        return _set_macos_startup(enabled)

    logger.warning("Startup launch is not supported on this platform: %s", sys.platform)
    return False


def _current_launch_command() -> list[str]:
    """Build the command used to relaunch this app on login/startup."""
    executable = str(Path(sys.executable).resolve())

    if sys.platform == "darwin" and getattr(sys, "frozen", False):
        app_bundle = _macos_app_bundle_path()
        if app_bundle is not None:
            return ["/usr/bin/open", str(app_bundle)]

    if getattr(sys, "frozen", False):
        return [executable]

    script_path = Path(sys.argv[0]).resolve()
    return [executable, str(script_path)]


def _macos_app_bundle_path() -> Path | None:
    """Return the containing .app bundle when running from a frozen macOS app."""
    executable = Path(sys.executable).resolve()
    for parent in executable.parents:
        if parent.suffix == ".app":
            return parent
    return None


def _set_windows_startup(enabled: bool) -> bool:
    """Add or remove ProPosture from the current user's Windows startup apps."""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            STARTUP_REGISTRY_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                command = subprocess.list2cmdline(_current_launch_command())
                winreg.SetValueEx(
                    key,
                    STARTUP_REGISTRY_NAME,
                    0,
                    winreg.REG_SZ,
                    command,
                )
                logger.info("Added to Windows startup: %s", command)
            else:
                try:
                    winreg.DeleteValue(key, STARTUP_REGISTRY_NAME)
                    logger.info("Removed from Windows startup")
                except FileNotFoundError:
                    logger.debug("Windows startup entry did not exist")
        return True
    except Exception:
        logger.exception("Failed to modify Windows startup registry")
        return False


def _set_macos_startup(enabled: bool) -> bool:
    """Add or remove ProPosture from the current user's macOS login items."""
    try:
        if enabled:
            MACOS_LAUNCH_AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
            plist = {
                "Label": MACOS_LAUNCH_AGENT_LABEL,
                "ProgramArguments": _current_launch_command(),
                "RunAtLoad": True,
                "KeepAlive": False,
            }
            with MACOS_LAUNCH_AGENT_PATH.open("wb") as f:
                plistlib.dump(plist, f)
            _run_launchctl("unload", MACOS_LAUNCH_AGENT_PATH)
            _run_launchctl("load", MACOS_LAUNCH_AGENT_PATH)
            logger.info("Added to macOS login: %s", MACOS_LAUNCH_AGENT_PATH)
        else:
            _run_launchctl("unload", MACOS_LAUNCH_AGENT_PATH)
            MACOS_LAUNCH_AGENT_PATH.unlink(missing_ok=True)
            logger.info("Removed from macOS login")
        return True
    except Exception:
        logger.exception("Failed to modify macOS login item")
        return False


def _run_launchctl(action: str, plist_path: Path) -> None:
    """Best-effort LaunchAgent load/unload; failures still apply on next login."""
    if not plist_path.exists():
        return

    subprocess.run(
        ["launchctl", action, str(plist_path)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
