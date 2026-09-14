# Atum — Computer Activity + Body / Hand / Face Motion Capture

**Professional activity tracking and motion capture for Windows, macOS, and Linux**

This application combines:

- 📊 Computer activity monitoring (active app/window detection)
- 🧘 Body pose tracking with MediaPipe
- 👤 Face landmark detection
- 🖐️ Hand tracking and gestures
- 📱 Touch and interaction detection
- 💾 Local database and CSV logging
- 🖥️ Professional desktop GUI

## Quick Start

### Windows
1. Download `Atum_installer.exe` from [Releases](https://github.com/yourname/atum/releases)
2. Run the installer
3. Search for "Atum" in Start Menu and click to launch

### macOS
1. Download `Atum.dmg` from [Releases](https://github.com/yourname/atum/releases)
2. Double-click to mount, then drag `Atum.app` to Applications
3. Launch from Applications or Spotlight (⌘+Space, type "Atum")

### Linux (Ubuntu/Debian)
```bash
curl -sSL https://your-domain.com/install-atum.sh | bash
```
Or download `.deb` package and install with:
```bash
sudo dpkg -i atum_*.deb
```

## Features

✨ **User-Friendly**
- One-click setup wizard
- Auto-detects your camera
- Works immediately after installation

🔧 **Powerful**
- Real-time motion capture
- Comprehensive activity logging
- Professional data export (CSV, Database)
- Work/non-work classification

🌍 **Cross-Platform**
- Windows (7+)
- macOS (10.12+)
- Linux (Ubuntu, Debian, Fedora)

## Main Components

- `tracking_gui.py` — Professional desktop interface
- `track_all.py` — Combined tracking engine (camera + activity)
- `activity_tracker.py` — Active window and productivity classification
- `camera_utils.py` — Camera detection and image processing
- `db_client.py` / `db_queries.py` — Database integration
- `pose_face_hand_detection.py` — Computer vision pipelines

## For Developers

### Install from Source

**Requirements:**
- Python 3.8 or higher
- 500 MB disk space
- Webcam (optional, required for motion tracking)

**Linux:**
```bash
git clone https://github.com/yourname/atum.git
cd atum
chmod +x build/install_linux.sh
./build/install_linux.sh
```

**macOS:**
```bash
git clone https://github.com/yourname/atum.git
cd atum
chmod +x build/install_macos.sh
./build/install_macos.sh
```

**Windows:**
```cmd
git clone https://github.com/yourname/atum.git
cd atum
build\install_windows.bat
```

Or manually:

```bash
# Clone and navigate
git clone https://github.com/yourname/atum.git
cd atum

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python atum.py
```

## Building Installers

To build installers for distribution:

```bash
# Install build dependencies
pip install pyinstaller pillow

# Run the build script (from your platform)
python build/build.py
```

Output installers will be in `dist/` directory.

## Requirements

### Python Packages
- `opencv-python` ≥ 4.8.0 — Video capture and image processing
- `mediapipe` == 0.10.14 — Body/face/hand detection (⚠️ use exactly this version)
- `psycopg2-binary` ≥ 2.9.0 — PostgreSQL database connection
- `matplotlib` ≥ 3.7.0 — Data visualization
- `pandas` ≥ 1.5.0 — Data manipulation

### System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt install python3-tk python3-dev libssl-dev
```

**Fedora/RHEL:**
```bash
sudo dnf install python3-tkinter python3-devel openssl-devel
```

**macOS:**
```bash
brew install python3 openssl
```

### Important Notes
- **MediaPipe version:** Do NOT use MediaPipe 1.0.1+ — it's missing the `mp.solutions` API
- **Python version:** Python 3.8+ required
- **Camera:** Optional; app works without camera for activity tracking only

## Run the application

```bash
# Quick start from anywhere (if installed)
atum

# Or from source folder
python atum.py
```

## Technical Architecture

**Data Flow:**
```
Camera Input ──┐
               ├─→ Motion Detection (MediaPipe) ──┐
Computer Activity ─→ Activity Classifier         ├─→ Database
Keyboard/Mouse ────→ Touch Detector         ──────┘
                        ↓
                    CSV Logging
```

**Database:**
- Optional PostgreSQL backend for scalable logging
- Fallback CSV storage (always enabled)
- Real-time batch flushing for performance

**Detection Pipelines:**
- **Pose:** Full body skeleton detection (33 keypoints)
- **Face:** 468 facial landmarks with expression inference
- **Hand:** Per-hand detection (21 keypoints × 2 hands)
- **Activity:** Window title parsing + ML classification

## Notes

- The app expects project files to remain in the same directory
- Camera and activity trackers run in one combined workflow
- Database is optional; CSV logging works offline
- Works with or without a webcam
- Minimal dependencies for easy deployment

## Troubleshooting

### App won't launch
- **Windows:** Make sure Python was installed with "Add to PATH" enabled
- **macOS:** Use "Open" from right-click menu if security prompt appears
- **Linux:** Check that Python 3 and tkinter are installed

### Camera not detected
- Ensure camera is connected and not in use by another app
- Try refreshing camera list in Settings
- App works without camera (activity tracking only)

### High CPU usage
- Reduce resolution in Settings
- Lower detection frequency
- Disable pose/face/hand tracking if not needed

### Database connection fails
- CSV logging continues automatically
- Check `db_config.json` credentials
- Database is optional

## Use Cases

This application is suitable for:

- 📊 Productivity and computer usage analysis
- 🧍 Ergonomics and posture monitoring
- 👁️ Face/hand/body motion tracking studies
- 🔬 Research prototypes and internal monitoring
- 💼 Employee activity tracking (with consent)

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test on all platforms
4. Submit a pull request

## License

This project is provided as-is. Please see LICENSE file for details.

## Support

- 📖 [Full Documentation](https://github.com/yourname/atum/wiki)
- 🐛 [Report Issues](https://github.com/yourname/atum/issues)
- 💬 [Discussions](https://github.com/yourname/atum/discussions)

---

**Made with ❤️ for activity tracking and motion capture**
