"""Reading and writing tags."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from .cancel import NO_CANCEL, Cancelled
from .config import MUTAGEN_AVAILABLE, READ_WORKERS

EMPTY_TAGS = {"artist": "", "album_artist": "", "album": "", "title": "", "genre": ""}

TAG_FIELDS = ("artist", "album_artist", "album", "title", "genre",
              "track", "disc", "year")

UNREADABLE = "unreadable"

_ID3_FRAMES = {
    "title": "TIT2", "artist": "TPE1", "album_artist": "TPE2",
    "album": "TALB", "genre": "TCON",
    "track": "TRCK", "disc": "TPOS", "year": "TDRC",
}
_MP4_TEXT_KEYS = {
    "title": "\xa9nam", "artist": "\xa9ART", "album_artist": "aART",
    "album": "\xa9alb", "genre": "\xa9gen", "year": "\xa9day",
}
_MP4_PAIR_KEYS = {"track": "trkn", "disc": "disk"}
_ASF_KEYS = {
    "title": "Title", "artist": "Author", "album_artist": "WM/AlbumArtist",
    "album": "WM/AlbumTitle", "genre": "WM/Genre",
    "track": "WM/TrackNumber", "disc": "WM/PartOfSet", "year": "WM/Year",
}
_VORBIS_KEYS = {
    "title": "title", "artist": "artist", "album_artist": "albumartist",
    "album": "album", "genre": "genre", "track": "tracknumber",
    "disc": "discnumber", "year": "date",
}


@dataclass
class TrackInfo:
    """All tags and stream properties of one file, without losing values."""

    artist: list[str] = field(default_factory=list)
    album_artist: list[str] = field(default_factory=list)
    album: list[str] = field(default_factory=list)
    title: list[str] = field(default_factory=list)
    genre: list[str] = field(default_factory=list)
    track: list[str] = field(default_factory=list)
    disc: list[str] = field(default_factory=list)
    year: list[str] = field(default_factory=list)
    codec: str = "?"
    duration: float = 0.0
    bitrate_kbps: int = 0
    sample_rate: int = 0
    channels: int = 0
    bits: int = 0
    has_cover: bool = False
    error: str = ""

    def joined(self, tag_field: str, sep: str) -> str:
        """The values of one tag field joined by ``sep`` ("" when empty)."""
        return sep.join(getattr(self, tag_field))


def probe_tags(path: Path) -> dict:
    """Read the five tag fields of one file (mutagen preferred, else ffprobe)."""
    info = read_info(path)
    return {
        "artist": info.joined("artist", "; "),
        "album_artist": info.joined("album_artist", "; "),
        "album": info.joined("album", "; "),
        "title": info.joined("title", "; "),
        "genre": info.joined("genre", "; "),
    }


def read_info(path: Path) -> TrackInfo:
    """Read tags and stream info of one file: mutagen preferred, else ffprobe."""
    info = _mutagen_info(path)
    if info is not None:
        return info
    return _ffprobe_info(path)


def _mutagen_info(path: Path) -> TrackInfo | None:
    """Read one file with mutagen's raw frames."""
    if not MUTAGEN_AVAILABLE:
        return None
    try:
        # pylint: disable=import-error,import-outside-toplevel
        import mutagen
        from mutagen.asf import ASF
        from mutagen.id3 import ID3
        from mutagen.mp4 import MP4

        handle = mutagen.File(path, easy=False)
        if handle is None:
            return None

        info = TrackInfo()
        _stream_info(info, handle)
        info.has_cover = _mutagen_cover(handle)
        tags = getattr(handle, "tags", None)
        if isinstance(tags, ID3):
            _read_id3(info, tags)
        elif isinstance(handle, MP4):
            _read_mp4(info, handle)
        elif isinstance(handle, ASF):
            _read_asf(info, tags)
        else:
            _read_vorbis(info, handle)
        return info
    except Exception:  # noqa: BLE001 - unsupported format or a broken file
        return None


