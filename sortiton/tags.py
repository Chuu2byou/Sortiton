"""Reading and writing tags.

mutagen is preferred, ffprobe/ffmpeg is the fallback. mutagen is optional, so
its imports live inside the functions that need it.
"""

from __future__ import annotations

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .config import MUTAGEN_AVAILABLE, READ_WORKERS

# TODO: these five fields are all that is read and written. Track, disc and
# year are missing on both sides.
EMPTY_TAGS = {"artist": "", "album_artist": "", "album": "", "title": "", "genre": ""}


def probe_tags(path: Path) -> dict:
    """Read tags: mutagen preferred, otherwise ffprobe."""
    tags = _mutagen_tags(path)
    if tags is not None:
        return tags
    return _ffprobe_tags(path)


def _mutagen_tags(path: Path) -> dict | None:
    """Read tags via mutagen. None = unsupported format or error."""
    if not MUTAGEN_AVAILABLE:
        return None
    try:
        # mutagen is optional (late import).
        # pylint: disable=import-error,import-outside-toplevel
        import mutagen

        handle = mutagen.File(path)
        if handle is None:
            return None

        from mutagen.asf import ASF
        from mutagen.id3 import ID3
        from mutagen.mp4 import MP4

        def as_text(value) -> str:
            if value is None:
                return ""
            if isinstance(value, (list, tuple)):
                return "; ".join(str(x).strip() for x in value if str(x).strip())
            return str(value).strip()

        if isinstance(getattr(handle, "tags", None), ID3):
            tag = handle.tags

            def id3_text(frame_name: str) -> str:
                parts: list[str] = []
                # getall() is required: get() returns the frame object itself.
                for frame in tag.getall(frame_name):
                    values = getattr(frame, "text", [])
                    if isinstance(values, str):
                        values = [values]
                    for value in values:
                        value = str(value).strip()
                        if value:
                            parts.append(value)
                return "; ".join(parts)

            return {
                "artist":       id3_text("TPE1"),
                "album_artist": id3_text("TPE2"),
                "album":        id3_text("TALB"),
                "title":        id3_text("TIT2"),
                "genre":        id3_text("TCON"),
            }

        if isinstance(handle, MP4):
            return {
                "artist":       as_text(handle.get("\xa9ART")),
                "album_artist": as_text(handle.get("aART")),
                "album":        as_text(handle.get("\xa9alb")),
                "title":        as_text(handle.get("\xa9nam")),
                "genre":        as_text(handle.get("\xa9gen")),
            }

        if isinstance(handle, ASF):
            asf_tags = handle.tags

            def asf_text(key: str) -> str:
                if asf_tags is None:
                    return ""
                values = asf_tags.get(key) or []
                return as_text([str(x) for x in values])

            return {
                "artist":       asf_text("Author"),
                "album_artist": asf_text("WM/AlbumArtist"),
                "album":        asf_text("WM/AlbumTitle"),
                "title":        asf_text("Title"),
                "genre":        asf_text("WM/Genre"),
            }

        # Vorbis comments (FLAC, OGG, OPUS …)
        def vorbis_text(*keys: str) -> str:
            for key in keys:
                value = as_text(handle.get(key))
                if value:
                    return value
            return ""

        return {
            "artist":       vorbis_text("artist", "artists"),
            "album_artist": vorbis_text("albumartist", "album_artist", "album artist"),
            "album":        vorbis_text("album"),
            "title":        vorbis_text("title"),
            "genre":        vorbis_text("genre", "genres"),
        }
    except Exception:
        return None


