#!/usr/bin/env python3
"""
musik_export.py - liest alle Infos und Tags eines Musikordners (NUR LESEND)
und erzeugt kompakte Berichte, die ein LLM (Claude, ChatGPT, ...) auswerten
kann, um Verbesserungen vorzuschlagen.

Aufruf:
    python3 musik_export.py ~/Music
    python3 musik_export.py ~/Music -o ~/export --chunk-zeichen 40000

Ausgabe (im Ausgabeordner):
    00_prompt.md         fertige Anweisung an das LLM (zuerst hochladen/einfuegen)
    01_zusammenfassung.md  Zusammenfassung und Statistik
    02_auffaelligkeiten.md automatisch gefundene Auffaelligkeiten
    03_duplikate.md       Audio-Fingerprint-Duplikate (optional)
    fpcalc_fehler.log    Dateien, die nicht fingerprinted werden konnten (optional)
    tracks_part01.tsv ...  kompakte Tabelle aller Dateien, in LLM-tauglichen Stuecken
    alle_tags.jsonl        ALLE Tags jeder Datei (optional, nur bei Bedarf)

Abhaengigkeiten: Python 3.8+, optional mutagen (schnell), sonst ffprobe.
"""
import argparse
import functools
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import mutagen
except ImportError:  # ffprobe-Fallback
    mutagen = None

_HAS_FFPROBE: bool = shutil.which("ffprobe") is not None  # einmal beim Start gecacht
QUIET = False

__version__ = "1.4"

# MP4-Container werden ebenfalls nach lesbaren Audio-Tags/Streams durchsucht.
EXTS = {".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".mp4", ".aac",
        ".wav", ".wma", ".ape", ".wv", ".aiff", ".aif", ".mpc"}

CORE = ["artist", "albumartist", "album", "title", "track", "disc", "year", "genre"]
ALIASES = {
    "artist": "artist", "albumartist": "albumartist", "album artist": "albumartist",
    "album_artist": "albumartist", "album": "album", "title": "title",
    "tracknumber": "track", "track": "track", "discnumber": "disc", "disc": "disc",
    "date": "year", "year": "year", "genre": "genre",
}
LOSSY = {"mp3", "oggvorbis", "oggopus", "mp4", "aac", "asf", "musepackfile",
         "opus", "vorbis", "wmav2"}
JUNK_RE = re.compile(
    r"(?i)(official\s*(music\s*)?(video|audio)|lyric\s*video|www\.|\.com\b|"
    r"\bhq\b|\bhd\b(?!\s*-\s*\S)|320\s*kbps|free\s*download)")
SEP = " | "  # trennt mehrere Werte desselben Tags
VA_NAMES = {"variousartists", "various", "va"}  # fuer Sampler-Erkennung


# --------------------------------------------------------------------------
# Einlesen
# --------------------------------------------------------------------------
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
    if mutagen is None:
        return False
    try:
        f = file_or_path if hasattr(file_or_path, "tags") else mutagen.File(file_or_path)
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
    if mutagen is None:
        return None
    try:
        f = mutagen.File(path, easy=True)
        if f is None:
            return None
        tags, extra = {}, {}
        if f.tags:
            for k in list(f.tags.keys()):
                try:
                    _add_tag(tags, extra, k, f.tags[k])
                except Exception:  # noqa: BLE001 - einzelne kaputte Tags ignorieren
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
        raise TimeoutError(f"ffprobe-Timeout nach {timeout}s") from e
    if r.returncode != 0 and not r.stdout.strip():
        return None
    try:
        d = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return None
    if not d:
        return None
    streams = d.get("streams", [])
    # Erster gefundener Audio-Stream (leeres Dict als Fallback, falls kein Stream vorhanden)
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


def read_file(item):
    root, path = item
    rel = path.relative_to(root).as_posix()
    rec = {"path": rel, "ext": path.suffix.lower().lstrip("."), "size": 0, "error": ""}
    try:
        rec["size"] = path.stat().st_size
        data = read_mutagen(path) if mutagen else None
        if data is None and (not mutagen or _HAS_FFPROBE):
            data = read_ffprobe(path)
        if data is None:
            rec["error"] = "nicht lesbar"
            data = _empty_data()
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
        data = _empty_data()
    rec.update({k: data[k] for k in ("codec", "dur", "kbps", "sr", "ch", "bits", "cover", "extra")})
    for c in CORE:
        rec[c] = SEP.join(data["tags"].get(c, []))
    return rec


def scan(root, workers):
    files = []
    for dp, _dn, fn in os.walk(root):
        for n in fn:
            p = Path(dp) / n
            if p.suffix.lower() in EXTS:
                files.append(p)
    files.sort(key=lambda p: p.relative_to(root).as_posix().casefold())
    total = len(files)
    out = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, rec in enumerate(ex.map(read_file, ((root, p) for p in files)), 1):
            out.append(rec)
            if not QUIET and (i % 200 == 0 or i == total):
                print(f"\r  {i}/{total} Dateien gelesen", end="", file=sys.stderr, flush=True)
    if not QUIET:
        print(file=sys.stderr)
    return out


# --------------------------------------------------------------------------
# Analyse
# --------------------------------------------------------------------------
_DROP = re.compile(r"[\s\-\u2010-\u2015_'’‘`\"“”]+")
_LOOSE = re.compile(r"[\W_]+")
THRESH = {"mp3": 128, "oggopus": 80, "opus": 80}  # kbps, sonst 96
TRUNC_MIN = 25  # Mindestlänge für Erkennung gekappter Ordnernamen
MAX_FILENAME_BYTES = 240  # Längengrenze für Dateinamen (Dateisystem-Kappung)
TRACK_DENSE_MIN = 3  # Mindestanzahl Tracks für dichte Folgen
TRACK_DENSE_RATIO = 0.60  # Mindestquote vorhandener Tracks für Lücken-Erkennung
TRACK_MAX_EXPECTED = 200  # Obergrenze für plausible Gesamtzahl eines Albums


@functools.lru_cache(maxsize=8192)
def norm(s):
    """Vergleichsschluessel fuer TAG-Varianten: ohne Gross/Klein, Latin-Akzente,
    Leerzeichen, Bindestriche (alle Arten), Unterstrich, Anfuehrungszeichen.
    Kana-Dakuten bleiben erhalten; reine Symboltitel kollidieren nicht."""
    s = unicodedata.normalize("NFKD", s.casefold())
    # Akzente/Diakritika entfernen, aber Kana-Dakuten (U+3099, U+309A) beibehalten
    s = "".join(
        c for c in s
        if not (unicodedata.category(c).startswith("M") and ord(c) not in (0x3099, 0x309A))
    )
    return _DROP.sub("", s) or s


