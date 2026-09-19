#!/usr/bin/env python3
"""
Cross-platform build script for Atum
Builds installers for Windows (NSIS), macOS (DMG) and Linux (AppImage + .deb).

Usage (from anywhere):  python build/build.py

In CI (env var CI=true, set automatically by GitHub Actions) the script is
strict: a missing installer makes the build fail instead of being ignored.
"""

import os
import sys
import platform
import subprocess
import shutil
import time
from pathlib import Path

# Windows consoles default to cp1252, which can't encode the emoji used in
# this script's log output. Force UTF-8 so prints don't crash the build.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent  # repo root (parent of build/)

PROJECT_NAME = "Atum"
ICON_SOURCE = "workspace-tracking-icon.png"  # Source icon for all platforms
BUILD_DIR = Path("build")
DIST_DIR = Path("dist")
SPEC_FILE = "build/atum.spec"

# TODO: enter your real maintainer data (used in the .deb control file)
MAINTAINER = "Dein Name <deine@mail.de>"

# System libraries Qt needs at runtime on Debian/Ubuntu
DEB_DEPENDS = [
    "libegl1", "libgl1", "libglib2.0-0", "libdbus-1-3", "libfontconfig1",
    "libxkbcommon0", "libxkbcommon-x11-0", "libxcb-cursor0",
    "libxcb-icccm4", "libxcb-image0", "libxcb-keysyms1", "libxcb-randr0",
    "libxcb-render-util0", "libxcb-shape0", "libxcb-xinerama0",
]

# In CI, errors in installer steps must not be swallowed
STRICT = bool(os.environ.get("CI"))

# CPU architecture handling (Linux packaging)
MACHINE = platform.machine().lower()
DEB_ARCH = {"x86_64": "amd64", "amd64": "amd64",
            "aarch64": "arm64", "arm64": "arm64"}.get(MACHINE, "amd64")
APPIMAGE_ARCH = "aarch64" if MACHINE in ("aarch64", "arm64") else "x86_64"


def _detect_version():
    """Use the git tag (v1.2.3 -> 1.2.3) when built from a tag in CI."""
    if os.environ.get("GITHUB_REF_TYPE") == "tag":
        ref_name = os.environ.get("GITHUB_REF_NAME", "")
        if ref_name:
            return ref_name.lstrip("v")
    return "1.0.0"


VERSION = _detect_version()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def run_command(cmd, description, allow_fail=False, env=None, retries=1):
    """Run a command and report progress. Prefer list commands (no shell)."""
    print(f"\n{'=' * 60}")
    print(f"📦 {description}")
    print(f"{'=' * 60}")
    shown = " ".join(str(c) for c in cmd) if isinstance(cmd, list) else cmd
    print(f"$ {shown}")
    print()

    for attempt in range(1, retries + 1):
        result = subprocess.run(cmd, shell=isinstance(cmd, str), env=env)
        if result.returncode == 0:
            print(f"✅ Completed: {description}")
            return True
        if attempt < retries:
            print(f"⚠️  Attempt {attempt}/{retries} failed, retrying in 5s...")
            time.sleep(5)

    if allow_fail:
        print(f"⚠️  Non-fatal failure: {description}")
        return False
    print(f"❌ Failed: {description}")
    sys.exit(1)


def ensure_directories():
    """Create necessary directories"""
    BUILD_DIR.mkdir(exist_ok=True)
    DIST_DIR.mkdir(exist_ok=True)


