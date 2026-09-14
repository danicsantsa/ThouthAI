# Atum Installation & Setup Guide

**For Regular Users** — Follow the simple steps for your operating system.

---

## Installation

### Windows (Easiest!)

1. **Download the Windows installer**
   - Download `Atum_1.0.0_installer.exe` from your release page.
   - File size: ~150 MB

2. **Run installer**
   - Double-click `Atum_1.0.0_installer.exe`
   - Click "Next" and then "Install".
   - Wait for completion (~1-2 minutes)

3. **Launch Atum**
   - **Method 1:** Search for "Atum" in Windows Start Menu → Click
   - **Method 2:** Find shortcut on Desktop
   - **Method 3:** Start Menu → Programs → Atum

✅ **That's it! No technical knowledge required.**

---

### macOS

1. **Download the DMG**
   - Download `Atum_1.0.0.dmg` from your release page.
   - File size: ~180 MB

2. **Install**
   - Double-click `Atum_1.0.0.dmg`
   - Drag `Atum.app` → Applications folder
   - Wait for copy to complete (~1 minute)

3. **Launch Atum**
   - **Method 1:** Spotlight search (⌘+Space) → type "Atum" → press Enter
   - **Method 2:** Applications folder → double-click Atum
   - **Method 3:** Launchpad → Atum

**Tip:** First time opening? macOS may show security warning → Click "Open"

✅ **Done! Start tracking your activity.**

---

### Linux (Ubuntu/Debian)

For Linux, use the provided AppImage or `.deb` package. No Python or Tkinter installation is required.

#### Quick Install (Recommended)
```bash
# One-line installer (requires internet)
curl -sSL https://your-domain.com/install-atum.sh | bash
```

#### Manual Install from .deb Package
```bash
# 1. Download
wget https://github.com/yourname/atum/releases/download/v1.0.0/atum_1.0.0_amd64.deb

# 2. Install
sudo dpkg -i atum_1.0.0_amd64.deb

# 3. Launch
atum
```

#### Using AppImage (No Installation)
```bash
# 1. Download
wget https://github.com/yourname/atum/releases/download/v1.0.0/Atum_1.0.0.AppImage

# 2. Make executable
chmod +x Atum_1.0.0.AppImage

# 3. Run
./Atum_1.0.0.AppImage
```

**Tip:** For .deb installation, you can search "Atum" in your application menu afterward.

---

## First Launch

When you open Atum for the first time:

1. **Setup Wizard** appears automatically
   ```
   Welcome to Atum!
   ────────────────
   Let's set up your tracking profile.
   ```

2. **Enter your name** (e.g., "John")
   - This identifies the person in the session data.

3. **Allow camera access** when Windows or macOS asks.

4. **Click "Start Tracking"**
   - Application begins monitoring your activity
   - You'll see real-time status in the window

---

## ⚙️ Basic Settings

### Access Settings
- **Windows/macOS/Linux:** Menu → Settings (gear icon 🔧)

### Common Settings

**Activity Categories**
- Set which apps count as "Work" vs "Breaks"
- Default: Office apps = Work, Social media = Breaks

**Camera Settings**
- On/Off: Enable if you want pose tracking
- Detection interval: How often to check motion
- Resolution: Lower = faster but less accurate

**Recording**
- Start/Stop recording anytime
- Data saved automatically to local database
- CSV exports available in "Export Data"

**Database**
- Local CSV/video data works without a database.
- Supabase synchronization is optional and configured by the administrator.

---

## ✅ System Requirements

### Minimum (Will Work)
- **Windows:** 10 or newer
- **macOS:** 12 or newer
- **Linux:** Ubuntu 20.04+ or Debian 11+
- **RAM:** 2 GB
- **Disk:** 500 MB free space
- **Camera:** Optional (activity tracking works without it)

### Recommended (Better Experience)
- **RAM:** 4 GB+
- **SSD:** Better startup speed
- **Camera:** 720p or better
- **Stable internet:** For cloud sync (optional)

