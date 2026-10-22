"""yt-dlp process handling for the fetch feature (preview and download)."""

from __future__ import annotations

import os
import queue
import subprocess
import threading
from pathlib import Path
from typing import NamedTuple

from ... import i18n, output
from ...cancel import NO_CANCEL, Cancelled

META_MARK = "SORTITON_META"
PROGRESS_MARK = "SORTITON_PROGRESS"
FILE_MARK = "SORTITON_FILE"
SEP = "\t"

POLL_SECS = 0.2
TERM_GRACE_SECS = 5.0
LOG_TAIL = 5

NA_VALUES = {"", "NA", "None", "none"}

PREVIEW_PRINT = f"{META_MARK}{SEP}%(webpage_url)s{SEP}%(title)s{SEP}%(duration)s"

PROGRESS_TEMPLATE = (f"download:{PROGRESS_MARK}{SEP}%(progress.downloaded_bytes)s"
                     f"{SEP}%(progress.total_bytes)s"
                     f"{SEP}%(progress.total_bytes_estimate)s")

DOWNLOAD_PRINT = f"after_move:{FILE_MARK}{SEP}%(filepath)s"


class Entry(NamedTuple):
    """One video the preview found: URL, title and duration (seconds or None)."""

    url: str
    title: str
    duration: int | None


class Saved(NamedTuple):
    """One finished download: its file path and its download-archive id."""

    path: Path
    archive_id: str


def _playlist_args(playlist: bool) -> list[str]:
    """``--yes-playlist`` when the whole playlist is wanted, else ``--no-playlist``."""
    return ["--yes-playlist"] if playlist else ["--no-playlist"]