def _stream_info(info: TrackInfo, handle) -> None:
    """Fill codec, duration and the stream numbers from a mutagen handle."""
    stream = getattr(handle, "info", None)
    info.codec = type(handle).__name__.replace("Easy", "")
    info.duration = float(getattr(stream, "length", 0) or 0)
    info.bitrate_kbps = round((getattr(stream, "bitrate", 0) or 0) / 1000)
    info.sample_rate = int(getattr(stream, "sample_rate", 0) or 0)
    info.channels = int(getattr(stream, "channels", 0) or 0)
    info.bits = int(getattr(stream, "bits_per_sample", 0) or 0)


def _mutagen_cover(handle) -> bool:
    """True when the mutagen handle carries an embedded cover."""
    try:
        if getattr(handle, "pictures", None):
            return True
        tags = getattr(handle, "tags", None)
        if tags is None:
            return False
        if hasattr(tags, "getall") and tags.getall("APIC"):
            return True
        return any(str(key).lower() in {"covr", "metadata_block_picture"} for key in tags)
    except Exception:  # noqa: BLE001
        return False


def _texts(value) -> list[str]:
    """Every value of a tag frame as a stripped, non-empty string."""
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else [value]
    return [text for text in (str(item).strip() for item in items) if text]


def _read_id3(info: TrackInfo, tag) -> None:
    """ID3 (MP3, WAV): the raw frames, TDRC as text instead of a timestamp."""
    def frame(name: str) -> list[str]:
        found: list[str] = []
        for item in tag.getall(name):
            found.extend(_texts(getattr(item, "text", [])))
        return found

    info.artist = frame("TPE1")
    info.album_artist = frame("TPE2")
    info.album = frame("TALB")
    info.title = frame("TIT2")
    info.genre = frame("TCON")
    info.track = frame("TRCK")
    info.disc = frame("TPOS")
    info.year = frame("TDRC")


def _read_mp4(info: TrackInfo, handle) -> None:
    """MP4/M4A: the raw atoms; ``trkn``/``disk`` are ``(number, total)``."""
    info.artist = _texts(handle.get("\xa9ART"))
    info.album_artist = _texts(handle.get("aART"))
    info.album = _texts(handle.get("\xa9alb"))
    info.title = _texts(handle.get("\xa9nam"))
    info.genre = _texts(handle.get("\xa9gen"))
    info.track = _mp4_number(handle.get("trkn"))
    info.disc = _mp4_number(handle.get("disk"))
    info.year = _texts(handle.get("\xa9day"))


def _mp4_number(value) -> list[str]:
    """``trkn``/``disk`` values as "number" or "number/total" (total 0 = none)."""
    numbers: list[str] = []
    for item in value or []:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            number, total = item
            numbers.append(f"{number}/{total}" if total else str(number))
        elif item:
            numbers.append(str(item).strip())
    return numbers


def _mp4_pairs(value: str) -> list[tuple[int, int]]:
    """MP4 ``trkn``/``disk`` value: "3/12" -> ``[(3, 12)]``, "3" -> ``[(3, 0)]``."""
    text = value.strip()
    if not text:
        return []
    number, _, total = text.partition("/")
    return [(int(number), int(total or 0))]


def _read_asf(info: TrackInfo, tag) -> None:
    """WMA/ASF: the WM/* attributes."""
    def attribute(key: str) -> list[str]:
        if tag is None:
            return []
        return _texts([str(item) for item in (tag.get(key) or [])])

    info.artist = attribute("Author")
    info.album_artist = attribute("WM/AlbumArtist")
    info.album = attribute("WM/AlbumTitle")
    info.title = attribute("Title")
    info.genre = attribute("WM/Genre")
    info.track = attribute("WM/TrackNumber")
    info.disc = attribute("WM/PartOfSet")
    info.year = attribute("WM/Year")


def _read_vorbis(info: TrackInfo, handle) -> None:
    """FLAC/Ogg/Opus: the Vorbis comments (tracknumber/discnumber/date)."""
    def comment(*keys: str) -> list[str]:
        found: list[str] = []
        for key in keys:
            found.extend(_texts(handle.get(key)))
        return found

    info.artist = comment("artist")
    info.album_artist = comment("albumartist")
    info.album = comment("album")
    info.title = comment("title")
    info.genre = comment("genre")
    info.track = comment("tracknumber")
    info.disc = comment("discnumber")
    info.year = comment("date")


