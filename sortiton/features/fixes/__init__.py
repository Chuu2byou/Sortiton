"""The fixes feature: apply single tag corrections from a CSV."""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from ... import external, i18n, journal, output
from ...backup import backup_files
from ...cancel import NO_CANCEL, Cancelled
from ...config import AUDIO_EXTENSIONS
from ...tags import read_info, write_tags
from ..base import CmdArgs, Feature, Option, Requirement, resolve_args
from . import parse

JOIN_SEP = "; "

MULTI_VALUE_FIELDS = {"artist", "album_artist", "genre"}
_VALUE_SPLIT = re.compile(r"\s*[|;]\s*")


@dataclass
class _Action:
    """One row that will really change a tag (current value matches ``old``)."""

    line: int
    path: Path
    field: str
    current: str
    new: str


def _value_list(text: str) -> list[str]:
    """Split a multi-value tag cell at ``|`` and ``;`` (both joins are in use)."""
    return [part for part in (item.strip() for item in _VALUE_SPLIT.split(text)) if part]


def _same_value(left: str, right: str) -> bool:
    """True when two renderings name the same values (separator-independent)."""
    if left.strip() == right.strip():
        return True
    return _value_list(left) == _value_list(right)


def _normalised_new(field: str, value: str) -> str:
    """Store a CSV value in the ``; `` form ``write_tags`` understands."""
    if field not in MULTI_VALUE_FIELDS or "|" not in value:
        return value
    return "; ".join(_value_list(value))


def cmd_fixes(args: CmdArgs) -> int:
    """Apply (or preview) single tag corrections from a CSV file."""
    args = resolve_args(FEATURE, args)
    cancel = getattr(args, "cancel", NO_CANCEL)

    lacking = external.missing(FEATURE, args)
    if lacking:
        output.message(external.format_missing(lacking))
        return 2

    csv_path = Path(str(getattr(args, "file", "") or "")).expanduser()
    if not csv_path.is_file():
        output.message(i18n.t("fixes.error.csv", path=csv_path))
        return 2
    try:
        text = csv_path.read_text(encoding="utf-8-sig")
    except OSError as error:
        output.message(i18n.t("fixes.error.read", path=csv_path, error=error))
        return 2

    root: Path | None = None
    root_text = str(getattr(args, "root", "") or "").strip()
    if root_text:
        root = Path(root_text).expanduser().resolve()
        if not root.is_dir():
            output.message(i18n.t("task.error.folder", path=root))
            return 2

    output.banner(i18n.t("fixes.title"), not args.apply)
    output.message(i18n.t("fixes.label.csv", value=csv_path))

    rows = parse.read_csv(text)
    if not rows:
        output.message(i18n.t("fixes.error.no_rows", path=csv_path))
        return 1

    actions, skipped, problems = _prepare(rows, root)
    output.message(i18n.t("fixes.label.rows", value=len(rows)))
    output.message()

    for action in actions:
        output.report_plan("tags", path=action.path,
                           changes={action.field: (action.current, action.new)})
        output.message(f"  {action.path.name}")
        output.message(f"      {action.field:<13} '{action.current}'  ->  '{action.new}'")
        if action.new == "":
            output.message(i18n.t("fixes.warn.empty", field=action.field))

    for line, path_text, field, expected, current in skipped:
        output.message(i18n.t("fixes.skip.changed", line=line, path=path_text,
                              field=field, expected=expected, current=current))

    for line, key, values in problems:
        output.message(i18n.t("fixes.row_error", line=line,
                              reason=i18n.t(key, **values)))

    changed = len(actions)
    errors = len(problems)
    write_errors = 0
    backup_folder: Path | None = None

    if args.apply and actions:
        if getattr(args, "backup", False):
            backup_folder = _backup_files(root or csv_path.parent,
                                          [action.path for action in actions])
            if backup_folder is None:
                _report(rows, 0, len(skipped), errors, args, None)
                return 2

        output.message()
        output.message(i18n.t("fixes.writing", count=changed))
        done = 0
        for action in actions:
            try:
                cancel.check()
            except Cancelled:
                output.message(i18n.t("task.cancelled"))
                _report(rows, done, len(skipped), errors, args, backup_folder)
                return 130
            try:
                _write(action)
                done += 1
                output.message(i18n.t("task.ok", name=action.path.name))
            except Exception as error:  # noqa: BLE001 - one file must not stop the rest
                journal.record_failure("tags", error, path=str(action.path),
                                       before={action.field: action.current})
                errors += 1
                write_errors += 1
                output.message(i18n.t("task.error.file", name=action.path.name,
                                      error=error))

    if not actions and not skipped and errors:
        _report(rows, 0, 0, errors, args, backup_folder)
        return 1

    _finish(changed, len(skipped), len(rows), errors, args)
    _report(rows, changed, len(skipped), errors, args, backup_folder)
    return 1 if write_errors else 0


