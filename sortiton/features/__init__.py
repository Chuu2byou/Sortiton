"""The static feature registry: the CLI and the GUI read the very same tuple."""

from __future__ import annotations

from .base import Feature
from .dedupe import FEATURE as _DEDUPE
from .export import FEATURE as _EXPORT
from .fetch import FEATURE as _FETCH
from .fixes import FEATURE as _FIXES

__all__ = ["Feature", "FEATURES", "get"]

FEATURES: tuple[Feature, ...] = (_EXPORT, _FIXES, _FETCH, _DEDUPE)


def get(key: str) -> Feature | None:
    """The feature registered under ``key``, or None."""
    for feature in FEATURES:
        if feature.key == key:
            return feature
    return None