def loose(s):
    """Sehr grob (nur Buchstaben/Ziffern) fuer Datei-/Ordnernamen, in denen das
    Dateisystem Zeichen wie : / ? * | durch _ ersetzt hat."""
    return _LOOSE.sub("", unicodedata.normalize("NFKC", s.casefold()))


def track_info(s):
    """Liest Tracknummer und optional die Gesamtzahl aus z. B. 03/12 oder 3 of 12."""
    s = (s or "").strip()
    m = re.match(r"^(\d+)(?:\s*/\s*(\d+)|\s+of\s+(\d+))?", s, re.IGNORECASE)
    if not m:
        return None, None
    num = int(m.group(1))
    total = int(m.group(2) or m.group(3)) if (m.group(2) or m.group(3)) else None
    return num, total


def track_num(s):
    return track_info(s)[0]


def track_analysis(recs):
    """Prueft Tracknummern pro Album konservativ.

    Fehlende Tags werden separat von echten Nummernluecken behandelt.
    Nummernluecken werden nur gemeldet, wenn genug Evidenz fuer eine vollstaendige
    Trackfolge vorhanden ist: explizite Gesamtzahl im Tag oder eine dichte Folge ab 1.
    """
    by_dir = defaultdict(list)
    for r in recs:
        d = str(Path(r["path"]).parent)
        if d != ".":
            by_dir[d].append(r)

    checked = 0
    missing_multi = 0
    albums_with_missing = 0
    all_missing = 0
    gap_groups = []
    incomplete_groups = []
    sparse_groups = set()

    for d, rs in sorted(by_dir.items(), key=lambda kv: kv[0].casefold()):
        albums = defaultdict(list)
        for r in rs:
            owner = norm(r["albumartist"] or r["artist"] or "")
            album = norm(r["album"] or "")
            albums[(owner, album)].append(r)

        for (_owner, _album), ars in albums.items():
            if len(ars) < 2:
                continue
            checked += 1
            missing = [r for r in ars if track_num(r["track"]) is None]
            missing_multi += len(missing)
            if missing:
                albums_with_missing += 1

            by_disc = defaultdict(list)
            for r in ars:
                disc = track_num(r["disc"])
                disc = 1 if disc is None else disc
                by_disc[disc].append(r)

            gaps = []
            for disc, drs in sorted(by_disc.items()):
                infos = [track_info(r["track"]) for r in drs]
                valid = [num for num, _total in infos if num is not None and num > 0]
                totals = [total for track_number, total in infos if total and total > 0]
                if not valid:
                    continue

                present = set(valid)
                max_n = max(valid)
                total_hint = max(totals) if totals and len(set(totals)) == 1 else None

                # Starke Evidenz: ein expliziter /Gesamtwert im Track-Tag.
                explicit_total_ok = (
                    total_hint is not None and
                    total_hint >= max_n and
                    total_hint <= max(TRACK_MAX_EXPECTED, len(drs) * 3) and
                    len(drs) >= max(2, int((total_hint * TRACK_DENSE_RATIO) + 0.999))
                )

                # Ohne Gesamtwert nur dichte Folgen ab 1 analysieren. So werden
                # teilweise vorhandene Alben nicht als dutzende "fehlende" Tracks
                # fehlinterpretiert.
                dense_sequence_ok = (
                    len(valid) >= TRACK_DENSE_MIN and
                    min(valid) == 1 and
                    max_n <= len(valid) * 2 and
                    (len(valid) / max_n) >= TRACK_DENSE_RATIO
                )

                if explicit_total_ok and total_hint is not None:
                    expected_max = total_hint
                    local_gaps = [n for n in range(1, expected_max + 1) if n not in present]
                    if local_gaps:
                        gaps.extend((disc, n) for n in local_gaps)
                elif dense_sequence_ok:
                    local_gaps = [n for n in range(1, max_n + 1) if n not in present]
                    if local_gaps:
                        gaps.extend((disc, n) for n in local_gaps)
                elif len(valid) >= 2 and max_n > len(valid) * 2:
                    # Sparse Nummernfolge: interessant, aber keine belastbare Aussage
                    # darueber, welche Tracks tatsaechlich fehlen.
                    sparse_groups.add((d, _album))

            label = f"`{d}`"
            album_display = next((r["album"] for r in ars if r["album"]), "(ohne Album)")

            if missing:
                if len(missing) == len(ars):
                    all_missing += 1
                    incomplete_groups.append(
                        f"{label} / `{album_display}`: ALLE {len(ars)} Track-Tags fehlen"
                    )
                else:
                    incomplete_groups.append(
                        f"{label} / `{album_display}`: {len(missing)} von {len(ars)} Track-Tags fehlen"
                    )

            if gaps:
                shown = ", ".join(f"CD{disc}#{num}" for disc, num in gaps[:12])
                if len(gaps) > 12:
                    shown += f", ... ({len(gaps)} Lücken)"
                gap_groups.append(
                    f"{label} / `{album_display}`: belastbare Lücken -> {shown}"
                )

    return {
        "checked": checked,
        "missing_multi": missing_multi,
        "albums_with_missing": albums_with_missing,
        "all_missing": all_missing,
        "incomplete": sorted(incomplete_groups, key=str.casefold),
        "gaps": sorted(gap_groups, key=str.casefold),
        "sparse": len(sparse_groups),
    }


def lst(items, limit):
    """Formatiert eine Liste von Einträgen für Markdown, gekürzt auf `limit` Zeilen."""
    items = list(items)
    if not items:
        return ["- (keine)"]
    out = [x if x.startswith("- ") else f"- {x}" for x in items[:limit]]
    if len(items) > limit:
        out.append(f"- ... ({len(items) - limit} weitere)")
    return out


def date_fmt(s):
    """Erkennt das Datums-/Jahresformat eines Jahr-Tags."""
    s = (s or "").strip()
    if not s:
        return "(leer)"
    if re.fullmatch(r"\d{4}", s):
        return "YYYY"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return "YYYY-MM-DD"
    if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", s):
        return "YYYY.MM.DD"
    if re.fullmatch(r"\d{4}-\d{2}", s):
        return "YYYY-MM"
    if re.fullmatch(r"\d{4}/\d{2}/\d{2}", s):
        return "YYYY/MM/DD"
    if re.fullmatch(r"\d{4}/\d{2}", s):
        return "YYYY/MM"
    if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", s):
        return "DD.MM.YYYY"
    if re.match(r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}", s):
        return "ISO-Zeitstempel"
    if re.fullmatch(r"\d{4}\s*[-/]\s*\d{4}", s):
        return "YYYY-YYYY (Bereich)"
    return "Freitext / Sonstiges"