def _prepare(rows: list[parse.FixRow], root: Path | None
             ) -> tuple[list[_Action], list[tuple[int, str, str, str, str]],
                        list[tuple[int, str, dict]]]:
    """Check every row: the usable actions, the skips and the row errors."""
    prepared: list[tuple[parse.FixRow, Path]] = []
    problems: list[tuple[int, str, dict]] = []

    for row in rows:
        if row.error:
            problems.append((row.line, row.error, row.error_args))
            continue
        if not row.field:
            problems.append((row.line, "fixes.error.field",
                             {"field": row.field_text}))
            continue
        path, key = parse.resolve_path(root, row.path)
        if key:
            problems.append((row.line, key, {"path": row.path}))
            continue
        if path.suffix.lower() not in AUDIO_EXTENSIONS:
            problems.append((row.line, "fixes.error.extension", {"path": row.path}))
            continue
        if not path.is_file():
            problems.append((row.line, "fixes.error.missing_file", {"path": row.path}))
            continue
        if not parse.value_ok(row.field, row.new):
            problems.append((row.line, "fixes.error.value",
                             {"field": row.field, "value": row.new}))
            continue
        prepared.append((row, path))

    counts: dict[tuple[Path, str], int] = {}
    for row, path in prepared:
        key = (path, row.field)
        counts[key] = counts.get(key, 0) + 1

    actions: list[_Action] = []
    skipped: list[tuple[int, str, str, str, str]] = []
    for row, path in prepared:
        if counts[(path, row.field)] > 1:
            problems.append((row.line, "fixes.error.duplicate",
                             {"path": row.path, "field": row.field}))
            continue
        info = read_info(path)
        if info.error:
            problems.append((row.line, "fixes.error.unreadable", {"path": row.path}))
            continue
        current = info.joined(row.field, JOIN_SEP).strip()
        if current != row.old.strip():
            skipped.append((row.line, row.path, row.field, row.old, current))
            continue
        actions.append(_Action(row.line, path, row.field, current, row.new))
    return actions, skipped, problems


def _write(action: _Action) -> None:
    """Write one correction and remember it in the journal (after the write)."""
    if write_tags(action.path, {action.field: action.new}) is False:
        raise RuntimeError(f"tags could not be written: {action.path.name}")
    journal.record_tags(action.path, {action.field: action.current},
                        {action.field: action.new})


def _finish(changed: int, skipped: int, total: int, errors: int, args: CmdArgs) -> None:
    """Close the run with the boxed summary every command ends with."""
    line = "=" * 62
    output.message()
    output.message(line)
    output.message(i18n.t("fixes.done", changed=changed, skipped=skipped, total=total))
    if errors:
        output.message(i18n.t("task.error.count", count=errors))
    if not args.apply and changed:
        output.message(i18n.t("fixes.hint.apply"))
    output.message(line)


def _report(rows: list[parse.FixRow], changed: int, skipped: int, errors: int,
            args: CmdArgs, backup_folder: Path | None) -> None:
    """Publish the counters the GUI shows (files/changed/skipped/errors)."""
    output.report_stats("fixes", files=len(rows), changed=changed, skipped=skipped,
                        errors=errors, applied=bool(args.apply),
                        backup=str(backup_folder) if backup_folder else "")


def _backup_files(root: Path, paths: list[Path]) -> Path | None:
    """Backwards-compatible name for the shared backup helper."""
    return backup_files(root, paths)


FEATURE = Feature(
    key="fixes",
    title_key="fixes.title",
    help_key="cli.fixes.help",
    run=cmd_fixes,
    options=(
        Option("file", "text", positional=True, help_key="cli.fixes.file"),
        Option("root", "folder", None, "cli.fixes.root",
               flags=("-r", "--root")),
        Option("apply", "bool", False, "cli.fixes.apply", flags=("--apply",)),
        Option("backup", "bool", False, "cli.fixes.backup", flags=("--backup",)),
    ),
    requires=(Requirement(any_of=(external.MUTAGEN, external.FFPROBE)),
              Requirement(any_of=(external.MUTAGEN, external.FFMPEG),
                          when="apply")),
    writes=True,
)
