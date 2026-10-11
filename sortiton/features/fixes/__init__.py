"""The fixes feature: apply single tag corrections from a CSV.

``sortiton fixes datei.csv [--root ORDNER] [--apply] [--backup]`` reads a CSV
with the columns ``path;field;old;new`` (a header is optional), checks every row
against the current tags and - only with ``--apply`` - writes the corrections.
Without ``--apply`` it is a pure preview.

This closes the loop with the export: the report asks the LLM for corrections in
exactly this CSV shape. The command writes, so it needs ``--apply`` and gets a
journal entry per changed file (undo via ``sortiton restore``).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ... import external, i18n, journal, output
from ...cancel import NO_CANCEL, Cancelled
from ...config import AUDIO_EXTENSIONS, BACKUP_DIR, BACKUP_KEEP
from ...tags import read_info, write_tags
from ..base import CmdArgs, Feature, Option, Requirement, resolve_args
from . import parse

#: Separator the export uses when it joins several tag values into one cell.
JOIN_SEP = "; "


@dataclass
class _Action:
    """One row that will really change a tag (current value matches ``old``)."""

    line: int
    path: Path
    field: str
    current: str
    new: str


def cmd_fixes(args: CmdArgs) -> int:
    """Apply (or preview) single tag corrections from a CSV file.

    Returns 0 on success, 1 when no row could be used, 2 on a bad input or a
    missing tool, 130 when the run was cancelled.
    """
    args = resolve_args(FEATURE, args)
    cancel = getattr(args, "cancel", NO_CANCEL)

    # The GUI does not go through cli.main, so the tool check lives here too.
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
        # The preview card and the log show exactly what would be written.
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
    backup_folder: Path | None = None

    if args.apply and actions:
        if getattr(args, "backup", False):
            backup_folder = _backup_files(root or csv_path.parent,
                                          [action.path for action in actions])

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
                output.message(i18n.t("task.error.file", name=action.path.name,
                                      error=error))

    if not actions and not skipped and errors:
        # Nothing could even be checked - treat it as a failed input.
        _report(rows, 0, 0, errors, args, backup_folder)
        return 1

    _finish(changed, len(skipped), len(rows), errors, args)
    _report(rows, changed, len(skipped), errors, args, backup_folder)
    return 0


def _prepare(rows: list[parse.FixRow], root: Path | None
             ) -> tuple[list[_Action], list[tuple[int, str, str, str, str]],
                        list[tuple[int, str, dict]]]:
    """Check every row: the usable actions, the skips and the row errors.

    A row is rejected when its field, path, extension, new value or readability
    is not usable. Two rows naming the same (path, field) are errors for both -
    nothing is written for them, so the correction stays unambiguous.
    """
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
    write_tags(action.path, {action.field: action.new})
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
    """Copy the files that are about to change into a fresh backup folder.

    A feature may not import :mod:`sortiton.tasks`, so the small backup helper
    lives here; it mirrors ``tasks._backup_files`` (same folder name, same path
    below ``root``) so undo stays a plain copy.
    """
    folder = BACKUP_DIR / f"backup_{datetime.now():%Y-%m-%d_%H-%M-%S}"
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        output.message(i18n.t("task.backup.failed", path=folder, error=error))
        return None

    copied = 0
    for path in paths:
        try:
            relative = path.relative_to(root)
        except ValueError:
            relative = Path(path.name)
        try:
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(path), str(target))
            copied += 1
        except OSError as error:
            output.message(i18n.t("task.backup.file_error", name=path.name, error=error))

    output.message(i18n.t("task.backup.done", count=copied, path=folder))
    _prune_backups()
    return folder


def _prune_backups(keep: int = BACKUP_KEEP) -> None:
    """Keep only the most recent backup folders (mirrors the task's helper)."""
    try:
        folders = sorted((folder for folder in BACKUP_DIR.glob("backup_*")
                          if folder.is_dir()), key=lambda path: path.name, reverse=True)
        for old in folders[keep:]:
            shutil.rmtree(old, ignore_errors=True)
    except OSError:
        pass


#: The one description the CLI and the GUI share.
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
    requires=(Requirement(any_of=(external.MUTAGEN, external.FFPROBE)),),
    writes=True,
)