def variants(recs, field, split=False, by_artist=False):
    """Findet Schreibweisevarianten (Groß/Klein, Akzente, Bindestriche etc.) desselben Tags."""
    groups = defaultdict(lambda: {"counts": Counter(), "artist": ""})
    for r in recs:
        raw = r.get(field) or ""
        if not raw:
            continue
        vals = [v.strip() for v in raw.split(SEP)] if split else [raw.strip()]
        artist = (r.get("albumartist") or r.get("artist") or "").strip()
        for v in vals:
            if not v:
                continue
            nv = norm(v)
            if not nv:
                continue
            key = (norm(artist), nv) if by_artist else nv
            groups[key]["counts"][v] += 1
            if by_artist and not groups[key]["artist"]:
                groups[key]["artist"] = artist

    out = []
    for info in groups.values():
        counts = info["counts"]
        if len(counts) > 1:
            parts = [f'"{name}" ({c}x)' for name, c in counts.most_common()]
            line = " <-> ".join(parts)
            if info["artist"]:
                line = f"`{info['artist']}`: {line}"
            out.append(line)
    out.sort(key=str.casefold)
    return out


def folder_vs_tags(recs):
    """Vergleicht Ordnernamen mit Künstler- und Album-Tags."""
    t_mis = Counter()
    a_mis = Counter()
    skipped_paths = set()

    for r in recs:
        path = r["path"]
        parts = Path(path).parts
        if len(parts) < 2:
            continue

        top_folder = parts[0]
        artist_tag = (r.get("albumartist") or r.get("artist") or "").strip()
        if artist_tag:
            l_top = loose(top_folder)
            l_tag = loose(artist_tag)
            tag_artists = [a.strip() for a in re.split(r"\s*(?:\||;|&|\bfeat\.?\b|/)\s*", artist_tag) if a.strip()]
            l_tag_artists = [loose(a) for a in tag_artists]

            if l_top == l_tag:
                pass
            elif any(l_top == la for la in l_tag_artists if la):
                skipped_paths.add(path)
            elif len(top_folder) >= TRUNC_MIN and (l_tag.startswith(l_top) or l_top.startswith(l_tag)):
                skipped_paths.add(path)
            elif l_top in VA_NAMES and any(loose(a) in VA_NAMES for a in [r.get("albumartist", ""), r.get("artist", "")]):
                pass
            else:
                t_mis[(top_folder, artist_tag)] += 1

        if len(parts) >= 3:
            album_folder = parts[-2]
            if album_folder.lower().startswith(("cd", "disc", "disk")) and len(parts) >= 4:
                album_folder = parts[-3]

            album_tag = (r.get("album") or "").strip()
            if album_tag:
                l_album_folder = loose(album_folder)
                l_album_tag = loose(album_tag)
                if l_album_folder == l_album_tag:
                    pass
                elif len(album_folder) >= TRUNC_MIN and (l_album_tag.startswith(l_album_folder) or l_album_folder.startswith(l_album_tag)):
                    skipped_paths.add(path)
                else:
                    a_mis[(album_folder, album_tag)] += 1

    return t_mis, a_mis, skipped_paths


def style_issues(r, check_case=False):
    """Findet Stil- und Formatierungsprobleme in den Tags einer Datei."""
    issues = []
    for field, name in (("title", "Titel"), ("artist", "Künstler"), ("album", "Album")):
        val = r.get(field) or ""
        m = JUNK_RE.search(val)
        if m:
            issues.append(f"Junk im {name} ('{m.group(0)}')")
        if "  " in val:
            issues.append(f"Doppelte Leerzeichen im {name}")

    title = r.get("title") or ""
    if re.match(r"^\d{1,3}\s*[-.]\s*\S", title):
        issues.append("Tracknummer im Titel-Tag")

    if title and "_" in title and " " not in title and len(title) > 3:
        issues.append("Unterstriche statt Leerzeichen im Titel")

    if check_case:
        for field, name in (("artist", "Künstler"), ("album", "Album"), ("title", "Titel")):
            val = r.get(field) or ""
            chars = [c for c in val if c.isalpha()]
            if len(chars) >= 4:
                if all(c.isupper() for c in chars):
                    issues.append(f"{name} nur in GROSSBUCHSTABEN")
                elif all(c.islower() for c in chars):
                    issues.append(f"{name} nur kleingeschrieben")

    return issues


def _summary_formats_and_tags(ok, recs, n_ok, max_ex):
    lines = ["## Formate", ""]
    for k, c in Counter(r["ext"] for r in recs).most_common():
        lines.append(f"- {k}: {c}")
    by = defaultdict(list)
    for r in ok:
        if r["kbps"] and r["codec"].lower() in LOSSY:
            by[r["codec"]].append(r["kbps"])
    for c, v in sorted(by.items()):
        t = THRESH.get(c.lower(), 96)
        lines.append(f"- Bitrate {c}: Median {statistics.median(v):.0f} kbps, unter {t} kbps: "
                     f"{sum(1 for x in v if x < t)} von {len(v)}")
    lines.append(f"- Ohne Cover: {sum(1 for r in ok if not r['cover'])}")
    lines.append("")

    # Prozentwerte relativ zu lesbaren Dateien; disc wird separat erlaeutert
    lines += ["## Fehlende Tags (Anzahl Dateien; `disc` fehlt bei Einzel-CDs normal)", ""]
    for c in CORE:
        if c == "disc":
            continue
        n_missing = sum(1 for r in ok if not r[c])
        lines.append(f"- {c}: {n_missing} ({100 * n_missing / n_ok:.1f} %)")
    n_disc = sum(1 for r in ok if not r["disc"])
    lines.append(f"- disc: {n_disc} ({100 * n_disc / n_ok:.1f} %; meist normal bei Einzel-CDs)")
    lines.append("")

    lines += ["## Oberste Ordner (Dateien)", ""]
    top = Counter(r["path"].split("/")[0] if "/" in r["path"] else "(Wurzel)" for r in recs)
    lines += lst([f"{k}: {v}" for k, v in top.most_common()], max_ex) + [""]

    lines += ["## Genres (alle, mit Anzahl)", ""]
    g = Counter(v for r in ok for v in (r["genre"].split(SEP) if r["genre"] else []))
    lines += [f"- {k}: {v}" for k, v in g.most_common()] + [""]

    lines += ["## Datumsformate im Jahr-Tag", ""]
    fm = defaultdict(list)
    for r in ok:
        if r["year"]:
            fm[date_fmt(r["year"])].append(r["path"])
    max_fm_len = max((len(x) for x in fm.values()), default=0)
    for k, v in sorted(fm.items(), key=lambda kv: -len(kv[1])):
        ex = "" if len(v) == max_fm_len else f" (z. B. `{v[0]}`)"
        lines.append(f"- {k}: {len(v)}{ex}")
    lines.append("")

    lines += ["## Jahrzehnte", ""]
    dec = Counter(f"{r['year'][:3]}0er" for r in ok if re.match(r"\d{4}", r["year"] or ""))
    lines += [f"- {k}: {v}" for k, v in sorted(dec.items())] + [""]

    lines += ["## Top-Künstler", ""]
    a = Counter(r["artist"] for r in ok if r["artist"])
    lines += [f"- {k}: {v}" for k, v in a.most_common(max_ex)] + [""]
    return lines


