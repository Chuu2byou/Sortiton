"""Analysis of the read records: variants, folders vs. tags, style, tracks."""

from __future__ import annotations

import functools
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from ... import i18n
from .reader import SEP

_DROP = re.compile(r"[\s\-\u2010-\u2015_'’‘`\"“”]+")
_LOOSE = re.compile(r"[\W_]+")
THRESH = {"mp3": 128, "oggopus": 80, "opus": 80}
TRUNC_MIN = 25
MAX_FILENAME_BYTES = 240
TRACK_DENSE_MIN = 3
TRACK_DENSE_RATIO = 0.60
TRACK_MAX_EXPECTED = 200

LOSSY = {"mp3", "oggvorbis", "oggopus", "mp4", "aac", "asf", "musepackfile",
         "opus", "vorbis", "wmav2"}
JUNK_RE = re.compile(
    r"(?i)(official\s*(music\s*)?(video|audio)|lyric\s*video|www\.|\.com\b|"
    r"\bhq\b|\bhd\b(?!\s*-\s*\S)|320\s*kbps|free\s*download)")
VA_NAMES = {"variousartists", "various", "va"}


@functools.lru_cache(maxsize=8192)
def norm(s):
    """Comparison key for tag variants: without case, Latin accents, spaces, hyphens (all kinds), underscore, quotes."""
    s = unicodedata.normalize("NFKD", s.casefold())
    s = "".join(
        c for c in s
        if not (unicodedata.category(c).startswith("M") and ord(c) not in (0x3099, 0x309A))
    )
    return _DROP.sub("", s) or s


def loose(s):
    """Very rough (letters/digits only) for file/folder names in which the file system replaced characters like : / ?"""
    return _LOOSE.sub("", unicodedata.normalize("NFKC", s.casefold()))


def track_info(s):
    """Read the track number and optionally the total from e.g. 03/12 or 3 of 12."""
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
    """Check track numbers per album, conservatively."""
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

                explicit_total_ok = (
                    total_hint is not None and
                    total_hint >= max_n and
                    total_hint <= max(TRACK_MAX_EXPECTED, len(drs) * 3) and
                    len(drs) >= max(2, int((total_hint * TRACK_DENSE_RATIO) + 0.999))
                )

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
                    sparse_groups.add((d, _album))

            album_raw = next((r["album"] for r in ars if r["album"]), "")

            if missing:
                if len(missing) == len(ars):
                    all_missing += 1
                incomplete_groups.append({
                    "dir": d, "album": album_raw,
                    "missing": len(missing), "total": len(ars),
                    "all": len(missing) == len(ars),
                })

            if gaps:
                gap_groups.append({"dir": d, "album": album_raw, "gaps": list(gaps)})

    return {
        "checked": checked,
        "missing_multi": missing_multi,
        "albums_with_missing": albums_with_missing,
        "all_missing": all_missing,
        "incomplete": incomplete_groups,
        "gaps": gap_groups,
        "sparse": len(sparse_groups),
    }


def lst(items, limit, lang):
    """Format a list of entries for Markdown, cut off after `limit` lines."""
    items = list(items)
    if not items:
        return [i18n.t_in(lang, "export.report.list.empty")]
    out = [x if x.startswith("- ") else f"- {x}" for x in items[:limit]]
    if len(items) > limit:
        out.append(i18n.t_in(lang, "export.report.list.more", count=len(items) - limit))
    return out


def date_fmt(s):
    """Classify the date/year format of a year tag; returns a stable code."""
    s = (s or "").strip()
    if not s:
        return "empty"
    if re.fullmatch(r"\d{4}", s):
        return "year"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return "ymd"
    if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", s):
        return "ymd_dot"
    if re.fullmatch(r"\d{4}-\d{2}", s):
        return "ym"
    if re.fullmatch(r"\d{4}/\d{2}/\d{2}", s):
        return "slash_ymd"
    if re.fullmatch(r"\d{4}/\d{2}", s):
        return "slash_ym"
    if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", s):
        return "dmy"
    if re.match(r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}", s):
        return "iso"
    if re.fullmatch(r"\d{4}\s*[-/]\s*\d{4}", s):
        return "range"
    return "other"


def variants(recs, field, split=False, by_artist=False):
    """Find spelling variants (case, accents, hyphens etc.) of the same tag."""
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
    """Compare folder names with artist and album tags."""
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
            if re.fullmatch(r"(?:cd|disc|disk)[\s._-]*\d*", album_folder,
                            re.IGNORECASE) and len(parts) >= 4:
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
    """Find style and formatting problems in the tags of one file."""
    issues = []
    for field in ("title", "artist", "album"):
        val = r.get(field) or ""
        m = JUNK_RE.search(val)
        if m:
            issues.append(("junk", field, m.group(0)))
        if "  " in val:
            issues.append(("double_space", field))

    title = r.get("title") or ""
    if re.match(r"^\d{1,3}\s*[-.]\s*\S", title):
        issues.append(("track_in_title",))

    if title and "_" in title and " " not in title and len(title) > 3:
        issues.append(("underscores",))

    if check_case:
        for field in ("artist", "album", "title"):
            val = r.get(field) or ""
            chars = [c for c in val if c.isalpha()]
            if len(chars) >= 4:
                if all(c.isupper() for c in chars):
                    issues.append(("all_caps", field))
                elif all(c.islower() for c in chars):
                    issues.append(("all_lower", field))

    return issues