def _number(text: str) -> int | None:
    """Integer of a template field, or None for a placeholder/unknown value."""
    text = str(text).strip()
    if text in NA_VALUES:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _archive_lines(path: Path) -> list[str]:
    """The non-empty lines of a download archive (empty when there is none)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def _snapshot(root: Path) -> set[Path]:
    """Pfade aller Dateien unter ``root`` vor dem Download, aufgelöst.

    Nur ein Pfad, der hier nicht vorkommt, kann in diesem Lauf entstanden sein;
    die Menge ist damit der Herkunftsnachweis für das Journal. Fehlt der Ordner
    oder ist er unlesbar, bleibt die Menge leer - die Einzelprüfungen greifen
    trotzdem.
    """
    found: set[Path] = set()
    try:
        for dirpath, _dirnames, filenames in os.walk(root):
            base = Path(dirpath)
            for name in filenames:
                try:
                    found.add((base / name).resolve())
                except OSError:
                    continue
    except OSError:
        return found
    return found


def _own_path(text: str, root: Path, before: set[Path]) -> Path | None:
    """Gemeldete Datei dieses Laufs innerhalb ``root``, sonst ``None``.

    Der Pfad muss als Datei existieren, nach dem Auflösen von ``..`` und
    Symlink-Zielen innerhalb von ``root`` liegen und vor dem Lauf noch nicht
    vorhanden gewesen sein. Alles andere ist fremd und bleibt aus Ergebnis und
    Journal heraus.
    """
    try:
        path = Path(text).expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if not path.is_file() or path in before:
        return None
    return path


def _stream(argv: list[str], cancel, on_line) -> tuple[int | None, str]:
    """Run ``argv`` and call ``on_line`` for every output line."""
    cancel = cancel or NO_CANCEL
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1,
                                encoding="utf-8", errors="replace")
    except OSError as exc:
        return None, str(exc)

    lines: queue.Queue[str | None] = queue.Queue()

    def reader() -> None:
        try:
            for line in proc.stdout:
                lines.put(line)
        finally:
            lines.put(None)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        while True:
            try:
                line = lines.get(timeout=POLL_SECS)
            except queue.Empty:
                if cancel.is_set():
                    raise Cancelled
                continue
            if line is None:
                break
            if cancel.is_set():
                raise Cancelled
            on_line(line.rstrip("\r\n"))
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=TERM_GRACE_SECS)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        thread.join(timeout=TERM_GRACE_SECS)
    return proc.returncode, ""


def preview(url: str, *, playlist: bool, cancel=None) -> tuple[list[Entry], str]:
    """Return what yt-dlp would download, without downloading anything."""
    argv = ["yt-dlp", "--simulate", "--no-warnings", "--print", PREVIEW_PRINT]
    argv += _playlist_args(playlist)
    argv.append(url)

    entries: list[Entry] = []

    def collect(line: str) -> None:
        if not line.startswith(META_MARK + SEP):
            return
        parts = line.split(SEP)
        if len(parts) < 4:
            return
        entries.append(Entry(parts[1], parts[2], _number(parts[3])))

    rc, error = _stream(argv, cancel, collect)
    if rc != 0:
        return [], error or i18n.t("fetch.error.exit", rc=rc)
    return entries, ""


def download(url: str, target: Path, *, audio_format: str, playlist: bool,
             archive: Path | None = None,
             cancel=None, on_saved=None) -> tuple[list[Saved], str]:
    """Download ``url`` as audio into ``target``; return the finished files."""
    if archive is not None:
        try:
            archive.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    before = _archive_lines(archive) if archive is not None else []
    root = target.resolve()
    before_files = _snapshot(root)

    argv = ["yt-dlp", "--no-simulate", "--newline", "--no-warnings",
            "-x", "--audio-format", audio_format, "--audio-quality", "0",
            "--embed-metadata", "--embed-thumbnail", "--no-overwrites",
            "--no-post-overwrites",
            "--progress", "--progress-template", PROGRESS_TEMPLATE,
            "--print", DOWNLOAD_PRINT,
            "-P", str(target), "-o", "%(title)s.%(ext)s"]
    if archive is not None:
        argv += ["--download-archive", str(archive)]
    argv += _playlist_args(playlist)
    argv.append(url)

    reported: list[str] = []
    log_tail: list[str] = []

    def handle(line: str) -> None:
        if line.startswith(PROGRESS_MARK + SEP):
            _report_progress(line)
        elif line.startswith(FILE_MARK + SEP):
            reported.append(line[len(FILE_MARK) + 1:])
        elif line.strip():
            log_tail.append(line)
            del log_tail[:-LOG_TAIL]

    def collect() -> list[Saved]:
        """Bisher fertige eigene Dateien, mit den zugehörigen Archiv-Ids.

        Die Archiv-Ids werden vor dem Filtern zugeordnet, damit die Reihenfolge
        zu den Meldungen passt; erst danach fällt alles Fremde weg.
        """
        if archive is None:
            pairs = [(text, "") for text in reported]
        else:
            new_ids = _archive_lines(archive)[len(before):]
            pairs = [(text, new_ids[index] if index < len(new_ids) else "")
                     for index, text in enumerate(reported)]
        saved: list[Saved] = []
        seen: set[Path] = set()
        for text, archive_id in pairs:
            path = _own_path(text, root, before_files)
            if path is None or path in seen:
                continue
            seen.add(path)
            saved.append(Saved(path, archive_id))
        return saved

    def deliver(saved: list[Saved]) -> None:
        if on_saved is not None:
            for item in saved:
                on_saved(item)

    try:
        rc, error = _stream(argv, cancel, handle)
    except Cancelled:
        deliver(collect())
        raise

    saved = collect()
    deliver(saved)
    if rc != 0:
        detail = error or "\n".join(log_tail)
        return saved, detail or i18n.t("fetch.error.exit", rc=rc)
    return saved, ""


def _report_progress(line: str) -> None:
    """Turn one ``--progress-template`` line into an :func:`output.progress` call."""
    parts = line.split(SEP)
    if len(parts) < 4:
        return
    done = _number(parts[1])
    total = _number(parts[2]) or _number(parts[3])
    if done is None or not total:
        return
    percent = min(round(done * 100 / total), 100)
    output.progress(percent, 100, i18n.t("fetch.progress"))
