"""The tasks: tags / rename / sort / all / rules.

Both the CLI and the GUI call these ``cmd_*`` functions; they return a status
code (0 = ok).
"""

from __future__ import annotations

import argparse
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

from . import i18n, journal
from .cancel import NO_CANCEL, Cancelled
from .config import (BACKUP_DIR, BACKUP_KEEP, COPY_WORKERS, FALLBACK_ARTIST,
                     FETCH_ARCHIVE, LOG_DIR, RULES_FILE, WRITE_WORKERS)
from .features.fetch import cmd_fetch
from .files import build_name, free_target, iter_audio, safe_name, same_content
from .output import progress, banner, last_stats, message, report_plan, report_stats
from .rules import (builtin_rules_text, clean_artist, clean_genre, clean_text_field,
                    load_custom_rules, rules_summary, rules_template)
from .tags import probe_many, write_tags

# CLI: argparse.Namespace, GUI: SimpleNamespace.
CmdArgs = argparse.Namespace | SimpleNamespace

_SUMMARY_LINE = "=" * 62
_STEP_LINE = "#" * 62


def _finish(key: str, fields: dict, *, changed: int, errors: int, applied: bool,
            hint: str = "task.hint.apply_run") -> None:
    """Close a run: the summary block every command ends with.

    ``changed`` is what the hint line looks at - a preview that found nothing
    to do gets no "run it with --apply" hint.
    """
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
        tags_list = probe_many(files, report=lambda i, name: progress(i, total, name),
                               cancel=cancel)
    except Cancelled:
        message(i18n.t("task.cancelled"))
        return 130

    plan: list[tuple[Path, dict, dict]] = []
    for path, tags in zip(files, tags_list):
        new = {
            "artist":       clean_artist(tags["artist"]),
            "album_artist": clean_artist(tags["album_artist"]),
            "title":        clean_text_field(tags["title"]),
            "album":        clean_text_field(tags["album"]),
            "genre":        clean_genre(tags["genre"]),
        }
        # An empty new value counts as a change if something was there before,
        # so a custom rule can delete a genre on purpose.
        diff = {k: v for k, v in new.items() if v != tags[k]}
        if not diff:
            continue

        plan.append((path, tags, diff))
        # The GUI needs both sides of a change; write_tags() only the new value.
        report_plan("tags", path=path,
                    changes={key: (tags[key], value) for key, value in diff.items()})
        message(f"  {path.name}")
        for key, value in diff.items():
            message(f"      {key:<13} '{tags[key]}'  ->  '{value}'")

    changed = len(plan)
    errors = 0
    backup_folder: Path | None = None

    if args.apply and plan:
        if getattr(args, "backup", False):
            backup_folder = _backup_files(root, [path for path, _, _ in plan])

        message()
        message(i18n.t("task.writing", count=changed))
        lock = threading.Lock()
        done_count = 0

        def store(path: Path, before: dict, diff: dict) -> None:
            nonlocal done_count, errors
            # The journal records what really happened, not what was planned -
            # so it is written after the file has been touched.
            old = {key: before[key] for key in diff}
            try:
                write_tags(path, diff)
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
                future.cancel()          # drop the writes that have not started
            message(i18n.t("task.cancelled"))
            return 130
        finally:
            # Writes that already run must finish before the run ends.
            pool.shutdown(wait=True)

    _finish("task.tags.done", {"changed": changed, "total": total},
            changed=changed, errors=errors, applied=args.apply,
            hint="task.hint.apply")
    report_stats("tags", files=total, changed=changed, skipped=total - changed,
                 errors=errors, applied=bool(args.apply),
                 backup=str(backup_folder) if backup_folder else "")
    return 0


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
        tags_list = probe_many(files, report=lambda i, name: progress(i, total, name),
                               cancel=cancel)
    except Cancelled:
        message(i18n.t("task.cancelled"))
        return 130

    used: set[str] = set()
    renamed = skipped = errors = 0

    for index, (path, tags) in enumerate(zip(files, tags_list), start=1):
        progress(index, total, path.name)
        base = build_name(tags, path.stem, args.pattern)
        target = path.parent / f"{base}{path.suffix}"

        if str(target) == str(path):
            skipped += 1
            continue

        target = free_target(target, used, ignore=path)

        # free_target() can hand back the file's own name - renaming
        # "Song (2).mp3" to "Song.mp3" ends up at "Song (2).mp3" again.
        if str(target) == str(path):
            skipped += 1
            continue

        renamed += 1
        report_plan("rename", source=path, target=target)
        if args.apply:
            try:
                path.rename(target)
                journal.record_move("rename", path, target)
                message(f"  OK: '{path.name}'  ->  '{target.name}'")
            except Exception as error:
                journal.record_failure("rename", error, source=str(path),
                                       target=str(target))
                errors += 1
                message(i18n.t("task.error.file", name=path.name, error=error))
        else:
            message(f"  '{path.name}'  ->  '{target.name}'")

    _finish("task.rename.done", {"renamed": renamed, "skipped": skipped},
            changed=renamed, errors=errors, applied=args.apply)
    report_stats("rename", files=total, changed=renamed, skipped=skipped,
                 errors=errors, applied=bool(args.apply))
    return 0


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
        tags_list = probe_many(files, report=lambda i, name: progress(i, total, name),
                               cancel=cancel)
    except Cancelled:
        message(i18n.t("task.cancelled"))
        return 130

    used: set[str] = set()
    plan: list[tuple[Path, Path]] = []
    skipped = 0

    for path, tags in zip(files, tags_list):
        artist = tags["album_artist"] or tags["artist"] or FALLBACK_ARTIST
        album = tags["album"]
        base = build_name(tags, path.stem, args.pattern)

        # TODO: artist/album/file is hardcoded; a song without an album tag
        # ends up as artist/file. No setting for the layout yet.
        relative = Path(safe_name(artist))
        if album:
            relative = relative / safe_name(album)
        target_path = target / relative / f"{base}{path.suffix}"

        if target_path.exists():
            # same file, or the same content already in place - nothing to do
            if target_path.resolve() == path.resolve() or same_content(path, target_path):
                skipped += 1
                continue

        target_path = free_target(target_path, used)
        plan.append((path, target_path))
        report_plan("sort", source=path, target=target_path)
        if not args.apply:
            message(f"  {path.name}  ->  {target_path.relative_to(target)}")

    processed = len(plan)
    errors = 0

    if args.apply and plan:
        lock = threading.Lock()

        def place(path: Path, target_path: Path) -> None:
            nonlocal errors
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                if args.move:
                    shutil.move(str(path), str(target_path))
                else:
                    shutil.copy2(str(path), str(target_path))
                journal.record_move("sort" if args.move else "copy", path, target_path,
                                    mode="move" if args.move else "copy")
                with lock:
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
                future.cancel()          # drop the copies that have not started
            message(i18n.t("task.cancelled"))
            return 130
        finally:
            # Copies that already run must finish before the run ends.
            pool.shutdown(wait=True)

    _finish("task.sort.done",
            {"done": processed, "total": total, "skipped": skipped},
            changed=processed, errors=errors, applied=args.apply)
    report_stats("sort", files=total, changed=processed, skipped=skipped,
                 errors=errors, applied=bool(args.apply))
    return 0


