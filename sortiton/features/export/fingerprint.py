"""Audio fingerprints (optional, ``--fingerprint``): duplicates independent of tags.

``fpcalc`` (Chromaprint) builds a raw fingerprint; an inverted index keeps the
comparison cheap, and the cache keyed by path+size+mtime makes a second run
fast.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ... import config, i18n, output
from .analysis import lst, norm

_popcount = (lambda x: x.bit_count()) if hasattr(int, "bit_count") else (lambda x: bin(x).count("1"))
FP_MAX_POSTINGS = 50   # sub-fingerprints that appear in more files are noise
FP_MIN_VOTES = 8       # this many equal sub-fingerprints at the same offset = candidate
FP_MIN_OVERLAP_RATIO = 0.5  # minimum overlap share relative to the shorter fingerprint
FP_MIN_OVERLAP_FRAMES = 20  # minimum number of sub-fingerprints in the overlap window
DURATION_TOLERANCE_SECS = 3.0  # fixed tolerance in seconds for equal play time
DURATION_TOLERANCE_RATIO = 0.02  # relative tolerance (2%) for play time
# Bit packing in the inverted index: (fid << FP_POS_BITS) | pos
FP_POS_BITS = 20          # bits for the position (max 2^20 = 1 048 576 sub-FPs per file)
FP_POS_MASK = (1 << FP_POS_BITS) - 1  # 0xFFFFF


def run_fpcalc(path, secs) -> tuple[Any, str]:
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


def _legacy_fp_cache_path(key: str) -> Path:
    """Cache file the old standalone script used (read once, for migration)."""
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "musik_export"
    return base / f"fp_{key}.json"


def fp_cache_path(root: Path) -> Path:
    """Fingerprint cache for ``root`` under ``SORTITON_CACHE_DIR``.

    The first time it is missing, the cache of the old standalone script is
    copied over once - otherwise every user would recompute all fingerprints
    (hours for a large library). It is a copy, never a move or a delete, and the
    cache format stays the same.
    """
    key = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
    base = config.CACHE_DIR / "fingerprints"
    base.mkdir(parents=True, exist_ok=True)
    target = base / f"fp_{key}.json"
    if not target.exists():
        legacy = _legacy_fp_cache_path(key)
        if legacy.is_file():
            try:
                shutil.copy2(legacy, target)
            except OSError:
                pass
    return target


def compute_fingerprints(recs, root: Path, secs: int,
                         workers: int, outdir: Path) -> dict[int, list[int]]:
    """Fingerprints with a cache (path+size+mtime) so repeats stay fast."""
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
    output.message(i18n.t("export.fp.cache", cached=len(fps), todo=len(todo)))

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
            output.progress(n, len(todo), i18n.t("export.fp.progress"))
    if todo or cache_changed:
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
        output.message(i18n.t("export.fp.failed", count=failed))
    return fps


def _similarity(a, b, off):
    """Similarity 0..1 of a[i] and b[i+off] over the overlap range."""
    lo, hi = max(0, -off), min(len(a), len(b) - off)
    n = hi - lo
    if n < FP_MIN_OVERLAP_RATIO * min(len(a), len(b)) or n < FP_MIN_OVERLAP_FRAMES:
        return 0.0
    bits = sum(_popcount(a[i] ^ b[i + off]) for i in range(lo, hi))
    return 1.0 - bits / (32.0 * n)


def fingerprint_groups(recs, fps: dict[int, list[int]],
                       threshold: float) -> tuple[list[tuple[list[int], float]], int]:
    """Inverted-index approach: only pairs with many equal sub-fingerprints at the
    same offset are compared closely (no n*n comparison)."""
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
    # Pairs -> groups (Union-Find)
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
    # Only rate high audio similarity + matching metadata/length as a real
    # duplicate. High similarity alone is not enough (cover versions!).
    if sim >= 0.95 and same_identity and duration_close and same_album:
        return "sehr_wahrscheinlich"
    if sim >= 0.90 and same_identity and (duration_close or marker):
        return "wahrscheinlich"
    if sim >= 0.90 and marker and duration_close:
        return "wahrscheinlich"
    if sim >= 0.80:
        return "pruefen"
    return "aehnlich"


def _quality_hint(rs, lang):
    # No automatic deletion: merely a hint which file is technically the
    # larger/higher bitrate variant of the same recording.
    if len(rs) < 2:
        return ""
    bitrates = [(r["kbps"], r["path"]) for r in rs if r["kbps"]]
    if not bitrates:
        return ""
    max_k = max(k for k, _ in bitrates)
    min_k = min(k for k, _ in bitrates)
    if max_k > min_k:
        winner = next(path for k, path in bitrates if k == max_k)
        return i18n.t_in(lang, "export.report.fp.quality_hint", path=winner, kbps=max_k)
    return ""


def fp_section(recs, groups, n_fp, n_total, threshold, max_ex, lang):
    """Order fingerprint groups by several kinds of evidence, not just the percent."""
    rows = []
    for members, sim in groups:
        rs = [recs[i] for i in members]
        same_identity = _same_identity(rs)
        same_album = _same_album(rs)
        durs = [r["dur"] for r in rs]
        duration_close = _duration_close(durs)
        marker = any(_duplicate_marker(r["path"]) for r in rs)
        classification = _dupe_class(sim, same_identity, duration_close, marker, same_album)

        flags = [
            i18n.t_in(lang, "export.report.fp.flag.same_identity" if same_identity
                      else "export.report.fp.flag.diff_identity"),
            i18n.t_in(lang, "export.report.fp.flag.same_duration" if duration_close
                      else "export.report.fp.flag.diff_duration"),
        ]
        if same_album:
            flags.append(i18n.t_in(lang, "export.report.fp.flag.same_album"))
        if marker:
            flags.append(i18n.t_in(lang, "export.report.fp.flag.marker"))
        hint = (_quality_hint(rs, lang)
                if classification in {"sehr_wahrscheinlich", "wahrscheinlich"} else "")
        items = " ; ".join(
            f"`{r['path']}` ({r['kbps']}k, {round(r['dur'])}s, {r['size'] / 1e6:.1f}MB, "
            f'"{r["artist"]} - {r["title"]}")' for r in rs)
        rows.append((sim, classification, f"[{sim:.0%}, {', '.join(flags)}{hint}] {items}"))

    rows.sort(key=lambda x: (-x[0], x[1]))
    buckets = ("sehr_wahrscheinlich", "wahrscheinlich", "pruefen", "aehnlich")

    lines = [i18n.t_in(lang, "export.report.fp.title", groups=len(groups),
                       n_fp=n_fp, n_total=n_total, threshold=threshold), "",
             i18n.t_in(lang, "export.report.fp.note"), ""]

    for key in buckets:
        bucket = [row for row in rows if row[1] == key]
        lines += [i18n.t_in(lang, "export.report.fp.bucket.title",
                            title=i18n.t_in(lang, f"export.report.fp.bucket.{key}"),
                            count=len(bucket)), ""]
        lines += lst([row[2] for row in bucket], max_ex, lang) + [""]
    return lines
