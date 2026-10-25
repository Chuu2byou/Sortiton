"""Build the export report as structured sections and write the report files."""

from __future__ import annotations

import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from ... import i18n
from ...tags import UNREADABLE
from .analysis import (LOSSY, MAX_FILENAME_BYTES, THRESH, TRUNC_MIN, VA_NAMES,
                       date_fmt, folder_vs_tags, lst, loose, norm, style_issues,
                       track_analysis, track_num, variants)
from .reader import CORE, SEP


@dataclass
class Section:
    """One rendered block of the report and the file it belongs to."""

    target: Literal["summary", "anomalies", "duplicates"]
    lines: list[str]


@dataclass(frozen=True)
class ReportOptions:
    """Everything the report needs besides the records and the language."""

    max_examples: int = 40
    check_case: bool = False


def _date_text(code: str, lang: str) -> str:
    """Translate a :func:`date_fmt` code for the year-format table."""
    return i18n.t_in(lang, f"export.report.date.{code}")


def _field_text(field: str, lang: str) -> str:
    """Translate a tag-field name (title, artist, album, albumartist, genre)."""
    return i18n.t_in(lang, f"export.report.field.{field}")


def _style_text(issue: tuple, lang: str) -> str:
    """Render one :func:`style_issues` code (a tuple of code and parameters)."""
    kind = issue[0]
    if kind in ("junk", "double_space"):
        field = _field_text(issue[1], lang)
        if kind == "junk":
            return i18n.t_in(lang, "export.report.style.junk", field=field, match=issue[2])
        return i18n.t_in(lang, "export.report.style.double_space", field=field)
    if kind in ("all_caps", "all_lower"):
        return i18n.t_in(lang, f"export.report.style.{kind}",
                         field=_field_text(issue[1], lang))
    return i18n.t_in(lang, f"export.report.style.{kind}")


def _error_text(error: str, lang: str) -> str:
    """Ein Lesefehler aus dem Reader: der Sentinel wird übersetzt."""
    return i18n.t_in(lang, "export.report.unreadable") if error == UNREADABLE else error


def _error_lines(recs, opts, lang):
    """The read-error block (shared by the normal and the 'nothing readable' case)."""
    errs = [f"`{r['path']}`: {_error_text(r['error'], lang)}"
            for r in recs if r["error"]]
    if not errs:
        return []
    return [i18n.t_in(lang, "export.report.errors.title", count=len(errs)), ""] \
        + lst(errs, opts.max_examples, lang) + [""]


def _summary_overview(recs, root, lang):
    n = len(recs)
    errors = sum(1 for r in recs if r["error"])
    return [
        i18n.t_in(lang, "export.report.summary.title"), "",
        i18n.t_in(lang, "export.report.summary.folder", root=root),
        i18n.t_in(lang, "export.report.summary.created",
                  date=f"{datetime.now():%Y-%m-%d %H:%M}"),
        i18n.t_in(lang, "export.report.summary.files", n=n, errors=errors),
        i18n.t_in(lang, "export.report.summary.size",
                  gb=sum(r["size"] for r in recs) / 1e9),
        i18n.t_in(lang, "export.report.summary.duration",
                  hours=sum(r["dur"] for r in recs) / 3600),
        i18n.t_in(lang, "export.report.summary.loose",
                  count=sum(1 for r in recs if "/" not in r["path"])),
        "",
    ]


