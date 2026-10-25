"""The dedupe feature: move duplicate audio files into ``.duplicates``.

The default mode compares the file content, so it can only ever move byte-for-byte
identical files.  ``--by tags`` is deliberately opt-in: it groups files with the
same artist, title, album and duration, which may also catch different encodings
of the same recording.

Nothing is ever deleted.  Every move is written to the journal, so
``sortiton restore`` brings the files back.
"""

from __future__ import annotations

import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ... import external, i18n, journal, output
from ...cancel import NO_CANCEL, Cancelled
from ...config import READ_WORKERS
from ...fileops import move_no_clobber
from ...files import content_digest, free_target, iter_audio, same_content
from ...tags import read_info
from ..base import CmdArgs, Feature, Option, resolve_args

DUPLICATES_DIR = ".duplicates"

_READ_REQUIREMENT = external.Requirement((external.MUTAGEN, external.FFPROBE))


def _norm(text: str) -> str:
    """Comparison form for the opt-in tag mode: case and whitespace only."""
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def _content_groups(files: list[Path], cancel) -> tuple[list[list[Path]], list[tuple[Path, Exception]]]:
    """Groups of byte-identical files; only files with the same size are hashed."""
    by_size: dict[int, list[Path]] = defaultdict(list)
    errors: list[tuple[Path, Exception]] = []
    for path in files:
        try:
            by_size[path.stat().st_size].append(path)
        except OSError as error:
            errors.append((path, error))
    candidates = [group for group in by_size.values() if len(group) > 1]
    if not candidates:
        return [], errors

    by_digest: dict[str, list[Path]] = defaultdict(list)
    pool = ThreadPoolExecutor(max_workers=READ_WORKERS)
    futures = {pool.submit(content_digest, path): path
               for group in candidates for path in group}
    try:
        for future in as_completed(futures):
            cancel.check()
            path = futures[future]
            try:
                by_digest[future.result()].append(path)
            except OSError as error:
                errors.append((path, error))
    except Cancelled:
        for future in futures:
            future.cancel()
        raise
    finally:
        pool.shutdown(wait=True)

    groups = [sorted(group, key=lambda path: str(path).casefold())
              for group in by_digest.values() if len(group) > 1]
    groups.sort(key=lambda group: str(group[0]).casefold())
    return groups, errors


def _tag_key(path: Path) -> tuple[tuple[str, str, str, int], object] | None:
    """The conservative tag-mode key plus the info object used for the choice.

    Files without artist, title or duration cannot be grouped safely and are
    left alone; a broken/unreadable file is reported instead.
    """
    info = read_info(path)
    if info.error:
        raise OSError(info.error)
    artist = info.joined("artist", "; ")
    title = info.joined("title", "; ")
    if not artist.strip() or not title.strip() or not info.duration:
        return None
    key = (_norm(artist), _norm(title), _norm(info.joined("album", "; ")),
           round(float(info.duration)))
    return key, info


