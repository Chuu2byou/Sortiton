"""The run journal: machine-readable record of what a run changed.

The log file (see :mod:`sortiton.output`) is for humans - file names without
their folder, wording in the interface language. Undo cannot be built on that,
so every change is appended here as one JSON object per line.

Created and pruned together with the log file of the same run::

    logs/sortiton_2026-09-24_19-03-19.log       # for humans
    logs/sortiton_2026-09-24_19-03-19.jsonl     # for restore
    logs/latest_journal.jsonl -> sortiton_…_19-03-19.jsonl

Unknown operations and unknown fields are ignored while reading, so a restore
from an older version keeps working. Written only while changes are applied; a
preview leaves no file behind.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

from .config import (JOURNAL_KEEP, JOURNAL_SUFFIX, LATEST_JOURNAL_NAME, LOG_DIR,
                     LOG_PREFIX, OFF_VALUES)
from .files import free_path

SCHEMA = 1

# Operations a restore can undo.
UNDOABLE = ("tags", "rename", "sort", "copy")

_file = None                 # open file handle while a run is in progress
_path: Path | None = None    # its path
_lock = threading.Lock()     # writes come from several worker threads


def enabled() -> bool:
    """Whether a journal is written (SORTITON_JOURNAL overrides, default yes)."""
    from_env = os.environ.get("SORTITON_JOURNAL", "").strip().lower()
    if from_env:
        return from_env not in OFF_VALUES
    return True


def journal_path_for(log_path: Path) -> Path:
    """Journal that belongs to ``log_path`` (same name, other suffix)."""
    return Path(log_path).with_suffix(JOURNAL_SUFFIX)


def is_open() -> bool:
    """True while a journal is being written."""
    return _file is not None


def latest_path() -> Path | None:
    """The journal that is open right now, or None."""
    return _path


def open_for(log_path: Path) -> Path | None:
    """Start the journal for a run. Returns the path, or None if impossible.

    Does nothing when a journal is already open: one run, one journal. A
    combined run (tags -> rename -> sort) therefore writes a single file, which
    is exactly what undo needs.
    """
    global _file, _path

    if _file is not None:
        return _path
    if not enabled():
        return None

    path = free_path(journal_path_for(log_path))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("w", encoding="utf-8")
    except OSError:
        return None

    with _lock:
        _file = handle
        _path = path

    _link_latest(path)
    _prune_journals()
    try:
        cwd = os.getcwd()
    except OSError:
        cwd = "?"      # the working directory was removed while we ran
    record("run", status="start", argv=list(sys.argv), cwd=cwd)
    return path


def close() -> None:
    """Close the journal of this run.

    Clearing the path as well matters: as long as it is set, :func:`latest_journal`
    treats that file as "the run that is going on" and skips it.
    """
    global _file, _path

    with _lock:
        handle, _file, _path = _file, None, None
    if handle is None:
        return
    try:
        handle.close()
    except OSError:
        pass


def record(op: str, **data: object) -> None:
    """Append one event. Never raises, never interrupts the run."""
    if _file is None:
        return

    event = {"v": SCHEMA, "ts": f"{datetime.now():%Y-%m-%d %H:%M:%S}", "op": op}
    event.update(data)
    try:
        line = json.dumps(event, ensure_ascii=False)
    except (TypeError, ValueError):
        return

    try:
        with _lock:
            _file.write(line + "\n")
            _file.flush()      # a crash keeps everything written so far
    except (OSError, ValueError):
        pass


def record_tags(path: Path, before: dict, after: dict) -> None:
    """Remember a tag change: the old values are what undo writes back."""
    record("tags", path=str(path), before=dict(before), after=dict(after))


def record_move(op: str, source: Path, target: Path, mode: str = "") -> None:
    """Remember a rename or a sort step (``op`` is "rename"/"sort"/"copy")."""
    data: dict[str, object] = {"source": str(source), "target": str(target)}
    if mode:
        data["mode"] = mode
    record(op, **data)


def record_failure(op: str, error: object, **data: object) -> None:
    """Remember a change that failed, so a restore can report it."""
    record(op, status="error", error=str(error), **data)


def read_journal(path: Path):
    """Yield every readable event of ``path``; broken lines are skipped."""
    try:
        with Path(path).open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict) and event.get("op"):
                    yield event
    except OSError:
        return


def read_header(path: Path) -> dict:
    """Header event (``op=run``) of a journal, or an empty dict."""
    for event in read_journal(path):
        if event.get("op") == "run":
            return event
    return {}


def schema_version(path: Path) -> int:
    """Schema version of ``path`` (0 when it has no readable header)."""
    header = read_header(path)
    try:
        return int(header.get("v", 0))
    except (TypeError, ValueError):
        return 0


def plan_restore(path: Path) -> list[dict]:
    """Events of ``path`` in the order they have to be undone.

    Newest first: a combined run writes tags -> rename -> sort, so undoing it
    has to happen the other way round. Failed and unknown events stay in the
    list - the caller reports them instead of hiding them.
    """
    return list(reversed([event for event in read_journal(path)
                          if event.get("op") != "run"]))


def summarize(events) -> dict[str, int]:
    """Count the events per operation, in the order of :data:`UNDOABLE`."""
    counts: dict[str, int] = {}
    for event in events:
        op = str(event.get("op"))
        counts[op] = counts.get(op, 0) + 1
    return {op: counts[op] for op in sorted(counts, key=_op_order)}


def _op_order(op: str) -> tuple[int, str]:
    return (UNDOABLE.index(op) if op in UNDOABLE else len(UNDOABLE), op)


def find_journals(limit: int | None = JOURNAL_KEEP) -> list[Path]:
    """Available journals, newest first."""
    try:
        files = sorted(LOG_DIR.glob(f"{LOG_PREFIX}_*{JOURNAL_SUFFIX}"),
                       key=lambda path: path.name, reverse=True)
    except OSError:
        return []
    return files if limit is None else files[:limit]


def latest_journal() -> Path | None:
    """The newest journal of an **earlier** run.

    The journal that is currently open is skipped: while a run is going on, the
    ``latest_journal.jsonl`` link already points at that run's own, still empty
    file. Without skipping it, ``restore --apply`` would read its own journal,
    find nothing and do nothing.
    """
    current = _path
    for path in find_journals(limit=None):
        if current is None or path != current:
            return path
    return None


def resolve_journal(path: Path | str | None = None) -> Path | None:
    """The journal to undo: the given one, else the most recent."""
    if path:
        return Path(path).expanduser()
    return latest_journal()


def _link_latest(path: Path) -> None:
    """Point ``latest_journal.jsonl`` at the newest journal (like latest.log)."""
    link = LOG_DIR / LATEST_JOURNAL_NAME
    try:
        link.unlink(missing_ok=True)
        link.symlink_to(path.name)
    except OSError:
        pass


def _prune_journals(keep: int = JOURNAL_KEEP) -> None:
    """Throw away everything past the newest JOURNAL_KEEP."""
    for old in find_journals(limit=None)[keep:]:
        try:
            old.unlink()
        except OSError:
            pass
