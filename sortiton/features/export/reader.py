"""Reading the export: extensions, records and the folder scan."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from ... import config, output
from ...cancel import NO_CANCEL, Cancelled
from ...files import iter_audio
from ...tags import TrackInfo, read_info

CORE = ["artist", "albumartist", "album", "title", "track", "disc", "year", "genre"]
ALIASES = {
    "artist": "artist", "albumartist": "albumartist", "album artist": "albumartist",
    "album_artist": "albumartist", "album": "album", "title": "title",
    "tracknumber": "track", "track": "track", "discnumber": "disc", "disc": "disc",
    "date": "year", "year": "year", "genre": "genre",
}
SEP = " | "

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
        # pylint: disable=import-error,import-outside-toplevel
        import mutagen
    except ImportError:
        return None
    return mutagen


def read_extra(path):
    """The tags the export keeps besides its core fields (only for --jsonl)."""
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
        # Der Sentinel bleibt sprachneutral ("unreadable"); erst der Bericht
        # übersetzt ihn, damit auch alle_tags.jsonl sprachunabhängig bleibt.
        rec["error"] = info.error
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
        info = TrackInfo()
    rec.update({"codec": info.codec, "dur": info.duration or 0, "kbps": info.bitrate_kbps,
                "sr": info.sample_rate, "ch": info.channels, "bits": info.bits,
                "cover": info.has_cover, "extra": {}})
    for field in CORE:
        rec[field] = info.joined(_INFO_FIELD[field], SEP)
    return rec


def scan(root, workers, cancel=None):
    """Walk ``root`` and read every audio file; report progress per file."""
    cancel = cancel or NO_CANCEL
    cancel.check()
    files = sorted(iter_audio(root, config.READ_EXTENSIONS),
                   key=lambda p: p.relative_to(root).as_posix().casefold())
    total = len(files)

    results: list = [None] * total
    pool = ThreadPoolExecutor(max_workers=workers)
    futures = {pool.submit(read_file, root, path): index
               for index, path in enumerate(files)}
    cancelled = False
    try:
        for done, future in enumerate(as_completed(futures), start=1):
            cancel.check()
            index = futures[future]
            results[index] = future.result()
            output.progress(done, total, files[index].name)
    except Cancelled:
        cancelled = True
        for future in futures:
            future.cancel()
        raise
    finally:
        pool.shutdown(wait=not cancelled, cancel_futures=cancelled)
    return results
