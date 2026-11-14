"""Start the graphical interface."""

from __future__ import annotations


def tkinter_problem() -> "str | None":
    """Return the message for the user when Tkinter cannot be imported."""
    try:
        import tkinter  # noqa: F401  # pylint: disable=unused-import
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
    from .app import main as run
    return run()