def _summary_track_quality(ok, max_ex):
    ta = track_analysis(ok)
    lines = ["## Tracknummern-Qualität pro Mehrspur-Album", "",
             f"- Mehrspur-Alben/Ordner geprüft: {ta['checked']}",
             f"- Dateien mit fehlendem Track-Tag innerhalb dieser Mehrspur-Alben: {ta['missing_multi']}",
             f"- Alben mit mindestens einem fehlenden Track-Tag: {ta['albums_with_missing']}",
             f"- Alben, bei denen sämtliche Track-Tags fehlen: {ta['all_missing']}",
             f"- Alben mit belastbaren Tracknummern-Lücken: {len(ta['gaps'])}",
             f"- Weitere Alben mit sehr sparsamen/unklaren Nummernfolgen: {ta['sparse']}", ""]
    lines += [f"### Fehlende Track-Tags ({len(ta['incomplete'])})", "",
              "_Ein fehlender Track-Tag wird nicht automatisch als fehlender Track gewertet._", ""]
    lines += lst(ta["incomplete"], max_ex) + [""]
    lines += [f"### Belastbare Tracknummern-Lücken ({len(ta['gaps'])})", "",
              "_Nur dichte Folgen ab 1 oder explizite Gesamtzahlen (z. B. 03/12) werden als Lücke gewertet._", ""]
    lines += lst(ta["gaps"], max_ex) + [""]
    return lines


def _summary_anomalies(ok, recs, max_ex, check_case):
    lines = ["# Automatisch gefundene Auffälligkeiten", "",
             "_Nur Hinweise, keine bewiesenen Fehler. Verglichen wird ohne Groß/Klein, Akzente, "
             "Leerzeichen und Bindestrich-Arten._", ""]
    for title, field, split, ba in (
            ("Künstler: nur Schreibweise verschieden", "artist", False, False),
            ("Album-Künstler: nur Schreibweise verschieden", "albumartist", False, False),
            ("Album (pro Künstler): nur Schreibweise verschieden", "album", False, True),
            ("Genre: nur Schreibweise verschieden", "genre", True, False)):
        v = variants(ok, field, split, ba)
        lines += [f"## {title} ({len(v)})", ""] + lst(v, max_ex) + [""]

    t_mis, a_mis, skipped_paths = folder_vs_tags(ok)
    lines += [f"## Oberster Ordner passt nicht zu Album-Künstler/Künstler-Tag ({len(t_mis)} Paare)", "",
              f"_Schon herausgerechnet: gekappte Ordnernamen (ab {TRUNC_MIN} Zeichen als Anfang des Tags "
              f"akzeptiert) und Ordner, die einem von mehreren Künstlern im Tag entsprechen "
              f"({len(skipped_paths)} Dateien betroffen, Ordner- und Album-Prüfung zusammen)._", ""]
    lines += lst([f'Ordner "{f}" <-> Tag "{t}" ({c}x)' for (f, t), c in t_mis.most_common()], max_ex) + [""]
    lines += [f"## Album-Ordner passt nicht zum Album-Tag ({len(a_mis)} Paare)", ""]
    lines += lst([f'Ordner "{f}" <-> Tag "{t}" ({c}x)' for (f, t), c in a_mis.most_common()], max_ex) + [""]

    st = [(r["path"], style_issues(r, check_case)) for r in ok]
    st = [(p, x) for p, x in st if x]
    lines += [f"## Stil-Probleme in Tags ({len(st)} Dateien)", ""]
    lines += lst([f"`{p}`: {', '.join(x)}" for p, x in st], max_ex) + [""]

    mism = []
    for r in ok:
        name = Path(r["path"]).name
        if len(name.encode("utf-8")) >= MAX_FILENAME_BYTES:  # vom Dateisystem gekuerzt
            continue
        if r["title"] and loose(r["title"]) not in loose(Path(r["path"]).stem):
            mism.append(f"`{r['path']}` (Titel-Tag: \"{r['title']}\")")
    lines += [f"## Dateiname enthält den Titel-Tag nicht ({len(mism)}; `: / ? * |` -> `_` und "
              f"gekürzte Namen sind schon herausgerechnet)", ""] + lst(mism, max_ex) + [""]

    dup = defaultdict(list)
    for r in ok:
        if r["artist"] and r["title"]:
            dup[(norm(r["artist"]), norm(r["title"]))].append(r)
    dups = [v for v in dup.values() if len(v) > 1]
    lines += [f"## Mögliche Duplikate (gleicher Künstler+Titel) ({len(dups)} Gruppen)", ""]
    lines += lst([" ; ".join(f"`{r['path']}` ({r['kbps']}k, {round(r['dur'])}s, {r['size'] / 1e6:.1f}MB)"
                             for r in v) for v in dups], max_ex) + [""]

    bydir = defaultdict(list)
    for r in ok:
        d = str(Path(r["path"]).parent)
        if d != ".":  # lose Dateien im Wurzelordner gehoeren zu keinem Album
            bydir[d].append(r)
    inc, dbl, comp = [], [], []
    for d, rs in sorted(bydir.items()):
        probs = []
        for f, lbl in (("album", "Album"), ("albumartist", "Album-Künstler"), ("genre", "Genre")):
            vals = {r[f] for r in rs if r[f]}
            if len(vals) > 1:
                probs.append(f"{lbl}: {sorted(vals)}")
        if probs:
            inc.append(f"`{d}` - " + "; ".join(probs))
        seen = defaultdict(int)
        for r in rs:
            t = track_num(r["track"])
            if t is not None:  # Tracknummer vorhanden (auch Track 0 berücksichtigen)
                disc = track_num(r["disc"])
                disc = 1 if disc is None else disc
                seen[(norm(r["album"]), disc, t)] += 1
        twice = sorted({f"CD{k[1]}#{k[2]}" for k, c in seen.items() if c > 1})
        if twice:
            dbl.append(f"`{d}`: {twice[:10]}")
        # Sampler-Erkennung greift bei wechselnden Künstlern ohne einheitlichen Album-Künstler
        # oder wenn Album-Künstler explizit "Various Artists" ist.
        artists = {r["artist"] for r in rs if r["artist"]}
        if len(rs) >= 4 and len(artists) > 3:
            albumartists = {r["albumartist"] for r in rs if r["albumartist"]}
            missing = sum(1 for r in rs if not r["albumartist"])
            if missing:
                comp.append(f"`{d}` ({len(artists)} Künstler, Album-Künstler fehlt bei "
                            f"{missing}/{len(rs)})")
            elif albumartists and all(loose(a) in VA_NAMES for a in albumartists):
                comp.append(f"`{d}` ({len(artists)} Künstler, Album-Künstler überall "
                            f"\"Various Artists\")")
    lines += [f"## Ordner mit uneinheitlichem Album/Album-Künstler/Genre ({len(inc)}; Wurzel ausgenommen)", ""]
    lines += lst(inc, max_ex) + [""]
    lines += [f"## Doppelte Tracknummern im selben Ordner+Album ({len(dbl)})", ""] + lst(dbl, max_ex) + [""]
    lines += [f"## Vermutliche Sampler ohne expliziten Album-Künstler ({len(comp)})", ""] + lst(comp, max_ex) + [""]

    errs = [f"`{r['path']}`: {r['error']}" for r in recs if r["error"]]
    if errs:
        lines += [f"## Lesefehler ({len(errs)})", ""] + lst(errs, max_ex) + [""]
    return lines


