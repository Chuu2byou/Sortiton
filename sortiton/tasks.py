"""The tasks: tags / rename / sort / all / rules."""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

from . import i18n, journal
from .backup import backup_files, prune_backups
from .cancel import NO_CANCEL, Cancelled
from .config import (BACKUP_KEEP, COPY_WORKERS, FALLBACK_ARTIST, LOG_DIR,
                     RULES_FILE, WRITE_WORKERS)
from .fileops import atomic_write_text, copy_new, move_no_clobber
from .files import build_name, free_target, iter_audio, safe_name, same_content
from .output import (progress, banner, clear_stats, colorize, last_stats, message,
                     report_plan, report_stats)
from .rules import (builtin_rules_text, clean_artist, clean_genre, clean_text_field,
                    load_custom_rules, rules_summary, rules_template)
from .rules import snapshot as rules_snapshot
from .settings import resolve_track_format
from .tags import TAG_FIELDS, probe_many, read_info, write_tags

CmdArgs = argparse.Namespace | SimpleNamespace

_SUMMARY_LINE = "=" * 62
_STEP_LINE = "#" * 62

#: ``1``, ``01`` or ``3/12`` - only these forms are normalised.
_NUMBER_RE = re.compile(r"^(\d+)(?:/\d+)?$")


def _normalise_number(value: str, mode: str) -> str:
    """Normalise a track/disc value without touching anything unexpected.

    ``keep`` returns the value unchanged.  ``number`` turns ``1/11`` into
    ``1``; ``padded`` additionally writes ``01``.  Values that are not a
    plain number (``A1``, ``1a``, empty, ``1; 2``) stay as they are.
    """
    text = (value or "").strip()
    if not text or mode not in ("number", "padded"):
        return value
    match = _NUMBER_RE.match(text)
    if match is None:
        return value
    number = int(match.group(1))
    return f"{number:02d}" if mode == "padded" else str(number)


def _relative_name(root: Path, path: Path) -> str:
    """Path for a diff line: relative to ``root`` when possible."""
    try:
        return str(path.relative_to(root))
    except (ValueError, OSError):
        return str(path)


def _print_tag_diff(groups: dict[str, dict[tuple[str, str], list[Path]]],
                    root: Path) -> None:
    """Print the planned tag changes grouped by field and old/new value."""
    message()
    message(i18n.t("task.diff.title"))
    if not groups:
        message(i18n.t("task.diff.none"))
        return
    for field in TAG_FIELDS:
        entries = groups.get(field)
        if not entries:
            continue
        message(f"  {field}")
        for (old, new), paths in sorted(
                entries.items(), key=lambda item: (item[0][0].casefold(),
                                                   item[0][1].casefold())):
            old_text = colorize(old or "∅", "red")
            new_text = colorize(new or "∅", "green")
            message(f"    {old_text}  ->  {new_text}  ({len(paths)})")
            for path in sorted(paths, key=lambda item: str(item).casefold()):
                message(f"      {colorize(_relative_name(root, path), 'dim')}")


def _write_diff_csv(groups: dict[str, dict[tuple[str, str], list[Path]]],
                    target: Path) -> int:
    """Write the planned tag changes in the ``fixes`` CSV format; return the rows."""
    def absolute(path: Path) -> str:
        try:
            return str(path.resolve())
        except OSError:
            return str(path)

    rows: list[tuple[str, str, str, str]] = []
    for field in TAG_FIELDS:
        for (old, new), paths in groups.get(field, {}).items():
            for path in paths:
                rows.append((absolute(path), field, old, new))
    rows.sort(key=lambda row: (row[0].casefold(), TAG_FIELDS.index(row[1])))

    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";", lineterminator="\n")
    writer.writerow(("path", "field", "old", "new"))
    writer.writerows(rows)
    atomic_write_text(target, stream.getvalue())
    return len(rows)


def _no_clobber_copy(source: Path, target: Path) -> None:
    """Copy ``source`` to a *new* ``target``; never overwrite one."""
    copy_new(source, target)


def _no_clobber_move(source: Path, target: Path) -> None:
    """Move ``source`` to ``target`` only when the name is still free."""
    move_no_clobber(source, target)


def _backup_files(root: Path, paths: list[Path]) -> Path | None:
    """Backwards-compatible name for the shared backup helper."""
    return backup_files(root, paths)


def _prune_backups(keep: int = BACKUP_KEEP) -> None:
    """Backwards-compatible name for the shared retention helper."""
    prune_backups(keep)


def _library_path(target: Path, tags: dict, name: str) -> Path:
    """Destination in ``target``: artist/album/file (artist/file without album)."""
    artist = tags["album_artist"] or tags["artist"] or FALLBACK_ARTIST
    album = tags["album"]
    folder = Path(safe_name(artist))
    if album:
        folder = folder / safe_name(album)
    return target / folder / name


