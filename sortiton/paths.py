"""Shared, side-effect-free path validation for core operations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .files import target_inside_source


class PathProblem(Enum):
    """Machine-readable reasons why an operation path is invalid."""

    SOURCE_MISSING = "source_missing"
    SOURCE_INVALID = "source_invalid"
    TARGET_MISSING = "target_missing"
    TARGET_IN_SOURCE = "target_in_source"
    TARGET_INVALID = "target_invalid"
    TARGET_UNWRITABLE = "target_unwritable"


@dataclass(frozen=True)
class PathCheck:
    """Validated paths, or the first error without filesystem changes."""

    source: Path | None
    target: Path | None
    problem: PathProblem | None = None


def check_core_paths(source: str | Path | None, target: str | Path | None,
                     *, target_required: bool = False) -> PathCheck:
    """Validate source and target; an empty optional target means in-place.

    Relative paths are resolved from the process working directory.
    A target above the source is allowed. Validation does not create folders.
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
