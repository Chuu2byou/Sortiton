"""Command line: parse arguments, start the log and run the task."""

from __future__ import annotations

import argparse
import sys
import time

from . import external, i18n, journal, output, redact, settings
from .config import RULES_FILE
from .features import FEATURES
from .features.base import add_feature_parser
from .output import close_log_file, message, open_log_file
from .rules import load_custom_rules, rules_summary
from .tasks import (cmd_all, cmd_rename, cmd_restore, cmd_rules, cmd_scan, cmd_sort,
                    cmd_tags)

PATTERN_DEFAULT = "%artist% - %title%"

READ_COMMANDS = frozenset({"tags", "rename", "sort", "scan", "all"})
WRITE_COMMANDS = frozenset({"restore"})
#: Commands that write tags and require mutagen or ffmpeg.
TAG_WRITE_COMMANDS = frozenset({"tags", "all"})

_PROGRESS_INTERVAL = 0.1
_progress_last = 0.0
_progress_open = False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=i18n.t("cli.description"))
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-q", "--quiet", action="store_true", help=i18n.t("cli.quiet"))
    sub = parser.add_subparsers(dest="command", required=True)

    p_tags = sub.add_parser("tags", parents=[common], help=i18n.t("cli.tags.help"))
    p_tags.add_argument("folder", help=i18n.t("cli.tags.folder"))
    p_tags.add_argument("target", nargs="?", default=None, help=i18n.t("cli.tags.target"))
    p_tags.add_argument("--move", action="store_true", help=i18n.t("cli.tags.move"))
    p_tags.add_argument("--apply", action="store_true", help=i18n.t("cli.tags.apply"))
    p_tags.add_argument("--backup", action="store_true", help=i18n.t("cli.tags.backup"))
    p_tags.add_argument("--track-format", dest="track_format", default=None,
                        choices=settings.TRACK_FORMATS,
                        help=i18n.t("cli.tags.track_format"))
    p_tags.add_argument("--diff", action="store_true",
                        help=i18n.t("cli.tags.diff"))
    p_tags.add_argument("--diff-csv", dest="diff_csv", default=None,
                        help=i18n.t("cli.tags.diff_csv"))
    p_tags.set_defaults(func=cmd_tags)

    p_rename = sub.add_parser("rename", parents=[common], help=i18n.t("cli.rename.help"))
    p_rename.add_argument("folder", help=i18n.t("cli.rename.folder"))
    p_rename.add_argument("target", nargs="?", default=None,
                          help=i18n.t("cli.rename.target"))
    p_rename.add_argument("--pattern", default=PATTERN_DEFAULT,
                          help=i18n.t("cli.rename.pattern"))
    p_rename.add_argument("--move", action="store_true", help=i18n.t("cli.rename.move"))
    p_rename.add_argument("--apply", action="store_true", help=i18n.t("cli.rename.apply"))
    p_rename.set_defaults(func=cmd_rename)

    p_sort = sub.add_parser("sort", parents=[common], help=i18n.t("cli.sort.help"))
    p_sort.add_argument("source", help=i18n.t("cli.sort.source"))
    p_sort.add_argument("target", help=i18n.t("cli.sort.target"))
    p_sort.add_argument("--pattern", default=PATTERN_DEFAULT,
                        help=i18n.t("cli.sort.pattern"))
    p_sort.add_argument("--move", action="store_true", help=i18n.t("cli.sort.move"))
    p_sort.add_argument("--apply", action="store_true", help=i18n.t("cli.sort.apply"))
    p_sort.set_defaults(func=cmd_sort)

    p_all = sub.add_parser("all", parents=[common], help=i18n.t("cli.all.help"))
    p_all.add_argument("source", help=i18n.t("cli.all.source"))
    p_all.add_argument("target", help=i18n.t("cli.all.target"))
    p_all.add_argument("--pattern", default=PATTERN_DEFAULT,
                       help=i18n.t("cli.all.pattern"))
    p_all.add_argument("--move", action="store_true", help=i18n.t("cli.all.move"))
    p_all.add_argument("--apply", action="store_true", help=i18n.t("cli.all.apply"))
    p_all.add_argument("--backup", action="store_true", help=i18n.t("cli.all.backup"))
    p_all.add_argument("--track-format", dest="track_format", default=None,
                       choices=settings.TRACK_FORMATS,
                       help=i18n.t("cli.all.track_format"))
    p_all.add_argument("--diff", action="store_true",
                       help=i18n.t("cli.all.diff"))
    p_all.add_argument("--diff-csv", dest="diff_csv", default=None,
                       help=i18n.t("cli.all.diff_csv"))
    p_all.add_argument("--fetch-url", dest="fetch_url", default=None,
                       help=i18n.t("cli.all.fetch_url"))
    p_all.add_argument("--fetch-confirmed", dest="fetch_confirmed",
                       action="store_true", help=i18n.t("cli.all.fetch_confirmed"))
    p_all.set_defaults(func=cmd_all)

    p_scan = sub.add_parser("scan", parents=[common], help=i18n.t("cli.scan.help"))
    p_scan.add_argument("folder", help=i18n.t("cli.scan.folder"))
    p_scan.set_defaults(func=cmd_scan)

    p_rules = sub.add_parser("rules", parents=[common], help=i18n.t("cli.rules.help"))
    p_rules.add_argument("--template", action="store_true", help=i18n.t("cli.rules.template"))
    p_rules.add_argument("--builtin", action="store_true", help=i18n.t("cli.rules.builtin"))
    p_rules.set_defaults(func=cmd_rules)

    p_restore = sub.add_parser("restore", parents=[common], help=i18n.t("cli.restore.help"))
    p_restore.add_argument("--journal", default=None, help=i18n.t("cli.restore.journal"))
    p_restore.add_argument("--list", action="store_true", dest="list_journals",
                           help=i18n.t("cli.restore.list"))
    p_restore.add_argument("--apply", action="store_true", help=i18n.t("cli.restore.apply"))
    p_restore.add_argument("--backup", action="store_true", help=i18n.t("cli.restore.backup"))
    p_restore.add_argument("--keep-copies", action="store_true", dest="keep_copies",
                           help=i18n.t("cli.restore.keep_copies"))
    p_restore.set_defaults(func=cmd_restore)

    for feature in FEATURES:
        add_feature_parser(sub, feature, common)

    return parser