def _placement(source: Path, tags: dict, target: Path, used: set[str],
               name: str | None = None, *, skip_identical: bool = True
               ) -> Path | None:
    """Free destination for ``source`` - or None when it already is in place."""
    destination = _library_path(target, tags, name or source.name)
    try:
        if destination.resolve() == source.resolve():
            return None
    except OSError:
        if destination == source:
            return None
    if skip_identical and destination.exists() and same_content(source, destination):
        return None
    return free_target(destination, used, ignore=source)


def _target_name(target: Path, path: Path) -> str:
    """Path relative to the library root, for log lines."""
    try:
        return str(path.relative_to(target))
    except (ValueError, OSError):
        return path.name


def _place_files(plan: list[tuple[Path, Path]], target: Path, move: bool,
                 apply: bool, cancel) -> tuple[int, int]:
    """Copy/move planned files into the library; returns (placed, errors)."""
    if not plan:
        return 0, 0
    if not apply:
        for source, destination in plan:
            message(f"  {source.name}  ->  {_target_name(target, destination)}")
        return 0, 0

    placed = 0
    errors = 0
    lock = threading.Lock()

    def place(source: Path, destination: Path) -> None:
        nonlocal placed, errors
        cancel.check()
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            cancel.check()
            if move:
                _no_clobber_move(source, destination)
            else:
                _no_clobber_copy(source, destination)
            journal.record_move("sort" if move else "copy", source, destination,
                                mode="move" if move else "copy")
            with lock:
                placed += 1
                message(f"  {source.name}  ->  {_target_name(target, destination)}")
        except Cancelled:
            raise
        except Exception as error:
            journal.record_failure("sort", error, source=str(source),
                                   target=str(destination))
            with lock:
                errors += 1
                message(i18n.t("task.error.file", name=source.name, error=error))

    pool = ThreadPoolExecutor(max_workers=COPY_WORKERS)
    futures = [pool.submit(place, source, destination) for source, destination in plan]
    try:
        for done, future in enumerate(as_completed(futures), start=1):
            cancel.check()
            future.result()
            progress(done, len(plan), i18n.t("task.progress.sorting"))
    except Cancelled:
        for future in futures:
            future.cancel()
        raise
    finally:
        pool.shutdown(wait=True)
    return placed, errors


def _finish(key: str, fields: dict, *, changed: int, errors: int, applied: bool,
            hint: str = "task.hint.apply_run") -> None:
    """Close a run: the summary block every command ends with."""
    message()
    message(_SUMMARY_LINE)
    message(i18n.t(key, **fields))
    if errors:
        message(i18n.t("task.error.count", count=errors))
    if not applied and changed:
        message(i18n.t(hint))
    message(_SUMMARY_LINE)


