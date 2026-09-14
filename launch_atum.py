#!/usr/bin/env python3
"""
Universal Atum Launcher
Works on Windows, macOS, and Linux
"""

import os
import sys
import subprocess
import platform

def get_venv_python():
    """Get path to Python in virtual environment"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    
    # Virtual environment paths
    venv_paths = [
        os.path.join(root_dir, "myenv", "bin", "python"),      # Linux/macOS - myenv
        os.path.join(root_dir, "myenv", "bin", "python3"),     # Linux/macOS - myenv
        os.path.join(root_dir, "venv", "bin", "python"),       # Linux/macOS - venv
        os.path.join(root_dir, "venv", "bin", "python3"),      # Linux/macOS - venv
        os.path.join(root_dir, "myenv", "Scripts", "python"),  # Windows - myenv
        os.path.join(root_dir, "venv", "Scripts", "python"),   # Windows - venv
    ]
    
    # Use system Python if venv not found
    for path in venv_paths:
        if os.path.exists(path):
            return path
    
    # Fall back to system Python
    if sys.platform == 'win32':
        return "python"
    else:
        return "python3"

def launch_atum():
    """Launch Atum application"""
    
    # Get project root
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    os.chdir(root_dir)
    
    # Find Python executable
    python_exe = get_venv_python()
    
    # Main script
    atum_script = os.path.join(root_dir, "atum.py")
    
    if not os.path.exists(atum_script):
        print("Error: atum.py not found in", root_dir)
        sys.exit(1)
    
    # Launch
    try:
        if sys.platform == 'win32':
            # Windows: use subprocess with shell
            subprocess.Popen([python_exe, atum_script])
        else:
            # Unix-like: use subprocess
            subprocess.Popen([python_exe, atum_script])
    except Exception as e:
        print(f"Error launching Atum: {e}")
        print(f"Tried to run: {python_exe} {atum_script}")
        sys.exit(1)

if __name__ == "__main__":
    launch_atum()
