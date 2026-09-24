#!/usr/bin/env python3
"""Sortiton for Linux - graphical entry point (Tkinter).

Uses the same logic as sortiton.py. Rules are edited in the app, the language
and the tag backends in the settings. Needs ffmpeg and Tkinter (Arch: tk,
Debian/Ubuntu: python3-tk, Fedora: python3-tkinter).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Makes the folder importable when the script runs from somewhere else.
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# The Tkinter check and the start live in the package (sortiton.gui.launch), so
# this script, the console script and "python -m sortiton.gui" do the same.
from sortiton.gui.launch import main  # noqa: E402  (after the sys.path entry)


if __name__ == "__main__":
    raise SystemExit(main())
