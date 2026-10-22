"""The fetch feature: download audio with yt-dlp."""

from __future__ import annotations

from pathlib import Path

from ... import config, external, i18n, journal, output, redact
from ...cancel import NO_CANCEL, Cancelled
from ..base import CmdArgs, Feature, Option, Requirement, resolve_args
from . import download

AUDIO_FORMATS: tuple[str, ...] = ("mp3", "m4a", "opus", "flac")


def _duration_text(seconds: int | None) -> str:
    """Format a duration in seconds as ``M:SS`` or ``H:MM:SS`` (``?`` if unknown)."""
    if not seconds:
        return "?"
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def cmd_fetch(args: CmdArgs) -> int:
    """Preview a URL with yt-dlp and, on request, download it as audio."""
    args = resolve_args(FEATURE, args)
    cancel = getattr(args, "cancel", NO_CANCEL)

    lacking = external.missing(FEATURE, args)
    if lacking:
        output.message(external.format_missing(lacking))
        return 2

    url = str(args.url or "").strip()
    if not url:
        output.message(i18n.t("fetch.error.url"))
        return 2
    if url.startswith("-") or any(char in url for char in "\r\n\0"):
        output.message(i18n.t("fetch.error.url_invalid", url=url))
        return 2

    target = Path(str(args.target or "")).expanduser()
    if not target.is_dir():
        output.message(i18n.t("task.error.folder", path=target))
        return 2

    output.banner(i18n.t("fetch.title"), not args.apply)
    finished: list[download.Saved] = []
    try:
        entries, error = download.preview(url, playlist=args.playlist, cancel=cancel)
        if error:
            output.message(i18n.t("fetch.error.preview",
                                  detail=redact.text(error)))
            return 1
        if not entries:
            output.message(i18n.t("fetch.error.empty"))
            return 1

        output.message(i18n.t("fetch.preview.header", count=len(entries)))
        for entry in entries:
            output.report_plan("fetch", url=entry.url, title=entry.title,
                               duration=entry.duration)
            output.message(i18n.t("fetch.preview.entry", title=entry.title,
                                  duration=_duration_text(entry.duration)))

        if not args.apply:
            output.message(i18n.t("fetch.preview.only"))
            output.report_stats("fetch", files=len(entries), applied=False)
            return 0

        if not args.confirm:
            output.message(i18n.t("fetch.apply.needs_confirm"))
            return 2

        output.message(i18n.t("fetch.download.start", count=len(entries)))
        archive = None if args.no_archive else config.FETCH_ARCHIVE

        def remember(item: download.Saved) -> None:
            """Journal every finished file immediately - also a partial run."""
            finished.append(item)
            journal.record_download(item.path, redact.url(url), item.archive_id)
            output.message(i18n.t("fetch.download.file", path=item.path))

        saved, error = download.download(url, target, audio_format=args.audio_format,
                                         playlist=args.playlist,
                                         archive=archive, cancel=cancel,
                                         on_saved=remember)
        if error:
            output.message(i18n.t("fetch.error.download",
                                  detail=redact.text(error)))
            output.report_stats("fetch", files=len(finished), errors=1, applied=True)
            return 1
    except Cancelled:
        output.message(i18n.t("task.cancelled"))
        output.report_stats("fetch", files=len(finished), errors=0, applied=True,
                            cancelled=True)
        return 130

    output.message(i18n.t("fetch.download.done", files=len(saved)))
    output.report_stats("fetch", files=len(saved), applied=True)
    return 0


FEATURE = Feature(
    key="fetch",
    title_key="fetch.title",
    help_key="cli.fetch.help",
    run=cmd_fetch,
    options=(
        Option("url", "text", positional=True, help_key="cli.fetch.url"),
        Option("target", "folder", positional=True, help_key="cli.fetch.target"),
        Option("audio_format", "choice", "mp3", "cli.fetch.audio_format",
               flags=("--audio-format",), choices=AUDIO_FORMATS),
        Option("playlist", "bool", False, "cli.fetch.playlist",
               flags=("--playlist",)),
        Option("no_archive", "bool", False, "cli.fetch.no_archive",
               flags=("--no-archive",)),
        Option("apply", "bool", False, "cli.fetch.apply", flags=("--apply",)),
        Option("confirm", "bool", False, "cli.fetch.confirm", flags=("--confirm",)),
    ),
    requires=(Requirement((external.YT_DLP,)),
              Requirement((external.FFMPEG,), when="apply")),
    writes=True,
)