def _ffprobe_tags(path: Path) -> dict:
    """Fallback: read tags with ffprobe (for formats mutagen cannot handle)."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
            capture_output=True, text=True, timeout=120, check=False,
        )
        data = json.loads(result.stdout or "{}")
    except Exception:
        return dict(EMPTY_TAGS)

    raw = {k.lower(): v for k, v in (data.get("format", {}).get("tags") or {}).items()}

    def pick(*names: str) -> str:
        for name in names:
            if name in raw and raw[name]:
                return str(raw[name]).replace("\x00", "; ").strip()
        return ""

    return {
        "artist":       pick("artist", "artists", "performer"),
        "album_artist": pick("album_artist", "albumartist", "album artist"),
        "album":        pick("album"),
        "title":        pick("title"),
        "genre":        pick("genre", "genres"),
    }


def probe_many(files: list[Path], report=None) -> list[dict]:
    """Read tags of many files in parallel."""
    if not files:
        return []

    results: list[dict] = [dict(EMPTY_TAGS) for _ in files]
    workers = min(READ_WORKERS, len(files))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(probe_tags, path): i for i, path in enumerate(files)}
        for done, future in enumerate(as_completed(futures), start=1):
            i = futures[future]
            try:
                results[i] = future.result()
            except Exception:
                results[i] = dict(EMPTY_TAGS)
            if report is not None:
                report(done, files[i].name)

    return results


def write_tags(path: Path, updates: dict) -> bool:
    """Write tags: mutagen preferred, otherwise an ffmpeg remux."""
    try:
        return _write_mutagen(path, updates)
    except Exception:
        pass  # no mutagen, or a format it cannot write -> ffmpeg remux
    return _write_ffmpeg(path, updates)


def _write_mutagen(path: Path, updates: dict) -> bool:
    # mutagen is optional (the caller falls back to ffmpeg).
    # pylint: disable=import-error,import-outside-toplevel
    import mutagen

    from mutagen.asf import ASF, ASFTags
    from mutagen.id3 import ID3, TALB, TCON, TIT2, TPE1, TPE2
    from mutagen.mp4 import MP4

    def as_list(value: str) -> list[str]:
        return [part.strip() for part in value.split(";") if part.strip()]

    handle = mutagen.File(path, easy=False)
    if handle is None:
        raise RuntimeError(f"Unknown format: {path.name}")

    # MP3 / WAV with ID3
    id3_tags = getattr(handle, "tags", None)
    if isinstance(id3_tags, ID3) or path.suffix.lower() == ".mp3":
        if not isinstance(id3_tags, ID3):
            try:
                handle.add_tags()
            except Exception:
                pass
        id3 = handle.tags
        frames = {"title": TIT2, "artist": TPE1, "album_artist": TPE2,
                  "album": TALB, "genre": TCON}
        for key, value in updates.items():
            frame = frames[key]
            values = as_list(value)
            if values:
                id3.setall(frame.__name__, [frame(encoding=3, text=values)])
            else:
                id3.delall(frame.__name__)          # empty value = remove the field
        handle.save()
        return True

    # M4A / MP4
    if isinstance(handle, MP4):
        mp4_keys = {"title": "\xa9nam", "artist": "\xa9ART", "album_artist": "aART",
                    "album": "\xa9alb", "genre": "\xa9gen"}
        for key, value in updates.items():
            values = as_list(value)
            if values:
                handle[mp4_keys[key]] = values
            else:
                try:
                    del handle[mp4_keys[key]]
                except KeyError:
                    pass
        handle.save()
        return True

    # WMA (ASF)
    if isinstance(handle, ASF):
        asf_keys = {"title": "Title", "artist": "Author", "album_artist": "WM/AlbumArtist",
                    "album": "WM/AlbumTitle", "genre": "WM/Genre"}
        if handle.tags is None:
            handle.tags = ASFTags()
        for key, value in updates.items():
            values = as_list(value)
            if values:
                handle.tags[asf_keys[key]] = values
            else:
                try:
                    del handle.tags[asf_keys[key]]
                except KeyError:
                    pass
        handle.save()
        return True

    # FLAC / OGG / OPUS (Vorbis comments)
    vorbis_keys = {"title": "title", "artist": "artist", "album_artist": "albumartist",
                   "album": "album", "genre": "genre"}
    for key, value in updates.items():
        values = as_list(value)
        if not values:
            try:
                del handle[vorbis_keys[key]]
            except KeyError:
                pass
            continue
        try:
            handle[vorbis_keys[key]] = values
        except TypeError:
            handle[vorbis_keys[key]] = value
    handle.save()
    return True


def _write_ffmpeg(path: Path, updates: dict) -> bool:
    """Fallback without mutagen: remux with -c copy (no re-encoding)."""
    temp = path.with_name(path.name + ".tagtmp" + path.suffix)
    command = ["ffmpeg", "-v", "error", "-y", "-i", str(path),
               "-map", "0", "-c", "copy", "-map_metadata", "0"]
    for key, value in updates.items():
        command += ["-metadata", f"{key}={value}"]
    command.append(str(temp))
    try:
        subprocess.run(command, check=True, capture_output=True)
        os.replace(temp, path)
        return True
    finally:
        # Same idiom as the log and the journal use.
        temp.unlink(missing_ok=True)
