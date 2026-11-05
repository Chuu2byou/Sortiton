"""Gemeinsame, nebenwirkungsfreie Prüfung der Pfade von Kernaufträgen."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .files import target_inside_source


class PathProblem(Enum):
    """Maschinenlesbare Ursachen für ungültige Auftragspfade."""

    SOURCE_MISSING = "source_missing"
    SOURCE_INVALID = "source_invalid"
    TARGET_MISSING = "target_missing"
    TARGET_IN_SOURCE = "target_in_source"
    TARGET_INVALID = "target_invalid"
    TARGET_UNWRITABLE = "target_unwritable"


@dataclass(frozen=True)
class PathCheck:
    """Validierte Pfade oder der erste Fehler ohne Dateisystemänderungen."""

    source: Path | None
    target: Path | None
    problem: PathProblem | None = None


def check_core_paths(source: str | Path | None, target: str | Path | None,
                     *, target_required: bool = False) -> PathCheck:
    """Prüfe Quelle und Ziel; ein leeres optionales Ziel bedeutet in-place.

    Relative Pfade beziehen sich auf das Arbeitsverzeichnis des Prozesses.
    Ein Ziel oberhalb der Quelle ist erlaubt. Die Prüfung erzeugt keine Ordner.
    """
    source_text = str(source or "").strip()
    target_text = str(target or "").strip()
    if not source_text:
        return PathCheck(None, None, PathProblem.SOURCE_MISSING)
    try:
        root = Path(source_text).expanduser()
        if not root.is_dir():
            return PathCheck(root, None, PathProblem.SOURCE_INVALID)
    except (OSError, RuntimeError, ValueError):
        return PathCheck(None, None, PathProblem.SOURCE_INVALID)
    try:
        dest = Path(target_text).expanduser() if target_text else None
    except (OSError, RuntimeError, ValueError):
        return PathCheck(root, None, PathProblem.TARGET_INVALID)
    if dest is None:
        return PathCheck(root, dest, PathProblem.TARGET_MISSING if target_required else None)
    try:
        if target_inside_source(root, dest):
            return PathCheck(root, dest, PathProblem.TARGET_IN_SOURCE)
        parent = dest
        while not parent.exists() and parent != parent.parent:
            if parent.is_symlink():
                return PathCheck(root, dest, PathProblem.TARGET_INVALID)
            parent = parent.parent
        if not parent.is_dir():
            return PathCheck(root, dest, PathProblem.TARGET_INVALID)
        if not os.access(parent, os.W_OK | os.X_OK):
            return PathCheck(root, dest, PathProblem.TARGET_UNWRITABLE)
    except (OSError, RuntimeError, ValueError):
        return PathCheck(root, dest, PathProblem.TARGET_INVALID)
    return PathCheck(root, dest)
