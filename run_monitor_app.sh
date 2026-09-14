#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "$SCRIPT_DIR/myenv/bin/python" ]; then
  exec "$SCRIPT_DIR/myenv/bin/python" atum.py
else
  echo "Virtual environment not found at $SCRIPT_DIR/myenv"
  echo "Please create or activate the project environment first."
  exit 1
fi
