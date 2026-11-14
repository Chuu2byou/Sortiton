"""Small file-system primitives shared by the tasks and the features."""

from __future__ import annotations

import errno
import os
import shutil
import stat
import tempfile
from pathlib import Path


def copy_new(source: Path, target: Path) -> None:
    """Copy ``source`` to a target that must not exist yet."""
    descriptor, temporary = tempfile.mkstemp(dir=target.parent,
                                               prefix=f".{target.name}.",
                                               suffix=".tmp")
    temp_path = Path(temporary)
    os.close(descriptor)
    try:
        with source.open("rb") as reader, temp_path.open("wb") as writer:
            shutil.copyfileobj(reader, writer)
        shutil.copystat(source, temp_path)
        try:
            os.link(temp_path, target)
        except (OSError, NotImplementedError) as error:
            if isinstance(error, OSError) and error.errno not in {
                    errno.EXDEV, errno.EPERM, errno.EOPNOTSUPP, errno.ENOSYS, errno.EMLINK}:
                raise
            with temp_path.open("rb") as reader:
                writer = target.open("xb")
                try:
                    with writer:
                        shutil.copyfileobj(reader, writer)
                    shutil.copystat(temp_path, target)
                except BaseException:
                    target.unlink(missing_ok=True)
                    raise
    finally:
        temp_path.unlink(missing_ok=True)


def _unlink_after_move(source: Path, target: Path) -> None:
    """Remove the source of a completed link/copy, undoing it if that fails."""
    try:
        source.unlink()
    except OSError:
        try:
            target.unlink()
        except OSError:
            pass
        raise


def _copy_then_unlink(source: Path, target: Path) -> None:
    """Cross-device fallback: exclusive copy, then remove the source."""
    if source.is_symlink():
        os.symlink(os.readlink(source), target)
    else:
        copy_new(source, target)
    _unlink_after_move(source, target)


def move_no_clobber(source: Path, target: Path) -> None:
    """Move ``source`` to ``target`` without ever replacing an existing name."""
    if target.exists():
        raise FileExistsError(f"target already exists: {target}")

    try:
        os.link(source, target, follow_symlinks=False)
    except FileExistsError:
        raise
    except OSError as error:
        if error.errno not in {errno.EXDEV, errno.EPERM, errno.EOPNOTSUPP,
                               errno.ENOSYS, errno.EMLINK}:
            raise
        _copy_then_unlink(source, target)
        return
    except NotImplementedError:
        try:
            os.link(source, target)
        except FileExistsError:
            raise
        except OSError as error:
            if error.errno not in {errno.EXDEV, errno.EPERM, errno.EOPNOTSUPP,
                                   errno.ENOSYS, errno.EMLINK}:
                raise
            _copy_then_unlink(source, target)
            return

    _unlink_after_move(source, target)


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write a small state file via a temp file and ``os.replace``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        mode = None

    handle, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temp_path = Path(temporary)
    try:
        with os.fdopen(handle, "w", encoding=encoding, newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    except BaseException:
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise
