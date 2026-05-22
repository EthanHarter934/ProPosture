# ProPosture

**Real-time posture monitoring for your desk setup.** ProPosture uses your webcam and MediaPipe Pose to analyze your sitting posture, compares it against your personal calibrated baseline, and coaches you with spoken alerts when you start slouching. The standalone desktop UI is a React + Tailwind frontend loaded from bundled files in a native WebView shell, with direct JavaScript-to-Python calls through the desktop bridge.

## Features

- 🎯 **Personalized Calibration** — Your baseline is YOUR good posture, with practical tolerance floors to avoid overreacting to webcam jitter.
- 📐 **Vertical Posture Measurements** — Nose-to-shoulder height and shoulder screen position, both compared against your calibrated baseline.
- 🎙️ **Voice Options** — Standard gTTS voices or optional VoxCPM2 custom voice generation.
- 🔒 **100% Local** — Camera feed is processed on-device. Nothing is recorded or transmitted.
- 📌 **System Tray** — Runs silently in the background with quick tray menu access.
- ⌨️ **Global Hotkey** — Ctrl+Shift+P to toggle pause from anywhere.
- 📊 **Session Stats** — Track time monitored, alerts, and longest good posture streak.

## Quick Start

### Prerequisites

- **Python 3.11+** (test with `python --version`)
- **Node.js and npm** (test with `npm --version`)
- **Windows only: Microsoft Edge WebView2 Runtime** — [Download](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)
- **Webcam** and speakers/headphones

### 1. Clone & Install

```bash
git clone <repo-url>
cd ProPosture

# Create a Python 3.11+ virtual environment
python3 -m venv .venv

# Activate the virtual environment
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Install Python dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# Install and build frontend
npm install
npm run build
```

### 2. Verify the Setup

Run the verification script to ensure all dependencies are installed correctly:

```bash
python verify_setup.py
```

If verification passes, you're ready to run the app. If any checks fail, follow the error messages to fix them.

### 3. Run the App

```bash
python main.py
```

The Python backend opens the bundled React UI inside the ProPosture desktop window. On first launch, the **Calibration Wizard** guides you through setting your personal posture baseline.

⚠️ **Note:** If you set voice mode to "Custom Voice (VoxCPM2)", the app will warn you if the voice server is not running.

### 4. (Optional) Run the VoxCPM2 Voice Server

To use the **Custom Voice (VoxCPM2)** feature, you need to run the voice generation server. This is optional and only required if you want custom voice generation. The server runs on a CUDA-capable machine and can be hosted separately.

```bash
cd voice_server

# 1. Create a Python 3.11 virtual environment
#    (Python 3.12+ or 3.10 may fail to install PyTorch/Pythonnet)
py -3.11 -m venv venv

# 2. Activate the environment
# Windows
venv\Scripts\activate
# OR macOS/Linux
source venv/bin/activate

# 3. Verify you're using Python 3.11.x
python --version

# 4. Install dependencies
pip install -r requirements.txt

# 5. (Optional) Configure Gemini Preprocessing
# Create a .env file in the voice_server/ directory:
#   GEMINI_API_KEY=your_actual_api_key_here
# This allows the server to optimize voice prompts automatically.

# 6. Pre-download the voice model (handles network interruptions)
huggingface-cli download openbmb/VoxCPM2

# 7. Start the server
python server.py --host 0.0.0.0 --port 5123
```

The app will look for the server at `http://localhost:5123` by default. You can change this in **Settings > Voice > Voice Server URL**.

### 5. Usage

- The app monitors your posture via webcam and alerts you with spoken feedback.
- To use **custom voices**, go to **Settings > Voice**, select **Custom Voice (VoxCPM2)**, type a voice description, and click **Generate Voice** (requires the voice server running).
- **Minimize** the window to send it to the system tray.
- **Right-click the tray icon** for quick access to Pause, Resume, Recalibrate, or Quit.
- Press **Ctrl+Shift+P** anywhere to toggle pause on platforms supported by the `keyboard` package.

