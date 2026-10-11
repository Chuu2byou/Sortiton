"""The fetch feature: download audio with yt-dlp (step 4.2: definition).

``sortiton fetch URL FOLDER`` downloads the given track - or, with
``--playlist``, the whole playlist - as audio into ``FOLDER``. The command
writes, so it needs ``--apply`` and (see step 4.3) an explicit ``--confirm``;
without both it must stay a network-free no-op. yt-dlp is never bundled: it is
looked up on the user's ``PATH`` (step 4.1).

This module defines the feature and its options only. The network part - a
preview that parses ``yt-dlp --simulate`` and the confirmed download - is step
4.3 and will replace the body of :func:`cmd_fetch`; until then the function only
checks the tool and the arguments and never touches the network, so nothing is
ever downloaded.
"""

from __future__ import annotations

from pathlib import Path

from ... import external, i18n, output
from ..base import CmdArgs, Feature, Option, Requirement, resolve_args

#: Audio formats ``--audio-format`` accepts for our downloads (a subset of the
#: formats yt-dlp supports: best, aac, alac, flac, m4a, mp3, opus, vorbis, wav).
AUDIO_FORMATS: tuple[str, ...] = ("mp3", "m4a", "opus", "flac")


def cmd_fetch(args: CmdArgs) -> int:
    """Validate the input for ``sortiton fetch`` (step 4.2: definition only).

    Returns 0 on success, 2 on a bad input or a missing tool. The network part
    (preview with ``yt-dlp --simulate``, confirmation, download) is step 4.3;
    until it lands this function only checks the tool and the arguments and
    reports that the download is not wired yet, so it never downloads and never
    writes.
    """
    args = resolve_args(FEATURE, args)

    # The GUI does not go through cli.main, so the tool check lives here too.
    lacking = external.missing(FEATURE, args)
    if lacking:
        output.message(external.format_missing(lacking))
        return 2

    if not str(args.url or "").strip():
        output.message(i18n.t("fetch.error.url"))
        return 2

    target = Path(str(args.target or "")).expanduser()
    if not target.is_dir():
        output.message(i18n.t("task.error.folder", path=target))
        return 2

    # Step 4.3 wires the yt-dlp preview and download here. Until then the run
    # stops after the checks and reports that nothing was loaded.
    output.message(i18n.t("fetch.error.pending"))
    return 2


#: The one description the CLI and the GUI share.
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
        # A bool with default True is not supported by base.py yet, so the
        # archive is opt-out: the flag turns it off instead of on.
        Option("no_archive", "bool", False, "cli.fetch.no_archive",
               flags=("--no-archive",)),
        Option("apply", "bool", False, "cli.fetch.apply", flags=("--apply",)),
        Option("confirm", "bool", False, "cli.fetch.confirm", flags=("--confirm",)),
    ),
    requires=(Requirement((external.YT_DLP,)),),
    writes=True,
)
