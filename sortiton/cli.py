"""Command line: parse arguments, start the log and run the task."""

from __future__ import annotations

import argparse
import shutil
import sys

from . import i18n, journal, settings
from .config import RULES_FILE
from .output import close_log_file, message, open_log_file
from .rules import load_custom_rules, rules_summary
from .tasks import (cmd_all, cmd_rename, cmd_restore, cmd_rules, cmd_scan, cmd_sort,
                    cmd_tags)

PATTERN_DEFAULT = "%artist% - %title%"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=i18n.t("cli.description"))
    sub = parser.add_subparsers(dest="command", required=True)

    p_tags = sub.add_parser("tags", help=i18n.t("cli.tags.help"))
    p_tags.add_argument("folder", help=i18n.t("cli.tags.folder"))
    p_tags.add_argument("--apply", action="store_true", help=i18n.t("cli.tags.apply"))
    p_tags.add_argument("--backup", action="store_true", help=i18n.t("cli.tags.backup"))
    p_tags.set_defaults(func=cmd_tags)

    p_rename = sub.add_parser("rename", help=i18n.t("cli.rename.help"))
    p_rename.add_argument("folder", help=i18n.t("cli.rename.folder"))
    p_rename.add_argument("--pattern", default=PATTERN_DEFAULT,
                          help=i18n.t("cli.rename.pattern"))
    p_rename.add_argument("--apply", action="store_true", help=i18n.t("cli.rename.apply"))
    p_rename.set_defaults(func=cmd_rename)

    p_sort = sub.add_parser("sort", help=i18n.t("cli.sort.help"))
    p_sort.add_argument("source", help=i18n.t("cli.sort.source"))
    p_sort.add_argument("target", help=i18n.t("cli.sort.target"))
    p_sort.add_argument("--pattern", default=PATTERN_DEFAULT,
                        help=i18n.t("cli.sort.pattern"))
    p_sort.add_argument("--move", action="store_true", help=i18n.t("cli.sort.move"))
    p_sort.add_argument("--apply", action="store_true", help=i18n.t("cli.sort.apply"))
    p_sort.set_defaults(func=cmd_sort)

    p_all = sub.add_parser("all", help=i18n.t("cli.all.help"))
    p_all.add_argument("source", help=i18n.t("cli.all.source"))
    p_all.add_argument("target", help=i18n.t("cli.all.target"))
    p_all.add_argument("--pattern", default=PATTERN_DEFAULT,
                       help=i18n.t("cli.all.pattern"))
    p_all.add_argument("--move", action="store_true", help=i18n.t("cli.all.move"))
    p_all.add_argument("--apply", action="store_true", help=i18n.t("cli.all.apply"))
    p_all.add_argument("--backup", action="store_true", help=i18n.t("cli.all.backup"))
    p_all.set_defaults(func=cmd_all)

    p_scan = sub.add_parser("scan", help=i18n.t("cli.scan.help"))
    p_scan.add_argument("folder", help=i18n.t("cli.scan.folder"))
    p_scan.set_defaults(func=cmd_scan)

    p_rules = sub.add_parser("rules", help=i18n.t("cli.rules.help"))
    p_rules.add_argument("--template", action="store_true", help=i18n.t("cli.rules.template"))
    p_rules.add_argument("--builtin", action="store_true", help=i18n.t("cli.rules.builtin"))
    p_rules.set_defaults(func=cmd_rules)

    p_restore = sub.add_parser("restore", help=i18n.t("cli.restore.help"))
    p_restore.add_argument("--journal", default=None, help=i18n.t("cli.restore.journal"))
    p_restore.add_argument("--list", action="store_true", dest="list_journals",
                           help=i18n.t("cli.restore.list"))
    p_restore.add_argument("--apply", action="store_true", help=i18n.t("cli.restore.apply"))
    p_restore.add_argument("--backup", action="store_true", help=i18n.t("cli.restore.backup"))
    p_restore.add_argument("--keep-copies", action="store_true", dest="keep_copies",
                           help=i18n.t("cli.restore.keep_copies"))
    p_restore.set_defaults(func=cmd_restore)

    return parser


def main() -> int:
    settings.apply_language()
    args = _build_parser().parse_args()

    if shutil.which("ffprobe") is None:
        message(i18n.t("cli.error.ffprobe"))
        return 2

    log = open_log_file(" ".join(sys.argv[1:]))
    if log:
        message(i18n.t("cli.log_file", path=log))
    if log and getattr(args, "apply", False):
        # Only a run that writes gets a journal; a preview leaves no file.
        journal.open_for(log)

    if args.command != "rules":
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
        journal.close()
        close_log_file(rc)
    return rc