def _summary_formats_and_tags(ok, recs, n_ok, opts, lang):
    max_ex = opts.max_examples
    lines = [i18n.t_in(lang, "export.report.formats.title"), ""]
    for k, c in Counter(r["ext"] for r in recs).most_common():
        lines.append(f"- {k}: {c}")
    by = defaultdict(list)
    for r in ok:
        if r["kbps"] and r["codec"].lower() in LOSSY:
            by[r["codec"]].append(r["kbps"])
    for c, v in sorted(by.items()):
        t = THRESH.get(c.lower(), 96)
        lines.append(i18n.t_in(lang, "export.report.formats.bitrate", codec=c,
                               median=statistics.median(v), threshold=t,
                               below=sum(1 for x in v if x < t), total=len(v)))
    lines.append(i18n.t_in(lang, "export.report.formats.no_cover",
                           count=sum(1 for r in ok if not r["cover"])))
    lines.append("")

    lines += [i18n.t_in(lang, "export.report.tags.title"), ""]
    for c in CORE:
        if c == "disc":
            continue
        n_missing = sum(1 for r in ok if not r[c])
        lines.append(i18n.t_in(lang, "export.report.tags.entry", field=c,
                               count=n_missing, percent=100 * n_missing / n_ok))
    n_disc = sum(1 for r in ok if not r["disc"])
    lines.append(i18n.t_in(lang, "export.report.tags.disc", count=n_disc,
                           percent=100 * n_disc / n_ok))
    lines.append("")

    lines += [i18n.t_in(lang, "export.report.folders.title"), ""]
    top = Counter(r["path"].split("/")[0] if "/" in r["path"]
                  else i18n.t_in(lang, "export.report.folders.root") for r in recs)
    lines += lst([f"{k}: {v}" for k, v in top.most_common()], max_ex, lang) + [""]

    lines += [i18n.t_in(lang, "export.report.genres.title"), ""]
    g = Counter(v for r in ok for v in (r["genre"].split(SEP) if r["genre"] else []))
    lines += lst([f"{k}: {v}" for k, v in g.most_common()], max_ex, lang) + [""]

    lines += [i18n.t_in(lang, "export.report.dates.title"), ""]
    fm = defaultdict(list)
    for r in ok:
        if r["year"]:
            fm[date_fmt(r["year"])].append(r["path"])
    max_fm_len = max((len(x) for x in fm.values()), default=0)
    for k, v in sorted(fm.items(), key=lambda kv: -len(kv[1])):
        ex = "" if len(v) == max_fm_len else i18n.t_in(
            lang, "export.report.dates.example", path=v[0])
        lines.append(i18n.t_in(lang, "export.report.dates.entry",
                               format=_date_text(k, lang), count=len(v), example=ex))
    lines.append("")

    lines += [i18n.t_in(lang, "export.report.decades.title"), ""]
    dec = Counter(r["year"][:3] for r in ok if re.match(r"\d{4}", r["year"] or ""))
    lines += [i18n.t_in(lang, "export.report.decades.entry", prefix=k, count=v)
              for k, v in sorted(dec.items())] + [""]

    lines += [i18n.t_in(lang, "export.report.artists.title"), ""]
    a = Counter(r["artist"] for r in ok if r["artist"])
    lines += [f"- {k}: {v}" for k, v in a.most_common(max_ex)] + [""]
    return lines


def _incomplete_line(entry, lang):
    album = entry["album"] or i18n.t_in(lang, "export.report.tracks.no_album")
    label = f"`{entry['dir']}`"
    if entry["all"]:
        return i18n.t_in(lang, "export.report.tracks.incomplete.all",
                         label=label, album=album, total=entry["total"])
    return i18n.t_in(lang, "export.report.tracks.incomplete.some", label=label,
                     album=album, missing=entry["missing"], total=entry["total"])


def _gap_line(entry, lang):
    album = entry["album"] or i18n.t_in(lang, "export.report.tracks.no_album")
    gaps = entry["gaps"]
    shown = ", ".join(f"CD{disc}#{num}" for disc, num in gaps[:12])
    if len(gaps) > 12:
        shown += i18n.t_in(lang, "export.report.tracks.gaps.more", count=len(gaps))
    return i18n.t_in(lang, "export.report.tracks.gaps.entry",
                     label=f"`{entry['dir']}`", album=album, gaps=shown)


def _sorted_lines(entries, render, opts, lang):
    """Render structured entries, sort them like the old text, then cut them off."""
    items = [render(entry, lang) for entry in entries]
    items.sort(key=str.casefold)
    return lst(items, opts.max_examples, lang)


