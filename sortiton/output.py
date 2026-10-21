"""Output: console/GUI text, progress, structured results and the log file."""

from __future__ import annotations

import shutil
import threading
from datetime import datetime
from pathlib import Path

from . import i18n
from .config import (JOURNAL_SUFFIX, LATEST_LOG_NAME, LOG_DIR, LOG_KEEP,
                     LOG_PREFIX, MUTAGEN_AVAILABLE, READ_WORKERS, WRITE_WORKERS)
from .files import open_new

_sink = None                 # GUI callback; None = console
_progress_sink = None
_plan_sink = None
_stats_sink = None
_last_stats: dict[str, dict] = {}
_stats_lock = threading.Lock()   # report_stats() runs in worker threads

_log_file = None
_log_path: Path | None = None
_log_lock = threading.Lock()


def _emit(sink, *args) -> None:
    """Hand a message to a GUI sink - a broken sink must not kill the run."""
    if sink is None:
        return
    try:
        sink(*args)
    except Exception:
        pass


def set_logger(sink) -> None:
    """Redirect output into a callback (GUI). None = console."""
    global _sink
    _sink = sink


def message(text: str = "") -> None:
    """Write a line to the console/GUI and always into the log file."""
    line = str(text)
    _log_line(line)
    if _sink is not None:
        _sink(line)
    else:
        print(line, flush=True)


def set_progress(sink) -> None:
    """Report progress: sink(current, total, text). None = off."""
    global _progress_sink
    _progress_sink = sink


def progress(current: int, total: int, text: str = "") -> None:
    """Report progress to the current sink: ``sink(current, total, text)``."""
    _emit(_progress_sink, current, total, str(text))


def set_plan_sink(sink) -> None:
    """Report planned changes: sink(kind, data). None = off.

    ``kind`` is "tags" (``path``, ``changes``), "rename" or "sort" (``source``,
    ``target``); only real changes are reported.
    """
    global _plan_sink
    _plan_sink = sink


def report_plan(kind: str, **data) -> None:
    """Publish one planned change."""
    _emit(_plan_sink, kind, data)


def set_stats_sink(sink) -> None:
    """Report the counters of a run: sink(kind, stats). None = off."""
    global _stats_sink
    _stats_sink = sink


def report_stats(kind: str, **values) -> None:
    """Publish the counters of a run; they are kept per kind for :func:`last_stats`."""
    snapshot = dict(values)
    with _stats_lock:
        _last_stats[kind] = snapshot
    _emit(_stats_sink, kind, dict(snapshot))


def last_stats(kind: str) -> dict:
    """Counters of the most recent ``kind`` run; empty if there was none."""
    with _stats_lock:
        return dict(_last_stats.get(kind, {}))


def latest_log_file() -> Path | None:
    """Newest log file, or None."""
    return _log_path


def open_log_file(title: str = "") -> Path | None:
    """Open a new log file; every message() is also stored there."""
    global _log_file, _log_path
    close_log_file()

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path, handle = open_new(LOG_DIR / f"{LOG_PREFIX}_{stamp}.log")
    except (OSError, RuntimeError):
        with _log_lock:
            _log_file = None
            _log_path = None
        return None

    with _log_lock:
        _log_file = handle
        _log_path = path
    ok = i18n.t("log.available")
    missing = i18n.t("log.missing")
    _log_line(i18n.t("log.title"))
    _log_line(i18n.t("log.start", time=f"{datetime.now():%Y-%m-%d %H:%M:%S}"))
    _log_line(i18n.t("log.command", command=title))
    _log_line(i18n.t("log.system",
                     ffprobe=ok if shutil.which("ffprobe") else missing,
                     mutagen=ok if MUTAGEN_AVAILABLE else missing,
                     read=READ_WORKERS, write=WRITE_WORKERS))
    _log_line("#" + "-" * 62)

    try:
        link = LOG_DIR / LATEST_LOG_NAME
        link.unlink(missing_ok=True)
        link.symlink_to(path.name)
    except OSError:
        pass

    _prune_old_logs()
    return path


def close_log_file(rc: int | None = None) -> None:
    """Write the footer and close the log file."""
    global _log_file
    with _log_lock:
        handle, _log_file = _log_file, None
        if handle is None:
            return
        try:
            stamp = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
            if rc is None:
                footer = i18n.t("log.end", time=stamp)
            else:
                footer = i18n.t("log.end_rc", time=stamp, rc=rc)
            handle.write("#" + "-" * 62 + "\n")
            handle.write(footer + "\n")
            handle.close()
        except (OSError, ValueError):
            pass


def _log_line(text: str) -> None:
    with _log_lock:
        if _log_file is None:
            return
        try:
            _log_file.write(text + "\n")
            _log_file.flush()
        except (OSError, ValueError):
            pass


def _prune_old_logs(keep: int = LOG_KEEP) -> None:
    """Keep only the most recent logs, and drop their journal with them.

    Journals have a smaller limit of their own (:mod:`sortiton.journal`); this
    is the safety net that leaves no orphaned journal behind.
    """
    try:
        logs = sorted(LOG_DIR.glob(f"{LOG_PREFIX}_*.log"),
                      key=lambda p: p.name, reverse=True)
        for old in logs[keep:]:
            old.unlink(missing_ok=True)
            old.with_suffix(JOURNAL_SUFFIX).unlink(missing_ok=True)
    except OSError:
        pass


def banner(title: str, preview: bool) -> None:
    """Print the boxed header of a run."""
    mode = i18n.t("log.mode.preview") if preview else i18n.t("log.mode.live")
    line = "=" * 62
    message()
    message(line)
    message(f"  {title}")
    message(i18n.t("log.mode_line", mode=mode))
    message(line)
