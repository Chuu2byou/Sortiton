"""Configuration: constants, paths and performance settings."""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    """Unveränderliche Pfade eines Anwendungsstarts."""

    package_dir: Path
    source_dir: Path
    data_home: Path
    project_dir: Path
    assets_dir: Path
    config_home: Path
    downloads_dir: Path
    rules_file: Path
    log_dir: Path
    settings_file: Path
    backup_dir: Path
    export_dir: Path
    cache_dir: Path
    legacy_cache_dir: Path
    music_source_dir: Path
    music_target_dir: Path
    frozen: bool
    in_source_tree: bool


def _xdg_user_dir(variable: str, fallback: Path, config_home: Path | None = None,
                  home: Path | None = None) -> Path:
    """Der XDG-Nutzerordner ``variable`` (z. B. ``XDG_DOWNLOAD_DIR``).

    Gelesen wird ``~/.config/user-dirs.dirs``; fehlt die Datei oder der
    Eintrag, gilt ``fallback``. ``$HOME`` in der Datei wird aufgelöst.
    """
    try:
        directory = config_home if config_home is not None else current_paths().config_home
        text = (directory / "user-dirs.dirs").read_text(encoding="utf-8")
    except OSError:
        return fallback
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(f"{variable}="):
            continue
        value = line.split("=", 1)[1].strip().strip('"')
        if value:
            return Path(value.replace("$HOME", str(home or Path.home())))
    return fallback


def production_paths(*, environ: Mapping[str, str] | None = None,
                     home: Path | None = None, source_dir: Path | None = None,
                     frozen: bool | None = None, assets_base: Path | None = None) -> AppPaths:
    """Produktionspfade aus Umgebung und Installation zum Aufrufzeitpunkt bestimmen."""
    env = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    package = Path(__file__).resolve().parent
    source = package.parent if source_dir is None else Path(source_dir)
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    in_source = not is_frozen and (source / "sortiton.py").is_file()
    data_value = env.get("XDG_DATA_HOME", "").strip()
    data_home = Path(data_value) if data_value else home / ".local" / "share"
    project_value = env.get("SORTITON_DATA_DIR", "").strip()
    project = (Path(project_value) if project_value else
               source if in_source else data_home / "sortiton")
    config_value = env.get("XDG_CONFIG_HOME", "").strip()
    config_home = Path(config_value) if config_value else home / ".config"
    downloads = _xdg_user_dir("XDG_DOWNLOAD_DIR", home / "Downloads", config_home, home)
    assets = Path(getattr(sys, "_MEIPASS", source) if assets_base is None else assets_base)
    assets /= "assets"
    folder_value = env.get("SORTITON_FOLDER", "").strip()
    music_source = Path(folder_value) if folder_value else project.parent / "Musik"
    if not music_source.is_dir():
        music_source = home / "Musik"
    target_value = env.get("SORTITON_TARGET", "").strip()
    music_target = Path(target_value) if target_value else home / "Musik"
    return AppPaths(
        package, source, data_home, project, assets, config_home, downloads,
        Path(env.get("SORTITON_RULES", project / "my_rules.ini")),
        Path(env.get("SORTITON_LOG_DIR", project / "logs")),
        Path(env.get("SORTITON_SETTINGS", project / "settings.ini")),
        Path(env.get("SORTITON_BACKUP_DIR", project / "backups")),
        Path(env.get("SORTITON_EXPORT_DIR") or downloads / "Sortiton"),
        Path(env.get("SORTITON_CACHE_DIR", project / "cache")),
        Path(env.get("XDG_CACHE_HOME", home / ".cache")) / "musik_export",
        music_source, music_target, is_frozen, in_source,
    )


_PATH_NAMES = {item.name.upper(): item.name for item in fields(AppPaths)}
_paths_context: ContextVar[AppPaths | None] = ContextVar("sortiton_paths", default=None)


def selected_paths() -> AppPaths | None:
    """Explizit für den aktuellen Ausführungskontext gewählte Pfade liefern."""
    return _paths_context.get()


def current_paths() -> AppPaths:
    """Gewählte Pfade oder die aktuelle Produktionskonfiguration liefern."""
    return selected_paths() or production_paths()


@contextmanager
def use_paths(paths: AppPaths) -> Iterator[None]:
    """Pfade für einen Lauf setzen und anschließend den Kontext wiederherstellen."""
    token = _paths_context.set(paths)
    try:
        yield
    finally:
        _paths_context.reset(token)


def __getattr__(name: str):
    """Alte Konstantennamen als dynamischen Kompatibilitätsadapter anbieten."""
    if name in _PATH_NAMES:
        return getattr(current_paths(), _PATH_NAMES[name])
    raise AttributeError(name)

AUDIO_EXTENSIONS = {
    ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wav", ".wma",
    ".opus", ".ape", ".mpc", ".wv",
}

READ_EXTENSIONS = AUDIO_EXTENSIONS | {".oga", ".mp4", ".aiff", ".aif"}

FALLBACK_ARTIST = "_Unknown"
MAX_NAME_LENGTH = 120

READ_WORKERS = min(8, os.cpu_count() or 4)
MUTAGEN_AVAILABLE = importlib.util.find_spec("mutagen") is not None
WRITE_WORKERS = 8 if MUTAGEN_AVAILABLE else 4
COPY_WORKERS = 4

INVISIBLE = re.compile(
    r"[\u00AD\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFE00-\uFE0F\uFEFF\uFFF0-\uFFFF]"
)

INVALID_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1F\x7F]')

DEFAULT_LANGUAGE = "en"

LOG_KEEP = 50
LOG_PREFIX = "sortiton"
LATEST_LOG_NAME = "latest.log"

JOURNAL_SUFFIX = ".jsonl"
LATEST_JOURNAL_NAME = "latest_journal.jsonl"
JOURNAL_KEEP = 20

BACKUP_KEEP = 10

OFF_VALUES = {"0", "false", "no", "off", "nein", "aus"}


def display_path(path: Path | str) -> str:
    """Ein Pfad für die Anzeige: das Home-Verzeichnis wird zu ``~``.

    In der Oberfläche steht damit ``~/Downloads/Sortiton`` statt eines
    vollständigen, nutzerspezifischen Pfades.
    """
    text = str(path or "").strip()
    if not text:
        return text
    try:
        home = Path.home()
        candidate = Path(text).expanduser()
        if candidate == home:
            return "~"
        if home in candidate.parents:
            return "~/" + str(candidate.relative_to(home))
    except (OSError, ValueError):
        pass
    return text
