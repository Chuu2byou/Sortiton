"""The tasks: tags / rename / sort / all / rules."""

from __future__ import annotations

import argparse
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

from . import i18n, journal
from .backup import backup_files, prune_backups
from .cancel import NO_CANCEL, Cancelled
from .config import (BACKUP_KEEP, COPY_WORKERS, FALLBACK_ARTIST, FETCH_ARCHIVE,
                     LOG_DIR, RULES_FILE, WRITE_WORKERS)
from .features.fetch import cmd_fetch
from .fileops import atomic_write_text, copy_new, move_no_clobber
from .files import build_name, free_target, iter_audio, safe_name, same_content
from .output import (progress, banner, clear_stats, last_stats, message,
                     report_plan, report_stats)
from .rules import (builtin_rules_text, clean_artist, clean_genre, clean_text_field,
                    load_custom_rules, rules_summary, rules_template)
from .rules import snapshot as rules_snapshot
from .tags import TAG_FIELDS, probe_many, read_info, write_tags

CmdArgs = argparse.Namespace | SimpleNamespace

_SUMMARY_LINE = "=" * 62
_STEP_LINE = "#" * 62


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

    banner(i18n.t("task.title.tags"), not args.apply)
    files = list(iter_audio(root))
    total = len(files)
    message(i18n.t("task.label.folder", value=root))
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
    bad = set(unreadable)
    custom = rules_snapshot()
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
            }
            diff = {k: v for k, v in new.items() if v != tags[k]}
            if not diff:
                continue

            plan.append((path, tags, diff))
            report_plan("tags", path=path,
                        changes={key: (tags[key], value) for key, value in diff.items()})
            message(f"  {path.name}")
            for key, value in diff.items():
                message(f"      {key:<13} '{tags[key]}'  ->  '{value}'")
    except Cancelled:
        message(i18n.t("task.cancelled"))
        return 130

    changed = len(plan)
    errors = 0
    for path in unreadable:
        message(i18n.t("task.error.unreadable", name=path.name))
    backup_folder: Path | None = None
    done_count = 0

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
                if write_tags(path, diff) is False:
                    raise RuntimeError(f"tags could not be written: {path.name}")
                journal.record_tags(path, old, diff)
                with lock:
                    done_count += 1
                    message(i18n.t("task.ok", name=path.name))
            except Exception as error:
                journal.record_failure("tags", error, path=str(path), before=old)
                with lock:
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

    _finish("task.tags.done", {"changed": changed, "total": total},
            changed=changed, errors=errors, applied=args.apply,
            hint="task.hint.apply")
    report_stats("tags", files=total, changed=changed,
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

    banner(i18n.t("task.title.rename"), not args.apply)
    message(i18n.t("task.label.folder", value=root))
    message(i18n.t("task.label.pattern", value=args.pattern))
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
    bad = set(unreadable)

    try:
        for index, (path, tags) in enumerate(zip(files, tags_list), start=1):
            cancel.check()
            progress(index, total, path.name)
            if path in bad:
                continue
            base = build_name(tags, path.stem, args.pattern)
            target = path.parent / f"{base}{path.suffix}"

            if str(target) == str(path):
                skipped += 1
                continue

            target = free_target(target, used, ignore=path)

            if str(target) == str(path):
                skipped += 1
                continue

            renamed += 1
            report_plan("rename", source=path, target=target)
            if args.apply:
                try:
                    if target.exists():
                        raise FileExistsError(f"target already exists: {target}")
                    path.rename(target)
                    journal.record_move("rename", path, target)
                    done += 1
                    message(f"  OK: '{path.name}'  ->  '{target.name}'")
                except Exception as error:
                    journal.record_failure("rename", error, source=str(path),
                                           target=str(target))
                    errors += 1
                    message(i18n.t("task.error.file", name=path.name, error=error))
            else:
                message(f"  '{path.name}'  ->  '{target.name}'")
    except Cancelled:
        message(i18n.t("task.cancelled"))
        return 130

    if args.apply:
        renamed = done

    _finish("task.rename.done", {"renamed": renamed, "skipped": skipped},
            changed=renamed, errors=errors, applied=args.apply)
    report_stats("rename", files=total, changed=renamed, skipped=skipped,
                 errors=errors, applied=bool(args.apply))
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

    try:
        for path, tags in zip(files, tags_list):
            cancel.check()
            if path in bad:
                continue
            artist = tags["album_artist"] or tags["artist"] or FALLBACK_ARTIST
            album = tags["album"]
            base = build_name(tags, path.stem, args.pattern)

            relative = Path(safe_name(artist))
            if album:
                relative = relative / safe_name(album)
            target_path = target / relative / f"{base}{path.suffix}"

            if target_path.exists():
                if target_path.resolve() == path.resolve() or same_content(path, target_path):
                    skipped += 1
                    continue

            target_path = free_target(target_path, used)
            plan.append((path, target_path))
            report_plan("sort", source=path, target=target_path)
            if not args.apply:
                message(f"  {path.name}  ->  {target_path.relative_to(target)}")
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
                target_path.parent.mkdir(parents=True, exist_ok=True)
                if args.move:
                    _no_clobber_move(path, target_path)
                else:
                    _no_clobber_copy(path, target_path)
                journal.record_move("sort" if args.move else "copy", path, target_path,
                                    mode="move" if args.move else "copy")
                with lock:
                    placed += 1
                    message(f"  {path.name}  ->  {target_path.relative_to(target)}")
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
    steps: list[Step] = []
    if getattr(args, "fetch_url", None):
        steps.append(Step("task.step.fetch", lambda: _run_fetch_step(args, cancel)))
    steps.extend([
        Step("task.step.tags",
             lambda: cmd_tags(SimpleNamespace(folder=args.source, apply=args.apply,
                                              backup=getattr(args, "backup", False),
                                              cancel=cancel))),
        Step("task.step.rename",
             lambda: cmd_rename(SimpleNamespace(folder=args.source, pattern=args.pattern,
                                                apply=args.apply, cancel=cancel))),
        Step("task.step.sort",
             lambda: cmd_sort(SimpleNamespace(source=args.source, target=args.target,
                                              pattern=args.pattern, move=args.move,
                                              apply=args.apply, cancel=cancel))),
    ])
    return steps


def _run_fetch_step(args: CmdArgs, cancel) -> int:
    """Download ``args.fetch_url`` into ``args.source`` - never without consent."""
    apply = bool(getattr(args, "apply", False))
    confirmed = getattr(args, "fetch_confirmed", False) is True
    if apply and not confirmed:
        message(i18n.t("fetch.apply.needs_confirm"))
        return 2
    return cmd_fetch(SimpleNamespace(url=args.fetch_url, target=args.source,
                                     apply=apply, confirm=apply and confirmed,
                                     cancel=cancel))


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
    clear_stats("fetch", "tags", "rename", "sort")
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
    fetch_stats = last_stats("fetch")
    errors = (tags_stats.get("errors", 0) + rename_stats.get("errors", 0)
              + sort_stats.get("errors", 0) + fetch_stats.get("errors", 0))
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
    root = Path(args.folder).expanduser()
    if not root.is_dir():
        message(i18n.t("task.error.folder", path=root))
        return 2

    files = list(iter_audio(root))
    total = len(files)
    unreadable: list[Path] = []
    tags_list = probe_many(files, report=lambda i, name: progress(i, total, name),
                           unreadable=unreadable)

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


def _drop_archive_id(archive_id: str) -> bool:
    """Remove one line from the yt-dlp download archive (step 4.4)."""
    if not archive_id:
        return True
    try:
        lines = FETCH_ARCHIVE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return not FETCH_ARCHIVE.exists()
    remaining = [line for line in lines if line.strip() != archive_id]
    if len(remaining) == len(lines):
        return True
    try:
        atomic_write_text(FETCH_ARCHIVE,
                          "\n".join(remaining) + ("\n" if remaining else ""))
    except OSError:
        return False
    return True


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

        if op == "download":
            path = step["path"]
            if not path.is_file():
                message(i18n.t("restore.skip.missing", name=path.name))
                return "skipped"
            if not _drop_archive_id(step["archive_id"]):
                message(i18n.t("restore.error.archive", name=path.name))
                journal.record_failure("download", "archive line could not be removed",
                                       path=str(path))
                return "error"
            path.unlink()
            journal.record("rmfile", path=str(path))
            message(i18n.t("restore.ok.download", name=path.name))
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

        if op == "download":
            target = Path(str(event.get("path", "")))
            archive_id = str(event.get("archive_id") or "")
            if keep_copies:
                message(i18n.t("restore.skip.keep_download", name=target.name))
                skipped += 1
                continue
            if not exists(target):
                message(i18n.t("restore.skip.missing", name=target.name))
                skipped += 1
                continue
            steps.append({"op": "download", "path": target, "archive_id": archive_id,
                          "backup": now(target)})
            state[target] = False
            report_plan("download", path=target, archive_id=archive_id)
            message(i18n.t("restore.remove_download", name=target.name))
            continue

        if op in ("rename", "sort"):
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
