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
        # A cut can leave a trailing dot/space behind, which some file systems
        # silently drop - the name we report and write would then differ.
        name = name[:MAX_NAME_LENGTH].rstrip(" .")
    return name


def build_name(tags: dict, file_base: str, pattern: str) -> str:
    """Build the base name from a naming pattern (e.g. '%artist% - %title%').

    The pattern understands ``%artist%``, ``%albumartist%``, ``%album%``,
    ``%title%``, ``%track%``, ``%disc%`` and ``%year%``. Every value is run
    through :func:`safe_name`, so a missing tag renders like an empty album
    (``_``); ``%title%`` falls back to the file name and ``%artist%`` /
    ``%albumartist%`` to :data:`FALLBACK_ARTIST`.

    The finished name is sanitized once more: a pattern is user input and may
    contain a path separator or ``..``. Without that last pass ``--pattern
    ../../outside`` would write outside the folder the user chose.
    """
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
    # One pass over the pattern: a tag value that happens to contain a
    # placeholder ("100% %album%") must be taken literally, not substituted in
    # a later step. unknown placeholders stay as they are.
    name = re.sub(r"%(artist|albumartist|album|title|track|disc|year)%",
                  lambda match: safe_name(values[match.group(0)]), pattern)

    # Collapse repeated separators ("A -  - B" -> "A - B").
    name = re.sub(r"(\s*-\s*){2,}", " - ", name)
    name = name.strip(" -")

    if not name:
        name = file_base
    return safe_name(name)


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


def open_new(path: Path):
    """Create a new text file and return ``(path, handle)``.

    ``free_path`` alone is a check followed by an open, so two runs starting in
    the same second can both pick the same name and the second one truncates
    the first. Opening exclusively (``"x"``) closes that gap; a name that was
    taken in between is simply skipped.
    """
    path = Path(path)
    for _ in range(1000):
        candidate = free_path(path)
        try:
            return candidate, candidate.open("x", encoding="utf-8")
        except FileExistsError:
            continue
    raise RuntimeError(i18n.t("file.error.no_free_name", path=path))


def _key(path: Path) -> str:
    """Comparison key for path names.

    FAT32, exFAT and NTFS (the usual USB stick / memory card) treat names
    case-insensitively, so ``used`` and the ``ignore`` comparison have to do
    the same - otherwise a file blocks its own target name.
    """
    return str(path).casefold()


def _same_file(first: Path, second: Path | None) -> bool:
    """True when both names point at the same file (case-only names included).

    The casefold key alone is not enough: on a case-sensitive file system
    ``Song.mp3`` and ``song.mp3`` are two different files. Treating them as the
    same would let a rename overwrite the other one.
    """
    if second is None:
        return False
    try:
        return first.samefile(second)
    except OSError:
        # At least one side cannot be inspected. If both names "exist" (a test
        # may fake that) and only the case differs, treat them as one file;
        # on a real case-sensitive disk both files exist and samefile() above
        # would have answered instead of raising.
        return (_key(first) == _key(second)
                and first.exists() and second.exists())


def free_target(dst: Path, used: set[str], ignore: Path | None = None) -> Path:
    """Return a free target path, never overwriting it (" (2)", " (3)", ...).

    ``ignore`` counts as free, so a file never blocks its own target name.
    """
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