def cmd_tags(args: CmdArgs) -> int:
    """Clean the tags of every audio file below ``args.folder``."""
    cancel = getattr(args, "cancel", NO_CANCEL)
    root = Path(args.folder).expanduser()
    if not root.is_dir():
        message(i18n.t("task.error.folder", path=root))
        return 2
    target = Path(args.target).expanduser() if getattr(args, "target", None) else None
    move = bool(getattr(args, "move", False))
    if move and target is None:
        message(i18n.t("task.error.target_required"))
        return 2

    banner(i18n.t("task.title.tags"), not args.apply)
    files = list(iter_audio(root))
    total = len(files)
    message(i18n.t("task.label.folder", value=root))
    if target is not None:
        message(i18n.t("task.label.target", value=target))
        message(i18n.t("task.label.mode",
                       value=i18n.t("task.action.move") if move
                       else i18n.t("task.action.copy")))
    message(i18n.t("task.label.files", value=total))
    message()

    try:
        unreadable: list[Path] = []
        tags_list = probe_many(files, report=lambda i, name: progress(i, total, name),
                               cancel=cancel, unreadable=unreadable)
    except Cancelled:
        message(i18n.t("task.cancelled"))
        return 130

    plan: list[tuple[Path, dict, dict]] = []
    placements: list[tuple[Path, Path]] = []
    used: set[str] = set()
    bad = set(unreadable)
    custom = rules_snapshot()
    track_format = (getattr(args, "track_format", None)
                    or resolve_track_format())
    diff_mode = bool(getattr(args, "diff", False))
    diff_csv_path = (Path(str(getattr(args, "diff_csv", "") or "")).expanduser()
                     if getattr(args, "diff_csv", None) else None)
    diff_groups: dict[str, dict[tuple[str, str], list[Path]]] = {}
    try:
        for path, tags in zip(files, tags_list):
            cancel.check()
            if path in bad:
                continue
            new = {
                "artist":       clean_artist(tags["artist"], custom),
                "album_artist": clean_artist(tags["album_artist"], custom),
                "title":        clean_text_field(tags["title"]),
                "album":        clean_text_field(tags["album"]),
                "genre":        clean_genre(tags["genre"], custom),
                "track":        _normalise_number(tags.get("track", ""), track_format),
                "disc":         _normalise_number(tags.get("disc", ""), track_format),
            }
            pipeline_state = getattr(args, "pipeline_state", None)
            if pipeline_state is not None:
                pipeline_state["tags"][path] = {**tags, **new}
                pipeline_state["paths"].setdefault(path, path)
            diff = {k: v for k, v in new.items() if v != tags.get(k, "")}
            destination = None
            if target is not None:
                destination = _placement(path, {**tags, **new}, target, used,
                                          skip_identical=not diff)
                if destination is not None:
                    placements.append((path, destination))

            if diff or destination is not None:
                report_plan("tags", path=path,
                            changes={key: (tags.get(key, ""), value)
                                     for key, value in diff.items()},
                            source=str(path),
                            target=str(destination) if destination is not None else "")
            if not diff:
                continue

            if diff_mode or diff_csv_path is not None:
                for key, value in diff.items():
                    group = diff_groups.setdefault(key, {})
                    group.setdefault((tags.get(key, ""), value), []).append(path)

            plan.append((path, tags, diff))
            if not diff_mode:
                message(f"  {path.name}")
                for key, value in diff.items():
                    message(f"      {key:<13} '{tags.get(key, '')}'  ->  '{value}'")
    except Cancelled:
        message(i18n.t("task.cancelled"))
        return 130

    if diff_mode:
        _print_tag_diff(diff_groups, root)
    if diff_csv_path is not None:
        try:
            rows = _write_diff_csv(diff_groups, diff_csv_path)
        except OSError as error:
            message(i18n.t("task.diff.csv_error", path=diff_csv_path, error=error))
            return 2
        message(i18n.t("task.diff.csv", path=diff_csv_path, count=rows))

    changed = len(plan)
    errors = 0
    for path in unreadable:
        message(i18n.t("task.error.unreadable", name=path.name))
    backup_folder: Path | None = None
    done_count = 0
    failed: set[Path] = set()

    if args.apply and plan:
        if getattr(args, "backup", False):
            backup_folder = _backup_files(root, [path for path, _, _ in plan])
            if backup_folder is None:
                message(i18n.t("task.backup.aborted"))
                return 2

        message()
        message(i18n.t("task.writing", count=changed))
        lock = threading.Lock()

        def store(path: Path, before: dict, diff: dict) -> None:
            nonlocal done_count, errors
            old = {key: before[key] for key in diff}
            try:
                cancel.check()
                if write_tags(path, diff) is False:
                    raise RuntimeError(f"tags could not be written: {path.name}")
                journal.record_tags(path, old, diff)
                with lock:
                    done_count += 1
                    message(i18n.t("task.ok", name=path.name))
            except Cancelled:
                raise
            except Exception as error:
                journal.record_failure("tags", error, path=str(path), before=old)
                with lock:
                    failed.add(path)
                    errors += 1
                    message(i18n.t("task.error.file", name=path.name, error=error))

        pool = ThreadPoolExecutor(max_workers=WRITE_WORKERS)
        futures = [pool.submit(store, path, before, diff)
                   for path, before, diff in plan]
        try:
            for done, future in enumerate(as_completed(futures), start=1):
                cancel.check()
                future.result()
                progress(done, changed, i18n.t("task.progress.writing"))
        except Cancelled:
            for future in futures:
                future.cancel()
            message(i18n.t("task.cancelled"))
            return 130
        finally:
            pool.shutdown(wait=True)

    if args.apply:
        changed = done_count
        placements = [(path, destination) for path, destination in placements
                      if path not in failed]

    placed = 0
    if placements and target is not None:
        try:
            placed, place_errors = _place_files(placements, target, move,
                                                bool(args.apply), cancel)
        except Cancelled:
            message(i18n.t("task.cancelled"))
            return 130
        errors += place_errors

    if placed:
        message(i18n.t("task.placed", count=placed))

    _finish("task.tags.done", {"changed": changed, "total": total},
            changed=changed, errors=errors, applied=args.apply,
            hint="task.hint.apply")
    report_stats("tags", files=total, changed=changed, placed=placed,
                 skipped=total - changed, errors=errors, applied=bool(args.apply),
                 backup=str(backup_folder) if backup_folder else "")
    return 1 if errors else 0


