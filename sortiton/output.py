"""Output: console/GUI text, progress, structured results and the log file."""

from __future__ import annotations

import os
import re
import shutil
import sys
import threading
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator

from . import config, i18n
from .config import (JOURNAL_SUFFIX, LATEST_LOG_NAME, LOG_KEEP,
                     LOG_PREFIX, MUTAGEN_AVAILABLE, READ_WORKERS, WRITE_WORKERS)
from .files import open_new

_sink = None
_progress_sink = None
_plan_sink = None
_stats_sink = None
_last_stats: dict[str, dict] = {}
_stats_lock = threading.Lock()

_log_file = None
_log_path: Path | None = None
_log_lock = threading.Lock()


@dataclass(frozen=True)
class PlanEvent:
    """Ein Planereignis und seine auftragsspezifischen Daten."""

    kind: str
    data: dict


@dataclass(frozen=True)
class TagPlanEvent(PlanEvent):
    """Geplante Änderung von Tagfeldern einer Datei."""

    path: str | Path
    changes: dict[str, tuple[str, str]]


@dataclass(frozen=True)
class FilePlanEvent(PlanEvent):
    """Geplante Dateioperation mit optionaler Referenzdatei."""

    source: str | Path
    target: str | Path
    keep: str | Path | None = None


@dataclass(frozen=True)
class RunReport:
    """Abschlussstatus und Zähler eines einzelnen Laufs."""

    returncode: int
    stats: dict[str, dict]


@dataclass
class RunContext:
    """Ausgabe und Zähler eines Laufs; Callbacks werden unmittelbar aufgerufen."""

    logger: Callable | None = None
    progress_sink: Callable | None = None
    plan_sink: Callable | None = None
    stats_sink: Callable | None = None
    log_to_file: bool = True
    paths: config.AppPaths | None = None
    stats: dict[str, dict] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def execute(self, action: Callable[[], int]) -> RunReport:
        """Aktion im Kontext ausführen und ihren Abschlussbericht zurückgeben."""
        with use_run_context(self):
            returncode = action()
        with self.lock:
            stats = {kind: dict(values) for kind, values in self.stats.items()}
        return RunReport(returncode, stats)


_run_context: ContextVar[RunContext | None] = ContextVar("sortiton_run_context", default=None)


@contextmanager
def use_run_context(context: RunContext) -> Iterator[None]:
    """Kontext nur für den aktuellen Ausführungspfad aktivieren."""
    token = _run_context.set(context)
    try:
        if context.paths is None:
            yield
        else:
            with config.use_paths(context.paths):
                yield
    finally:
        _run_context.reset(token)


def current_run_context() -> RunContext | None:
    """Aktiven Kontext zurückgeben; ohne Lauf gelten die bisherigen Senken."""
    return _run_context.get()


def default_run_context() -> RunContext:
    """Die bisherigen Ausgabesenken für einen einzelnen Lauf übernehmen."""
    plan_sink = _plan_sink
    return RunContext(
        logger=_sink,
        progress_sink=_progress_sink,
        plan_sink=(lambda event: plan_sink(event.kind, event.data)) if plan_sink else None,
        stats_sink=_stats_sink,
    )


def submit_with_context(pool, function, *args):
    """Den Ausführungskontext für jeden Poolauftrag einzeln übernehmen."""
    context = copy_context()
    return pool.submit(context.run, function, *args)


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
    context = current_run_context()
    if context is None or context.log_to_file:
        _log_line(line)
    sink = context.logger if context is not None else _sink
    if sink is not None:
        sink(line)
    else:
        print(line, flush=True)


def set_progress(sink) -> None:
    """Report progress: sink(current, total, text). None = off."""
    global _progress_sink
    _progress_sink = sink


def progress(current: int, total: int, text: str = "") -> None:
    """Report progress to the current sink: ``sink(current, total, text)``."""
    context = current_run_context()
    sink = context.progress_sink if context is not None else _progress_sink
    _emit(sink, current, total, str(text))


