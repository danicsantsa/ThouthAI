#!/usr/bin/env python3
"""
Cross-platform build script for Atum
Builds installers for Windows, macOS, and Linux
"""

import os
import sys
import platform
import subprocess
import shutil
import json
from pathlib import Path

# Windows consoles default to cp1252, which can't encode the emoji used in
# this script's log output. Force UTF-8 so prints don't crash the build.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass  # Python < 3.7 fallback, not expected here

# Configuration
PROJECT_NAME = "Atum"
VERSION = "1.0.0"
ICON_SOURCE = "workspace-tracking-icon.png"  # Source icon for all platforms
BUILD_DIR = Path("build")
DIST_DIR = Path("dist")
SPEC_FILE = "build/atum.spec"

def run_command(cmd, description, allow_fail=False):
    """Run a shell command and report progress"""
    print(f"\n{'='*60}")
    print(f"📦 {description}")
    print(f"{'='*60}")
    print(f"$ {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    print()

    result = subprocess.run(cmd, shell=isinstance(cmd, str))
    if result.returncode != 0:
        if allow_fail:
            print(f"⚠️  Non-fatal failure: {description}")
            return False
        print(f"❌ Failed: {description}")
        sys.exit(1)
    print(f"✅ Completed: {description}")
    return True

def ensure_directories():
    """Create necessary directories"""
    BUILD_DIR.mkdir(exist_ok=True)
    DIST_DIR.mkdir(exist_ok=True)

def install_build_dependencies():
    """Install PyInstaller and platform-specific tools"""
    print("\n📥 Installing build dependencies...")

    deps = ["pyinstaller", "pillow"]  # Pillow for icon conversion

    # Platform-specific dependencies
    system = platform.system()
    if system == "Windows":
        pass  # PyInstaller itself handles windowed builds via --windowed flag / spec
    elif system == "Darwin":  # macOS
        pass  # DMG creation uses the built-in hdiutil, no pip package needed
    elif system == "Linux":
        deps.extend(["fpm"])  # optional alt-path; dpkg-deb comes from dpkg-dev (apt, not pip)

    run_command(
        f"pip install {' '.join(deps)}",
        "Installing build dependencies"
    )

def convert_icon(source_path):
    """Convert PNG icon to platform-specific formats"""
    if not Path(source_path).exists():
        print(f"⚠️  Icon file not found: {source_path}")
        print("   Create a 512x512 PNG icon and place it at:", source_path)
        return

    print("\n🎨 Converting icon to platform formats...")

    try:
        from PIL import Image

        img = Image.open(source_path)

        # Windows icon (.ico)
        icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img_copy = img.convert('RGBA')
        ico_path = BUILD_DIR / "icon.ico"
        img_copy.save(str(ico_path), 'ico', sizes=icon_sizes)
        print(f"  ✅ Created Windows icon: {ico_path}")

        # macOS icon (.icns) - requires sips/iconutil, macOS only
        if platform.system() == "Darwin":
            icns_path = BUILD_DIR / "icon.icns"
            run_command(
                f"sips -s format icns {source_path} --out {icns_path}",
                "Creating macOS icon",
                allow_fail=True,
            )

        # Linux icon (PNG 512x512)
        linux_icon = BUILD_DIR / "icon_512.png"
        img.save(str(linux_icon))
        print(f"  ✅ Created Linux icon: {linux_icon}")

    except ImportError:
        print("  ⚠️  Pillow not installed - skipping icon conversion")

def build_windows_exe():
    """Build Windows executable using PyInstaller"""
    if platform.system() != "Windows":
        print("⏭️  Skipping Windows build (not on Windows)")
        return

    run_command(
        f"pyinstaller --noconfirm --clean {SPEC_FILE}",
        "Building Windows executable"
    )

    # Create Windows installer using NSIS (if available)
    installer_script = BUILD_DIR / "atum_installer.nsi"
    if shutil.which("makensis") and installer_script.exists():
        run_command(
            f"makensis {installer_script}",
            "Creating Windows installer (.exe)",
            allow_fail=True,
        )
    else:
        print("⚠️  NSIS not found or no .nsi script - shipping raw folder as .zip instead")

def build_mac_app():
    """Build macOS .app bundle and DMG"""
    if platform.system() != "Darwin":
        print("⏭️  Skipping macOS build (not on macOS)")
        return

    run_command(
        f"pyinstaller --noconfirm --clean {SPEC_FILE}",
        "Building macOS app bundle"
    )

    # Create DMG from just the .app bundle, not the whole dist/ folder
    app_path = DIST_DIR / f"{PROJECT_NAME}.app"
    dmg_path = DIST_DIR / f"{PROJECT_NAME}_{VERSION}.dmg"

    if app_path.exists():
        dmg_src = BUILD_DIR / "dmg_staging"
        if dmg_src.exists():
            shutil.rmtree(dmg_src)
        dmg_src.mkdir(parents=True)
        shutil.copytree(app_path, dmg_src / f"{PROJECT_NAME}.app")

        run_command(
            f"hdiutil create -volname {PROJECT_NAME} -srcfolder {dmg_src} -ov -format UDZO {dmg_path}",
            "Creating macOS DMG installer"
        )
    else:
        print(f"⚠️  {app_path} not found - PyInstaller may have produced a onedir build instead of .app")
        print("   Check that atum.spec builds a BUNDLE() for macOS.")

def build_linux_appimage():
    """Build Linux AppImage"""
    if platform.system() != "Linux":
        print("⏭️  Skipping Linux build (not on Linux)")
        return

    run_command(
        f"pyinstaller --noconfirm --clean {SPEC_FILE}",
        "Building Linux executable"
    )

    # Create AppImage directory structure
    appdir = DIST_DIR / f"{PROJECT_NAME}.AppDir"
    appdir.mkdir(exist_ok=True)

    # Copy built files
    exe_path = DIST_DIR / PROJECT_NAME
    shutil.copytree(exe_path, appdir / "usr" / "bin", dirs_exist_ok=True)

    # Create .desktop file
    desktop_content = f"""[Desktop Entry]
Type=Application
Name={PROJECT_NAME}
Comment=Activity Tracking Application
Exec=AppRun
Icon=atum
Terminal=false
Categories=Utility;
"""
    (appdir / f"{PROJECT_NAME}.desktop").write_text(desktop_content)

    # Copy icon
    icon_src = BUILD_DIR / "icon_512.png"
    if icon_src.exists():
        shutil.copy(icon_src, appdir / "atum.png")

    # Create AppImage (requires appimagetool on PATH)
    if shutil.which("appimagetool"):
        run_command(
            f"appimagetool {appdir} {DIST_DIR / f'{PROJECT_NAME}_{VERSION}.AppImage'}",
            "Creating Linux AppImage",
            allow_fail=True,
        )
    else:
        print("⚠️  appimagetool not found on PATH - skipping AppImage")
        print("   Download from: https://github.com/AppImage/AppImageKit/releases")

def build_linux_deb():
    """Build Debian package"""
    if platform.system() != "Linux":
        print("⏭️  Skipping Debian build (not on Linux)")
        return

    if not shutil.which("dpkg-deb"):
        print("⚠️  dpkg-deb not found - skipping .deb (install with: apt install dpkg-dev)")
        return

    # Create .deb structure
    deb_root = BUILD_DIR / "atum-deb"
    if deb_root.exists():
        shutil.rmtree(deb_root)
    deb_root.mkdir(exist_ok=True)

    # Create DEBIAN directory
    debian_dir = deb_root / "DEBIAN"
    debian_dir.mkdir(exist_ok=True)

    # Create control file
    control = f"""Package: atum
Version: {VERSION}
Architecture: amd64
Maintainer: Your Name <you@example.com>
Description: Atum - Activity Tracking Application
 Monitor computer activity and capture body/hand/face motion
 Real-time tracking with local database
 Cross-platform desktop application
"""
    (debian_dir / "control").write_text(control)

    # Copy executable (whole onedir folder so dependent .so files come along)
    exe_dir = deb_root / "usr" / "lib" / "atum"
    exe_dir.mkdir(parents=True, exist_ok=True)
    exe_src_dir = DIST_DIR / PROJECT_NAME
    if exe_src_dir.exists():
        shutil.copytree(exe_src_dir, exe_dir, dirs_exist_ok=True)

    bin_dir = deb_root / "usr" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "atum").write_text(f"#!/bin/sh\nexec /usr/lib/atum/{PROJECT_NAME} \"$@\"\n")
    os.chmod(bin_dir / "atum", 0o755)

    # Copy icon and desktop file
    share_dir = deb_root / "usr" / "share" / "applications"
    share_dir.mkdir(parents=True, exist_ok=True)

    desktop_file = share_dir / "atum.desktop"
    desktop_content = f"""[Desktop Entry]
Type=Application
Name=Atum
Comment=Activity Tracking Application
Exec=atum
Icon=atum
Terminal=false
Categories=Utility;
"""
    desktop_file.write_text(desktop_content)

    # Build deb package
    run_command(
        f"dpkg-deb --build {deb_root} {DIST_DIR / f'atum_{VERSION}_amd64.deb'}",
        "Creating Debian package",
        allow_fail=True,
    )

def main():
    """Main build orchestrator"""
    print(f"\n{'='*60}")
    print(f"🔨 Building {PROJECT_NAME} v{VERSION}")
    print(f"{'='*60}")
    print(f"Platform: {platform.system()}")
    print(f"Python: {sys.version.split()[0]}")

    # Setup
    ensure_directories()

    # Check if PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("\n⚠️  PyInstaller not found. Installing...")
        run_command("pip install pyinstaller", "Installing PyInstaller")

    # Convert icon
    convert_icon(ICON_SOURCE)

    # Build for current platform
    system = platform.system()

    if system == "Windows":
        build_windows_exe()
    elif system == "Darwin":
        build_mac_app()
    elif system == "Linux":
        build_linux_appimage()
        build_linux_deb()

    print(f"\n{'='*60}")
    print(f"✅ Build completed!")
    print(f"{'='*60}")
    print(f"\n📂 Output files in: {DIST_DIR}")
    print(f"   Run 'ls -la {DIST_DIR}' to see created installers\n")

if __name__ == "__main__":
    main()