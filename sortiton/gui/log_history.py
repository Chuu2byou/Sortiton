"""Begrenzter Verlauf und Klassifizierung von Protokollzeilen."""

from __future__ import annotations

_ERROR_MARKERS = ("ERROR", "FEHLER")
_OK_MARKERS = ("Done.", "OK:", "Renamed:", "Fertig.", "Umbenannt:")
_INFO_MARKERS = ("->", "PREVIEW", "VORSCHAU")


class LogHistory:
    """Bewahrt die letzten Zeilen unabhängig von den GUI-Widgets auf."""

    def __init__(self) -> None:
        self._lines: list[str] = []

    def append(self, line: str) -> None:
        """Eine Zeile ergänzen und alte Einträge bei Bedarf entfernen."""
        self._lines.append(line)
        if len(self._lines) > 2000:
            del self._lines[:1000]

    def clear(self) -> None:
        """Den Verlauf leeren."""
        self._lines.clear()

    def lines(self) -> list[str]:
        """Eine Kopie des Verlaufs liefern."""
        return self._lines.copy()


def line_marker(line: str) -> str | None:
    """Die Darstellungsfarbe einer Protokollzeile bestimmen."""
    if any(word in line for word in _ERROR_MARKERS):
        return "err"
    if any(word in line for word in _OK_MARKERS):
        return "ok"
    if any(word in line for word in _INFO_MARKERS):
        return "info"
    return None
