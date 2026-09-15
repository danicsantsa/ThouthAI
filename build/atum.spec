# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Atum - Activity Tracking Application
Builds standalone executables for Windows, Mac, and Linux
"""

import os
import sys

try:
    spec_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    spec_path = os.path.abspath(sys.argv[0]) if sys.argv else os.getcwd()
    spec_dir = os.path.dirname(spec_path)

project_root = os.path.dirname(spec_dir)

block_cipher = None

icon_path = os.path.join(project_root, 'build', 'icon.ico')
icon_path = icon_path if os.path.exists(icon_path) else None
mac_icon_path = os.path.join(project_root, 'build', 'icon.icns')
mac_icon_path = mac_icon_path if os.path.exists(mac_icon_path) else None


a = Analysis(
    [os.path.join(project_root, 'atum.py')],
    pathex=[project_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, 'efficientdet.tflite'), '.'),
        (os.path.join(project_root, 'face_landmarker.task'), '.'),
        (os.path.join(project_root, 'hand_landmarker.task'), '.'),
        (os.path.join(project_root, 'pose_landmarker_lite.task'), '.'),
        (os.path.join(project_root, 'atum.desktop'), '.'),
        (os.path.join(project_root, 'db_config.json'), '.'),
    ],
    hiddenimports=[
        'cv2',
        'mediapipe',
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'track_all',
        'activity_tracker',
        'camera_utils',
        'gui_settings',
        'db_client',
        'db_queries',
        'psycopg2',
        'pandas',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- One-dir mode ---
# EXE now only builds the bootstrap executable; binaries/zipfiles/datas are
# excluded here and instead collected into a folder by COLLECT below.
# This keeps dist/Atum as a directory (containing the exe + libs + datas),
# which is what build.py's shutil.copytree(...) expects for AppImage packaging.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Atum',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Atum',
)

# For macOS app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Atum.app',
        icon=mac_icon_path,
        bundle_identifier='com.atum.tracking',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': 'True',
        },
    )
