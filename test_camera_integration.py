#!/usr/bin/env python3
"""
Quick test to verify camera 1 works with the new settings.
"""
import cv2
import gui_settings
import time

def test_camera():
    print("=" * 60)
    print("CAMERA INTEGRATION TEST")
    print("=" * 60)
    
    # Get default camera from settings
    default_camera = gui_settings.DEFAULTS['camera']
    print(f"\n[Settings] Default camera: {default_camera}")
    
    # Try to open and read frames
    print(f"\n[Test] Opening camera {default_camera}...")
    cap = cv2.VideoCapture(default_camera, cv2.CAP_V4L2)
    
    if not cap.isOpened():
        print("  ✗ Failed to open camera")
        return False
    
    print("  ✓ Camera opened")
    
    # Set buffer size to avoid timeouts
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    # Try to read 5 frames
    frames_read = 0
    print(f"\n[Test] Trying to read frames...")
    
    for i in range(5):
        ret, frame = cap.read()
        if ret and frame is not None:
            frames_read += 1
            print(f"  Frame {i+1}: ✓ ({frame.shape})")
        else:
            print(f"  Frame {i+1}: ✗ Failed to read")
            break
        time.sleep(0.2)  # Small delay between reads
    
    cap.release()
    
    print(f"\n[Result] Successfully read {frames_read}/5 frames")
    
    if frames_read >= 3:
        print("✅ Camera integration PASSED")
        return True
    else:
        print("❌ Camera integration FAILED - not enough frames")
        return False

if __name__ == "__main__":
    success = test_camera()
    exit(0 if success else 1)
