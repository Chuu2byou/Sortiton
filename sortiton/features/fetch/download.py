"""yt-dlp process handling for the fetch feature (preview and download).

The feature never parses yt-dlp's human-readable log: it asks for machine
output with ``--print`` and ``--progress-template`` (see the yt-dlp README,
"Embedding yt-dlp"), so a change of wording cannot break the parsing. Each line
carries a marker (:data:`META_MARK`, :data:`PROGRESS_MARK`, :data:`FILE_MARK`);
everything else is ignored.

The process runs line by line, so the progress reaches
:func:`sortiton.output.progress` and a :class:`~sortiton.cancel.CancelToken` can
terminate it. Nothing here downloads on its own: :func:`download` is only called
after the feature checked ``--apply`` *and* ``--confirm`` (or the GUI asked its
dialog).
"""

from __future__ import annotations

import queue
import subprocess
import threading
from pathlib import Path
from typing import NamedTuple

from ... import i18n, output
from ...cancel import NO_CANCEL, Cancelled

# Machine-readable markers. Distinct, ASCII-only markers keep a localized log
# line from ever looking like our data.
META_MARK = "SORTITON_META"
PROGRESS_MARK = "SORTITON_PROGRESS"
FILE_MARK = "SORTITON_FILE"
SEP = "\t"

POLL_SECS = 0.2          # short wait, so a cancel is noticed quickly
TERM_GRACE_SECS = 5.0    # then the process is killed
LOG_TAIL = 5             # log lines kept for an error message

#: The value yt-dlp writes when a field is unknown (``--output-na-placeholder``).
NA_VALUES = {"", "NA", "None", "none"}

#: ``--print`` template of the preview: one line per entry, tab separated.
#: ``--print`` implies ``--quiet`` and, at the video stage, ``--simulate``, so
#: the preview never downloads.
PREVIEW_PRINT = f"{META_MARK}{SEP}%(webpage_url)s{SEP}%(title)s{SEP}%(duration)s"

#: Machine progress line of the download stage (bytes; total may be an estimate).
PROGRESS_TEMPLATE = (f"download:{PROGRESS_MARK}{SEP}%(progress.downloaded_bytes)s"
                     f"{SEP}%(progress.total_bytes)s"
                     f"{SEP}%(progress.total_bytes_estimate)s")

#: Final file name after post-processing, printed once the file has been moved.
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


def _stream(argv: list[str], cancel, on_line) -> tuple[int | None, str]:
    """Run ``argv`` and call ``on_line`` for every output line.

    stdout and stderr are merged, so the progress lines and the ``--print``
    output arrive on one stream; the markers filter out the rest. The process is
    polled in short steps so a :class:`~sortiton.cancel.CancelToken` can
    terminate it. Returns ``(returncode, error)``; on a cancelled token
    :class:`~sortiton.cancel.Cancelled` is raised and ``error`` is unused.
    """
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
    """Return what yt-dlp would download, without downloading anything.

    Runs ``yt-dlp --simulate`` and parses the ``--print`` lines. Returns
    ``(entries, "")`` on success and ``([], error)`` on failure; the caller
    reports the error.
    """
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
    """Download ``url`` as audio into ``target``; return the finished files.

    ``archive`` is yt-dlp's download archive (``--download-archive``): when it
    is given, an already recorded track is skipped and every finished file is
    recorded there. Each returned :class:`Saved` carries the archive id of its
    file (empty when no archive is used), so a restore can delete the file and
    drop its archive line again (step 4.4).

    ``--no-overwrites`` keeps yt-dlp from replacing an existing file, matching
    the project rule that nothing is ever overwritten. Returns ``(files, "")``
    on success and ``(files, error)`` on failure; the list also contains the
    files of a playlist that finished before the error or the cancellation, so
    the caller can journal (and later undo) them. ``on_saved`` is called once
    per completed file, before the function returns or raises.
    """
    if archive is not None:
        try:
            archive.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass                     # yt-dlp reports the real problem below
    before = _archive_lines(archive) if archive is not None else []

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

    paths: list[Path] = []
    log_tail: list[str] = []

    def handle(line: str) -> None:
        if line.startswith(PROGRESS_MARK + SEP):
            _report_progress(line)
        elif line.startswith(FILE_MARK + SEP):
            paths.append(Path(line[len(FILE_MARK) + 1:]))
        elif line.strip():
            log_tail.append(line)
            del log_tail[:-LOG_TAIL]

    def collect() -> list[Saved]:
        """Finished files so far, with the archive ids that belong to them."""
        if archive is None:
            return [Saved(path, "") for path in paths]
        # yt-dlp appends one archive line per finished file, in the order of the
        # after_move prints; the new lines are exactly this run's archive ids.
        new_ids = _archive_lines(archive)[len(before):]
        return [Saved(path, new_ids[index] if index < len(new_ids) else "")
                for index, path in enumerate(paths)]

    def deliver(saved: list[Saved]) -> None:
        if on_saved is not None:
            for item in saved:
                on_saved(item)

    try:
        rc, error = _stream(argv, cancel, handle)
    except Cancelled:
        # Keep what finished before the cancel: the caller journals it, so a
        # half-done playlist stays undoable.
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