def build_summary(recs: List[Dict[str, Any]], root: Path, max_ex: int,
                  check_case: bool = False) -> str:
    n = len(recs)
    ok = [r for r in recs if not r["error"]]
    n_ok = max(len(ok), 1)  # Vermeidet Division durch 0 bei reinen Lesefehlern
    lines = ["# Zusammenfassung Musikordner", "",
             f"- Ordner: `{root}`", f"- Erstellt: {datetime.now():%Y-%m-%d %H:%M}",
             f"- Dateien: **{n}** (Lesefehler: {n - len(ok)})",
             f"- Gesamtgröße: {sum(r['size'] for r in recs) / 1e9:.2f} GB",
             f"- Gesamtdauer: {sum(r['dur'] for r in recs) / 3600:.1f} Stunden",
             f"- Lose Dateien direkt im Wurzelordner (unsortiert): "
             f"{sum(1 for r in recs if '/' not in r['path'])}", ""]

    if not ok:
        lines += ["> [!WARNING]",
                  "> Es konnten keine Dateien erfolgreich gelesen werden.", ""]
        errs = [f"`{r['path']}`: {r['error']}" for r in recs if r["error"]]
        if errs:
            lines += [f"## Lesefehler ({len(errs)})", ""] + lst(errs, max_ex) + [""]
        return "\n".join(lines)

    lines += _summary_formats_and_tags(ok, recs, n_ok, max_ex)
    lines += _summary_track_quality(ok, max_ex)
    lines += _summary_anomalies(ok, recs, max_ex, check_case)
    return "\n".join(lines)


def write_summary_split(summary: str, outdir: Path) -> List[str]:
    headings = (
        "Zusammenfassung", "Formate", "Fehlende Tags", "Oberste Ordner", "Genres",
        "Datumsformate", "Jahrzehnte", "Top-Künstler", "Tracknummern-Qualität",
        "Automatisch gefundene Auffälligkeiten", "Audio-Fingerprint-Duplikate",
    )
    sections = []
    current = []
    target = "summary"
    for line in summary.splitlines():
        match = re.match(r"^#{1,2} (.+)$", line)
        heading = next((name for name in headings
                        if match and match.group(1).startswith(name)), None)
        if heading:
            if current:
                sections.append((target, "\n".join(current).strip()))
            current = [line]
            target = ("anomalies" if heading == "Automatisch gefundene Auffälligkeiten"
                      else "duplicates" if heading == "Audio-Fingerprint-Duplikate"
                      else "summary")
        else:
            current.append(line)
    if current:
        sections.append((target, "\n".join(current).strip()))

    contents = {
        "summary": "\n\n".join(text for kind, text in sections if kind == "summary"),
        "anomalies": "\n\n".join(text for kind, text in sections if kind == "anomalies"),
        "duplicates": "\n\n".join(text for kind, text in sections if kind == "duplicates"),
    }
    names = ["01_zusammenfassung.md", "02_auffaelligkeiten.md"]
    (outdir / names[0]).write_text(contents["summary"] + "\n", encoding="utf-8")
    (outdir / names[1]).write_text(contents["anomalies"] + "\n", encoding="utf-8")
    if contents["duplicates"]:
        names.append("03_duplikate.md")
        (outdir / names[2]).write_text(contents["duplicates"] + "\n", encoding="utf-8")
    return names


# --------------------------------------------------------------------------
# Audio-Fingerprints (optional, --fingerprint) - findet Duplikate unabhaengig von Tags
# --------------------------------------------------------------------------
_popcount = (lambda x: x.bit_count()) if hasattr(int, "bit_count") else (lambda x: bin(x).count("1"))
FP_MAX_POSTINGS = 50   # Sub-Fingerprints, die in mehr Dateien vorkommen, sind Rauschen
FP_MIN_VOTES = 8       # so viele gleiche Sub-Fingerprints am selben Versatz = Kandidat
FP_MIN_OVERLAP_RATIO = 0.5  # Mindestanteil Überlappung bezogen auf kürzeren Fingerprint
FP_MIN_OVERLAP_FRAMES = 20  # Mindestanzahl Sub-Fingerprints im Überlappungsfenster
DURATION_TOLERANCE_SECS = 3.0  # Feste Toleranz in Sekunden für gleiche Spieldauer
DURATION_TOLERANCE_RATIO = 0.02  # Relative Toleranz (2%) für Spieldauer
# Bitpacking im Inverted-Index: (fid << FP_POS_BITS) | pos
FP_POS_BITS = 20          # Bits für die Position (max. 2^20 = 1 048 576 Sub-FPs pro Datei)
FP_POS_MASK = (1 << FP_POS_BITS) - 1  # 0xFFFFF


def run_fpcalc(path, secs) -> Tuple[Any, str]:
    try:
        r = subprocess.run(["fpcalc", "-raw", "-length", str(secs), str(path)],
                           capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError) as e:
        return None, str(e)
    if r.returncode != 0:
        return None, r.stderr.strip() or f"fpcalc exit code {r.returncode}"
    for line in r.stdout.splitlines():
        if line.startswith("FINGERPRINT="):
            return [int(x) & 0xFFFFFFFF for x in line[12:].split(",") if x.strip()], ""
    return None, r.stderr.strip() or "keine FINGERPRINT-Ausgabe"


def fp_cache_path(root: Path) -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "musik_export"
    base.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
    return base / f"fp_{key}.json"


