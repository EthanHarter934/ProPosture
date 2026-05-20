# ProPosture

**Real-time posture monitoring for your desk setup.** ProPosture uses your webcam and MediaPipe Pose to analyze your sitting posture, compares it against your personal calibrated baseline, and coaches you with spoken alerts when you start slouching. The standalone desktop UI is a React + Tailwind frontend loaded from bundled files in a native WebView shell, with direct JavaScript-to-Python calls through the desktop bridge.

## Features

- 🎯 **Personalized Calibration** — Your baseline is YOUR good posture, with practical tolerance floors to avoid overreacting to webcam jitter.
- 📐 **Vertical Posture Measurements** — Nose-to-shoulder height and shoulder screen position, both compared against your calibrated baseline.
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
npm install
npm run build
```

### 2. Run the VoxCPM2 Voice Server (Optional)

If you want to use the Custom Voice (VoxCPM2) feature, you need to run the voice generation server on a CUDA-capable machine. This only needs to be run once and can be hosted on a separate machine if needed.

```bash
cd voice_server

# 1. Create a Python 3.11 virtual environment (newer Python versions may fail to install PyTorch/Pythonnet)
py -3.11 -m venv venv

# 2. Activate the environment (Windows)
venv\Scripts\activate
# OR macOS/Linux: source venv/bin/activate

# 3. Install requirements
pip install -r requirements.txt

# 4. Pre-download the voice model (this handles network interruptions and resumes broken downloads)
huggingface-cli download openbmb/VoxCPM2

# 5. Start the server
python server.py --host 0.0.0.0 --port 5123
```

### 3. Run the App

```bash
python main.py
```

The Python backend opens the bundled React UI inside the ProPosture desktop window. On first launch, the **Calibration Wizard** will guide you through setting your personal posture baseline.

### 4. Use

- The app monitors your posture via webcam and alerts you with spoken feedback.
- To use custom voices, go to **Settings > Voice**, select **Custom Voice (VoxCPM2)**, type a voice description, and click **Generate Voice**.
- **Minimize** the window to send it to the system tray.
- **Right-click the tray icon** for quick access to Pause, Resume, Recalibrate, or Quit.
- Press **Ctrl+Shift+P** anywhere to toggle pause on platforms supported by the `keyboard` package.

## How It Works

1. **Calibrate** — Sit with ideal posture. ProPosture captures 90 frames (3 seconds) to learn your personal baseline, using robust center and jitter estimates so a few noisy frames do not skew the profile.

2. **Monitor** — In the background, each frame is compared to your baseline using vertical screen distances. Thresholds are percentages of your calibrated nose-to-shoulder distance, which keeps posture scoring relative to each person and camera setup.

3. **Alert** — If bad posture persists for a configurable duration (default: 10 seconds), your chosen coach speaks up with specific feedback (e.g., "lift your head" or "sit up straighter"). Some measurements are directional: improving relative to your calibrated posture does not count as bad.

## Measurements

| Measurement | What It Detects |
|---|---|
| **Nose-Shoulder Gap** | Nose dropping too close to the shoulder line |
| **Shoulder Height** | Shoulders sitting lower on screen than the calibrated posture |

## Settings

- Coach personality (Standard / Drill Sergeant)
- gTTS voice/accent (US, UK, Australian, Canadian, Indian English)
- Sensitivity multipliers per measurement (1.0 = very sensitive, 4.0 = lenient)
- Bad posture time before an alert (5–60 seconds)
- Cooldown between alerts (15–300 seconds)
- Camera index selection
- Dark / Light mode
- Launch at startup/login

## Project Structure

```
proposture/
├── main.py                    # Entry point
├── constants.py               # All configurable values
├── package.json               # React/Tailwind frontend dependencies
├── vite.config.js             # Vite dev/build configuration
├── requirements.txt           # Dependencies
├── requirements-build.txt     # Build dependencies
├── build.py                   # Cross-platform PyInstaller build wrapper
├── ProPosture.spec            # PyInstaller app/exe spec
├── src/                       # React frontend source
├── frontend/
│   └── dist/                  # Built frontend loaded by WebView
├── backend/
│   ├── controller.py          # React-facing app controller
│   └── desktop_api.py         # pywebview JavaScript bridge
├── assets/
│   └── icon.png               # App icon
├── core/
│   ├── pose_detector.py       # MediaPipe landmark extraction
│   ├── posture_analyzer.py    # Vertical distance posture math
│   ├── calibration.py         # Calibration session management
│   ├── alert_engine.py        # Threshold and timing logic
│   └── startup.py             # Windows/macOS startup integration
├── audio/
│   └── voice_manager.py       # TTS with coach personalities
├── ui/
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

`build.py` runs the React production build first, then PyInstaller. PyInstaller builds for the OS it is running on. Run `python build.py` on Windows to create `dist/ProPosture.exe`, and run it on macOS to create `dist/ProPosture.app`.

## Requirements

- Python 3.11+
- Windows 10/11 or macOS
- Microsoft Edge WebView2 Runtime on Windows
- Webcam
- Speakers or headphones (for voice alerts)

## License

MIT