def cmd_rename(args: CmdArgs) -> int:
    """Rename the files below ``args.folder`` from their tags."""
    cancel = getattr(args, "cancel", NO_CANCEL)
    root = Path(args.folder).expanduser()
    if not root.is_dir():
        message(i18n.t("task.error.folder", path=root))
        return 2
    target = Path(args.target).expanduser() if getattr(args, "target", None) else None
    move = bool(getattr(args, "move", False))
    if move and target is None:
        message(i18n.t("task.error.target_required"))
        return 2

    banner(i18n.t("task.title.rename"), not args.apply)
    message(i18n.t("task.label.folder", value=root))
    message(i18n.t("task.label.pattern", value=args.pattern))
    if target is not None:
        message(i18n.t("task.label.target", value=target))
        message(i18n.t("task.label.mode",
                       value=i18n.t("task.action.move") if move
                       else i18n.t("task.action.copy")))
    message()

    files = list(iter_audio(root))
    total = len(files)
    try:
        unreadable: list[Path] = []
        tags_list = probe_many(files, report=lambda i, name: progress(i, total, name),
                               cancel=cancel, unreadable=unreadable)
    except Cancelled:
        message(i18n.t("task.cancelled"))
        return 130

    used: set[str] = set()
    renamed = 0
    skipped = len(unreadable)
    errors = 0
    for path in unreadable:
        message(i18n.t("task.error.unreadable", name=path.name))
    done = 0
    failed: set[Path] = set()
    placements: list[tuple[Path, Path, Path]] = []
    bad = set(unreadable)
    pipeline_state = getattr(args, "pipeline_state", None)

    try:
        for index, (path, tags) in enumerate(zip(files, tags_list), start=1):
            cancel.check()
            progress(index, total, path.name)
            if path in bad:
                continue
            if pipeline_state is not None:
                tags = pipeline_state["tags"].get(path, tags)
            base = build_name(tags, path.stem, args.pattern)
            candidate = path.parent / f"{base}{path.suffix}"

            final = candidate
            if str(candidate) != str(path):
                final = free_target(candidate, used, ignore=path)
            needs_rename = str(final) != str(path)
            if needs_rename:
                renamed += 1
            else:
                skipped += 1

            destination = None
            if target is not None:
                destination = _placement(final, tags, target, used)
                if destination is not None:
                    placements.append((path, final, destination))

            if target is not None:
                if destination is not None or needs_rename:
                    report_plan("rename", source=path,
                                target=destination if destination is not None else final)
            elif needs_rename:
                report_plan("rename", source=path, target=final)

            if not needs_rename:
                if pipeline_state is not None:
                    pipeline_state["paths"][path] = path
                continue
            if pipeline_state is not None:
                pipeline_state["paths"][path] = final
            if args.apply:
                try:
                    _no_clobber_move(path, final)
                    journal.record_move("rename", path, final)
                    done += 1
                    message(f"  OK: '{path.name}'  ->  '{final.name}'")
                except Exception as error:
                    journal.record_failure("rename", error, source=str(path),
                                           target=str(final))
                    failed.add(path)
                    errors += 1
                    message(i18n.t("task.error.file", name=path.name, error=error))
            else:
                message(f"  '{path.name}'  ->  '{final.name}'")
    except Cancelled:
        message(i18n.t("task.cancelled"))
        return 130

    if args.apply:
        renamed = done

    ready = [(final, destination) for original, final, destination in placements
             if original not in failed]
    placed = 0
    if ready and target is not None:
        try:
            placed, place_errors = _place_files(ready, target, move,
                                                bool(args.apply), cancel)
        except Cancelled:
            message(i18n.t("task.cancelled"))
            return 130
        errors += place_errors

    if placed:
        message(i18n.t("task.placed", count=placed))

    _finish("task.rename.done", {"renamed": renamed, "skipped": skipped},
            changed=renamed, errors=errors, applied=args.apply)
    report_stats("rename", files=total, changed=renamed, placed=placed,
                 skipped=skipped, errors=errors, applied=bool(args.apply))
    return 1 if errors else 0