def _num(value, *, cast=float, default=0):
    """Best-effort number from an ffprobe string ("" / "N/A" -> default)."""
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.upper() in {"N/A", "NA", "NULL", "NONE"}:
        return default
    try:
        return cast(text)
    except (TypeError, ValueError):
        return default


def _ffprobe_info(path: Path) -> TrackInfo:
    """Fallback: read tags and streams with ffprobe."""
    info = TrackInfo()
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=120, check=False)
        data = json.loads(result.stdout or "{}")
    except Exception:  # noqa: BLE001
        data = {}
    if not data:
        info.error = UNREADABLE
        return info

    streams = data.get("streams", [])
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})

    raw: dict[str, list[str]] = {}
    sources = [data.get("format", {}).get("tags", {})] + \
        [stream.get("tags", {}) for stream in streams]
    for source in sources:
        for key, value in (source or {}).items():
            lowered = str(key).strip().lower()
            if lowered not in raw:
                raw[lowered] = _texts(value)

    def pick(*keys: str) -> list[str]:
        found: list[str] = []
        for key in keys:
            found.extend(raw.get(key, []))
        return found

    info.artist = pick("artist", "artists", "performer")
    info.album_artist = pick("album_artist", "albumartist", "album artist")
    info.album = pick("album")
    info.title = pick("title")
    info.genre = pick("genre", "genres")
    info.track = pick("tracknumber", "track")
    info.disc = pick("discnumber", "disc")
    info.year = pick("date", "year")

    fmt = data.get("format", {})
    bitrate = _num(audio.get("bit_rate") or fmt.get("bit_rate") or 0, cast=int, default=0)
    info.codec = audio.get("codec_name", "?")
    info.duration = _num(fmt.get("duration"), cast=float, default=0.0)
    info.bitrate_kbps = round(bitrate / 1000)
    info.sample_rate = _num(audio.get("sample_rate") or 0, cast=int, default=0)
    info.channels = _num(audio.get("channels") or 0, cast=int, default=0)
    info.bits = _num(audio.get("bits_per_raw_sample") or audio.get("bits_per_sample") or 0,
                     cast=int, default=0)
    info.has_cover = any(stream.get("codec_type") == "video"
                         and stream.get("disposition", {}).get("attached_pic")
                         for stream in streams)
    return info


def probe_many(files: list[Path], report=None, cancel=None,
               unreadable: list[Path] | None = None) -> list[dict]:
    """Read tags of many files in parallel."""
    cancel = cancel or NO_CANCEL
    if not files:
        cancel.check()
        return []

    results: list[dict] = [dict(EMPTY_TAGS) for _ in files]
    workers = min(READ_WORKERS, len(files))

    def read(path: Path) -> dict:
        info = read_info(path)
        if info.error and unreadable is not None:
            unreadable.append(path)
        return {
            "artist": info.joined("artist", "; "),
            "album_artist": info.joined("album_artist", "; "),
            "album": info.joined("album", "; "),
            "title": info.joined("title", "; "),
            "genre": info.joined("genre", "; "),
        }

    pool = ThreadPoolExecutor(max_workers=workers)
    futures = {pool.submit(read, path): i for i, path in enumerate(files)}
    cancelled = False
    try:
        for done, future in enumerate(as_completed(futures), start=1):
            cancel.check()
            i = futures[future]
            try:
                results[i] = future.result()
            except Exception:
                results[i] = dict(EMPTY_TAGS)
                if unreadable is not None:
                    unreadable.append(files[i])
            if report is not None:
                report(done, files[i].name)
    except Cancelled:
        cancelled = True
        for future in futures:
            future.cancel()
        raise
    finally:
        pool.shutdown(wait=not cancelled, cancel_futures=cancelled)
    return results


def write_tags(path: Path, updates: dict) -> bool:
    """Write tags: mutagen preferred, otherwise an ffmpeg remux."""
    try:
        return _write_mutagen(path, updates)
    except Exception:
        pass
    return _write_ffmpeg(path, updates)


def _write_mutagen(path: Path, updates: dict) -> bool:
    """Tag a temporary copy, then replace the original atomically."""
    path = Path(path).resolve()
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=f".sortiton-{path.name[:40]}.",
        suffix=f".tagtmp{path.suffix}")
    os.close(descriptor)
    temp = Path(temporary)
    try:
        shutil.copy2(path, temp)
        _write_mutagen_inplace(temp, updates)
        try:
            shutil.copystat(path, temp)
        except OSError:
            pass
        os.replace(temp, path)
        return True
    finally:
        try:
            temp.unlink()
        except OSError:
            pass


