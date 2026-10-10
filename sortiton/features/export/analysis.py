"""Analysis of the read records: variants, folders vs. tags, style, tracks.

Pure text work on the records that :mod:`sortiton.features.export.reader`
produced - no file access, no output.
"""

from __future__ import annotations

import functools
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from .reader import SEP

_DROP = re.compile(r"[\s\-\u2010-\u2015_'’‘`\"“”]+")
_LOOSE = re.compile(r"[\W_]+")
THRESH = {"mp3": 128, "oggopus": 80, "opus": 80}  # kbps, otherwise 96
TRUNC_MIN = 25  # minimum length for detecting truncated folder names
MAX_FILENAME_BYTES = 240  # length limit for file names (file system truncation)
TRACK_DENSE_MIN = 3  # minimum number of tracks for dense sequences
TRACK_DENSE_RATIO = 0.60  # minimum share of present tracks for gap detection
TRACK_MAX_EXPECTED = 200  # upper bound for a plausible album total

LOSSY = {"mp3", "oggvorbis", "oggopus", "mp4", "aac", "asf", "musepackfile",
         "opus", "vorbis", "wmav2"}
JUNK_RE = re.compile(
    r"(?i)(official\s*(music\s*)?(video|audio)|lyric\s*video|www\.|\.com\b|"
    r"\bhq\b|\bhd\b(?!\s*-\s*\S)|320\s*kbps|free\s*download)")
VA_NAMES = {"variousartists", "various", "va"}  # for sampler detection


@functools.lru_cache(maxsize=8192)
def norm(s):
    """Comparison key for tag variants: without case, Latin accents, spaces,
    hyphens (all kinds), underscore, quotes. Kana dakuten stay; pure symbol
    titles do not collide."""
    s = unicodedata.normalize("NFKD", s.casefold())
    # Remove accents/diacritics, but keep kana dakuten (U+3099, U+309A).
    s = "".join(
        c for c in s
        if not (unicodedata.category(c).startswith("M") and ord(c) not in (0x3099, 0x309A))
    )
    return _DROP.sub("", s) or s


def loose(s):
    """Very rough (letters/digits only) for file/folder names in which the file
    system replaced characters like : / ? * | with _."""
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
    """Check track numbers per album, conservatively.

    Missing tags are handled apart from real number gaps. Number gaps are only
    reported when there is enough evidence for a complete track sequence: an
    explicit total in the tag or a dense sequence starting at 1.
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

                # Strong evidence: an explicit /total value in the track tag.
                explicit_total_ok = (
                    total_hint is not None and
                    total_hint >= max_n and
                    total_hint <= max(TRACK_MAX_EXPECTED, len(drs) * 3) and
                    len(drs) >= max(2, int((total_hint * TRACK_DENSE_RATIO) + 0.999))
                )

                # Without a total only analyse dense sequences from 1. This way
                # partially present albums are not misread as dozens of "missing"
                # tracks.
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
                    # Sparse number sequence: interesting, but no reliable claim
                    # about which tracks actually are missing.
                    sparse_groups.add((d, _album))

            label = f"`{d}`"
            album_display = next((r["album"] for r in ars if r["album"]), "(ohne Album)")

            # TODO(phase 2): i18n
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
    """Format a list of entries for Markdown, cut off after `limit` lines."""
    items = list(items)
    if not items:
        return ["- (keine)"]  # TODO(phase 2): i18n
    out = [x if x.startswith("- ") else f"- {x}" for x in items[:limit]]
    if len(items) > limit:
        out.append(f"- ... ({len(items) - limit} weitere)")
    return out


def date_fmt(s):
    """Detect the date/year format of a year tag."""
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
    """Find style and formatting problems in the tags of one file."""
    issues = []
    # TODO(phase 2): i18n
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