def cmd_sort(args: CmdArgs) -> int:
    """Sort the files below ``args.source`` into ``args.target``."""
    cancel = getattr(args, "cancel", NO_CANCEL)
    source = Path(args.source).expanduser()
    target = Path(args.target).expanduser()
    if not source.is_dir():
        message(i18n.t("task.error.source", path=source))
        return 2

    action = i18n.t("task.action.move") if args.move else i18n.t("task.action.copy")
    banner(i18n.t("task.title.sort", action=action), not args.apply)
    message(i18n.t("task.label.source", value=source))
    message(i18n.t("task.label.target", value=target))
    message(i18n.t("task.label.pattern", value=args.pattern))
    message()

    files = list(iter_audio(source))
    total = len(files)
    message()
    try:
        unreadable: list[Path] = []
        tags_list = probe_many(files, report=lambda i, name: progress(i, total, name),
                               cancel=cancel, unreadable=unreadable)
    except Cancelled:
        message(i18n.t("task.cancelled"))
        return 130

    used: set[str] = set()
    plan: list[tuple[Path, Path]] = []
    skipped = len(unreadable)
    errors = 0
    for path in unreadable:
        message(i18n.t("task.error.unreadable", name=path.name))
    bad = set(unreadable)
    pipeline_state = getattr(args, "pipeline_state", None)

    try:
        for path, tags in zip(files, tags_list):
            cancel.check()
            if path in bad:
                continue
            tags_changed = False
            if pipeline_state is not None:
                planned_tags = pipeline_state["tags"].get(path, tags)
                tags_changed = planned_tags != tags
                tags = planned_tags
            planned_source = (pipeline_state["paths"].get(path, path)
                              if pipeline_state is not None else path)
            artist = tags["album_artist"] or tags["artist"] or FALLBACK_ARTIST
            album = tags["album"]
            base = build_name(tags, path.stem, args.pattern)

            relative = Path(safe_name(artist))
            if album:
                relative = relative / safe_name(album)
            target_path = target / relative / f"{base}{path.suffix}"

            if target_path.exists():
                if (target_path.resolve() == planned_source.resolve()
                        or (not tags_changed and same_content(path, target_path))):
                    skipped += 1
                    continue

            target_path = free_target(target_path, used)
            plan.append((path, target_path))
            report_plan("sort", source=planned_source, target=target_path)
            if not args.apply:
                message(f"  {planned_source.name}  ->  {target_path.relative_to(target)}")
    except Cancelled:
        message(i18n.t("task.cancelled"))
        return 130

    processed = len(plan)
    placed = 0

    if args.apply and plan:
        lock = threading.Lock()

        def place(path: Path, target_path: Path) -> None:
            nonlocal errors, placed
            try:
                cancel.check()
                target_path.parent.mkdir(parents=True, exist_ok=True)
                cancel.check()
                if args.move:
                    _no_clobber_move(path, target_path)
                else:
                    _no_clobber_copy(path, target_path)
                journal.record_move("sort" if args.move else "copy", path, target_path,
                                    mode="move" if args.move else "copy")
                with lock:
                    placed += 1
                    message(f"  {path.name}  ->  {target_path.relative_to(target)}")
            except Cancelled:
                raise
            except Exception as error:
                journal.record_failure("sort", error, source=str(path),
                                       target=str(target_path))
                with lock:
                    errors += 1
                    message(i18n.t("task.error.file", name=path.name, error=error))

        pool = ThreadPoolExecutor(max_workers=COPY_WORKERS)
        futures = [pool.submit(place, p, t) for p, t in plan]
        try:
            for done, future in enumerate(as_completed(futures), start=1):
                cancel.check()
                future.result()
                progress(done, processed, i18n.t("task.progress.sorting"))
        except Cancelled:
            for future in futures:
                future.cancel()
            message(i18n.t("task.cancelled"))
            return 130
        finally:
            pool.shutdown(wait=True)

    if args.apply:
        processed = placed

    _finish("task.sort.done",
            {"done": processed, "total": total, "skipped": skipped},
            changed=processed, errors=errors, applied=args.apply)
    report_stats("sort", files=total, changed=processed, skipped=skipped,
                 errors=errors, applied=bool(args.apply))
    return 1 if errors else 0


@dataclass(frozen=True)
class Step:
    """One stage of the all-in-one pipeline: an i18n title key and its action."""

    title_key: str
    run: Callable[[], int]


def _pipeline_steps(args: CmdArgs) -> list[Step]:
    """The stages ``cmd_all`` runs, in order."""
    cancel = getattr(args, "cancel", NO_CANCEL)
    pipeline_state = {"tags": {}, "paths": {}} if not args.apply else None

    def stage(**values) -> SimpleNamespace:
        """Argumente einer Stufe: gemeinsame Werte plus die der Stufe."""
        return SimpleNamespace(cancel=cancel, pipeline_state=pipeline_state, **values)

    steps: list[Step] = [
        Step("task.step.tags", lambda: cmd_tags(stage(
            folder=args.source, apply=args.apply,
            backup=getattr(args, "backup", False),
            track_format=getattr(args, "track_format", None),
            diff=getattr(args, "diff", False),
            diff_csv=getattr(args, "diff_csv", None)))),
        Step("task.step.rename", lambda: cmd_rename(stage(
            folder=args.source, pattern=args.pattern, apply=args.apply))),
        Step("task.step.sort", lambda: cmd_sort(stage(
            source=args.source, target=args.target, pattern=args.pattern,
            move=args.move, apply=args.apply))),
    ]
    return steps