## How It Works

1. **Calibrate** — Sit with ideal posture. ProPosture captures 90 frames (3 seconds) to learn your personal baseline, using robust center and jitter estimates so a few noisy frames do not skew the profile.

2. **Monitor** — In the background, each frame is compared to your baseline using vertical screen distances. Thresholds are percentages of your calibrated nose-to-shoulder distance, which keeps posture scoring relative to each person and camera setup.

3. **Alert** — If bad posture persists for a configurable duration (default: 10 seconds), your chosen coach speaks up with specific feedback (e.g., "lift your head" or "sit up straighter"). Some measurements are directional: improving relative to your calibrated posture does not count as bad.

## Measurements

| Measurement           | What It Detects                                               |
| --------------------- | ------------------------------------------------------------- |
| **Nose-Shoulder Gap** | Nose dropping too close to the shoulder line                  |
| **Shoulder Height**   | Shoulders sitting lower on screen than the calibrated posture |

## Settings

- Voice mode (Standard TTS / Custom Voice)
- gTTS voice/accent (US, UK, Australian, Canadian, Indian English)
- Custom Voice (VoxCPM2) mode with optional Gemini prompt preprocessing
- Sensitivity multipliers per measurement (1.0 = very sensitive, 4.0 = lenient)
- Bad posture time before an alert (5–60 seconds)
- Cooldown between alerts (15–300 seconds)
- Camera index selection
- Dark / Light mode
- Launch at startup/login

## Development Checks

Run these from the repository root after installing dependencies:

```bash
# Frontend lint
npm run lint

# Frontend production build used by the desktop app
npm run build

# Frontend lint + build
npm run check

# Python unit tests
python -m unittest discover -s tests

# Python syntax/import compilation check
python -m compileall -q . -x './(\.git|\.venv|node_modules|build|dist|frontend/dist)/'
```

The test suite uses Python's built-in `unittest`, so `pytest` is not required.

## Project Structure

```
proposture/
├── main.py                    # Entry point
├── constants.py               # All configurable values
├── package.json               # React/Tailwind frontend dependencies
├── eslint.config.js           # Frontend lint configuration
├── vite.config.js             # Vite dev/build configuration
├── requirements.txt           # Dependencies
├── requirements-build.txt     # Build dependencies
├── build.py                   # Cross-platform PyInstaller build wrapper
├── ProPosture.spec            # PyInstaller app/exe spec
├── src/                       # React frontend source
├── frontend/
│   └── dist/                  # Generated by npm run build; loaded by WebView
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
├── voice_server/              # Optional VoxCPM2 custom voice generation server
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

- **Python 3.11+** (test with `python --version`)
- **Node.js 14+** and npm
- **Windows 10/11, macOS, or Linux**
- **Microsoft Edge WebView2 Runtime** on Windows ([Download](https://developer.microsoft.com/en-us/microsoft-edge/webview2/))
- **Webcam** and speakers/headphones for voice alerts
- **CUDA GPU** (optional — only if running the custom voice server locally)

## Troubleshooting

**Setup Issues**

- Run `python verify_setup.py` to diagnose installation problems.
- Use the virtual environment's `python` after activation. On some systems, `python` outside the venv may point to Python 2.
- Ensure WebView2 Runtime is installed on Windows: [Download](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)

**Runtime Issues**

- **"Frontend build is missing"** — Run `npm run build` from the repository root.
- **Custom Voice not working** — Check that the voice server is running at the configured URL. The app will warn you if it cannot reach the server.
- **gTTS voice not generating** — Requires network access. Generated MP3 files are cached under the local app data directory for offline use.
- **Camera not detected** — Try a different camera index in **Settings > Camera**.
- **MediaPipe model not found** — Ensure `assets/pose_landmarker_lite.task` exists. This file is included in the repository.

## License

MIT
