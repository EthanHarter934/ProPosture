"""
Build ProPosture executables with PyInstaller.

Run this script on the target OS:
- Windows creates dist/ProPosture.exe
- macOS creates dist/ProPosture.app
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ICON_SOURCE = ROOT / "assets" / "icon.png"
ICON_BUILD_DIR = ROOT / "build" / "icons"
WINDOWS_ICON = ICON_BUILD_DIR / "proposture.ico"
MACOS_ICON = ICON_BUILD_DIR / "proposture.icns"


def main() -> int:
    """Prepare platform icons and run the PyInstaller spec."""
    if sys.platform not in {"win32", "darwin"}:
        print(
            f"Building on {platform.system()} is supported by the spec, but "
            "release executables should be built on Windows or macOS."
        )

    _check_tkinter_available()
    _prepare_platform_icon()
    _run_pyinstaller()
    _print_output_hint()
    return 0


def _check_tkinter_available() -> None:
    """Fail early if the active Python cannot bundle the Tk UI runtime."""
    try:
        import tkinter  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "This Python does not include Tkinter, which ProPosture needs for "
            "its CustomTkinter UI. Install a Tk-enabled Python, then recreate "
            "the virtualenv and rerun this build. On Homebrew macOS Python, "
            "install the matching python-tk package, for example: "
            "brew install python-tk@3.12"
        ) from exc


def _prepare_platform_icon() -> None:
    """Generate the platform-native icon file consumed by the spec."""
    if not ICON_SOURCE.exists():
        raise FileNotFoundError(f"Missing app icon: {ICON_SOURCE}")

    ICON_BUILD_DIR.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        _save_icon(WINDOWS_ICON, "ICO")
    elif sys.platform == "darwin":
        _save_icon(MACOS_ICON, "ICNS")


def _save_icon(destination: Path, image_format: str) -> None:
    """Save icon.png as an ICO or ICNS file with common icon sizes."""
    from PIL import Image

    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    if image_format == "ICNS":
        sizes += [(512, 512), (1024, 1024)]

    image = Image.open(ICON_SOURCE).convert("RGBA")
    image.save(destination, format=image_format, sizes=sizes)
    print(f"Wrote {destination}")


def _run_pyinstaller() -> None:
    """Run PyInstaller against the checked-in spec file."""
    try:
        import PyInstaller.__main__
    except ImportError as exc:
        raise SystemExit(
            "PyInstaller is missing. Install build requirements with: "
            "python -m pip install -r requirements-build.txt"
        ) from exc

    PyInstaller.__main__.run(
        [
            "--clean",
            "--noconfirm",
            str(ROOT / "ProPosture.spec"),
        ]
    )


def _print_output_hint() -> None:
    """Print the expected build artifact for the current OS."""
    if sys.platform == "win32":
        print("Built Windows executable: dist/ProPosture.exe")
    elif sys.platform == "darwin":
        print("Built macOS app: dist/ProPosture.app")
    else:
        print("Build complete. Check the dist/ directory.")


if __name__ == "__main__":
    raise SystemExit(main())
