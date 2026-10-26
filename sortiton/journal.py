"""The run journal: machine-readable record of what a run changed."""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

from . import i18n, output, redact
from .config import (JOURNAL_KEEP, JOURNAL_SUFFIX, LATEST_JOURNAL_NAME, LOG_DIR,
                     LOG_PREFIX, OFF_VALUES)
from .files import open_new

SCHEMA = 1

UNDOABLE = ("tags", "rename", "sort", "copy", "dedupe")

_file = None
_path: Path | None = None
_lock = threading.Lock()
_write_error_reported = False


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
    with _lock:
        return _file is not None


def latest_path() -> Path | None:
    """The journal that is open right now, or None."""
    with _lock:
        return _path


def open_for(log_path: Path) -> Path | None:
    """Start the journal for a run."""
    global _file, _path, _write_error_reported

    with _lock:
        if _file is not None:
            return _path
    if not enabled():
        return None

    path = journal_path_for(log_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path, handle = open_new(path)
    except (OSError, RuntimeError):
        return None

    with _lock:
        if _file is not None:
            handle.close()
            try:
                path.unlink()
            except OSError:
                pass
            return _path
        _file = handle
        _path = path
        _write_error_reported = False

    _link_latest(path)
    _prune_journals()
    try:
        cwd = os.getcwd()
    except OSError:
        cwd = "?"
    record("run", status="start", argv=redact.command(sys.argv), cwd=cwd)
    return path


def close() -> None:
    """Close the journal of this run."""
    global _file, _path

    with _lock:
        handle, _file, _path = _file, None, None
    if handle is None:
        return
    try:
        handle.close()
    except OSError:
        pass


def _report_write_error(error: object) -> None:
    """Warn once when the journal can no longer be written."""
    global _write_error_reported
    with _lock:
        if _write_error_reported:
            return
        _write_error_reported = True
    output.message(i18n.t("journal.error.write", error=error))


def record(op: str, **data: object) -> None:
    """Append one event. Never raises, never interrupts the run."""
    for key in ("path", "source", "target"):
        value = data.get(key)
        if isinstance(value, (str, Path)) and value:
            data[key] = str(Path(value).absolute())
    event = {"v": SCHEMA, "ts": f"{datetime.now():%Y-%m-%d %H:%M:%S}", "op": op}
    event.update(data)
    try:
        line = json.dumps(event, ensure_ascii=False)
    except (TypeError, ValueError):
        return

    try:
        with _lock:
            handle = _file
            if handle is None:
                return
            handle.write(line + "\n")
            handle.flush()
    except (OSError, ValueError) as error:
        _report_write_error(error)


def record_tags(path: Path, before: dict, after: dict) -> None:
    """Remember a tag change: the old values are what undo writes back."""
    record("tags", path=str(path), before=dict(before), after=dict(after))


def record_move(op: str, source: Path, target: Path, mode: str = "") -> None:
    """Remember a move (``op`` is "rename"/"sort"/"copy"/"dedupe")."""
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
    """Events of ``path`` in the order they have to be undone."""
    events = list(read_journal(path))
    cwd = read_header(path).get("cwd")
    base = Path(str(cwd)) if cwd else Path.cwd()
    planned = []
    for event in events:
        if event.get("op") == "run":
            continue
        event = dict(event)
        for key in ("path", "source", "target"):
            value = event.get(key)
            if isinstance(value, str) and value and not Path(value).is_absolute():
                event[key] = str(base / value)
        planned.append(event)
    return list(reversed(planned))


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
    def key(path: Path) -> tuple[int, str]:
        try:
            return path.stat().st_mtime_ns, path.name
        except OSError:
            return 0, path.name

    try:
        files = sorted(LOG_DIR.glob(f"{LOG_PREFIX}_*{JOURNAL_SUFFIX}"),
                       key=key, reverse=True)
    except OSError:
        return []
    return files if limit is None else files[:limit]


def latest_journal() -> Path | None:
    """The newest journal of an **earlier** run."""
    current = latest_path()
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