def cmd_all(args: CmdArgs) -> int:
    """All-in-one: clean tags -> rename -> sort."""
    banner(i18n.t("task.title.all"), not args.apply)
    message(i18n.t("task.label.source", value=args.source))
    message(i18n.t("task.label.target", value=args.target))
    message(i18n.t("task.label.pattern", value=args.pattern))
    mode = i18n.t("task.action.move") if args.move else i18n.t("task.action.copy")
    message(i18n.t("task.label.mode", value=mode))

    steps = _pipeline_steps(args)
    total = len(steps)
    step_rc = 0
    clear_stats("tags", "rename", "sort")
    for index, step in enumerate(steps, start=1):
        title = i18n.t("task.step.label", index=index, total=total,
                       title=i18n.t(step.title_key))
        message()
        message(_STEP_LINE)
        message(i18n.t("task.step", title=title))
        message(_STEP_LINE)
        rc = step.run()
        if rc not in (0, 1):
            message(i18n.t("task.aborted", title=title, rc=rc))
            return rc
        step_rc = max(step_rc, rc)

    message()
    message(_SUMMARY_LINE)
    mode = i18n.t("task.mode.applied") if args.apply else i18n.t("task.mode.preview")
    message(i18n.t("task.all.done", mode=mode))
    if not args.apply:
        message(i18n.t("task.hint.apply_run"))
    message(_SUMMARY_LINE)

    tags_stats = last_stats("tags")
    rename_stats = last_stats("rename")
    sort_stats = last_stats("sort")
    errors = (tags_stats.get("errors", 0) + rename_stats.get("errors", 0)
              + sort_stats.get("errors", 0))
    report_stats("all", files=sort_stats.get("files", 0), steps=len(steps),
                 tags_changed=tags_stats.get("changed", 0),
                 renamed=rename_stats.get("changed", 0),
                 sorted_files=sort_stats.get("changed", 0),
                 skipped=sort_stats.get("skipped", 0),
                 errors=errors,
                 applied=bool(args.apply))
    return 1 if errors or step_rc else 0


def cmd_rules(args: CmdArgs) -> int:
    """Show my_rules.ini - and create the template on request."""
    if getattr(args, "builtin", False):
        message(builtin_rules_text())
        message("")
        message(i18n.t("rules.builtin.note1"))
        message(i18n.t("rules.builtin.note2"))
        return 0

    file = RULES_FILE

    if getattr(args, "template", False):
        if file.exists():
            message(i18n.t("rules.present", path=file))
        else:
            try:
                atomic_write_text(file, rules_template())
                message(i18n.t("rules.created", path=file))
            except OSError as error:
                message(i18n.t("rules.error.create", error=error))
                return 2
        message()

    message(i18n.t("rules.file", path=file))
    if not file.is_file():
        message(i18n.t("rules.status.missing"))
        message()
        message(i18n.t("rules.hint.create"))
        message(i18n.t("rules.hint.gui"))
        message(i18n.t("rules.hint.builtin"))
        return 0

    warnings = load_custom_rules()
    summary = rules_summary() or i18n.t("rules.none")
    message(i18n.t("rules.loaded", summary=summary))
    for warning in warnings:
        message(i18n.t("rules.warning", text=warning))
    if not warnings:
        message(i18n.t("rules.status.ok"))
    return 0


def cmd_scan(args: CmdArgs) -> int:
    """Count files, albums and artists below ``args.folder``."""
    cancel = getattr(args, "cancel", NO_CANCEL)
    root = Path(args.folder).expanduser()
    if not root.is_dir():
        message(i18n.t("task.error.folder", path=root))
        return 2

    files: list[Path] = []
    for path in iter_audio(root):
        cancel.check()
        files.append(path)
    total = len(files)
    unreadable: list[Path] = []
    tags_list = probe_many(files, report=lambda i, name: progress(i, total, name),
                           cancel=cancel, unreadable=unreadable)

    albums: set[tuple[str, str]] = set()
    artists: set[str] = set()
    for tags in tags_list:
        artist = (tags["album_artist"] or tags["artist"]).strip()
        for part in artist.split(";"):
            part = part.strip()
            if part:
                artists.add(part.casefold())
        album = tags["album"].strip()
        if album:
            albums.add((artist.casefold(), album.casefold()))

    for path in unreadable:
        message(i18n.t("task.error.unreadable", name=path.name))
    report_stats("scan", files=total, albums=len(albums), artists=len(artists),
                 unreadable=len(unreadable))
    message(i18n.t("task.scan.done", files=total, albums=len(albums),
                   artists=len(artists)))
    return 0


