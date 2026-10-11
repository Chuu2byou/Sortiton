"""Reading the export: extensions, records and the folder scan.

The export only ever reads a music folder. Tag reading lives in
:mod:`sortiton.tags` (:func:`~sortiton.tags.read_info`): ``mutagen`` is
preferred, ``ffprobe`` is the fallback when mutagen is missing or when a file
cannot be read with it. This module turns a :class:`~sortiton.tags.TrackInfo`
into the flat record the report works on and joins the tag lists with
:data:`SEP`.

The extension list is :data:`sortiton.config.READ_EXTENSIONS`, deliberately
wider than :data:`sortiton.config.AUDIO_EXTENSIONS`: it also covers
MP4/Ogg-Audio and AIFF, formats the tag/rename/sort paths must leave alone. The
scan reuses :func:`sortiton.files.iter_audio`, so hidden files and folders are
skipped just like in every other Sortiton command.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ... import config, output
from ...files import iter_audio
from ...tags import UNREADABLE, TrackInfo, read_info

CORE = ["artist", "albumartist", "album", "title", "track", "disc", "year", "genre"]
ALIASES = {
    "artist": "artist", "albumartist": "albumartist", "album artist": "albumartist",
    "album_artist": "albumartist", "album": "album", "title": "title",
    "tracknumber": "track", "track": "track", "discnumber": "disc", "disc": "disc",
    "date": "year", "year": "year", "genre": "genre",
}
SEP = " | "  # separates several values of the same tag

# A record uses the export's own names; TrackInfo uses the tag names.
_INFO_FIELD = {
    "artist": "artist",
    "albumartist": "album_artist",
    "album": "album",
    "title": "title",
    "track": "track",
    "disc": "disc",
    "year": "year",
    "genre": "genre",
}


def _mutagen():
    """The mutagen module, or None when it is not installed (late import)."""
    if not config.MUTAGEN_AVAILABLE:
        return None
    try:
        # mutagen is optional (late import).
        # pylint: disable=import-error,import-outside-toplevel
        import mutagen
    except ImportError:
        return None
    return mutagen


def read_extra(path):
    """The tags the export keeps besides its core fields (only for --jsonl).

    Read through mutagen's easy interface, the way the old export did; a
    missing mutagen or an unreadable file simply yields no extra tags.
    """
    engine = _mutagen()
    if engine is None:
        return {}
    try:
        handle = engine.File(path, easy=True)
    except Exception:  # noqa: BLE001
        return {}
    if handle is None or not handle.tags:
        return {}
    extra: dict[str, list[str]] = {}
    for key in handle.tags.keys():
        name = str(key).strip().lower()
        if name in ALIASES:
            continue
        value = handle.tags[key]
        items = value if isinstance(value, (list, tuple)) else [value]
        values = [text for text in (str(item).strip() for item in items) if text]
        if values:
            extra.setdefault(name, []).extend(values)
    return extra


def read_file(root, path):
    """Read one file into a record (tags joined with :data:`SEP`)."""
    rel = path.relative_to(root).as_posix()
    rec = {"path": rel, "ext": path.suffix.lower().lstrip("."), "size": 0, "error": ""}
    try:
        rec["size"] = path.stat().st_size
        info = read_info(path)
        if info.error == UNREADABLE:
            rec["error"] = "nicht lesbar"  # TODO(phase 2): i18n
        else:
            rec["error"] = info.error
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
        info = TrackInfo()
    # ``or 0`` mirrors the old records: an unknown duration stays the integer 0.
    rec.update({"codec": info.codec, "dur": info.duration or 0, "kbps": info.bitrate_kbps,
                "sr": info.sample_rate, "ch": info.channels, "bits": info.bits,
                "cover": info.has_cover, "extra": {}})
    for field in CORE:
        rec[field] = info.joined(_INFO_FIELD[field], SEP)
    return rec


def scan(root, workers):
    """Walk ``root`` and read every audio file; report progress per file.

    :func:`sortiton.files.iter_audio` with :data:`sortiton.config.READ_EXTENSIONS`
    skips hidden files and folders (like every other Sortiton command) and
    accepts the read-only formats; the records are sorted by the casefolded
    relative path, the sort key the export has always used.
    """
    files = sorted(iter_audio(root, config.READ_EXTENSIONS),
                   key=lambda p: p.relative_to(root).as_posix().casefold())
    total = len(files)

    out = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, rec in enumerate(ex.map(lambda p: read_file(root, p), files), 1):
            out.append(rec)
            output.progress(i, total, files[i - 1].name)
    return out
