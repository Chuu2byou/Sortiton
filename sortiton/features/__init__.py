"""The static feature registry: the CLI and the GUI read the very same tuple.

Registration is explicit (no plugin loader): every feature is imported here by
name, so the wheel and a PyInstaller build both see it. ``features/export`` is
imported in step 1.5; until then the registry is empty on purpose.
"""

from __future__ import annotations

from .base import Feature

__all__ = ["Feature", "FEATURES", "get"]

# TODO(phase 1, step 1.5): FEATURES = (export.FEATURE,)
FEATURES: tuple[Feature, ...] = ()


def get(key: str) -> Feature | None:
    """The feature registered under ``key``, or None."""
    for feature in FEATURES:
        if feature.key == key:
            return feature
    return None
