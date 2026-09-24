"""File names, target paths, content comparison and collecting audio files.

Pure path/name layer - knows neither tags nor rules.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from . import i18n
from .config import (AUDIO_EXTENSIONS, FALLBACK_ARTIST, INVALID_CHARS, INVISIBLE,
                     MAX_NAME_LENGTH)


def safe_name(name: str) -> str:
    """Make a file/folder name safe (sync friendly, length limited)."""
    if not name:
        return "_"
    name = INVISIBLE.sub("", name)
    name = INVALID_CHARS.sub("_", name)
    name = name.strip().rstrip(".").strip()
    if not name:
        return "_"
    if len(name) > MAX_NAME_LENGTH:
        name = name[:MAX_NAME_LENGTH].rstrip()
    return name


def build_name(tags: dict, file_base: str, pattern: str) -> str:
    """Build the base name from a naming pattern (e.g. '%artist% - %title%')."""
    artist = tags.get("artist") or FALLBACK_ARTIST
    album_artist = tags.get("album_artist") or artist
    album = tags.get("album") or ""
    title = tags.get("title") or file_base

    name = pattern
    name = name.replace("%artist%", safe_name(artist))
    name = name.replace("%albumartist%", safe_name(album_artist))
    name = name.replace("%album%", safe_name(album))
    name = name.replace("%title%", safe_name(title))

    # Collapse repeated separators ("A -  - B" -> "A - B").
    name = re.sub(r"(\s*-\s*){2,}", " - ", name)
    name = name.strip(" -")

    if not name:
        name = safe_name(file_base)
    if len(name) > MAX_NAME_LENGTH:
        name = name[:MAX_NAME_LENGTH].rstrip()

    return name


def free_path(path: Path) -> Path:
    """Return a free path, never overwriting it (" (2)", " (3)", ...).

    Log file and journal are named after the second a run starts in. Two runs
    in the same second would therefore build the same name, and opening the
    second one would cut the first one short - here as everywhere else in
    Sortiton an existing file stays untouched.
    """
    path = Path(path)
    if not path.exists():
        return path
    for number in range(2, 1000):
        candidate = path.with_name(f"{path.stem} ({number}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(i18n.t("file.error.no_free_name", path=path))


def free_target(dst: Path, used: set[str], ignore: Path | None = None) -> Path:
    """Return a free target path, never overwriting it (" (2)", " (3)", ...).

    ``ignore`` counts as free, so a file never blocks its own target name.
    """
    key = str(dst).lower()

    # TODO: the ignore comparison is case sensitive while `used` is lowercased,
    # so on a case insensitive filesystem a file still blocks its own name.
    if ignore is not None and str(dst) == str(ignore):
        used.add(key)
        return dst

    if key not in used and not dst.exists():
        used.add(key)
        return dst

    base = re.sub(r" \(\d+\)$", "", dst.stem)
    number = 2
    while number <= 9999:
        candidate = dst.with_name(f"{base} ({number}){dst.suffix}")
        k = str(candidate).lower()
        taken = k in used or (candidate.exists() and str(candidate) != str(ignore))
        if not taken:
            used.add(k)
            return candidate
        number += 1

    raise RuntimeError(i18n.t("file.error.no_free_name", path=dst))


def _file_hash(path: Path) -> str:
    """SHA256 of a file, read in 1 MiB blocks.

    Only a fingerprint for comparing two files, not a security hash - but SHA1
    is what security scanners report (bandit B324), and SHA256 costs nothing
    measurable here. ``usedforsecurity=False`` would not help: it needs 3.9.
    """
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def same_content(a: Path, b: Path) -> bool:
    """True if both files are identical (same size + same SHA256)."""
    try:
        if a.stat().st_size != b.stat().st_size:
            return False
        return _file_hash(a) == _file_hash(b)
    except OSError:
        return False


def iter_audio(root: Path):
    """Yield every audio file below ``root`` (hidden entries are ignored)."""
    for folder, subfolders, files in os.walk(root):
        subfolders[:] = [d for d in subfolders if not d.startswith(".")]
        for name in sorted(files):
            if name.startswith("."):
                continue
            path = Path(folder) / name
            if path.suffix.lower() in AUDIO_EXTENSIONS:
                yield path
