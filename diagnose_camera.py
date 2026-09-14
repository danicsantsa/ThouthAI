#!/usr/bin/env python3
"""
Kamera-Diagnose-Skript
======================
Testet alle verfügbaren Kameras und gibt detaillierte Informationen aus.
"""

import cv2
import platform
import sys


def test_camera(index):
    """Testet eine einzelne Kamera."""
    print(f"\n📷 Teste Kamera-Index {index} (/dev/video{index})...")
    
    system = platform.system()
    if system == "Windows":
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    elif system == "Darwin":
        cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    else:
        cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    
    if not cap.isOpened():
        cap = cv2.VideoCapture(index)
    
    if not cap.isOpened():
        print(f"  ❌ Kamera-Index {index} nicht verfügbar.")
        return False
    
    print(f"  ✓ Kamera geöffnet")
    
    # Teste Frame-Erfassung
    ret, frame = cap.read()
    if not ret or frame is None:
        print(f"  ❌ Kein Frame von Kamera {index} erhalten.")
        cap.release()
        return False
    
    print(f"  ✓ Frame erfasst: {frame.shape[1]}x{frame.shape[0]} pixels")
    
    # Versuche, Auflösung zu setzen
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"  ✓ Auflösung: {actual_width}x{actual_height} @ {actual_fps} FPS")
    
    cap.release()
    print(f"  ✓ Kamera-Index {index} funktioniert einwandfrei!")
    return True


def main():
    print("=" * 60)
    print("🔍 KAMERA-DIAGNOSE")
    print("=" * 60)
    print(f"System: {platform.system()}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"OpenCV: {cv2.__version__}\n")
    
    found_cameras = []
    print("Scanne Kamera-Indizes 0-10...")
    for i in range(11):
        if test_camera(i):
            found_cameras.append(i)
    
    print("\n" + "=" * 60)
    if found_cameras:
        print(f"✓ {len(found_cameras)} Kamera(s) gefunden: {found_cameras}")
        print(f"\nEmpfohlener Kamera-Index: {found_cameras[0]}")
        print(f"Starten Sie die App mit: python track_all.py --user <name> --camera {found_cameras[0]}")
    else:
        print("❌ KEINE KAMERAS GEFUNDEN!")
        print("\nMögliche Lösungen:")
        print("1. Ist die Kamera an den Computer angeschlossen?")
        print("2. Ist die Kamera von einem anderen Programm belegt? (Chrome, OBS, etc.)")
        print("3. Auf Linux: Prüfen Sie die Berechtigung: ls -la /dev/video*")
        print("4. Auf macOS: Systemeinstellungen -> Datenschutz -> Kamera")
        print("5. Installieren Sie libcamera-tools: sudo apt install libcamera-tools")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