def compute_fingerprints(recs: List[Dict[str, Any]], root: Path, secs: int,
                         workers: int, outdir: Path) -> Dict[int, List[int]]:
    """Fingerprints mit Cache (Pfad+Groesse+mtime), damit Wiederholungen schnell sind."""
    cache_file = fp_cache_path(root)
    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        cache = {}
    active_paths = {r["path"] for r in recs}
    cache_size = len(cache)
    cache = {path: value for path, value in cache.items() if path in active_paths}
    cache_changed = len(cache) != cache_size
    cache_key = f"len{secs}"
    todo, fps = [], {}
    for i, r in enumerate(recs):
        try:
            st = (root / r["path"]).stat()
        except OSError:
            continue
        meta = [st.st_size, int(st.st_mtime)]
        c = cache.get(r["path"])
        if c and c.get("meta") == meta and c.get("k") == cache_key and c.get("fp"):
            fps[i] = c["fp"]
        else:
            todo.append((i, meta))
    if not QUIET:
        print(f"  Fingerprints: {len(fps)} aus Cache, {len(todo)} neu zu berechnen", file=sys.stderr)

    def work(item):
        i, meta = item
        try:
            return i, meta, *run_fpcalc(root / recs[i]["path"], secs)
        except Exception as e:  # noqa: BLE001
            return i, meta, None, str(e)

    failed = 0
    failed_paths = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for n, (i, meta, fp, error) in enumerate(ex.map(work, todo), 1):
            if fp:
                fps[i] = fp
                cache[recs[i]["path"]] = {"meta": meta, "k": cache_key, "fp": fp}
            else:
                failed += 1
                failed_paths.append((recs[i]["path"], error or "unbekannter Fehler"))
            if not QUIET and (n % 50 == 0 or n == len(todo)):
                print(f"\r  {n}/{len(todo)} berechnet", end="", file=sys.stderr, flush=True)
    if todo or cache_changed:
        if todo and not QUIET:
            print(file=sys.stderr)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=cache_file.parent,
                    prefix=f".{cache_file.name}.", suffix=".tmp", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                json.dump(cache, tmp)
            tmp_path.replace(cache_file)
        except OSError:
            pass
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
    if failed:
        (outdir / "fpcalc_fehler.log").write_text(
            "\n".join(f"{path}\t{error.replace(chr(9), ' ').replace(chr(10), ' ')}"
                      for path, error in failed_paths) + "\n",
            encoding="utf-8")
        print(f"  Hinweis: {failed} Datei(en) ohne Fingerprint, Details in fpcalc_fehler.log",
              file=sys.stderr)
    return fps


def _similarity(a, b, off):
    """Aehnlichkeit 0..1 von a[i] und b[i+off] ueber den Ueberlappungsbereich."""
    lo, hi = max(0, -off), min(len(a), len(b) - off)
    n = hi - lo
    if n < FP_MIN_OVERLAP_RATIO * min(len(a), len(b)) or n < FP_MIN_OVERLAP_FRAMES:
        return 0.0
    bits = sum(_popcount(a[i] ^ b[i + off]) for i in range(lo, hi))
    return 1.0 - bits / (32.0 * n)


def fingerprint_groups(recs: List[Dict[str, Any]], fps: Dict[int, List[int]],
                       threshold: float) -> Tuple[List[Tuple[List[int], float]], int]:
    """Inverted-Index-Verfahren: nur Paare mit vielen gleichen Sub-Fingerprints am
    gleichen Zeitversatz werden genauer verglichen (kein n*n-Vergleich)."""
    index = defaultdict(list)
    for fid, fp in fps.items():
        for pos, v in enumerate(fp):
            if v and pos <= FP_POS_MASK:
                index[v].append((fid << FP_POS_BITS) | pos)
    pairs = {}
    for fid, fp in fps.items():
        votes = Counter()
        for pos, v in enumerate(fp):
            if pos > FP_POS_MASK:
                break
            post = index.get(v)
            if not post or len(post) > FP_MAX_POSTINGS:
                continue
            for code in post:
                other = code >> FP_POS_BITS
                if other > fid:
                    votes[(other, (code & FP_POS_MASK) - pos)] += 1
        best = {}
        for (other, off), c in votes.items():
            if c >= FP_MIN_VOTES and c > best.get(other, (0, 0))[0]:
                best[other] = (c, off)
        for other, (_c, off) in best.items():
            sim = _similarity(fp, fps[other], off)
            if sim >= threshold:
                pairs[(fid, other)] = sim
    # Paare -> Gruppen (Union-Find)
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (a, b) in pairs:
        parent[find(a)] = find(b)
    groups = defaultdict(list)
    for x in list(parent):
        groups[find(x)].append(x)
    group_sims = defaultdict(list)
    for (a, b), sim in pairs.items():
        group_sims[find(a)].append(sim)
    out = []
    for uf_root, members in groups.items():
        members.sort()
        sims = group_sims.get(uf_root, [1.0])
        out.append((members, min(sims)))
    out.sort(key=lambda g: (-len(g[0]), -g[1]))
    return out, len(pairs)


def _duplicate_marker(path):
    stem = Path(path).stem
    return bool(re.search(r"(?i)(?:\(\d+\)|\bcopy\b|\bkopie\b|\bduplicate\b)", stem))


def _duration_close(durs):
    if not durs:
        return True
    mx = max(durs)
    return (mx - min(durs)) <= max(DURATION_TOLERANCE_SECS, DURATION_TOLERANCE_RATIO * mx)


def _same_identity(rs):
    return len({(norm(r["artist"]), norm(r["title"])) for r in rs}) == 1


def _same_album(rs):
    return len({(norm(r["albumartist"]), norm(r["album"])) for r in rs}) == 1


def _dupe_class(sim, same_identity, duration_close, marker, same_album):
    # Nur hohe Audioaehnlichkeit + passende Metadaten/Laenge als echte Dublette
    # einstufen. Hohe Aehnlichkeit allein reicht nicht (Cover/Versionen!).
    if sim >= 0.95 and same_identity and duration_close and same_album:
        return "sehr_wahrscheinlich"
    if sim >= 0.90 and same_identity and (duration_close or marker):
        return "wahrscheinlich"
    if sim >= 0.90 and marker and duration_close:
        return "wahrscheinlich"
    if sim >= 0.80:
        return "pruefen"
    return "aehnlich"


def _quality_hint(rs):
    # Kein automatisches Loeschen: nur ein Hinweis, welche Datei bei gleicher
    # Aufnahme technisch die groessere/hoeher bitrate Variante ist.
    if len(rs) < 2:
        return ""
    bitrates = [(r["kbps"], r["path"]) for r in rs if r["kbps"]]
    if not bitrates:
        return ""
    max_k = max(k for k, _ in bitrates)
    min_k = min(k for k, _ in bitrates)
    if max_k > min_k:
        winner = next(path for k, path in bitrates if k == max_k)
        return f"; höhere Bitrate: `{winner}` ({max_k}k)"
    return ""


