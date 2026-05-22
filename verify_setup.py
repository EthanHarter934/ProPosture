#!/usr/bin/env python3
"""
Verify that ProPosture development environment is set up correctly.

Run this script after initial setup to ensure all dependencies are installed
and configured properly.
"""

import subprocess
import sys
from pathlib import Path


def check(description: str, condition: bool, fix: str = "") -> bool:
    """Print a check result and return the condition."""
    status = "[OK]" if condition else "[FAIL]"
    print(f"  {status} {description}")
    if not condition and fix:
        print(f"      -> {fix}")
    return condition


def check_command(description: str, command: list[str], fix: str = "") -> bool:
    """Check if a command succeeds."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return check(description, result.returncode == 0, fix)
    except FileNotFoundError:
        return check(description, False, fix or f"Install {command[0]}")
    except subprocess.TimeoutExpired:
        return check(description, False, fix or f"Command {command[0]} timed out")


def main() -> int:
    """Run all verification checks."""
    root = Path(__file__).parent
    all_passed = True

    print("\n=== ProPosture Setup Verification ===\n")

    # Python version
    print("Python:")
    python_version = sys.version_info
    version_ok = python_version.major == 3 and python_version.minor >= 11
    all_passed &= check(
        f"Python {python_version.major}.{python_version.minor}+",
        version_ok,
        "Upgrade to Python 3.11 or later",
    )

    # Virtual environment
    print("\nVirtual Environment:")
    in_venv = (
        hasattr(sys, "real_prefix")
        or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
    )
    all_passed &= check(
        "Virtual environment activated",
        in_venv,
        "Run: python -m venv .venv && source .venv/bin/activate",
    )

    # Python dependencies
    print("\nPython Dependencies:")
    deps = {
        "mediapipe": ("mediapipe", "Main posture detection library"),
        "gTTS": ("gtts", "Standard voice generation"),
        "pywebview": ("webview", "Desktop UI framework"),
        "pystray": ("pystray", "System tray integration"),
        "Pillow": ("PIL", "Image processing"),
        "opencv-python": ("cv2", "Camera capture"),
        "numpy": ("numpy", "Numerical processing"),
    }
    for pkg, (module, desc) in deps.items():
        try:
            __import__(module)
            all_passed &= check(f"{pkg} installed", True)
        except ImportError:
            all_passed &= check(
                f"{pkg} installed",
                False,
                f"Run: pip install -r requirements.txt",
            )

    # Node.js and npm
    print("\nFrontend:")
    all_passed &= check_command(
        "Node.js installed",
        ["node", "--version"],
        "Install from https://nodejs.org/",
    )
    all_passed &= check_command(
        "npm installed",
        ["npm", "--version"],
        "Install Node.js (includes npm)",
    )

    # npm packages
    node_modules = root / "node_modules"
    all_passed &= check(
        "npm dependencies installed",
        node_modules.exists(),
        "Run: npm install",
    )

    # Frontend build
    print("\nFrontend Build:")
    dist_dir = root / "frontend" / "dist"
    all_passed &= check(
        "Frontend bundle exists",
        dist_dir.exists(),
        "Run: npm run build",
    )

    # MediaPipe model
    print("\nAssets:")
    model_file = root / "assets" / "pose_landmarker_lite.task"
    all_passed &= check(
        "MediaPipe model file present",
        model_file.exists(),
        f"Ensure {model_file} exists in the repository",
    )

    # Windows: WebView2
    if sys.platform == "win32":
        print("\nWindows Specific:")
        try:
            import winreg
            try:
                winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\WOW6432Node\Microsoft\EdgeWebView\Service",
                )
                all_passed &= check("Microsoft Edge WebView2 Runtime installed", True)
            except FileNotFoundError:
                all_passed &= check(
                    "Microsoft Edge WebView2 Runtime installed",
                    False,
                    "Download from https://developer.microsoft.com/en-us/microsoft-edge/webview2/",
                )
        except ImportError:
            print("  ? Could not verify WebView2 (winreg not available)")

    # Summary
    print("\n" + "=" * 40)
    if all_passed:
        print("[OK] All checks passed! You're ready to run ProPosture.")
        print("\n  To start the app:")
        print("    python main.py")
        return 0
    else:
        print("[FAIL] Some checks failed. Fix the issues above and try again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
