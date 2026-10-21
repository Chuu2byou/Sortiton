"""File names, target paths, content comparison and collecting audio files.

Pure path/name layer - knows neither tags nor rules.
"""

from __future__ import annotations

import filecmp
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
    """Build the base name from a naming pattern (e.g. '%artist% - %title%').

    The pattern understands ``%artist%``, ``%albumartist%``, ``%album%``,
    ``%title%``, ``%track%``, ``%disc%`` and ``%year%``. Every value is run
    through :func:`safe_name`, so a missing tag renders like an empty album
    (``_``); ``%title%`` falls back to the file name and ``%artist%`` /
    ``%albumartist%`` to :data:`FALLBACK_ARTIST`.
    """
    artist = tags.get("artist") or FALLBACK_ARTIST
    album_artist = tags.get("album_artist") or artist
    album = tags.get("album") or ""
    title = tags.get("title") or file_base
    track = tags.get("track") or ""
    disc = tags.get("disc") or ""
    year = tags.get("year") or ""

    name = pattern
    name = name.replace("%artist%", safe_name(artist))
    name = name.replace("%albumartist%", safe_name(album_artist))
    name = name.replace("%album%", safe_name(album))
    name = name.replace("%title%", safe_name(title))
    name = name.replace("%track%", safe_name(track))
    name = name.replace("%disc%", safe_name(disc))
    name = name.replace("%year%", safe_name(year))

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


def _key(path: Path) -> str:
    """Comparison key for path names.

    FAT32, exFAT and NTFS (the usual USB stick / memory card) treat names
    case-insensitively, so ``used`` and the ``ignore`` comparison have to do
    the same - otherwise a file blocks its own target name.
    """
    return str(path).casefold()


def free_target(dst: Path, used: set[str], ignore: Path | None = None) -> Path:
    """Return a free target path, never overwriting it (" (2)", " (3)", ...).

    ``ignore`` counts as free, so a file never blocks its own target name.
    """
    key = _key(dst)
    ignore_key = _key(ignore) if ignore is not None else None

    if ignore_key is not None and key == ignore_key:
        used.add(key)
        return dst

    if key not in used and not dst.exists():
        used.add(key)
        return dst

    base = re.sub(r" \(\d+\)$", "", dst.stem)
    number = 2
    while number <= 9999:
        candidate = dst.with_name(f"{base} ({number}){dst.suffix}")
        k = _key(candidate)
        taken = k in used or (candidate.exists() and k != ignore_key)
        if not taken:
            used.add(k)
            return candidate
        number += 1

    raise RuntimeError(i18n.t("file.error.no_free_name", path=dst))


def same_content(a: Path, b: Path) -> bool:
    """True if both files are identical (same size + byte-for-byte compare).

    ``filecmp`` reads in blocks and stops at the first difference, so a large
    pair that differs early costs almost nothing (a full SHA256 of both would
    always read everything).
    """
    try:
        if a.stat().st_size != b.stat().st_size:
            return False
        return filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False


def iter_audio(root: Path, extensions: set[str] = AUDIO_EXTENSIONS):
    """Yield every audio file below ``root`` (hidden entries are ignored).

    ``extensions`` is the set of file name suffixes to accept; the default is
    :data:`sortiton.config.AUDIO_EXTENSIONS`. Read-only features pass the wider
    :data:`sortiton.config.READ_EXTENSIONS`.
    """
    for folder, subfolders, files in os.walk(root):
        subfolders[:] = [d for d in subfolders if not d.startswith(".")]
        for name in sorted(files):
            if name.startswith("."):
                continue
            path = Path(folder) / name
            if path.suffix.lower() in extensions:
                yield path