def _summary_track_quality(ok, opts, lang):
    ta = track_analysis(ok)
    lines = [i18n.t_in(lang, "export.report.tracks.title"), "",
             i18n.t_in(lang, "export.report.tracks.checked", count=ta["checked"]),
             i18n.t_in(lang, "export.report.tracks.missing_multi", count=ta["missing_multi"]),
             i18n.t_in(lang, "export.report.tracks.albums_missing",
                       count=ta["albums_with_missing"]),
             i18n.t_in(lang, "export.report.tracks.all_missing", count=ta["all_missing"]),
             i18n.t_in(lang, "export.report.tracks.gap_albums", count=len(ta["gaps"])),
             i18n.t_in(lang, "export.report.tracks.sparse", count=ta["sparse"]), ""]
    lines += [i18n.t_in(lang, "export.report.tracks.incomplete.title",
                        count=len(ta["incomplete"])), "",
              i18n.t_in(lang, "export.report.tracks.incomplete.note"), ""]
    lines += _sorted_lines(ta["incomplete"], _incomplete_line, opts, lang) + [""]
    lines += [i18n.t_in(lang, "export.report.tracks.gaps.title", count=len(ta["gaps"])), "",
              i18n.t_in(lang, "export.report.tracks.gaps.note"), ""]
    lines += _sorted_lines(ta["gaps"], _gap_line, opts, lang) + [""]
    return lines


COVER_NAMES = frozenset({
    "cover.jpg", "cover.jpeg", "cover.png", "cover.webp",
    "folder.jpg", "folder.jpeg", "folder.png", "folder.webp",
    "front.jpg", "front.jpeg", "front.png", "album.jpg", "album.png",
    "albumart.jpg", "albumart.png", "albumartsmall.jpg", "artwork.jpg",
})


def _cover_file(directory: Path) -> str:
    """The first known cover image in ``directory``, or ""."""
    try:
        entries = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
    except OSError:
        return ""
    for entry in entries:
        try:
            if entry.is_file() and entry.name.casefold() in COVER_NAMES:
                return entry.name
        except OSError:
            continue
    return ""


def _folder_label(path: str) -> str:
    """Report a folder relative to the library root; "" means the root itself."""
    folder = str(Path(path).parent)
    return folder if folder != "." else ""


def _cover_lines(ok, root, opts, lang):
    """Report files without an embedded cover, split by folder image presence."""
    unembedded: dict[tuple[str, str], int] = defaultdict(int)
    missing: dict[str, int] = defaultdict(int)
    cache: dict[str, str] = {}
    for record in ok:
        if record.get("cover"):
            continue
        folder = _folder_label(record["path"])
        if folder not in cache:
            cache[folder] = (_cover_file(Path(root) / folder) if folder else
                             _cover_file(Path(root)))
        cover = cache[folder]
        if cover:
            unembedded[(folder, cover)] += 1
        else:
            missing[folder] += 1
    if not unembedded and not missing:
        return []

    total = sum(unembedded.values()) + sum(missing.values())
    lines = [i18n.t_in(lang, "export.report.covers.title", count=total), "",
             i18n.t_in(lang, "export.report.covers.note"), "",
             i18n.t_in(lang, "export.report.covers.unembedded.title",
                       folders=len(unembedded), files=sum(unembedded.values())), ""]
    lines += lst([i18n.t_in(lang, "export.report.covers.unembedded.entry",
                            folder=folder or ".", cover=cover, count=count)
                  for (folder, cover), count in sorted(unembedded.items())],
                 opts.max_examples, lang) + [""]
    lines += [i18n.t_in(lang, "export.report.covers.missing.title",
                        folders=len(missing), files=sum(missing.values())), ""]
    lines += lst([i18n.t_in(lang, "export.report.covers.missing.entry",
                            folder=folder or ".", count=count)
                  for folder, count in sorted(missing.items())],
                 opts.max_examples, lang) + [""]
    return lines


