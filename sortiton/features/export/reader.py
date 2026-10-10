"""Reading the export: extensions, tag readers and the folder scan.

The export only ever reads a music folder. ``mutagen`` is preferred and imported
late (the project treats it as an optional dependency, see
:mod:`sortiton.tags`); ``ffprobe`` is the fallback when mutagen is missing or
when a file cannot be read with it.

The extension list is deliberately wider than
:data:`sortiton.config.AUDIO_EXTENSIONS`: it also covers MP4/Ogg-Audio and AIFF,
formats the tag/rename/sort paths must leave alone.
"""

from __future__ import annotations

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ... import config, output

# MP4 containers are searched for readable audio tags and streams too.
EXPORT_EXTENSIONS = {".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".mp4", ".aac",
                     ".wav", ".wma", ".ape", ".wv", ".aiff", ".aif", ".mpc"}

CORE = ["artist", "albumartist", "album", "title", "track", "disc", "year", "genre"]
ALIASES = {
    "artist": "artist", "albumartist": "albumartist", "album artist": "albumartist",
    "album_artist": "albumartist", "album": "album", "title": "title",
    "tracknumber": "track", "track": "track", "discnumber": "disc", "disc": "disc",
    "date": "year", "year": "year", "genre": "genre",
}
SEP = " | "  # separates several values of the same tag


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


def _add_tag(tags, extra, key, values):
    key = key.strip().lower()
    vals = [str(v).strip() for v in (values if isinstance(values, (list, tuple)) else [values])
            if str(v).strip() != ""]
    if not vals:
        return
    core = ALIASES.get(key)
    if core:
        tags.setdefault(core, []).extend(vals)
    else:
        extra.setdefault(key, []).extend(vals)


def mutagen_cover(file_or_path):
    engine = _mutagen()
    if engine is None:
        return False
    try:
        f = file_or_path if hasattr(file_or_path, "tags") else engine.File(file_or_path)
        if f is None:
            return False
        if getattr(f, "pictures", None):
            return True
        t = f.tags
        if t is None:
            return False
        if hasattr(t, "getall") and t.getall("APIC"):
            return True
        return any(str(key).lower() in {"covr", "metadata_block_picture"} for key in t)
    except Exception:  # noqa: BLE001
        return False


def read_mutagen(path):
    engine = _mutagen()
    if engine is None:
        return None
    try:
        f = engine.File(path, easy=True)
        if f is None:
            return None
        tags, extra = {}, {}
        if f.tags:
            for k in list(f.tags.keys()):
                try:
                    _add_tag(tags, extra, k, f.tags[k])
                except Exception:  # noqa: BLE001 - ignore individual broken tags
                    pass
        info = getattr(f, "info", None)
        cover = mutagen_cover(f)
        return {
            "tags": tags, "extra": extra,
            "codec": type(f).__name__.replace("Easy", ""),
            "dur": getattr(info, "length", 0) or 0,
            "kbps": round((getattr(info, "bitrate", 0) or 0) / 1000),
            "sr": getattr(info, "sample_rate", 0) or 0,
            "ch": getattr(info, "channels", 0) or 0,
            "bits": getattr(info, "bits_per_sample", 0) or 0,
            "cover": cover,
        }
    except Exception:  # noqa: BLE001
        return None


def _num(value, *, cast: Any = float, default: Any = 0):
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.upper() in {"N/A", "NA", "NULL", "NONE"}:
        return default
    try:
        return cast(text)
    except (TypeError, ValueError):
        return default


def read_ffprobe(path, timeout=30):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(f"ffprobe timeout after {timeout}s") from e
    if r.returncode != 0 and not r.stdout.strip():
        return None
    try:
        d = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return None
    if not d:
        return None
    streams = d.get("streams", [])
    # First audio stream found (empty dict as fallback when none is present).
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    tags, extra = {}, {}
    sources = [d.get("format", {}).get("tags", {})] + [s.get("tags", {}) for s in streams]
    seen = set()
    for src in sources:
        for k, v in (src or {}).items():
            if k.lower() not in seen:
                seen.add(k.lower())
                _add_tag(tags, extra, k, v)
    fmt = d.get("format", {})
    br = _num(audio.get("bit_rate") or fmt.get("bit_rate") or 0, cast=int, default=0)
    return {
        "tags": tags, "extra": extra,
        "codec": audio.get("codec_name", "?"),
        "dur": _num(fmt.get("duration"), cast=float, default=0.0),
        "kbps": round(br / 1000),
        "sr": _num(audio.get("sample_rate") or 0, cast=int, default=0),
        "ch": _num(audio.get("channels") or 0, cast=int, default=0),
        "bits": _num(audio.get("bits_per_raw_sample") or audio.get("bits_per_sample") or 0,
                     cast=int, default=0),
        "cover": any(s.get("codec_type") == "video" and
                     s.get("disposition", {}).get("attached_pic") for s in streams),
    }


def _empty_data():
    return {
        "tags": {}, "extra": {}, "codec": "?", "dur": 0, "kbps": 0,
        "sr": 0, "ch": 0, "bits": 0, "cover": False,
    }


def read_file(root, path, *, use_ffprobe):
    """Read one file into a record; ``use_ffprobe`` allows the fallback reader."""
    rel = path.relative_to(root).as_posix()
    rec = {"path": rel, "ext": path.suffix.lower().lstrip("."), "size": 0, "error": ""}
    engine_available = _mutagen() is not None
    try:
        rec["size"] = path.stat().st_size
        data = read_mutagen(path) if engine_available else None
        if data is None and (not engine_available or use_ffprobe):
            data = read_ffprobe(path)
        if data is None:
            rec["error"] = "nicht lesbar"  # TODO(phase 2): i18n
            data = _empty_data()
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
        data = _empty_data()
    rec.update({k: data[k] for k in ("codec", "dur", "kbps", "sr", "ch", "bits", "cover", "extra")})
    for c in CORE:
        rec[c] = SEP.join(data["tags"].get(c, []))
    return rec


def scan(root, workers, *, use_ffprobe):
    """Walk ``root`` and read every audio file; report progress per file."""
    files = []
    for dp, _dn, fn in os.walk(root):
        for n in fn:
            p = Path(dp) / n
            if p.suffix.lower() in EXPORT_EXTENSIONS:
                files.append(p)
    files.sort(key=lambda p: p.relative_to(root).as_posix().casefold())
    total = len(files)

    def _read(pair):
        return read_file(pair[0], pair[1], use_ffprobe=use_ffprobe)

    out = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, rec in enumerate(ex.map(_read, ((root, p) for p in files)), 1):
            out.append(rec)
            output.progress(i, total, files[i - 1].name)
    return out
