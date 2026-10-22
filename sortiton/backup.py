"""Backup folders shared by the tasks and the features."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from . import config, i18n
from .fileops import copy_new
from .output import message, progress

_COMPLETE = ".complete"
_INCOMPLETE = ".incomplete"
_FAILED_DIR = "failed"


def _backup_root() -> Path:
    return Path(config.BACKUP_DIR)


def _mtime(path: Path) -> tuple[int, str]:
    try:
        return path.stat().st_mtime_ns, path.name
    except OSError:
        return 0, path.name


def _failed_dir() -> Path | None:
    try:
        path = _backup_root() / _FAILED_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError:
        return None


def _retire_incomplete(folder: Path) -> Path:
    """Move an incomplete folder out of the regular ``backup_*`` namespace."""
    failed = _failed_dir()
    if failed is None:
        return folder
    for number in range(1, 1000):
        name = folder.name if number == 1 else f"{folder.name} ({number})"
        target = failed / name
        if target.exists():
            continue
        try:
            folder.rename(target)
        except OSError:
            return folder
        return target
    return folder


def _remove(path: Path) -> None:
    try:
        shutil.rmtree(path)
    except OSError as error:
        message(i18n.t("task.backup.prune_failed", path=path, error=error))


def prune_backups(keep: int = config.BACKUP_KEEP) -> None:
    """Keep the most recent complete backups and a few failed ones as evidence."""
    root = _backup_root()
    try:
        folders = [folder for folder in root.glob("backup_*") if folder.is_dir()]
    except OSError:
        return

    complete: list[Path] = []
    for folder in folders:
        if (folder / _COMPLETE).is_file():
            (folder / _INCOMPLETE).unlink(missing_ok=True)
            complete.append(folder)
        elif (folder / _INCOMPLETE).is_file():
            _retire_incomplete(folder)
        else:
            complete.append(folder)

    complete.sort(key=_mtime, reverse=True)
    for old in complete[keep:]:
        _remove(old)

    failed = root / _FAILED_DIR
    if failed.is_dir():
        evidence = sorted((folder for folder in failed.glob("backup_*")
                           if folder.is_dir()), key=_mtime, reverse=True)
        for old in evidence[keep:]:
            _remove(old)


def backup_files(root: Path, paths: list[Path]) -> Path | None:
    """Copy the files that are about to change into a fresh backup folder."""
    stamp = f"{datetime.now():%Y-%m-%d_%H-%M-%S}"
    folder: Path | None = None
    backup_root = _backup_root()
    for number in range(1, 1000):
        name = f"backup_{stamp}" if number == 1 else f"backup_{stamp} ({number})"
        candidate = backup_root / name
        try:
            candidate.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        except OSError as error:
            message(i18n.t("task.backup.failed", path=candidate, error=error))
            return None
        folder = candidate
        break
    if folder is None:
        message(i18n.t("task.backup.failed", path=backup_root,
                       error=i18n.t("file.error.no_free_name", path=backup_root)))
        return None

    try:
        (folder / _INCOMPLETE).write_text("incomplete\n", encoding="utf-8")
    except OSError as error:
        message(i18n.t("task.backup.failed", path=folder, error=error))
        _retire_incomplete(folder)
        return None

    copied = 0
    failed = False
    for index, path in enumerate(paths, start=1):
        try:
            relative = path.relative_to(root)
        except ValueError:
            relative = Path(path.name)
        try:
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            copy_new(path, target)
            copied += 1
        except OSError as error:
            failed = True
            message(i18n.t("task.backup.file_error", name=path.name, error=error))
        progress(index, len(paths), i18n.t("task.progress.backup"))

    if failed:
        retired = _retire_incomplete(folder)
        message(i18n.t("task.backup.incomplete", path=retired))
        prune_backups()
        return None

    try:
        (folder / _COMPLETE).write_text("complete\n", encoding="utf-8")
    except OSError as error:
        message(i18n.t("task.backup.failed", path=folder, error=error))
        retired = _retire_incomplete(folder)
        message(i18n.t("task.backup.incomplete", path=retired))
        prune_backups()
        return None
    try:
        (folder / _INCOMPLETE).unlink()
    except OSError:
        pass

    message(i18n.t("task.backup.done", count=copied, path=folder))
    prune_backups()
    return folder