def ensure_pyinstaller():
    """Install PyInstaller if it is missing"""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("\n⚠️  PyInstaller not found. Installing...")
        run_command(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            "Installing PyInstaller",
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
        ico_path = BUILD_DIR / "icon.ico"
        img.convert("RGBA").save(str(ico_path), "ICO", sizes=icon_sizes)
        print(f"  ✅ Created Windows icon: {ico_path}")

        # macOS icon (.icns) - sips is macOS only
        if platform.system() == "Darwin":
            icns_path = BUILD_DIR / "icon.icns"
            run_command(
                ["sips", "-s", "format", "icns", str(source_path), "--out", str(icns_path)],
                "Creating macOS icon",
                allow_fail=True,
            )

        # Linux icon (PNG)
        linux_icon = BUILD_DIR / "icon_512.png"
        img.save(str(linux_icon))
        print(f"  ✅ Created Linux icon: {linux_icon}")

    except ImportError:
        print("  ⚠️  Pillow not installed - skipping icon conversion")


def run_pyinstaller():
    """Build the onedir application with PyInstaller (once for all platforms)"""
    if not Path(SPEC_FILE).exists():
        print(f"❌ Spec file not found: {SPEC_FILE}")
        sys.exit(1)

    run_command(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", SPEC_FILE],
        f"Building {PROJECT_NAME} with PyInstaller",
    )


def ensure_appimagetool():
    """Download appimagetool locally when the Linux build wants an AppImage."""
    if platform.system() != "Linux":
        return

    tool = shutil.which("appimagetool")
    if tool:
        return

    local_dir = Path.home() / ".local" / "bin"
    local_dir.mkdir(parents=True, exist_ok=True)
    tool_path = local_dir / "appimagetool"

    if tool_path.exists():
        os.environ["PATH"] = f"{local_dir}:{os.environ.get('PATH','')}"
        return

    url = "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    print("\n⚠️  appimagetool not found. Downloading it automatically...")
    try:
        import urllib.request
        urllib.request.urlretrieve(url, str(tool_path))
        tool_path.chmod(0o755)
        os.environ["PATH"] = f"{local_dir}:{os.environ.get('PATH','')}"
        print(f"  ✅ Downloaded appimagetool to {tool_path}")
    except Exception as exc:
        print(f"  ⚠️  Could not download appimagetool automatically: {exc}")


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------
def build_windows_installer():
    """Create the Windows installer with NSIS"""
    if platform.system() != "Windows":
        print("⏭️  Skipping Windows installer (not on Windows)")
        return

    installer_script = BUILD_DIR / "atum_installer.nsi"
    makensis = shutil.which("makensis")

    if not makensis or not installer_script.exists():
        print("⚠️  NSIS (makensis) or build/atum_installer.nsi not found - no installer created")
        return

    # makensis resolves relative paths against the folder of the .nsi file
    # (build/), so OutFile / File lines should use ..\dist\...
    run_command(
        [makensis, str(installer_script)],
        "Creating Windows installer (.exe)",
        allow_fail=not STRICT,
    )


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------
def build_mac_dmg():
    """Create a DMG from the .app bundle"""
    if platform.system() != "Darwin":
        print("⏭️  Skipping macOS DMG (not on macOS)")
        return

    app_path = DIST_DIR / f"{PROJECT_NAME}.app"
    dmg_path = DIST_DIR / f"{PROJECT_NAME}_{VERSION}.dmg"

    if not app_path.exists():
        print(f"⚠️  {app_path} not found - PyInstaller may have produced a onedir build instead of .app")
        print("   Check that atum.spec builds a BUNDLE() for macOS.")
        return

    dmg_src = BUILD_DIR / "dmg_staging"
    if dmg_src.exists():
        shutil.rmtree(dmg_src)
    dmg_src.mkdir(parents=True)

    # symlinks=True keeps the internal symlinks of the .app bundle intact
    shutil.copytree(app_path, dmg_src / app_path.name, symlinks=True)

    # Drag-and-drop shortcut to /Applications
    try:
        (dmg_src / "Applications").symlink_to("/Applications")
    except OSError:
        pass

    if dmg_path.exists():
        dmg_path.unlink()

    # hdiutil occasionally fails with "Resource busy" on CI runners -> retry
    run_command(
        ["hdiutil", "create", "-volname", PROJECT_NAME,
         "-srcfolder", str(dmg_src), "-ov", "-format", "UDZO", str(dmg_path)],
        "Creating macOS DMG installer",
        allow_fail=not STRICT,
        retries=3,
    )


# ---------------------------------------------------------------------------
# Linux
# ---------------------------------------------------------------------------
def _linux_onedir():
    exe_dir = DIST_DIR / PROJECT_NAME
    if not exe_dir.is_dir():
        print(f"❌ {exe_dir} not found. atum.spec must create a onedir build (COLLECT), not onefile.")
        sys.exit(1)
    return exe_dir


def build_linux_appimage():
    """Build Linux AppImage"""
    if platform.system() != "Linux":
        print("⏭️  Skipping AppImage build (not on Linux)")
        return

    ensure_appimagetool()

    # AppDir lives in build/ so dist/ only contains deliverables
    appdir = BUILD_DIR / f"{PROJECT_NAME}.AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)
    bin_dir = appdir / "usr" / "bin"
    bin_dir.mkdir(parents=True)
    shutil.copytree(exe_dir, bin_dir, dirs_exist_ok=True, symlinks=True)

    # .desktop file
    desktop_content = f"""[Desktop Entry]
Type=Application
Name={PROJECT_NAME}
Comment=Activity Tracking Application
Exec={PROJECT_NAME}
Icon=atum
Terminal=false
Categories=Utility;
"""
    (appdir / f"{PROJECT_NAME}.desktop").write_text(desktop_content)

    # AppRun: required entry point of every AppImage
    apprun = appdir / "AppRun"
    apprun.write_text(
        '#!/bin/sh\n'
        'HERE="$(dirname "$(readlink -f "$0")")"\n'
        f'exec "$HERE/usr/bin/{PROJECT_NAME}" "$@"\n'
    )
    os.chmod(apprun, 0o755)

    # Icon (must be named like the Icon= entry: atum.png)
    icon_src = BUILD_DIR / "icon_512.png"
    if icon_src.exists():
        shutil.copy(icon_src, appdir / "atum.png")
    else:
        print("⚠️  build/icon_512.png missing - AppImage will have no icon")

    env = {**os.environ, "ARCH": APPIMAGE_ARCH, "APPIMAGE_EXTRACT_AND_RUN": "1"}
    appimage_path = DIST_DIR / f"{PROJECT_NAME}_{VERSION}.AppImage"

    run_command(
        ["appimagetool", str(appdir), str(appimage_path)],
        "Creating Linux AppImage",
        allow_fail=not STRICT,
        env=env,
    )


def build_linux_deb():
    """Build Debian package"""
    if platform.system() != "Linux":
        print("⏭️  Skipping Debian build (not on Linux)")
        return

    if not shutil.which("dpkg-deb"):
        print("⚠️  dpkg-deb not found - skipping .deb (install with: apt install dpkg-dev)")
        return

    exe_src_dir = _linux_onedir()

    deb_root = BUILD_DIR / "atum-deb"
    if deb_root.exists():
        shutil.rmtree(deb_root)

    # DEBIAN/control
    debian_dir = deb_root / "DEBIAN"
    debian_dir.mkdir(parents=True)
    control = f"""Package: atum
Version: {VERSION}
Section: utils
Priority: optional
Architecture: {DEB_ARCH}
Maintainer: {MAINTAINER}
Depends: {", ".join(DEB_DEPENDS)}
Description: Atum - Activity Tracking Application
 Monitor computer activity and capture body/hand/face motion
 Real-time tracking with local database
 Cross-platform desktop application
"""
    (debian_dir / "control").write_text(control)

    # Application files (whole onedir folder so dependent .so files come along)
    lib_dir = deb_root / "usr" / "lib" / "atum"
    lib_dir.mkdir(parents=True)
    shutil.copytree(exe_src_dir, lib_dir, dirs_exist_ok=True, symlinks=True)

    # Launcher in /usr/bin
    bin_dir = deb_root / "usr" / "bin"
    bin_dir.mkdir(parents=True)
    launcher = bin_dir / "atum"
    launcher.write_text(f'#!/bin/sh\nexec /usr/lib/atum/{PROJECT_NAME} "$@"\n')
    os.chmod(launcher, 0o755)

    # Desktop entry
    apps_dir = deb_root / "usr" / "share" / "applications"
    apps_dir.mkdir(parents=True)
    desktop_content = """[Desktop Entry]
Type=Application
Name=Atum
Comment=Activity Tracking Application
Exec=atum
Icon=atum
Terminal=false
Categories=Utility;
"""
    (apps_dir / "atum.desktop").write_text(desktop_content)

    # Icon
    icon_src = BUILD_DIR / "icon_512.png"
    if icon_src.exists():
        icon_dir = deb_root / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps"
        icon_dir.mkdir(parents=True)
        shutil.copy(icon_src, icon_dir / "atum.png")
    else:
        print("⚠️  build/icon_512.png missing - .deb will have no icon")

    deb_path = DIST_DIR / f"atum_{VERSION}_{DEB_ARCH}.deb"
    run_command(
        ["dpkg-deb", "--root-owner-group", "--build", str(deb_root), str(deb_path)],
        "Creating Debian package",
        allow_fail=not STRICT,
    )


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def verify_outputs():
    """List dist/ and make sure the expected installers exist (fatal in CI)"""
    expected = {
        "Windows": ["*.exe"],
        "Darwin": ["*.dmg"],
        "Linux": ["*.AppImage", "*.deb"],
    }.get(platform.system(), [])

    print(f"\n📂 Contents of {DIST_DIR}:")
    for item in sorted(DIST_DIR.iterdir()):
        size = f"{item.stat().st_size / 1_048_576:.1f} MB" if item.is_file() else "<dir>"
        print(f"   {item.name}  ({size})")

    missing = [pattern for pattern in expected if not list(DIST_DIR.glob(pattern))]
    if missing:
        print(f"\n⚠️  Expected installer(s) missing in {DIST_DIR}: {', '.join(missing)}")
        if STRICT:
            print("❌ Failing build because CI is strict about missing installers.")
            sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    """Main build orchestrator"""
    os.chdir(ROOT)  # all relative paths refer to the repo root

    print(f"\n{'=' * 60}")
    print(f"🔨 Building {PROJECT_NAME} v{VERSION}")
    print(f"{'=' * 60}")
    print(f"Platform: {platform.system()} ({MACHINE})")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Strict mode: {STRICT}")

    ensure_directories()
    ensure_pyinstaller()
    convert_icon(ICON_SOURCE)
    run_pyinstaller()

    system = platform.system()
    if system == "Windows":
        build_windows_installer()
    elif system == "Darwin":
        build_mac_dmg()
    elif system == "Linux":
        build_linux_appimage()
        build_linux_deb()

    verify_outputs()

    print(f"\n{'=' * 60}")
    print("✅ Build completed!")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()