def console_progress(current: int, total: int, text: str = "") -> None:
    """Draw the progress line on stderr: throttled, ended with a newline."""
    global _progress_last, _progress_open
    now = time.monotonic()
    at_end = total <= 0 or current >= total
    if not at_end and now - _progress_last < _PROGRESS_INTERVAL:
        return
    _progress_last = now
    sys.stderr.write(f"\r  {current}/{total}  {text}")
    if at_end:
        sys.stderr.write("\n")
        _progress_open = False
    else:
        _progress_open = True
    sys.stderr.flush()


def _end_progress() -> None:
    """Close a progress line that the sink left open."""
    global _progress_open
    if _progress_open:
        sys.stderr.write("\n")
        sys.stderr.flush()
        _progress_open = False


def main() -> int:
    settings.apply_language()
    args = _build_parser().parse_args()

    feature = getattr(args, "feature", None)
    if feature is not None:
        lacking = external.missing(feature, args)
        if lacking:
            message(external.format_missing(lacking))
            return 2
    else:
        requirements = []
        if args.command in READ_COMMANDS:
            requirements.append(external.Requirement(
                (external.MUTAGEN, external.FFPROBE)))
        if getattr(args, "apply", False) and (
                args.command in WRITE_COMMANDS
                or args.command in TAG_WRITE_COMMANDS):
            requirements.append(external.Requirement(
                (external.MUTAGEN, external.FFMPEG)))
        lacking = [item for item in requirements
                   if not any(external.available(tool) for tool in item.any_of)]
        if lacking:
            message(external.format_missing(lacking))
            return 2

    if not getattr(args, "quiet", False) and sys.stderr.isatty():
        output.set_progress(console_progress)

    log = open_log_file(" ".join(redact.command(sys.argv[1:])))
    if log:
        message(i18n.t("cli.log_file", path=log))
    if getattr(args, "apply", False) and journal.enabled():
        if log is None or journal.open_for(log) is None:
            message(i18n.t("journal.error.open"))
            close_log_file(2)
            return 2

    show_rules = args.command != "rules" and (feature is None or feature.uses_rules)
    if show_rules:
        for warning in load_custom_rules():
            message(i18n.t("cli.rule_warning", text=warning))
        summary = rules_summary()
        if summary:
            message(i18n.t("cli.custom_rules", summary=summary, file=RULES_FILE.name))

    rc = 99
    try:
        rc = args.func(args)
    except KeyboardInterrupt:
        message("\n" + i18n.t("cli.cancelled"))
        rc = 130
    finally:
        _end_progress()
        journal.close()
        close_log_file(rc)
    return rc
