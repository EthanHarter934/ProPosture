# ProPosture

**Real-time posture monitoring for your desk setup.** ProPosture uses your webcam and MediaPipe Pose to analyze your sitting posture, compares it against your personal calibrated baseline, and coaches you with spoken alerts when you start slouching.

## Features

- 🎯 **Personalized Calibration** — No hardcoded thresholds. Your baseline is YOUR good posture.
- 📐 **4 Posture Measurements** — Shoulder angle, forward head ratio, head tilt, and neck angle.
- 🎙️ **Two Coach Personalities** — Calm professional or aggressive drill sergeant.
- 🔒 **100% Local** — Camera feed is processed on-device. Nothing is recorded or transmitted.
- 📌 **System Tray** — Runs silently in the background with quick tray menu access.
- ⌨️ **Global Hotkey** — Ctrl+Shift+P to toggle pause from anywhere.
- 📊 **Session Stats** — Track time monitored, alerts, and longest good posture streak.

## Quick Start

### 1. Clone & Install

```bash
git clone <repo-url>
cd ProPosture
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

On macOS, the Python used for the virtual environment must include Tkinter.
If `python -c "import tkinter"` fails, install a Tk-enabled Python and recreate
the virtual environment. For Homebrew Python 3.12, that usually means:

```bash
brew install python-tk@3.12
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run

```bash
python main.py
```

On first launch, the **Calibration Wizard** will guide you through setting your personal posture baseline.

### 3. Use

- The app monitors your posture via webcam and alerts you with spoken feedback.
- **Minimize** the window to send it to the system tray.
- **Right-click the tray icon** for quick access to Pause, Resume, Recalibrate, or Quit.
- Press **Ctrl+Shift+P** anywhere to toggle pause on platforms supported by the `keyboard` package.

## How It Works

1. **Calibrate** — Sit with ideal posture. ProPosture captures 90 frames (3 seconds) to learn your personal baseline, computing the mean and standard deviation of each measurement.

2. **Monitor** — In the background, each frame is compared to your baseline. If any measurement deviates beyond `mean ± (multiplier × std_dev)`, a warning is raised.

3. **Alert** — If bad posture persists for a configurable duration (default: 10 seconds), your chosen coach speaks up with specific feedback (e.g., "head too far forward").

## Measurements

| Measurement | What It Detects |
|---|---|
| **Shoulder Angle** | Uneven shoulders / slouching to one side |
| **Forward Head Ratio** | Head jutting forward (most common desk worker issue) |
| **Head Tilt Angle** | Head tilting sideways |
| **Neck Angle** | Forward neck flexion |

## Settings

- Coach personality (Standard / Drill Sergeant)
- Sensitivity multipliers per measurement (1.0 = very sensitive, 4.0 = lenient)
- Alert delay (5–60 seconds)
- Cooldown between alerts (15–300 seconds)
- Camera index selection
- Dark / Light mode
- Launch at startup/login

## Project Structure

```
proposture/
├── main.py                    # Entry point
├── constants.py               # All configurable values
├── requirements.txt           # Dependencies
├── requirements-build.txt     # Build dependencies
├── build.py                   # Cross-platform PyInstaller build wrapper
├── ProPosture.spec            # PyInstaller app/exe spec
├── assets/
│   └── icon.png               # App icon
├── core/
│   ├── pose_detector.py       # MediaPipe landmark extraction
│   ├── posture_analyzer.py    # Angle/distance math
│   ├── calibration.py         # Calibration session management
│   ├── alert_engine.py        # Threshold and timing logic
│   └── startup.py             # Windows/macOS startup integration
├── audio/
│   └── voice_manager.py       # TTS with coach personalities
├── ui/
│   ├── main_window.py         # Dashboard
│   ├── calibration_screen.py  # 4-step calibration wizard
│   ├── settings_window.py     # Settings controls
│   └── tray_icon.py           # System tray integration
└── data/
    └── profile_manager.py     # JSON profile persistence
```

## Data Storage

All data is stored locally in the OS-specific app data directory:

- Windows: `%LOCALAPPDATA%\ProPosture\`
- macOS: `~/Library/Application Support/ProPosture/`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/ProPosture/`

Stored files:
- `profile.json` — Calibration baseline and sensitivity settings
- `settings.json` — App preferences
- `logs/` — Application logs (retained for 7 days)

## Building Executables

```bash
python -m pip install -r requirements-build.txt
python build.py
```

PyInstaller builds for the OS it is running on. Run `python build.py` on
Windows to create `dist/ProPosture.exe`, and run it on macOS to create
`dist/ProPosture.app`.

## Requirements

- Python 3.11+
- Windows 10/11 or macOS
- Webcam
- Speakers or headphones (for voice alerts)

## License

MIT
