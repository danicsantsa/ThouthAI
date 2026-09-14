#!/usr/bin/env python3
"""
Comprehensive system integration test.
Tests all components of the workspace tracking system.
"""
import os
import sys
import subprocess
import time

def test_module_imports():
    """Test all modules import without errors."""
    print("\n" + "="*60)
    print("TEST 1: Module Imports")
    print("="*60)
    
    modules = ['gui_settings', 'camera_utils', 'track_all', 'db_queries', 'tracking_gui']
    
    for module in modules:
        try:
            __import__(module)
            print(f"✓ {module}.py imports successfully")
        except Exception as e:
            print(f"✗ {module}.py failed to import: {e}")
            return False
    
    return True

def test_camera_detection():
    """Test camera detection and defaults."""
    print("\n" + "="*60)
    print("TEST 2: Camera Detection")
    print("="*60)
    
    try:
        import gui_settings
        import camera_utils
        
        default_camera = gui_settings.DEFAULTS['camera']
        print(f"✓ Default camera from settings: {default_camera}")
        
        cameras = camera_utils.scan_cameras()
        print(f"✓ Found {len(cameras)} camera(s): {[c[0] for c in cameras]}")
        
        if default_camera in [c[0] for c in cameras]:
            print(f"✓ Default camera {default_camera} is available")
            return True
        else:
            print(f"✗ Default camera {default_camera} is NOT available")
            return False
    except Exception as e:
        print(f"✗ Camera detection failed: {e}")
        return False

def test_gui_startup():
    """Test that GUI can initialize (without full mainloop)."""
    print("\n" + "="*60)
    print("TEST 3: GUI Initialization")
    print("="*60)
    
    try:
        # This is a quick test - just import and check key classes exist
        import tracking_gui
        
        if hasattr(tracking_gui, 'App'):
            print("✓ App class exists")
        else:
            print("✗ App class not found")
            return False
            
        if hasattr(tracking_gui, 'HomeTab'):
            print("✓ HomeTab class exists")
        else:
            print("✗ HomeTab class not found")
            return False
            
        print("✓ GUI components are properly defined")
        return True
    except Exception as e:
        print(f"✗ GUI initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_camera_fallback():
    """Test camera fallback logic."""
    print("\n" + "="*60)
    print("TEST 4: Camera Fallback Logic")
    print("="*60)
    
    try:
        import track_all
        
        # Test the function exists
        if hasattr(track_all, 'list_available_cameras'):
            print("✓ list_available_cameras() function exists")
        else:
            print("✗ list_available_cameras() function not found")
            return False
        
        # Test it works
        available = track_all.list_available_cameras(max_index=5)
        print(f"✓ Found {len(available)} available camera(s): {available}")
        
        return len(available) > 0
    except Exception as e:
        print(f"✗ Camera fallback test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("\n" + "🧪 WORKSPACE TRACKING - INTEGRATION TESTS 🧪".center(60))
    
    tests = [
        ("Module Imports", test_module_imports),
        ("Camera Detection", test_camera_detection),
        ("GUI Startup", test_gui_startup),
        ("Camera Fallback", test_camera_fallback),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n✗ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} - {name}")
    
    print("="*60)
    print(f"Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests PASSED! System is ready to use.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) FAILED. Please review issues above.")
        return 1

if __name__ == "__main__":
    exit(main())
