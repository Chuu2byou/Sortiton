"""File names, target paths, content comparison and collecting audio files."""

from __future__ import annotations

import filecmp
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
        name = name[:MAX_NAME_LENGTH].rstrip(" .")
    return name


def build_name(tags: dict, file_base: str, pattern: str) -> str:
    """Build the base name from a naming pattern (e.g. '%artist% - %title%')."""
    artist = tags.get("artist") or FALLBACK_ARTIST
    album_artist = tags.get("album_artist") or artist
    album = tags.get("album") or ""
    title = tags.get("title") or file_base
    track = tags.get("track") or ""
    disc = tags.get("disc") or ""
    year = tags.get("year") or ""

    values = {
        "%artist%": artist,
        "%albumartist%": album_artist,
        "%album%": album,
        "%title%": title,
        "%track%": track,
        "%disc%": disc,
        "%year%": year,
    }
    name = re.sub(r"%(artist|albumartist|album|title|track|disc|year)%",
                  lambda match: safe_name(values[match.group(0)]), pattern)

    name = re.sub(r"(\s*-\s*){2,}", " - ", name)
    name = name.strip(" -")

    if not name:
        name = file_base
    return safe_name(name)


def free_path(path: Path) -> Path:
    """Return a free path, never overwriting it (" (2)", " (3)", ...)."""
    path = Path(path)
    if not path.exists():
        return path
    for number in range(2, 1000):
        candidate = path.with_name(f"{path.stem} ({number}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(i18n.t("file.error.no_free_name", path=path))


def open_new(path: Path):
    """Create a new text file and return ``(path, handle)``."""
    path = Path(path)
    for _ in range(1000):
        candidate = free_path(path)
        try:
            return candidate, candidate.open("x", encoding="utf-8")
        except FileExistsError:
            continue
    raise RuntimeError(i18n.t("file.error.no_free_name", path=path))


def _key(path: Path) -> str:
    """Comparison key for path names."""
    return str(path).casefold()


def _same_file(first: Path, second: Path | None) -> bool:
    """True when both names point at the same file (case-only names included)."""
    if second is None:
        return False
    try:
        return first.samefile(second)
    except OSError:
        return (_key(first) == _key(second)
                and first.exists() and second.exists())


def free_target(dst: Path, used: set[str], ignore: Path | None = None) -> Path:
    """Return a free target path, never overwriting it (" (2)", " (3)", ...)."""
    key = _key(dst)

    if _same_file(dst, ignore):
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
        taken = k in used or (candidate.exists() and not _same_file(candidate, ignore))
        if not taken:
            used.add(k)
            return candidate
        number += 1

    raise RuntimeError(i18n.t("file.error.no_free_name", path=dst))


def content_digest(path: Path) -> str:
    """SHA-256 des Dateiinhalts."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def same_content(a: Path, b: Path) -> bool:
    """True if both files are identical (same size + byte-for-byte compare)."""
    try:
        if a.stat().st_size != b.stat().st_size:
            return False
        return filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False


def iter_audio(root: Path, extensions: set[str] = AUDIO_EXTENSIONS):
    """Yield every audio file below ``root`` (hidden entries are ignored)."""
    for folder, subfolders, files in os.walk(root):
        # Sortiert, damit die Reihenfolge (und damit "(2)" bei Namensgleichheit)
        # bei jedem Lauf gleich ist - os.walk liefert sie sonst in Plattenordnung.
        subfolders[:] = sorted((d for d in subfolders if not d.startswith(".")),
                               key=str.casefold)
        for name in sorted(files):
            if name.startswith("."):
                continue
            path = Path(folder) / name
            if path.suffix.lower() in extensions:
                yield path
