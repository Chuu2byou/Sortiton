"""Configuration: constants, paths and performance settings."""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

# Folder of the package and of the entry scripts next to it.
PACKAGE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = PACKAGE_DIR.parent

# Running from the checkout (sortiton.py next to the package) keeps logs, rules,
# settings and backups in the project folder. A frozen build (PyInstaller) and an
# installed package must not write there - that folder belongs to the system -
# so both use the user's data folder instead. SORTITON_DATA_DIR moves it.
FROZEN = bool(getattr(sys, "frozen", False))
IN_SOURCE_TREE = not FROZEN and (SOURCE_DIR / "sortiton.py").is_file()
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
PROJECT_DIR = (SOURCE_DIR if IN_SOURCE_TREE
               else Path(os.environ.get("SORTITON_DATA_DIR") or DATA_HOME / "sortiton"))

# The icons travel with the program: a frozen build unpacks them next to the
# executable (sys._MEIPASS).
ASSETS_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_DIR)) / "assets"

AUDIO_EXTENSIONS = {
    ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wav", ".wma",
    ".opus", ".ape", ".mpc", ".wv",
}

FALLBACK_ARTIST = "_Unknown"
MAX_NAME_LENGTH = 120

READ_WORKERS = min(8, os.cpu_count() or 4)
MUTAGEN_AVAILABLE = importlib.util.find_spec("mutagen") is not None
WRITE_WORKERS = 8 if MUTAGEN_AVAILABLE else 4
COPY_WORKERS = 4

# Invisible, zero-width and BIDI characters.
INVISIBLE = re.compile(
    r"[\u00AD\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFE00-\uFE0F\uFEFF\uFFF0-\uFFFF]"
)

# Valid on Linux, but known to break sync tools and SMB shares.
INVALID_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1F\x7F]')

# Every user path can be moved with an environment variable.
RULES_FILE = Path(os.environ.get("SORTITON_RULES", PROJECT_DIR / "my_rules.ini"))
LOG_DIR = Path(os.environ.get("SORTITON_LOG_DIR", PROJECT_DIR / "logs"))
SETTINGS_FILE = Path(os.environ.get("SORTITON_SETTINGS", PROJECT_DIR / "settings.ini"))

# Copies of the original files, taken before tags are changed (GUI option).
BACKUP_DIR = Path(os.environ.get("SORTITON_BACKUP_DIR", PROJECT_DIR / "backups"))

# SORTITON_LANG overrides settings.ini.
DEFAULT_LANGUAGE = "en"

LOG_KEEP = 50
LOG_PREFIX = "sortiton"
LATEST_LOG_NAME = "latest.log"

# The run journal sits next to the log file and shares its name, so both are
# created and pruned together. SORTITON_JOURNAL=false switches it off; the
# journal keeps fewer runs than the log because it is the bigger file.
JOURNAL_SUFFIX = ".jsonl"
LATEST_JOURNAL_NAME = "latest_journal.jsonl"
JOURNAL_KEEP = 20

BACKUP_KEEP = 10

# SORTITON_JOURNAL and SORTITON_BACKUP: these values mean "off".
OFF_VALUES = {"0", "false", "no", "off", "nein", "aus"}
