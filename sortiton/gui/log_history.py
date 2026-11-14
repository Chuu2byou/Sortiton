"""Bounded log history and classification of log lines."""

from __future__ import annotations

_ERROR_MARKERS = ("ERROR", "FEHLER")
_OK_MARKERS = ("Done.", "OK:", "Renamed:", "Fertig.", "Umbenannt:")
_INFO_MARKERS = ("->", "PREVIEW", "VORSCHAU")


class LogHistory:
    """Keep recent lines independently of GUI widgets."""

    def __init__(self) -> None:
        self._lines: list[str] = []

    def append(self, line: str) -> None:
        """Append a line and remove old entries when needed."""
        self._lines.append(line)
        if len(self._lines) > 2000:
            del self._lines[:1000]

    def clear(self) -> None:
        """Clear the history."""
        self._lines.clear()

    def lines(self) -> list[str]:
        """Return a copy of the history."""
        return self._lines.copy()


def line_marker(line: str) -> str | None:
    """Determine the display colour for a log line."""
    if any(word in line for word in _ERROR_MARKERS):
        return "err"
    if any(word in line for word in _OK_MARKERS):
        return "ok"
    if any(word in line for word in _INFO_MARKERS):
        return "info"
    return None
