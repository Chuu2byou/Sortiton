"""Command line: parse arguments, start the log and run the task."""

from __future__ import annotations

import argparse
import shutil
import sys
import time

from . import external, i18n, journal, output, settings
from .config import RULES_FILE
from .features import FEATURES
from .features.base import add_feature_parser
from .output import close_log_file, message, open_log_file
from .rules import load_custom_rules, rules_summary
from .tasks import (cmd_all, cmd_rename, cmd_restore, cmd_rules, cmd_scan, cmd_sort,
                    cmd_tags)

PATTERN_DEFAULT = "%artist% - %title%"

# Console progress (P8): throttle the stderr line and close it at the end.
_PROGRESS_INTERVAL = 0.1
_progress_last = 0.0
_progress_open = False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=i18n.t("cli.description"))
    # -q/--quiet reaches every sub-command (built-in and feature) through this
    # parent; it only silences the progress line on stderr.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-q", "--quiet", action="store_true", help=i18n.t("cli.quiet"))
    sub = parser.add_subparsers(dest="command", required=True)

    p_tags = sub.add_parser("tags", parents=[common], help=i18n.t("cli.tags.help"))
    p_tags.add_argument("folder", help=i18n.t("cli.tags.folder"))
    p_tags.add_argument("--apply", action="store_true", help=i18n.t("cli.tags.apply"))
    p_tags.add_argument("--backup", action="store_true", help=i18n.t("cli.tags.backup"))
    p_tags.set_defaults(func=cmd_tags)

    p_rename = sub.add_parser("rename", parents=[common], help=i18n.t("cli.rename.help"))
    p_rename.add_argument("folder", help=i18n.t("cli.rename.folder"))
    p_rename.add_argument("--pattern", default=PATTERN_DEFAULT,
                          help=i18n.t("cli.rename.pattern"))
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

    # The features (export, later fetch) describe their own options; the CLI
    # only hands the shared list to the parser builder.
    for feature in FEATURES:
        add_feature_parser(sub, feature, common)

    return parser


def console_progress(current: int, total: int, text: str = "") -> None:
    """Draw the progress line on stderr: throttled, ended with a newline.

    Only the progress line is suppressed by ``--quiet``; ordinary messages are
    not. The sink is installed only for an interactive stderr, so a pipe or a
    log never sees carriage returns.
    """
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
        # A feature declares what it needs; the check matches the one in
        # cmd_export, so the GUI (which skips main) gets it too.
        lacking = external.missing(feature, args)
        if lacking:
            message(external.format_missing(lacking))
            return 2
    elif shutil.which("ffprobe") is None:      # unchanged for the built-in commands
        message(i18n.t("cli.error.ffprobe"))
        return 2

    if not getattr(args, "quiet", False) and sys.stderr.isatty():
        output.set_progress(console_progress)

    log = open_log_file(" ".join(sys.argv[1:]))
    if log:
        message(i18n.t("cli.log_file", path=log))
    if log and getattr(args, "apply", False):
        # Only a run that writes gets a journal; a preview leaves no file.
        journal.open_for(log)

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
