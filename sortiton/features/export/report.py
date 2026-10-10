"""Report text: summary, splitting, the TSV chunks and the LLM prompt.

Everything here produces user-visible Markdown text. Phase 1 keeps that text
German and hard-coded (marked ``# TODO(phase 2): i18n``); only the file names and
the TSV columns are the stable contracts.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .analysis import (LOSSY, MAX_FILENAME_BYTES, THRESH, TRUNC_MIN, VA_NAMES,
                       date_fmt, folder_vs_tags, lst, loose, norm, style_issues,
                       track_analysis, track_num, variants)
from .reader import CORE, SEP


def _summary_formats_and_tags(ok, recs, n_ok, max_ex):
    # TODO(phase 2): i18n
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

    # Percentages relative to readable files; disc is explained separately.
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
    # TODO(phase 2): i18n
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
    # TODO(phase 2): i18n
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
        if len(name.encode("utf-8")) >= MAX_FILENAME_BYTES:  # truncated by the file system
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
        if d != ".":  # loose files in the root folder belong to no album
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
            if t is not None:  # track number present (count track 0 too)
                disc = track_num(r["disc"])
                disc = 1 if disc is None else disc
                seen[(norm(r["album"]), disc, t)] += 1
        twice = sorted({f"CD{k[1]}#{k[2]}" for k, c in seen.items() if c > 1})
        if twice:
            dbl.append(f"`{d}`: {twice[:10]}")
        # Sampler detection kicks in with changing artists and no uniform album
        # artist, or when the album artist is explicitly "Various Artists".
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


def build_summary(recs: list[dict[str, Any]], root: Path, max_ex: int,
                  check_case: bool = False) -> str:
    # TODO(phase 2): i18n
    n = len(recs)
    ok = [r for r in recs if not r["error"]]
    n_ok = max(len(ok), 1)  # avoid division by zero for pure read errors
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


def write_summary_split(summary: str, outdir: Path) -> list[str]:
    # TODO(phase 2): i18n
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
# Output (TSV chunks and the prompt)
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
        cur.extend(block)  # folders stay together (unless they are huge)
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
