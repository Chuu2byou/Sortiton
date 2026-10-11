"""The static feature registry: the CLI and the GUI read the very same tuple.

Registration is explicit (no plugin loader): every feature is imported here by
name, so the wheel and a PyInstaller build both see it.
"""

from __future__ import annotations

from .base import Feature
from .export import FEATURE as _EXPORT
from .fixes import FEATURE as _FIXES

__all__ = ["Feature", "FEATURES", "get"]

FEATURES: tuple[Feature, ...] = (_EXPORT, _FIXES)


def get(key: str) -> Feature | None:
    """The feature registered under ``key``, or None."""
    for feature in FEATURES:
        if feature.key == key:
            return feature
    return None
