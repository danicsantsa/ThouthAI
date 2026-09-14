"""
camera_utils.py
================
Automatische Kamera-Erkennung für den Einrichtungs-Assistenten der GUI.
Statt den Nutzer einen Kamera-Index raten zu lassen (--camera 0, 1, 2 ...),
werden alle angeschlossenen Kameras kurz getestet und als kleine
Vorschaubilder angezeigt -- einfach anklicken statt raten.
"""

import platform
import cv2


def open_camera(index):
    """Gleiche Logik wie in track_all.py, hier separat, damit dieses Modul
    unabhängig importierbar bleibt (kein mediapipe-Import nötig)."""
    system = platform.system()
    if system == "Windows":
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    elif system == "Darwin":
        cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    else:
        cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(index)
    return cap


def scan_cameras(max_index=5):
    """Testet Kamera-Indizes 0..max_index-1 der Reihe nach. Gibt eine Liste
    von (index, frame_bgr) für jede gefundene Kamera zurück. Dauert je nach
    System 1-3 Sekunden pro Index -- deshalb immer in einem Hintergrund-
    Thread aufrufen, nie direkt im GUI-Thread."""
    found = []
    for i in range(max_index):
        cap = open_camera(i)
        if cap.isOpened():
            ok, frame = cap.read()
            if ok and frame is not None:
                found.append((i, frame))
            cap.release()
    return found


def frame_to_ppm_bytes(frame_bgr, max_width=180, rotate=0):
    """Wandelt ein BGR-Kamerabild in rohe PPM-Bilddaten um. tkinter kann
    PPM nativ laden (tk.PhotoImage(data=...)) -- so wird kein Pillow
    gebraucht, nur was track_all.py ohnehin schon mitbringt (opencv)."""
    if rotate == 90:
        frame_bgr = cv2.rotate(frame_bgr, cv2.ROTATE_90_CLOCKWISE)
    elif rotate == 180:
        frame_bgr = cv2.rotate(frame_bgr, cv2.ROTATE_180)
    elif rotate == 270:
        frame_bgr = cv2.rotate(frame_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)

    height, width = frame_bgr.shape[:2]
    scale = max_width / width
    small = cv2.resize(frame_bgr, (max_width, max(1, int(height * scale))))
    rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    header = f"P6\n{w} {h}\n255\n".encode("ascii")
    return header + rgb.tobytes()