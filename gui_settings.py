"""
gui_settings.py
================
Speichert die zuletzt verwendeten Einstellungen lokal in gui_settings.json
(im selben Ordner). Damit reicht nach der einmaligen Einrichtung beim
nächsten Start nur noch ein Klick auf "Aufnahme starten" -- nichts muss
erneut eingetippt werden.
"""

import json
import os
import cv2
import platform


def _find_first_working_camera(max_index=10):
    """Findet die erste Kamera, die tatsächlich Frames liefert."""
    for i in range(max_index):
        try:
            system = platform.system()
            if system == "Windows":
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            elif system == "Darwin":
                cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
            else:
                cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
            
            if not cap.isOpened():
                cap = cv2.VideoCapture(i)
            
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None and frame.size > 0:
                    return i
        except Exception:
            pass
    return 1  # Default to 1 if detection fails, since 0 often hangs on Linux


OUTPUT_DIR = os.environ.get("ATUM_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(OUTPUT_DIR, exist_ok=True)
SETTINGS_FILE = os.path.join(OUTPUT_DIR, "gui_settings.json")

# On Linux, camera 0 often times out. Prefer camera 1.
# Auto-detection will happen in track_all.py if the chosen camera fails
if platform.system() == "Linux":
    _DEFAULT_CAMERA = 1  # Linux: prefer /dev/video1 as primary
else:
    _DEFAULT_CAMERA = _find_first_working_camera()

DEFAULTS = {
    "user": "",
    "camera": _DEFAULT_CAMERA,
    "rotate": 0,
    "device_name": "",
    "work_apps": "code,pycharm,firefox,chrome,terminal,slack,word,excel,outlook",
    "non_work_apps": "spotify,steam,netflix,youtube,discord,instagram,tiktok,vlc",
    "check_interval": 3.0,
    "db_flush_interval": 2.0,
}


def has_settings():
    return os.path.exists(SETTINGS_FILE)


def load_settings():
    if not has_settings():
        return dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULTS)


def save_settings(settings):
    merged = dict(DEFAULTS)
    merged.update(settings)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    return merged