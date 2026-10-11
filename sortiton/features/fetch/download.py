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
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
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
             no_archive: bool, cancel=None) -> tuple[list[Path], str]:
    """Download ``url`` as audio into ``target``; return the finished paths.

    ``no_archive`` is accepted for the option already defined in step 4.2; the
    download archive itself (``--download-archive``) is step 4.4, so it is not
    passed yet. ``--no-overwrites`` keeps yt-dlp from replacing an existing
    file, matching the project rule that nothing is ever overwritten. Returns
    ``(paths, "")`` on success and ``([], error)`` on failure.
    """
    argv = ["yt-dlp", "--no-simulate", "--newline", "--no-warnings",
            "-x", "--audio-format", audio_format, "--audio-quality", "0",
            "--embed-metadata", "--embed-thumbnail", "--no-overwrites",
            "--progress", "--progress-template", PROGRESS_TEMPLATE,
            "--print", DOWNLOAD_PRINT,
            "-P", str(target), "-o", "%(title)s.%(ext)s"]
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

    rc, error = _stream(argv, cancel, handle)
    if rc != 0:
        detail = error or "\n".join(log_tail)
        return [], detail or i18n.t("fetch.error.exit", rc=rc)
    return paths, ""


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
