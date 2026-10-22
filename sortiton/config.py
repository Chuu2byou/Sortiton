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

EXPORT_DIR = Path(os.environ.get("SORTITON_EXPORT_DIR", PROJECT_DIR / "exports"))
CACHE_DIR = Path(os.environ.get("SORTITON_CACHE_DIR", PROJECT_DIR / "cache"))

FETCH_ARCHIVE = Path(os.environ.get("SORTITON_FETCH_ARCHIVE",
                                    PROJECT_DIR / "fetch_archive.txt"))

DEFAULT_LANGUAGE = "en"

LOG_KEEP = 50
LOG_PREFIX = "sortiton"
LATEST_LOG_NAME = "latest.log"

JOURNAL_SUFFIX = ".jsonl"
LATEST_JOURNAL_NAME = "latest_journal.jsonl"
JOURNAL_KEEP = 20

BACKUP_KEEP = 10

OFF_VALUES = {"0", "false", "no", "off", "nein", "aus"}
