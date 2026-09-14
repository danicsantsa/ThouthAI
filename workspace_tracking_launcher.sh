#!/bin/bash
cd "$HOME/Workspace-Tracking" 2>/dev/null || cd /home/danicsantsa/Computervision
source venv/bin/activate 2>/dev/null
python3 tracking_gui.py
