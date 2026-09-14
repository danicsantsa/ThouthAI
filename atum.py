#!/usr/bin/env python3
"""Atum entrypoint.

This is the official launch script for the Atum monitoring application.
It starts the desktop UI and loads all tracking components in the same
project workspace.
"""

import os
import platform
import sys


def configure_data_directory():
    if "ATUM_DATA_DIR" in os.environ:
        return
    if not getattr(sys, "frozen", False):
        return
    if platform.system() == "Windows":
        root = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    elif platform.system() == "Darwin":
        root = os.path.expanduser("~/Library/Application Support")
    else:
        root = os.path.expanduser("~/.local/share")
    data_dir = os.path.join(root, "Atum")
    os.makedirs(data_dir, exist_ok=True)
    os.environ["ATUM_DATA_DIR"] = data_dir


configure_data_directory()


if "--worker" in sys.argv:
    # In a packaged app, the worker must run from the same executable.
    sys.argv.remove("--worker")
    from track_all import main
else:
    from tracking_gui import main


if __name__ == "__main__":
    main()