def _anomalies(ok, recs, opts, lang, root=None):
    max_ex = opts.max_examples
    lines = [i18n.t_in(lang, "export.report.anomalies.title"), "",
             i18n.t_in(lang, "export.report.anomalies.note"), ""]
    if root is not None:
        lines += _cover_lines(ok, root, opts, lang)
    for title_key, field, split, ba in (
            ("export.report.variants.artist", "artist", False, False),
            ("export.report.variants.albumartist", "albumartist", False, False),
            ("export.report.variants.album", "album", False, True),
            ("export.report.variants.genre", "genre", True, False)):
        v = variants(ok, field, split, ba)
        lines += [i18n.t_in(lang, "export.report.variants.title",
                            title=i18n.t_in(lang, title_key), count=len(v)), ""]
        lines += lst(v, max_ex, lang) + [""]

    t_mis, a_mis, skipped_paths = folder_vs_tags(ok)
    lines += [i18n.t_in(lang, "export.report.folder_artist.title", count=len(t_mis)), "",
              i18n.t_in(lang, "export.report.folder_artist.note",
                        trunc=TRUNC_MIN, skipped=len(skipped_paths)), ""]
    lines += lst([i18n.t_in(lang, "export.report.folder_tag", folder=f, tag=t, count=c)
                  for (f, t), c in t_mis.most_common()], max_ex, lang) + [""]
    lines += [i18n.t_in(lang, "export.report.folder_album.title", count=len(a_mis)), ""]
    lines += lst([i18n.t_in(lang, "export.report.folder_tag", folder=f, tag=t, count=c)
                  for (f, t), c in a_mis.most_common()], max_ex, lang) + [""]

    st = [(r["path"], style_issues(r, opts.check_case)) for r in ok]
    st = [(p, x) for p, x in st if x]
    lines += [i18n.t_in(lang, "export.report.style.title", count=len(st)), ""]
    lines += lst([f"`{p}`: {', '.join(_style_text(x, lang) for x in issues)}"
                  for p, issues in st], max_ex, lang) + [""]

    mism = []
    for r in ok:
        name = Path(r["path"]).name
        if len(name.encode("utf-8")) >= MAX_FILENAME_BYTES:
            continue
        if r["title"] and loose(r["title"]) not in loose(Path(r["path"]).stem):
            mism.append(i18n.t_in(lang, "export.report.filename.entry",
                                  path=r["path"], title=r["title"]))
    lines += [i18n.t_in(lang, "export.report.filename.title", count=len(mism)), ""]
    lines += lst(mism, max_ex, lang) + [""]

    dup = defaultdict(list)
    for r in ok:
        if r["artist"] and r["title"]:
            dup[(norm(r["artist"]), norm(r["title"]))].append(r)
    dups = [v for v in dup.values() if len(v) > 1]
    lines += [i18n.t_in(lang, "export.report.duplicates.title", count=len(dups)), ""]
    lines += lst([" ; ".join(f"`{r['path']}` ({r['kbps']}k, {round(r['dur'])}s, "
                             f"{r['size'] / 1e6:.1f}MB)" for r in v) for v in dups],
                 max_ex, lang) + [""]

    bydir = defaultdict(list)
    for r in ok:
        d = str(Path(r["path"]).parent)
        if d != ".":
            bydir[d].append(r)
    inc, dbl, comp = [], [], []
    for d, rs in sorted(bydir.items()):
        probs = []
        for f, label_key in (("album", "export.report.field.album"),
                             ("albumartist", "export.report.field.albumartist"),
                             ("genre", "export.report.field.genre")):
            vals = {r[f] for r in rs if r[f]}
            if len(vals) > 1:
                probs.append(f"{i18n.t_in(lang, label_key)}: {sorted(vals)}")
        if probs:
            inc.append(f"`{d}` - " + "; ".join(probs))
        seen = defaultdict(int)
        for r in rs:
            t = track_num(r["track"])
            if t is not None:
                disc = track_num(r["disc"])
                disc = 1 if disc is None else disc
                seen[(norm(r["album"]), disc, t)] += 1
        twice = sorted({f"CD{k[1]}#{k[2]}" for k, c in seen.items() if c > 1})
        if twice:
            dbl.append(f"`{d}`: {twice[:10]}")
        artists = {r["artist"] for r in rs if r["artist"]}
        if len(rs) >= 4 and len(artists) > 3:
            albumartists = {r["albumartist"] for r in rs if r["albumartist"]}
            missing = sum(1 for r in rs if not r["albumartist"])
            if missing:
                comp.append(i18n.t_in(lang, "export.report.sampler.missing_albumartist",
                                      dir=d, artists=len(artists), missing=missing,
                                      total=len(rs)))
            elif albumartists and all(loose(a) in VA_NAMES for a in albumartists):
                comp.append(i18n.t_in(lang, "export.report.sampler.various",
                                      dir=d, artists=len(artists)))
    lines += [i18n.t_in(lang, "export.report.inconsistent.title", count=len(inc)), ""]
    lines += lst(inc, max_ex, lang) + [""]
    lines += [i18n.t_in(lang, "export.report.dup_tracks.title", count=len(dbl)), ""]
    lines += lst(dbl, max_ex, lang) + [""]
    lines += [i18n.t_in(lang, "export.report.samplers.title", count=len(comp)), ""]
    lines += lst(comp, max_ex, lang) + [""]

    lines += _error_lines(recs, opts, lang)
    return lines


