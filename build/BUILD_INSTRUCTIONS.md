# Atum Build Instructions

This guide explains how to build installers for Atum on Windows, macOS, and Linux.

## Prerequisites

All platforms require:
- Python 3.8+
- git
- Internet connection for downloading dependencies

### Windows-Specific
- Visual Studio Build Tools or MinGW (for compiling native packages)
- NSIS (for creating .exe installers) - [Download](https://nsis.sourceforge.io/)
- Administrator access

### macOS-Specific
- Xcode Command Line Tools: `xcode-select --install`
- Rosetta 2 (for Apple Silicon): `softwareupdate --install-rosetta`

### Linux-Specific (Ubuntu/Debian)
```bash
sudo apt install build-essential python3-dev python3-pip
```

## Quick Build (Current Platform Only)

```bash
# 1. Clone or navigate to project directory
cd atum

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows

# 3. Install build dependencies
pip install pyinstaller pillow

# 4. Run the build script
python build/build.py
```

Output files will be in `dist/` directory.

## Building for Specific Platforms

### Windows

**Option 1: Download Pre-built Installer**
```
https://github.com/yourname/atum/releases → Atum_x.x.x_installer.exe
```

**Option 2: Build Locally**
```cmd
cd atum
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
pyinstaller build/atum.spec --onefile
```

**Option 3: Create Windows Installer (requires NSIS)**
```cmd
# After running PyInstaller
"C:\Program Files (x86)\NSIS\makensis.exe" build\atum_installer.nsi
```

### macOS

**Option 1: Download Pre-built DMG**
```bash
# From releases page
curl -L "https://github.com/yourname/atum/releases/download/v1.0.0/Atum_1.0.0.dmg" -o Atum.dmg
hdiutil attach Atum.dmg
cp -r "/Volumes/Atum/Atum.app" /Applications/
```

**Option 2: Build Locally**
```bash
cd atum
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller
pyinstaller build/atum.spec --onedir
```

**Option 3: Create DMG Installer**
```bash
# After PyInstaller
hdiutil create -volname "Atum" -srcfolder dist/Atum.app -ov -format UDZO Atum_1.0.0.dmg
```

**Option 4: Notarization (for App Store/secure distribution)**
```bash
# Sign the app
codesign -s - --deep dist/Atum.app

# Submit for notarization (Apple Developer account required)
xcrun altool --notarize-app -f Atum_1.0.0.dmg \
    -t osx \
    -u "your-apple-id@example.com" \
    -p "app-password"
```

### Linux (Ubuntu/Debian)

**Option 1: Download Pre-built Package**
```bash
# Download .deb
wget https://github.com/yourname/atum/releases/download/v1.0.0/atum_1.0.0_amd64.deb

# Or download AppImage
wget https://github.com/yourname/atum/releases/download/v1.0.0/Atum_1.0.0.AppImage
chmod +x Atum_1.0.0.AppImage
./Atum_1.0.0.AppImage
```

**Option 2: Install from Repository**
```bash
# Using provided installer script
curl -sSL https://your-domain.com/install-atum.sh | bash
```

**Option 3: Build Locally (.AppImage)**
```bash
cd atum
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller

# Build AppImage
pyinstaller build/atum.spec --onedir
./build/create_appimage.sh  # if available
```

**Option 4: Build Debian Package**
```bash
# Install dependencies
sudo apt install dpkg-dev fakeroot

# Build
python build/build_deb.py

# Result: dist/atum_1.0.0_amd64.deb
# Install with: sudo dpkg -i dist/atum_1.0.0_amd64.deb
```

## Cross-Platform Build (Automated)

Use the automated build script to build for all platforms:

```bash
# Note: Only works if you're on that platform
# Run this on each platform and collect outputs

# On Windows:
python build/build.py

# On macOS:
python build/build.py

# On Linux:
python build/build.py
```

## Creating a Release

### GitHub Releases Workflow

1. **Update version**
   ```bash
   # Edit build/atum.spec and build/build.py
   VERSION = "1.0.1"
   ```

2. **Build on each platform**
   ```bash
   # Windows: build/build.py → Atum_1.0.1_installer.exe
   # macOS: build/build.py → Atum_1.0.1.dmg
   # Linux: build/build.py → atum_1.0.1_amd64.deb, Atum_1.0.1.AppImage
   ```

3. **Create GitHub release**
   - Go to: https://github.com/yourname/atum/releases/new
   - Tag: `v1.0.1`
   - Title: `Atum v1.0.1`
   - Upload all installers

4. **Update website/documentation**
   - Add download links
   - Update version numbers
   - Post announcement

## Troubleshooting Build Issues

### PyInstaller Issues

**"Module not found" errors**
```bash
# Ensure hidden imports are in atum.spec
# Or install the module explicitly:
pip install [missing-package]
```

**Large executable size**
```python
# In atum.spec, add:
excludedimports=['numpy', 'pandas']  # If not needed
```

**Code sign errors (macOS)**
```bash
# Remove code signature requirements
codesign --remove-signature dist/Atum.app
```

### Platform-Specific Issues

**Windows: "Python not found"**
- Reinstall Python with "Add Python to PATH" option
- Or set path manually in NSIS script

**macOS: "App is damaged"**
```bash
# Fix with:
xattr -d com.apple.quarantine /Applications/Atum.app
```

**Linux: AppImage won't run**
```bash
# Make executable
chmod +x Atum_*.AppImage

# Or run with:
./Atum_1.0.0.AppImage --appimage-extract-and-run
```

## CI/CD Integration

### GitHub Actions Example

See `.github/workflows/build.yml` for automated builds on every push:

```yaml
name: Build Atum

on: [push, pull_request]

jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt && pip install pyinstaller
      - run: python build/build.py
      - uses: actions/upload-artifact@v2
        with:
          name: atum-${{ matrix.os }}
          path: dist/
```

## Performance Optimization

### Reducing Binary Size
```bash
# Use UPX compression
pip install upx
pyinstaller --upx-dir=/path/to/upx build/atum.spec
```

### Startup Time
```python
# In atum.spec:
a = Analysis([...],
    hiddenimports=[],  # Remove unused imports
    excludedimports=['matplotlib', 'pandas'],  # If not needed
)
```

## Signing & Notarization

### Windows Authenticode Signing
```bash
# Requires digital certificate
signtool sign /f cert.pfx /p password /t http://timestamp.server.com Atum.exe
```

### macOS Notarization
```bash
# Create App ID, then:
xcrun altool --notarize-app -f Atum.dmg \
    -u your-apple-id \
    -p app-specific-password
```

## Distribution Options

1. **Direct Download** (Recommended for small teams)
   - GitHub Releases
   - Website download link
   - Cloud storage (Google Drive, Dropbox)

2. **Package Managers**
   - Homebrew (macOS): `brew install atum`
   - apt (Linux): `apt install atum`
   - choco/winget (Windows)

3. **Enterprise Distribution**
   - Microsoft Intune
   - JAMF (macOS)
   - Puppet/Chef (Linux)

## Support & Debugging

- **Build logs**: Check console output for errors
- **Common issues**: See "Troubleshooting" section above
- **Version compatibility**: Ensure Python 3.8+ and all dependencies installed
- **Platform testing**: Test on clean installations before release

---

For questions or issues, please open a GitHub issue or contact the maintainers.