def _tag_groups(files: list[Path], cancel) -> tuple[list[list[Path]], list[tuple[Path, Exception]]]:
    """Groups of files with the same artist, title, album and duration."""
    by_key: dict[tuple[str, str, str, int], list[tuple[Path, object]]] = defaultdict(list)
    errors: list[tuple[Path, Exception]] = []
    pool = ThreadPoolExecutor(max_workers=READ_WORKERS)
    futures = {pool.submit(_tag_key, path): path for path in files}
    try:
        for future in as_completed(futures):
            cancel.check()
            path = futures[future]
            try:
                result = future.result()
            except Exception as error:  # noqa: BLE001 - one broken file must not stop the run
                errors.append((path, error))
                continue
            if result is None:
                continue
            key, info = result
            by_key[key].append((path, info))
    except Cancelled:
        for future in futures:
            future.cancel()
        raise
    finally:
        pool.shutdown(wait=True)

    groups: list[list[Path]] = []
    for entries in by_key.values():
        if len(entries) < 2:
            continue
        # Keep the best copy: highest bitrate, then largest file, then name.
        entries.sort(key=lambda item: (
            -(getattr(item[1], "bitrate_kbps", 0) or 0),
            -_size(item[0]), str(item[0]).casefold()))
        groups.append([path for path, _info in entries])
    groups.sort(key=lambda group: str(group[0]).casefold())
    return groups, errors


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _relative(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except (ValueError, OSError):
        return str(path)


def _plan_groups(root: Path, groups: list[list[Path]]
                 ) -> list[tuple[Path, list[tuple[Path, Path]]]]:
    """Turn groups into (keeper, [(source, target), …]) with collision-free names."""
    used: set[str] = set()
    planned: list[tuple[Path, list[tuple[Path, Path]]]] = []
    for group in groups:
        # Prefer a real file as keeper: moving the target of a symlink would
        # leave that symlink dangling. The sort is stable, so the mode's own
        # order (name or best quality) survives within both categories.
        group = sorted(group, key=lambda path: path.is_symlink())
        keeper = group[0]
        moves: list[tuple[Path, Path]] = []
        for source in group[1:]:
            target = free_target(root / DUPLICATES_DIR / source.relative_to(root), used)
            moves.append((source, target))
        planned.append((keeper, moves))
    return planned


def _reader_hint() -> None:
    """Explain that tag mode needs a tag reader."""
    output.message(external.format_missing([_READ_REQUIREMENT]))


def cmd_dedupe(args: CmdArgs) -> int:
    """Find duplicate files and move all but the best copy into ``.duplicates``."""
    args = resolve_args(FEATURE, args)
    cancel = getattr(args, "cancel", NO_CANCEL)

    root = Path(str(args.folder or "")).expanduser().resolve()
    if not root.is_dir():
        output.message(i18n.t("task.error.folder", path=root))
        return 2
    mode = str(args.by or "content")
    if mode not in ("content", "tags"):
        output.message(i18n.t("dedupe.error.mode", mode=mode))
        return 2
    if mode == "tags" and not any(external.available(tool)
                                  for tool in _READ_REQUIREMENT.any_of):
        _reader_hint()
        return 2

    output.banner(i18n.t("dedupe.title"), not args.apply)
    output.message(i18n.t("task.label.folder", value=root))
    output.message(i18n.t("dedupe.label.mode", value=i18n.t(f"dedupe.mode.{mode}")))
    output.message(i18n.t("dedupe.label.target",
                          value=str(root / DUPLICATES_DIR)))

    files = list(iter_audio(root))
    output.message(i18n.t("task.label.files", value=len(files)))
    output.message()

    try:
        if mode == "content":
            groups, errors = _content_groups(files, cancel)
        else:
            groups, errors = _tag_groups(files, cancel)
    except Cancelled:
        output.message(i18n.t("task.cancelled"))
        return 130

    for path, error in errors:
        output.message(i18n.t("dedupe.error.read", name=path.name, error=error))
    if not groups:
        output.message(i18n.t("dedupe.none"))
        _finish(0, len(files), 0, len(errors), args)
        output.report_stats("dedupe", files=len(files), changed=0,
                            skipped=len(files), errors=len(errors),
                            applied=bool(args.apply))
        return 1 if errors else 0

    planned = _plan_groups(root, groups)
    total_moves = sum(len(moves) for _keeper, moves in planned)
    output.message(i18n.t("dedupe.found", groups=len(planned), files=total_moves))
    output.message()

    for index, (keeper, moves) in enumerate(planned, start=1):
        output.message(i18n.t("dedupe.group", index=index,
                              count=len(moves),
                              keeper=_relative(root, keeper)))
        for source, target in moves:
            output.report_plan("dedupe", source=str(source), target=str(target),
                               keep=str(keeper))
            output.message(i18n.t("dedupe.move",
                                  source=_relative(root, source),
                                  target=_relative(root, target)))

    changed = total_moves
    if args.apply:
        output.message()
        output.message(i18n.t("dedupe.moving", count=total_moves))
        done = 0
        errors_count = len(errors)
        for _index, (keeper, moves) in enumerate(planned, start=1):
            for source, target in moves:
                try:
                    cancel.check()
                    if mode == "content" and not same_content(keeper, source):
                        output.message(i18n.t("dedupe.skip.changed",
                                              name=_relative(root, source)))
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    move_no_clobber(source, target)
                    journal.record_move("dedupe", source, target, mode="move")
                    done += 1
                    output.message(i18n.t("task.ok",
                                          name=_relative(root, source)))
                except Cancelled:
                    output.message(i18n.t("task.cancelled"))
                    output.report_stats("dedupe", files=len(files), changed=done,
                                        skipped=len(files) - done,
                                        errors=errors_count, applied=True)
                    return 130
                except Exception as error:  # noqa: BLE001 - one file must not stop the rest
                    errors_count += 1
                    journal.record_failure("dedupe", error, source=str(source),
                                           target=str(target))
                    output.message(i18n.t("task.error.file",
                                          name=source.name, error=error))
        changed = done
        _finish(changed, len(files), len(planned), errors_count, args)
        output.report_stats("dedupe", files=len(files), changed=changed,
                            skipped=max(len(files) - changed, 0),
                            errors=errors_count, applied=True)
        return 1 if errors_count else 0

    _finish(changed, len(files), len(planned), len(errors), args)
    output.report_stats("dedupe", files=len(files), changed=changed,
                        skipped=max(len(files) - changed, 0),
                        errors=len(errors), applied=False)
    return 1 if errors else 0


def _finish(changed: int, total: int, groups: int, errors: int, args: CmdArgs) -> None:
    """Close the run with the same boxed summary as the classic tasks."""
    line = "=" * 62
    output.message()
    output.message(line)
    output.message(i18n.t("dedupe.done", changed=changed, total=total, groups=groups))
    if errors:
        output.message(i18n.t("task.error.count", count=errors))
    if not args.apply and changed:
        output.message(i18n.t("dedupe.hint.apply"))
    output.message(line)


FEATURE = Feature(
    key="dedupe",
    title_key="dedupe.title",
    help_key="cli.dedupe.help",
    run=cmd_dedupe,
    options=(
        Option("folder", "folder", positional=True, help_key="cli.dedupe.folder"),
        Option("by", "choice", "content", "cli.dedupe.by",
               flags=("--by",), choices=("content", "tags")),
        Option("apply", "bool", False, "cli.dedupe.apply", flags=("--apply",)),
    ),
    writes=True,
)