---

## 🚀 Quick Start: Activity Tracking

**Without Camera (Just Computer Activity)**

1. Launch Atum
2. Complete setup wizard
3. Click "Start Tracking"
4. Go about your work normally
5. Atum monitors:
   - Which apps you use
   - Time spent in each
   - Work vs. break time

**View Results**
- "Dashboard" tab shows real-time activity
- "Statistics" tab shows trends
- "Export" saves data as CSV

---

## 📊 Understanding Your Data

### Activity Dashboard Shows:
- **Active Window:** What you're currently using
- **Active App Category:** Work / Break / Other
- **Session Time:** How long tracking is running
- **Motion Detection:** If camera is detecting movement

### CSV Files Created:
- `activity_log.csv` — Every app switch
- `pose_data.csv` — Body position tracking (if camera on)
- `touch_events.csv` — Keyboard/mouse activity

### Export Options:
- Click "Export Data" → Choose date range
- Download CSV files for analysis in Excel/Sheets

---

## 🔧 Troubleshooting

### App Won't Start

**Windows:**
- Re-run the installer.
- Allow Atum to access the camera under **Settings > Privacy & security > Camera**.
- Run as Administrator (right-click → Run as Administrator)

**macOS:**
- Check that Atum is in Applications.
- If macOS blocks an unsigned app: right-click Atum and choose **Open**.
- Allow the camera under **System Settings > Privacy & Security > Camera**.

**Linux:**
- If using AppImage: `chmod +x Atum_*.AppImage`
- If using .deb: `sudo apt install atum`
- Check that Python 3 is installed: `python3 --version`

### Camera Not Working

1. Check camera in system settings
2. Make sure no other app is using it
3. In Atum Settings → Camera → Try "Refresh"
4. Restart Atum

**Note:** App works fine without camera!

### High CPU Usage

1. Open Settings
2. Lower "Detection Interval" value
3. Disable "Pose Tracking" if not needed
4. Close unnecessary apps

### Database Connection Error

- **Don't worry!** App continues logging to CSV files
- Check `db_config.json` file (advanced)
- Contact support or try offline mode

---

## 📁 Data Privacy

**Your data stays on your computer:**
- All activity logs saved locally
- No automatic upload to cloud
- You control exports

**To backup:**
- Use "Export Data" feature
- Or backup folder: (varies by OS)
  - Windows: `%ProgramFiles%\Atum`
  - macOS: `~/Library/Application Support/Atum`
  - Linux: `~/.local/share/atum`

---

## 🆘 Need Help?

### Common Issues

| Problem | Solution |
|---------|----------|
| App crashes on startup | Reinstall from scratch |
| Camera shows as unavailable | Try different camera in Settings |
| Very high CPU usage | Disable pose/face/hand tracking |
| Can't find installation folder | Default location shown in installer |

### Getting Support
- **Bug reports:** https://github.com/yourname/atum/issues
- **Questions:** https://github.com/yourname/atum/discussions
- **Documentation:** https://github.com/yourname/atum/wiki

---

## 🎓 Tips for Best Results

1. **Position camera well**
   - At eye level
   - Good lighting
   - Clear face view

2. **Set work/break categories**
   - Customize in Settings
   - Helps with productivity analysis

3. **Regular exports**
   - Export data monthly for backup
   - Useful for reporting

4. **Update regularly**
   - Check for updates monthly
   - Better performance and features

---

## Uninstalling

### Windows
- Settings → Programs → Programs and Features → Atum → Uninstall
- Or use installer again and choose "Uninstall"

### macOS
- Applications folder → Atum → Move to Trash
- Or drag Atum to Trash

### Linux (from .deb)
```bash
sudo apt remove atum
```

### Linux (AppImage)
- Simply delete the `.AppImage` file

---

**You're all set! Happy tracking! 🎉**

For the latest version and updates, visit:
👉 https://github.com/yourname/atum