@dataclass(frozen=True)
class Step:
    """One stage of the all-in-one pipeline: an i18n title key and its action."""

    title_key: str
    run: Callable[[], int]


def _pipeline_steps(args: CmdArgs) -> list[Step]:
    """The stages ``cmd_all`` runs, in order.

    Built per run, not kept as a module constant, so a stage can read the
    parsed arguments (see the optional fetch stage in step 4.5).
    """
    cancel = getattr(args, "cancel", NO_CANCEL)
    steps: list[Step] = []
    # The fetch stage is optional and runs first: the classic stages then see
    # the freshly fetched files in the source folder (step 4.5).
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
    """Download ``args.fetch_url`` into ``args.source`` - never without consent.

    Step 4.3: inside "all" the download only happens when ``fetch_confirmed``
    is explicitly True. Without it the stage stops the whole run before a
    single byte is fetched, so "all" can never download by accident.
    """
    if getattr(args, "fetch_confirmed", False) is not True:
        message(i18n.t("fetch.apply.needs_confirm"))
        return 2
    return cmd_fetch(SimpleNamespace(url=args.fetch_url, target=args.source,
                                     apply=True, confirm=True, cancel=cancel))


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
    for index, step in enumerate(steps, start=1):
        title = i18n.t("task.step.label", index=index, total=total,
                       title=i18n.t(step.title_key))
        message()
        message(_STEP_LINE)
        message(i18n.t("task.step", title=title))
        message(_STEP_LINE)
        rc = step.run()
        if rc != 0:
            message(i18n.t("task.aborted", title=title, rc=rc))
            return rc

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
    report_stats("all", files=sort_stats.get("files", 0), steps=len(steps),
                 tags_changed=tags_stats.get("changed", 0),
                 renamed=rename_stats.get("changed", 0),
                 sorted_files=sort_stats.get("changed", 0),
                 skipped=sort_stats.get("skipped", 0),
                 errors=(tags_stats.get("errors", 0) + rename_stats.get("errors", 0)
                         + sort_stats.get("errors", 0)),
                 applied=bool(args.apply))
    return 0


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
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(rules_template(), encoding="utf-8")
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
    """Count files, albums and artists below ``args.folder``.

    An album counts per artist, so "Greatest Hits" of two artists counts twice.
    """
    root = Path(args.folder).expanduser()
    if not root.is_dir():
        message(i18n.t("task.error.folder", path=root))
        return 2

    files = list(iter_audio(root))
    total = len(files)
    tags_list = probe_many(files, report=lambda i, name: progress(i, total, name))

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

    report_stats("scan", files=total, albums=len(albums), artists=len(artists))
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
    """The files that would change, for the optional backup before an undo.

    ``backup`` is the path the file has *before* the undo starts: in a chain of
    moves (sort -> rename -> tags) a step's own path may only be recreated by an
    earlier undo step, so backing that one up would find nothing.
    """
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
    """Remove one line from the yt-dlp download archive (step 4.4).

    Undoing a download has to take its archive line out again, otherwise the
    archive would skip the track on the next run. Returns True when a line was
    removed; an empty id or a missing archive is not an error.
    """
    if not archive_id:
        return False
    try:
        lines = FETCH_ARCHIVE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    remaining = [line for line in lines if line.strip() != archive_id]
    if len(remaining) == len(lines):
        return False
    try:
        FETCH_ARCHIVE.write_text("\n".join(remaining) + ("\n" if remaining else ""),
                                 encoding="utf-8")
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
    """Run one planned undo step.

    Returns ``"done"``, ``"skipped"`` (the step became impossible only after
    planning - reported, never forced) or ``"error"``. The file system is
    checked again here, because the state may have changed since the preview.
    """
    try:
        op = step["op"]
        if op == "tags":
            path = step["path"]
            if not path.is_file():
                message(i18n.t("restore.skip.missing", name=path.name))
                return "skipped"
            write_tags(path, step["values"])
            journal.record_tags(path, step["current"], step["values"])
            message(i18n.t("restore.ok.tags", name=path.name))
            return "done"

        if op == "copy":
            copy = step["target"]
            if not copy.is_file():
                message(i18n.t("restore.skip.missing", name=copy.name))
                return "skipped"
            if not step["original"].is_file():
                # The original vanished meanwhile: the copy is the only one
                # left, so never delete it.
                message(i18n.t("restore.skip.only_copy", name=copy.name))
                return "skipped"
            copy.unlink()
            journal.record("rmfile", path=str(copy))
            message(i18n.t("restore.ok.copy", name=copy.name))
            return "done"

        if op == "download":
            # Take the archive line out too, otherwise yt-dlp would skip the
            # track on the next run (step 4.4).
            path = step["path"]
            if not path.is_file():
                message(i18n.t("restore.skip.missing", name=path.name))
                return "skipped"
            path.unlink()
            _drop_archive_id(step["archive_id"])
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
            shutil.move(str(source), str(target))
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
    """Undo the changes of an earlier run (recorded in its journal).

    Like every other task: without ``--apply`` this only prints the plan. The
    events are undone newest first, which matters for a combined run
    (tags -> rename -> sort): the reverse order is sort -> rename -> tags.
    """
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

    # Undo steps are planned against a virtual file system: in a combined run
    # (tags -> rename -> sort) a file only returns to its old name through the
    # undo steps planned before it. That is why a dependency like "the rename
    # brings back the path the tag step needs" must not be checked against the
    # file system as it is right now.
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
                # Safety net: the original is gone, so the copy is the only one
                # left. Report it instead of deleting data.
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

        message()
        message(i18n.t("restore.undoing", count=planned))
        done_count = 0
        late_skipped = 0

        # One step after the other: the reverse order is what makes a chained
        # run undoable at all (sort -> rename -> tags), so the steps must never
        # run in parallel.
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

        # A step can turn out to be impossible only at run time (the file
        # vanished, a name was taken meanwhile): count what really happened.
        changed = done_count
        skipped += late_skipped

    _finish("restore.done",
            {"changed": changed, "skipped": skipped, "total": len(events)},
            changed=changed, errors=errors, applied=args.apply)
    report_stats("restore", files=len(events), changed=changed, skipped=skipped,
                 errors=errors, applied=bool(args.apply),
                 backup=str(backup_folder) if backup_folder else "")
    return 0


def _prune_backups(keep: int = BACKUP_KEEP) -> None:
    """Keep only the most recent backup folders."""
    try:
        folders = sorted((folder for folder in BACKUP_DIR.glob("backup_*")
                          if folder.is_dir()), key=lambda path: path.name, reverse=True)
        for old in folders[keep:]:
            shutil.rmtree(old, ignore_errors=True)
    except OSError:
        pass


def _backup_files(root: Path, paths: list[Path]) -> Path | None:
    """Copy the files that are about to change into a fresh backup folder.

    The path below ``root`` is kept, so restoring is a plain copy. Returns the
    folder, or None if it could not be created (the caller keeps going).
    """
    folder = BACKUP_DIR / f"backup_{datetime.now():%Y-%m-%d_%H-%M-%S}"
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        message(i18n.t("task.backup.failed", path=folder, error=error))
        return None

    copied = 0
    for index, path in enumerate(paths, start=1):
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
            message(i18n.t("task.backup.file_error", name=path.name, error=error))
        progress(index, len(paths), i18n.t("task.progress.backup"))

    message(i18n.t("task.backup.done", count=copied, path=folder))
    _prune_backups()
    return folder