def fp_section(recs, groups, n_fp, n_total, threshold, max_ex):
    """Ordnet Fingerprint-Gruppen nach mehreren Evidenzen statt nur nach Prozentwert."""
    rows = []
    for members, sim in groups:
        rs = [recs[i] for i in members]
        same_identity = _same_identity(rs)
        same_album = _same_album(rs)
        durs = [r["dur"] for r in rs]
        duration_close = _duration_close(durs)
        marker = any(_duplicate_marker(r["path"]) for r in rs)
        classification = _dupe_class(sim, same_identity, duration_close, marker, same_album)

        flags = []
        flags.append("Künstler+Titel gleich" if same_identity else "Künstler/Titel verschieden")
        flags.append("Länge ähnlich" if duration_close else "Länge verschieden")
        if same_album:
            flags.append("Album gleich")
        if marker:
            flags.append("Duplikat-Marker im Dateinamen")
        hint = _quality_hint(rs) if classification in {"sehr_wahrscheinlich", "wahrscheinlich"} else ""
        items = " ; ".join(
            f"`{r['path']}` ({r['kbps']}k, {round(r['dur'])}s, {r['size'] / 1e6:.1f}MB, "
            f'"{r["artist"]} - {r["title"]}")' for r in rs)
        rows.append((sim, classification, f"[{sim:.0%}, {', '.join(flags)}{hint}] {items}"))

    rows.sort(key=lambda x: (-x[0], x[1]))
    buckets = [
        ("sehr_wahrscheinlich", "Sehr wahrscheinlich echte Dublette"),
        ("wahrscheinlich", "Wahrscheinliche Dublette"),
        ("pruefen", "Prüfen – könnte andere Version sein"),
        ("aehnlich", "Ähnliche Aufnahme / mögliche Variante"),
    ]

    L = [f"## Audio-Fingerprint-Duplikate ({len(groups)} Gruppen; {n_fp}/{n_total} Dateien "
         f"hatten einen Fingerprint; Basisschwelle {threshold:.0%})", "",
         "_Die Einstufung kombiniert Audio-Ähnlichkeit, Künstler+Titel, Album, Dauer und "
         "Duplikat-Marker im Dateinamen. Ein hoher Fingerprint-Wert allein beweist keine "
         "identische Aufnahme. Versionen, Cover, Instrumentals, Edits und verschiedene "
         "Sprachfassungen können ebenfalls hohe Ähnlichkeit erreichen. Ein technischer "
         "Qualitätshinweis nennt bei wahrscheinlichen Dubletten eine Variante mit höherer "
         "Bitrate, löscht oder bevorzugt aber nichts automatisch._", ""]

    for key, title in buckets:
        bucket = [row for row in rows if row[1] == key]
        L += [f"### {title} ({len(bucket)} Gruppen)", ""]
        L += lst([row[2] for row in bucket], max_ex) + [""]
    return L


# --------------------------------------------------------------------------
# Ausgabe
# --------------------------------------------------------------------------
TSV_HEAD = ["path", "artist", "albumartist", "album", "title", "track", "disc",
            "year", "genre", "sek", "kbps", "codec", "cover"]


def clean(v: object) -> str:
    return "".join(" " if unicodedata.category(char) == "Cc" else char for char in str(v))


def tsv_row(r):
    vals = [r["path"], r["artist"], r["albumartist"], r["album"], r["title"], r["track"],
            r["disc"], r["year"], r["genre"], round(r["dur"]), r["kbps"], r["codec"],
            "j" if r["cover"] else "n"]
    return "\t".join(clean(v) for v in vals)