def set_plan_sink(sink) -> None:
    """Report planned changes: sink(kind, data)."""
    global _plan_sink
    _plan_sink = sink


def report_plan(kind: str, **data) -> None:
    """Publish one planned change."""
    context = current_run_context()
    if context is None:
        _emit(_plan_sink, kind, data)
    else:
        if kind == "tags" and "path" in data and "changes" in data:
            event = TagPlanEvent(kind, data, data["path"], data["changes"])
        elif "source" in data and "target" in data:
            event = FilePlanEvent(kind, data, data["source"], data["target"],
                                  data.get("keep"))
        else:
            event = PlanEvent(kind, data)
        _emit(context.plan_sink, event)


_COLORS = {"red": "31", "green": "32", "yellow": "33", "dim": "2"}
_ANSI_SGR = re.compile(r"\x1b\[[0-9;]*m")


def colorize(text: str, color: str) -> str:
    """Colour ``text`` on a real terminal, but never in the GUI or a pipe."""
    context = current_run_context()
    sink = context.logger if context is not None else _sink
    if sink is not None or sys.stdout is None or not sys.stdout.isatty():
        return text
    if "NO_COLOR" in os.environ:
        return text
    code = _COLORS.get(color)
    return f"\033[{code}m{text}\033[0m" if code else text


def set_stats_sink(sink) -> None:
    """Report the counters of a run: sink(kind, stats). None = off."""
    global _stats_sink
    _stats_sink = sink


def report_stats(kind: str, **values) -> None:
    """Publish the counters of a run; they are kept per kind for :func:`last_stats`."""
    snapshot = dict(values)
    with _stats_lock:
        _last_stats[kind] = snapshot
    context = current_run_context()
    if context is None:
        _emit(_stats_sink, kind, dict(snapshot))
    else:
        with context.lock:
            context.stats[kind] = snapshot
        _emit(context.stats_sink, kind, dict(snapshot))


def last_stats(kind: str) -> dict:
    """Counters of the most recent ``kind`` run; empty if there was none."""
    context = current_run_context()
    if context is not None:
        with context.lock:
            return dict(context.stats.get(kind, {}))
    with _stats_lock:
        return dict(_last_stats.get(kind, {}))


def clear_stats(*kinds: str) -> None:
    """Forget old counters before a combined run reads them again."""
    context = current_run_context()
    if context is not None:
        with context.lock:
            for kind in kinds:
                context.stats.pop(kind, None)
    with _stats_lock:
        for kind in kinds:
            _last_stats.pop(kind, None)


def latest_log_file() -> Path | None:
    """Newest log file, or None."""
    return _log_path


LOG_DIR = config.current_paths().log_dir
_DEFAULT_LOG_DIR = LOG_DIR


def _log_dir() -> Path:
    paths = config.selected_paths()
    if paths is not None:
        return paths.log_dir
    return LOG_DIR if LOG_DIR != _DEFAULT_LOG_DIR else config.current_paths().log_dir


def open_log_file(title: str = "") -> Path | None:
    """Open a new log file; every message() is also stored there."""
    global _log_file, _log_path
    close_log_file()

    log_dir = _log_dir()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path, handle = open_new(log_dir / f"{LOG_PREFIX}_{stamp}.log")
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
        link = log_dir / LATEST_LOG_NAME
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
            _log_file.write(_ANSI_SGR.sub("", text) + "\n")
            _log_file.flush()
        except (OSError, ValueError):
            pass


def _prune_old_logs(keep: int = LOG_KEEP) -> None:
    """Keep only the most recent logs, and drop their journal with them."""
    def recent(path: Path) -> tuple[int, str]:
        try:
            return path.stat().st_mtime_ns, path.name
        except OSError:
            return 0, path.name

    try:
        logs = sorted(_log_dir().glob(f"{LOG_PREFIX}_*.log"),
                      key=recent, reverse=True)
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