def build_report(recs: list[dict[str, Any]], root: Path, opts: ReportOptions,
                 lang: str) -> list[Section]:
    """Build the summary and anomaly sections."""
    ok = [r for r in recs if not r["error"]]
    n_ok = max(len(ok), 1)
    sections = [Section("summary", _summary_overview(recs, root, lang))]
    if not ok:
        sections.append(Section("summary",
                                i18n.t_in(lang, "export.report.summary.warning").splitlines()
                                + [""]))
        sections.append(Section("summary", _error_lines(recs, opts, lang)))
        return sections
    sections.append(Section("summary",
                            _summary_formats_and_tags(ok, recs, n_ok, opts, lang)))
    sections.append(Section("summary", _summary_track_quality(ok, opts, lang)))
    sections.append(Section("anomalies", _anomalies(ok, recs, opts, lang, root)))
    return sections


def write_report(sections: list[Section],
                 write: Callable[[str, str], str]) -> list[str]:
    """Write the report sections into the ``01_*``, ``02_*`` and ``03_*`` files.

    ``write`` legt eine Datei an und liefert ihren (eventuell abweichenden)
    Namen zurück. Der Export entscheidet dort, ob ein vorhandener Name uns
    gehört oder einer fremden Datei ausgewichen werden muss.
    """
    contents: dict[str, list[str]] = {"summary": [], "anomalies": [], "duplicates": []}
    for section in sections:
        if section.lines:
            contents[section.target].append("\n".join(section.lines).strip())
    names = []
    for name, target in (("01_zusammenfassung.md", "summary"),
                         ("02_auffaelligkeiten.md", "anomalies")):
        names.append(write(name, "\n\n".join(contents[target]) + "\n"))
    if contents["duplicates"]:
        names.append(write("03_duplikate.md",
                           "\n\n".join(contents["duplicates"]) + "\n"))
    return names


TSV_HEAD = ["path", "artist", "albumartist", "album", "title", "track", "disc",
            "year", "genre", "sek", "kbps", "codec", "cover"]


def clean(v: object) -> str:
    return "".join(" " if unicodedata.category(char) in {"Cc", "Zl", "Zp"} else char
                   for char in str(v))


def tsv_row(r):
    vals = [r["path"], r["artist"], r["albumartist"], r["album"], r["title"], r["track"],
            r["disc"], r["year"], r["genre"], round(r["dur"]), r["kbps"], r["codec"],
            "j" if r["cover"] else "n"]
    return "\t".join(clean(v) for v in vals)


def write_chunks(recs, write: Callable[[str, str], str], limit: int) -> list[str]:
    """Write one TSV per chunk; ``write`` legt die Datei an und liefert ihren Namen."""
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
        cur.extend(block)
        size += blen
    if cur:
        chunks.append(cur)
    names = []
    for i, rows in enumerate(chunks, 1):
        name = f"tracks_part{i:02d}.tsv"
        names.append(write(name, head + "\n" + "\n".join(rows) + "\n"))
    return names


def prompt_text(lang: str, n_files: int, n_parts: int) -> str:
    """The LLM task text (``export.prompt``) with the placeholders filled in."""
    cols = ", ".join(f"`{c}`" for c in TSV_HEAD)
    return i18n.t_in(lang, "export.prompt", cols=cols, n=n_files, parts=n_parts)
