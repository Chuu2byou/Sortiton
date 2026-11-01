"""Command line: parse arguments, start the log and run the task."""

from __future__ import annotations

import argparse
import sys
import time

from . import config, external, i18n, journal, output, redact, settings
from .core_features import CORE_FEATURES, PATTERN_DEFAULT as _PATTERN_DEFAULT
from .features import FEATURES
from .features.base import add_feature_parser, add_options
from .output import close_log_file, message, open_log_file
from .rules import load_custom_rules, rules_summary
from .tasks import (cmd_all, cmd_rename, cmd_restore, cmd_rules, cmd_scan, cmd_sort,
                    cmd_tags)

PATTERN_DEFAULT = _PATTERN_DEFAULT

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

    commands = {"tags": cmd_tags, "rename": cmd_rename, "sort": cmd_sort, "all": cmd_all}
    for feature in CORE_FEATURES:
        command = sub.add_parser(feature.key, parents=[common],
                                 help=i18n.t(f"cli.{feature.key}.help"))
        add_options(command, feature.options)
        command.set_defaults(func=commands[feature.key])

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
            message(i18n.t("cli.custom_rules", summary=summary, file=config.current_paths().rules_file.name))

    rc = 99
    try:
        rc = output.default_run_context().execute(lambda: args.func(args)).returncode
    except KeyboardInterrupt:
        message("\n" + i18n.t("cli.cancelled"))
        rc = 130
    finally:
        _end_progress()
        journal.close()
        close_log_file(rc)
    return rc