def _write_mutagen_inplace(path: Path, updates: dict) -> bool:
    # pylint: disable=import-error,import-outside-toplevel
    import mutagen
    import mutagen.id3 as id3_module

    from mutagen.asf import ASF, ASFTags
    from mutagen.id3 import ID3
    from mutagen.mp4 import MP4

    def as_list(value: str) -> list[str]:
        return [part.strip() for part in value.split(";") if part.strip()]

    handle = mutagen.File(path, easy=False)
    if handle is None:
        raise RuntimeError(f"Unknown format: {path.name}")

    id3_tags = getattr(handle, "tags", None)
    if isinstance(id3_tags, ID3) or path.suffix.lower() == ".mp3":
        id3 = id3_tags if isinstance(id3_tags, ID3) else None
        if id3 is None:
            try:
                handle.add_tags()
            except Exception:
                pass
            id3 = getattr(handle, "tags", None)
        if id3 is None:
            raise RuntimeError(f"Could not initialize ID3 tags on {path.name}")
        for key, value in updates.items():
            frame_name = _ID3_FRAMES.get(key)
            if frame_name is None:
                continue
            frame = getattr(id3_module, frame_name)
            values = as_list(value)
            if values:
                id3.setall(frame_name, [frame(encoding=3, text=values)])
            else:
                id3.delall(frame_name)
        handle.save()
        return True

    if isinstance(handle, MP4):
        for key, value in updates.items():
            if key in _MP4_PAIR_KEYS:
                pairs = _mp4_pairs(value)
                if pairs:
                    handle[_MP4_PAIR_KEYS[key]] = pairs
                else:
                    handle.pop(_MP4_PAIR_KEYS[key], None)
                continue
            text_key = _MP4_TEXT_KEYS.get(key)
            if text_key is None:
                continue
            values = as_list(value)
            if values:
                handle[text_key] = values
            else:
                try:
                    del handle[text_key]
                except KeyError:
                    pass
        handle.save()
        return True

    if isinstance(handle, ASF):
        if handle.tags is None:
            handle.tags = ASFTags()
        for key, value in updates.items():
            asf_key = _ASF_KEYS.get(key)
            if asf_key is None:
                continue
            values = as_list(value)
            if values:
                handle.tags[asf_key] = values
            else:
                try:
                    del handle.tags[asf_key]
                except KeyError:
                    pass
        handle.save()
        return True

    for key, value in updates.items():
        vorbis_key = _VORBIS_KEYS.get(key)
        if vorbis_key is None:
            continue
        values = as_list(value)
        if not values:
            try:
                del handle[vorbis_key]
            except KeyError:
                pass
            continue
        try:
            handle[vorbis_key] = values
        except TypeError:
            handle[vorbis_key] = value
    handle.save()
    return True


def _write_ffmpeg(path: Path, updates: dict) -> bool:
    """Fallback without mutagen: remux with -c copy (no re-encoding)."""
    path = Path(path).resolve()
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=f".sortiton-{path.name[:40]}.",
        suffix=f".tagtmp{path.suffix}")
    os.close(descriptor)
    temp = Path(temporary)
    command = ["ffmpeg", "-v", "error", "-y", "-i", str(path),
               "-map", "0", "-c", "copy", "-map_metadata", "0"]
    for key, value in updates.items():
        command += ["-metadata", f"{'date' if key == 'year' else key}={value}"]
    command.append(str(temp))
    try:
        try:
            subprocess.run(command, check=True, capture_output=True)
        except subprocess.CalledProcessError as error:
            stderr = error.stderr or b""
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", "replace")
            detail = stderr.strip() or str(error)
            raise RuntimeError(f"ffmpeg could not write {path.name}: {detail}") from error
        try:
            shutil.copystat(str(path), str(temp))
        except OSError:
            pass
        try:
            os.replace(temp, path)
        except OSError as error:
            raise RuntimeError(
                f"could not replace {path.name} with the written copy: {error}") from error
        return True
    finally:
        temp.unlink(missing_ok=True)