def write_chunks(recs, outdir, limit):
    head = "\t".join(TSV_HEAD)
    by_dir = defaultdict(list)
    for r in recs:
        by_dir[str(Path(r["path"]).parent)].append(tsv_row(r))
    chunks, cur, size = [], [], len(head)
    for d in sorted(by_dir, key=str.casefold):
        block = by_dir[d]
        blen = sum(len(x) + 1 for x in block)
        if cur and size + blen > limit:
            chunks.append(cur)
            cur, size = [], len(head)
        cur.extend(block)  # Ordner bleiben zusammen (ausser sie sind riesig)
        size += blen
    if cur:
        chunks.append(cur)
    names = []
    for i, rows in enumerate(chunks, 1):
        name = f"tracks_part{i:02d}.tsv"
        (outdir / name).write_text(head + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
        names.append(name)
    return names


PROMPT = """# Aufgabe: Musikbibliothek prüfen und Verbesserungen vorschlagen

Du bekommst den Tag-Export meines Musikordners:
- `01_zusammenfassung.md` - Zusammenfassung und Statistik
- `02_auffaelligkeiten.md` - automatisch gefundene Auffälligkeiten
- `03_duplikate.md` - Audio-Fingerprint-Duplikate (falls vorhanden)
- `tracks_part*.tsv` - eine Zeile pro Datei (tab-getrennt): {cols}
  (`path` ist relativ zum Musikordner, `sek` = Dauer in Sekunden, `cover` = j/n;
  mehrere Werte in einem Tag sind mit " | " getrennt)

Meine Sortier-Software (Sortiton) arbeitet mit Regeln in einer `my_rules.ini`.

## Was ich von dir möchte
1. **Überblick:** Was ist der Zustand der Bibliothek? Was sind die größten Baustellen?
2. **Regeln für `my_rules.ini`** - für Wiederkehrendes (Schreibweisen von Künstlern,
   Genres vereinheitlichen), exakt in diesem Format:
   ```
   [Artist]        ; Falsch = Richtig
   [Artist Regex]  ; Regulärer Ausdruck = Ersatz
   [Genre]         ; Falsch = Richtig   (leer rechts = Genre löschen)
   [Protected]     ; Namen, die nie getrennt/geändert werden (z. B. "Simon & Garfunkel")
   ```
3. **Einzelkorrekturen** für Dateien, die eine Regel nicht abdeckt, als CSV mit Semikolon:
   `path;feld;alt;neu` (feld = artist, albumartist, album, title, track, disc, year, genre)
4. **Ordner-/Dateinamen:** Wo passt die Ordnerstruktur nicht zu den Tags?
   Vorschläge für ein einheitliches Schema.
5. **Duplikate, Sampler, fehlende Cover/Tags und Tracknummern** kurz priorisiert auflisten.

## Regeln für dich
- Erfinde nichts. Jahre, Alben o. Ä. nur vorschlagen, wenn sie aus den Daten
  eindeutig hervorgehen; sonst als Rückfrage markieren.
- Groß-/Kleinschreibung NICHT anfassen: GROSSBUCHSTABEN, nur-klein und andere Stilisierungen
  (z. B. "Ado - KIRA", "amnesia", "deadmau5") sind meist die Originalschreibweise und korrekt.
  Melde nur Fälle, in denen DASSELBE Album/derselbe Künstler in mehreren Schreibweisen vorkommt.
- Sonderzeichen in Dateinamen wurden vom Dateisystem oft durch `_` ersetzt (`: / ? * |`) -
  das ist kein Fehler. `(2)` am Dateinamen deutet auf eine doppelte Datei hin.
- Genres können Länder, Sprachen, Fandoms, Plattform-Kategorien (z. B. "Music",
  "Film & Animation") oder Spaß-Tags enthalten. Schlage eine kleine, sinnvolle Liste echter
  Genres vor und frage mich bei Grenzfällen (z. B. "Hololive", "Japanese"), ob ich sie
  behalten will. Falsch geschriebene Kürzel (EDM, R&B, IDM, UK ...) darfst du korrigieren.
- Audio-Fingerprint-Gruppen sind nach Ähnlichkeit gestuft. Gleiche Aufnahme (Kopie) und verwandte Version (Instrumental,
  Cover, andere Sprache, Edit, Kurzfassung) sind NICHT dasselbe. Versionen behalten, echte
  Kopien zusammenfassen und dabei die bessere Datei (höhere Bitrate, vollständige Dauer,
  richtiger Ordner) nennen.
- Weicht ein Ordnername von den Tags ab, sag mir, ob eher der Ordner oder der Tag
  angepasst werden sollte.
- Tags, die zum Original passen, sind korrekt - "Auffälligkeiten" der Zusammenfassung sind nur
  Hinweise, keine Fehler. Prüfe selbst, ob wirklich etwas falsch ist.
- Bei Unsicherheit lieber fragen als raten.
- Arbeite die Teile der Reihe nach ab; gib pro Teil nur die *Änderungen* aus.
- Am Ende: eine zusammengeführte, deduplizierte `my_rules.ini`.

Es gibt {n} Datei(en) in {parts} Teil(en). Fang mit der Zusammenfassung an.
"""


def main():
    global QUIET
    ap = argparse.ArgumentParser(description="Liest Tags/Infos eines Musikordners (nur lesend) für LLM-Auswertung.")
    ap.add_argument("ordner", help="Musikordner")
    ap.add_argument("-o", "--ausgabe", help="Ausgabeordner (Standard: ./musik_export_<datum>)")
    ap.add_argument("--chunk-zeichen", type=int, default=60000,
                    help="max. Zeichen pro TSV-Teil (Standard 60000, ca. 20k Tokens)")
    ap.add_argument("--beispiele", type=int, default=40,
                    help="max. Beispiele pro Auffälligkeit (Standard 40)")
    ap.add_argument("--jsonl", action="store_true",
                    help="zusätzlich alle_tags.jsonl mit erkannten Kern- und Zusatz-Tags schreiben")
    ap.add_argument("--gross-klein", action="store_true",
                    help="GROSSBUCHSTABEN/nur-klein als Auffälligkeit melden (Standard: aus, "
                         "da oft Stilmittel)")
    ap.add_argument("--fingerprint", action="store_true",
                    help="Duplikate per Audio-Fingerprint (Chromaprint/fpcalc) suchen - langsamer")
    ap.add_argument("--fp-sekunden", type=int, default=120,
                    help="Länge pro Datei, die fingerprinted wird (Standard 120)")
    ap.add_argument("--fp-schwelle", type=float, default=0.70,
                    help="Mindest-Ähnlichkeit 0..1 für Fingerprint-Treffer (Standard 0.70; Ausgabe wird in Stufen sortiert)")
    ap.add_argument("--threads", type=int, default=min(8, os.cpu_count() or 4))
    ap.add_argument("--quiet", action="store_true",
                    help="Fortschrittsausgaben unterdrücken")
    args = ap.parse_args()
    QUIET = args.quiet

    if not 0.0 <= args.fp_schwelle <= 1.0:
        ap.error("--fp-schwelle muss zwischen 0.0 und 1.0 liegen")

    if mutagen is None and not _HAS_FFPROBE:
        sys.exit("Weder 'mutagen' (Python-Modul) noch 'ffprobe' gefunden.\n"
                 "Bitte mutagen installieren ('pip install mutagen') oder ffmpeg/ffprobe installieren.")

    if args.fingerprint and not shutil.which("fpcalc"):
        sys.exit("fpcalc nicht gefunden. Installieren: Debian/Ubuntu: sudo apt install "
                 "libchromaprint-tools | Fedora: sudo dnf install chromaprint-tools | "
                 "Arch: sudo pacman -S chromaprint")
    root = Path(args.ordner).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"Ordner nicht gefunden: {root}")
    outdir = Path(args.ausgabe).expanduser() if args.ausgabe else Path(f"musik_export_{datetime.now():%Y%m%d_%H%M%S}")
    outdir.mkdir(parents=True, exist_ok=True)

    if not QUIET:
        print(f"Lese {root} ({'mutagen' if mutagen else 'ffprobe - langsamer'}) ...", file=sys.stderr)
    recs = scan(root, args.threads)
    if not recs:
        sys.exit("Keine Audiodateien gefunden.")

    summary = build_summary(recs, root, args.beispiele, args.gross_klein)
    if args.fingerprint:
        if not QUIET:
            print("Berechne Audio-Fingerprints ...", file=sys.stderr)
        fps = compute_fingerprints(recs, root, args.fp_sekunden, args.threads, outdir)
        groups, _np = fingerprint_groups(recs, fps, args.fp_schwelle)
        summary += "\n" + "\n".join(fp_section(recs, groups, len(fps), len(recs),
                                              args.fp_schwelle, args.beispiele))
    summary_names = write_summary_split(summary, outdir)
    parts = write_chunks(recs, outdir, args.chunk_zeichen)
    (outdir / "00_prompt.md").write_text(
        PROMPT.format(cols=", ".join(f"`{c}`" for c in TSV_HEAD), n=len(recs), parts=len(parts)),
        encoding="utf-8")
    if args.jsonl:
        with open(outdir / "alle_tags.jsonl", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    if not QUIET:
        print(f"\nFertig: {len(recs)} Dateien -> {outdir.resolve()}", file=sys.stderr)
        print(f"  00_prompt.md, {', '.join(summary_names)}, {len(parts)} x tracks_part*.tsv",
              file=sys.stderr)


if __name__ == "__main__":
    main()
