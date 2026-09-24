"""Start the graphical interface.

The Tkinter check lives in front of the import of the window, so a missing libtk
ends in a readable message instead of a traceback. Used by ``sortiton_gui.py``,
by ``python -m sortiton.gui`` and by the console script ``sortiton-gui`` - all
three behave the same.
"""

from __future__ import annotations

import sys


def tkinter_problem() -> "str | None":
    """Return the message for the user when Tkinter cannot be imported."""
    try:
        import tkinter  # noqa: F401  - availability check only
    except ImportError as fehler:
        return (
            "ERROR: Tkinter is not available (libtk is missing).\n"
            "Install it with the package manager of your distribution, e.g.:\n"
            "  Arch / Manjaro :  sudo pacman -S tk\n"
            "  Debian / Ubuntu:  sudo apt install python3-tk\n"
            "  Fedora         :  sudo dnf install python3-tkinter\n"
            f"Details: {fehler}"
        )
    return None


def main() -> int:
    """Start the window; the return value is the exit code."""
    problem = tkinter_problem()
    if problem:
        print(problem)
        return 1
    # Late import: only here may Tkinter be touched.
    from .app import main as run
    return run()