def _shown_name(entry: dict) -> str:
    """File name of a journal event or an undo step, for messages only."""
    for key in ("path", "source", "target"):
        value = entry.get(key)
        if value:
            return Path(str(value)).name
    return "?"


def _step_files(steps: list[dict]) -> list[Path]:
    """The files that would change, for the optional backup before an undo."""
    files: list[Path] = []
    seen: set[str] = set()
    for step in steps:
        path = step.get("backup") or step.get("path") or step.get("source")
        if path is None:
            path = step.get("target")
        if path is None:
            continue
        path = Path(path)
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        files.append(path)
    return files


def _common_root(paths: list[Path]) -> Path:
    """Folder the backup keeps its relative structure from."""
    try:
        return Path(os.path.commonpath([str(path.parent) for path in paths]))
    except (ValueError, OSError):
        return paths[0].parent


def _undo_step(step: dict) -> str:
    """Run one planned undo step."""
    try:
        op = step["op"]
        if op == "tags":
            path = step["path"]
            if not path.is_file():
                message(i18n.t("restore.skip.missing", name=path.name))
                return "skipped"
            info = read_info(path)
            actual = {field: info.joined(field, "; ")
                      for field in step["values"] if field in TAG_FIELDS}
            changed = [key for key, value in step["values"].items()
                       if actual.get(key, "") != step["current"].get(key, "")]
            if changed:
                message(i18n.t("restore.skip.changed", name=path.name,
                               fields=", ".join(sorted(changed))))
                return "skipped"
            if write_tags(path, step["values"]) is False:
                raise RuntimeError(f"tags could not be written: {path.name}")
            journal.record_tags(path, step["current"], step["values"])
            message(i18n.t("restore.ok.tags", name=path.name))
            return "done"

        if op == "copy":
            copy = step["target"]
            if not copy.is_file():
                message(i18n.t("restore.skip.missing", name=copy.name))
                return "skipped"
            if not step["original"].is_file():
                message(i18n.t("restore.skip.only_copy", name=copy.name))
                return "skipped"
            if not same_content(step["original"], copy):
                message(i18n.t("restore.skip.modified", name=copy.name))
                return "skipped"
            copy.unlink()
            journal.record("rmfile", path=str(copy))
            message(i18n.t("restore.ok.copy", name=copy.name))
            return "done"

        if op == "move":
            source = step["source"]
            target = step["target"]
            if not source.is_file():
                message(i18n.t("restore.skip.missing", name=source.name))
                return "skipped"
            if target.exists():
                message(i18n.t("restore.skip.exists", name=target.name))
                return "skipped"
            target.parent.mkdir(parents=True, exist_ok=True)
            _no_clobber_move(source, target)
            journal.record_move(step["kind"], source, target, mode="move")
            message(i18n.t("restore.ok.move", name=source.name))
            return "done"
    except Exception as error:
        journal.record_failure("restore", error,
                               source=str(step.get("source")
                                          or step.get("path") or ""))
        message(i18n.t("task.error.file", name=_shown_name(step), error=error))
        return "error"

    return "skipped"


def _list_journals() -> int:
    """Print the available journals (``restore --list``)."""
    files = journal.find_journals()
    if not files:
        message(i18n.t("restore.list.none", path=LOG_DIR))
        return 0

    message(i18n.t("restore.list.title", count=len(files)))
    for path in files:
        counts = journal.summarize(journal.plan_restore(path))
        summary = ", ".join(f"{op} {count}" for op, count in counts.items())
        header = journal.read_header(path)
        message(i18n.t("restore.list.entry", name=path.name,
                       start=str(header.get("ts", ""))[:16],
                       summary=summary or i18n.t("restore.list.empty")))
    return 0


