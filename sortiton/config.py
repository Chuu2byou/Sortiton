"""Configuration: constants, paths and performance settings."""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = PACKAGE_DIR.parent

FROZEN = bool(getattr(sys, "frozen", False))
IN_SOURCE_TREE = not FROZEN and (SOURCE_DIR / "sortiton.py").is_file()
_XDG_DATA_HOME = os.environ.get("XDG_DATA_HOME", "").strip()
DATA_HOME = Path(_XDG_DATA_HOME) if _XDG_DATA_HOME else Path.home() / ".local" / "share"
_DATA_DIR = os.environ.get("SORTITON_DATA_DIR", "").strip()
PROJECT_DIR = (Path(_DATA_DIR) if _DATA_DIR else
               SOURCE_DIR if IN_SOURCE_TREE else DATA_HOME / "sortiton")

ASSETS_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_DIR)) / "assets"

_XDG_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME", "").strip()
CONFIG_HOME = Path(_XDG_CONFIG_HOME) if _XDG_CONFIG_HOME else Path.home() / ".config"


def _xdg_user_dir(variable: str, fallback: Path) -> Path:
    """Der XDG-Nutzerordner ``variable`` (z. B. ``XDG_DOWNLOAD_DIR``).

    Gelesen wird ``~/.config/user-dirs.dirs``; fehlt die Datei oder der
    Eintrag, gilt ``fallback``. ``$HOME`` in der Datei wird aufgelöst.
    """
    try:
        text = (CONFIG_HOME / "user-dirs.dirs").read_text(encoding="utf-8")
    except OSError:
        return fallback
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(f"{variable}="):
            continue
        value = line.split("=", 1)[1].strip().strip('"')
        if value:
            return Path(value.replace("$HOME", str(Path.home())))
    return fallback


DOWNLOADS_DIR = _xdg_user_dir("XDG_DOWNLOAD_DIR", Path.home() / "Downloads")
"""Der Standard-Downloadordner des Nutzers (XDG, sonst ``~/Downloads``)."""

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

RULES_FILE = Path(os.environ.get("SORTITON_RULES", PROJECT_DIR / "my_rules.ini"))
LOG_DIR = Path(os.environ.get("SORTITON_LOG_DIR", PROJECT_DIR / "logs"))
SETTINGS_FILE = Path(os.environ.get("SORTITON_SETTINGS", PROJECT_DIR / "settings.ini"))

BACKUP_DIR = Path(os.environ.get("SORTITON_BACKUP_DIR", PROJECT_DIR / "backups"))

# Ausgaben gehören dem Nutzer, nicht dem Projekt: standardmäßig in einem
# eigenen Ordner im Download-Verzeichnis, damit dort nichts im Quellbaum landet.
EXPORT_DIR = Path(os.environ.get("SORTITON_EXPORT_DIR") or DOWNLOADS_DIR / "Sortiton")
CACHE_DIR = Path(os.environ.get("SORTITON_CACHE_DIR", PROJECT_DIR / "cache"))

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
