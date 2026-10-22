"""Shared helpers for the pytest suite.

``conftest.py`` sets the ``SORTITON_*`` environment variables before this module
imports :mod:`sortiton`; the split test modules import the helpers they use from
here. ``check()`` keeps the wording of the old smoke runner but raises, so a
failing condition fails the test instead of being collected at the end.

Re-Export-Hub der Testsuite: die Testmodule holen ihre Importe hier, damit jede
Datei nur eine Quelle hat. Die meisten Namen werden deshalb in dieser Datei
selbst nicht benutzt - pylint soll sie hier nicht als tot melden.
"""

# pylint: disable=unused-import

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest  # noqa: F401  (some tests skip explicitly)

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

import sortiton as ms  # noqa: E402
from sortiton import config, files, i18n, journal, output, rules, settings  # noqa: E402
from sortiton.tags import probe_tags, write_tags  # noqa: E402
from sortiton.tasks import cmd_restore, cmd_scan  # noqa: E402

_SKIPPED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    """Assert one named condition; the name is what a failure reports."""
    if not ok:
        raise AssertionError(f"{name}: {detail}" if detail else name)


def skip(name: str, detail: str = "") -> None:
    """Record an optional check that cannot run inside an otherwise useful test.

    A terminal skip uses ``pytest.skip`` directly, so pytest reports it.
    """
    _SKIPPED.append(name)
    print(f"  [skip] {name}{(' - ' + detail) if detail else ''}")


KEY_RE = re.compile(r"""i18n\.t\(\s*["']([A-Za-z0-9_.-]+)["']""")

_INFO_TO_RECORD = {"artist": "artist", "album_artist": "albumartist", "album": "album",
                   "title": "title", "genre": "genre", "track": "track",
                   "disc": "disc", "year": "year"}

FAKE_YTDLP = BASE / "tests" / "fixtures" / "fake_ytdlp" / "yt-dlp"

class _FakeTTY:
    """A stream that claims to be a terminal and records what was written."""

    def __init__(self) -> None:
        self.text = ""

    def write(self, data: str) -> int:
        self.text += data
        return len(data)

    def flush(self) -> None:
        """No-op: nothing is buffered."""

    def isatty(self) -> bool:
        return True

class _FrozenClock(datetime):
    """A clock that stands still, so two runs start in the same second."""

    @classmethod
    def now(cls, tz=None):
        return cls(2026, 1, 1, 12, 0, 0)

def _fake_ytdlp_env(**extra: str) -> dict[str, str]:
    """Environment with the fake yt-dlp first on ``PATH`` (plus any extra vars)."""
    env = {"PATH": str(FAKE_YTDLP.parent) + os.pathsep + os.environ.get("PATH", "")}
    env.update(extra)
    return env

def _load_export_helper():
    """Load ``tests/export_golden.py`` by path (it is not an installed module)."""
    target = BASE / "tests" / "export_golden.py"
    spec = importlib.util.spec_from_file_location("export_golden", target)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def _export_texts(directory: Path, helper,
                  keep: tuple[str, ...] = ()) -> dict[str, str]:
    """Normalized text of every stored file, optionally limited to a prefix.

    Das Herkunfts-Manifest (``.sortiton-export.json``) gehört zum Lauf, nicht
    zum Bericht, und ist deshalb kein Teil des Golden-Vergleichs.
    """
    texts: dict[str, str] = {}
    for path in sorted(directory.iterdir()):
        if path.name.startswith("."):
            continue
        if path.is_file() and (not keep or path.name.startswith(keep)):
            texts[path.name] = helper.normalize_export_text(
                path.read_text(encoding="utf-8"))
    return texts

def _first_difference(left: dict[str, str], right: dict[str, str]) -> str:
    """Name the first differing file, so a failure stays readable."""
    if sorted(left) != sorted(right):
        return f"files: {sorted(left)} != {sorted(right)}"
    for name in sorted(left):
        if left[name] != right[name]:
            return f"first difference in {name}"
    return ""

def _export_args(fixture: Path, outdir: Path, **overrides) -> SimpleNamespace:
    """Arguments for ``cmd_export`` the way the CLI would deliver them.

    ``cmd_export`` fills every field it does not find with the option default
    (:func:`sortiton.features.base.resolve_args`), so a test only sets what it
    means to change.
    """
    values = {"folder": str(fixture), "output": str(outdir)}
    values.update(overrides)
    return SimpleNamespace(**values)

def _export_columns(directory: Path, columns: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    """The given TSV columns of every row, keyed by path (chunking independent)."""
    rows: dict[str, tuple[str, ...]] = {}
    for path in sorted(directory.glob("tracks_part*.tsv")):
        lines = path.read_text(encoding="utf-8").splitlines()
        head = lines[0].split("\t")
        index = [head.index(name) for name in columns]
        for line in lines[1:]:
            if line:
                cells = line.split("\t")
                rows[cells[index[0]]] = tuple(cells[i] for i in index)
    return rows

def _genre_values(value: str) -> frozenset[str]:
    """Genre as a set: mutagen joins with ``" | "``, ffprobe with ``";"``."""
    return frozenset(part.strip() for part in re.split(r"[;|]", value) if part.strip())

def _tree_digest(root: Path) -> list[tuple[str, int, int, str]]:
    """Path, size, mtime (ns) and SHA-256 of every file under ``root``."""
    import hashlib

    digest: list[tuple[str, int, int, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            stat = path.stat()
            digest.append((path.relative_to(root).as_posix(), stat.st_size,
                           stat.st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest()))
    return digest

def _restore_args(path, *, apply: bool = False, keep_copies: bool = False,
                  list_journals: bool = False, backup: bool = False, cancel=None):
    """The argument set cmd_restore expects (CLI: argparse, here a namespace)."""
    args = SimpleNamespace(journal=path, apply=apply, backup=backup,
                           keep_copies=keep_copies, list_journals=list_journals)
    if cancel is not None:
        args.cancel = cancel
    return args

def _open_journal(work: Path, day: int):
    """Open a journal for a synthetic run under ``work``; the caller closes it.

    ``day`` only keeps the file names of the runs apart.
    """
    log = work / f"sortiton_2026-01-{day:02d}_00-00-00.log"
    log.write_text("", encoding="utf-8")
    return journal.open_for(log)

def _make_flac(path: Path) -> bool:
    """Build a short, silent FLAC with ffmpeg (False when ffmpeg is missing)."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "anullsrc=r=8000:cl=mono", "-t", "0.2", str(path)],
            capture_output=True, check=False)
    except OSError:
        return False
    return result.returncode == 0 and path.is_file()

def _png_header(width: int, height: int) -> bytes:
    """A PNG header of the given size - the guard reads nothing else."""
    return (b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR"
            + width.to_bytes(4, "big") + height.to_bytes(4, "big")
            + b"\x08\x06\x00\x00\x00")