def cmd_restore(args: CmdArgs) -> int:
    """Undo the changes of an earlier run (recorded in its journal)."""
    if getattr(args, "list_journals", False):
        return _list_journals()

    path = journal.resolve_journal(getattr(args, "journal", None))
    if path is None or not Path(path).is_file():
        message(i18n.t("restore.error.no_journal", path=str(path or "-")))
        return 2

    version = journal.schema_version(path)
    if version > journal.SCHEMA:
        message(i18n.t("restore.error.schema", version=version,
                       known=journal.SCHEMA))
        return 2

    events = journal.plan_restore(path)
    banner(i18n.t("task.title.restore"), not args.apply)
    message(i18n.t("task.label.journal", value=path))
    message(i18n.t("task.label.events", value=len(events)))
    message()

    keep_copies = bool(getattr(args, "keep_copies", False))
    cancel = getattr(args, "cancel", NO_CANCEL)
    steps: list[dict] = []
    skipped = 0

    if not events:
        message(i18n.t("restore.nothing"))
        message(_SUMMARY_LINE)
        report_stats("restore", files=0, changed=0, skipped=0, errors=0,
                     applied=bool(args.apply))
        return 0

    state: dict[Path, bool] = {}
    origin: dict[Path, Path] = {}

    def exists(path: Path) -> bool:
        return state.get(path, path.is_file())

    def now(path: Path) -> Path:
        """Where ``path`` lies right now, before the first undo step runs."""
        return origin.get(path, path)

    def plan_move(source: Path, target: Path) -> None:
        """Remember that undoing moves ``target`` back to ``source``."""
        state[target] = False
        state[source] = True
        origin[source] = now(target)
        origin.pop(target, None)

    for event in events:
        op = str(event.get("op"))

        if str(event.get("status") or "ok") == "error":
            message(i18n.t("restore.skip.failed", name=_shown_name(event)))
            skipped += 1
            continue

        if op == "tags":
            target = Path(str(event.get("path", "")))
            values = {str(key): str(value)
                      for key, value in (event.get("before") or {}).items()}
            if not values:
                skipped += 1
                continue
            if not exists(target):
                message(i18n.t("restore.skip.missing", name=target.name))
                skipped += 1
                continue
            current = {str(key): str(value)
                       for key, value in (event.get("after") or {}).items()}
            steps.append({"op": "tags", "path": target, "values": values,
                          "current": current, "backup": now(target)})
            report_plan("tags", path=target,
                        changes={key: (current.get(key, ""), value)
                                 for key, value in values.items()})
            message(f"  {target.name}")
            for key, value in values.items():
                message(f"      {key:<13} '{current.get(key, '')}'  ->  '{value}'")
            continue

        if op == "copy":
            original = Path(str(event.get("source", "")))
            copy = Path(str(event.get("target", "")))
            if keep_copies:
                message(i18n.t("restore.skip.keep_copy", name=copy.name))
                skipped += 1
                continue
            if not exists(copy):
                message(i18n.t("restore.skip.missing", name=copy.name))
                skipped += 1
                continue
            if not exists(original):
                message(i18n.t("restore.skip.only_copy", name=copy.name))
                skipped += 1
                continue
            steps.append({"op": "copy", "target": copy, "original": original,
                          "backup": now(copy)})
            state[copy] = False
            report_plan("sort", source=copy, target=original)
            message(i18n.t("restore.remove_copy", name=copy.name))
            continue

        if op in ("rename", "sort", "dedupe"):
            source = Path(str(event.get("source", "")))
            target = Path(str(event.get("target", "")))
            if not exists(target):
                message(i18n.t("restore.skip.missing", name=target.name))
                skipped += 1
                continue
            if exists(source):
                message(i18n.t("restore.skip.exists", name=source.name))
                skipped += 1
                continue
            steps.append({"op": "move", "kind": op, "source": target,
                          "target": source, "backup": now(target)})
            plan_move(source, target)
            report_plan(op, source=target, target=source)
            message(f"  {target.name}  ->  {source}")
            continue

        message(i18n.t("restore.skip.unknown", op=op))
        skipped += 1

    planned = len(steps)
    changed = planned
    errors = 0
    backup_folder: Path | None = None

    if args.apply and steps:
        if getattr(args, "backup", False):
            changed_files = _step_files(steps)
            backup_folder = _backup_files(_common_root(changed_files), changed_files)
            if backup_folder is None:
                message(i18n.t("task.backup.aborted"))
                return 2

        message()
        message(i18n.t("restore.undoing", count=planned))
        done_count = 0
        late_skipped = 0

        for index, step in enumerate(steps, start=1):
            try:
                cancel.check()
            except Cancelled:
                message(i18n.t("task.cancelled"))
                return 130
            outcome = _undo_step(step)
            if outcome == "done":
                done_count += 1
            elif outcome == "skipped":
                late_skipped += 1
            else:
                errors += 1
            progress(index, planned, i18n.t("task.progress.restore"))

        changed = done_count
        skipped += late_skipped

    _finish("restore.done",
            {"changed": changed, "skipped": skipped, "total": len(events)},
            changed=changed, errors=errors, applied=args.apply)
    report_stats("restore", files=len(events), changed=changed, skipped=skipped,
                 errors=errors, applied=bool(args.apply),
                 backup=str(backup_folder) if backup_folder else "")
    return 1 if errors else 0
