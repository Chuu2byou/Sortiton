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
_XDG_DATA_HOME = os.environ.get("XDG_DATA_HOME", "").strip()
DATA_HOME = Path(_XDG_DATA_HOME) if _XDG_DATA_HOME else Path.home() / ".local" / "share"
_DATA_DIR = os.environ.get("SORTITON_DATA_DIR", "").strip()
# An explicit SORTITON_DATA_DIR wins everywhere - also in the checkout, where a
# test run or a portable setup may want its data somewhere else.
PROJECT_DIR = (Path(_DATA_DIR) if _DATA_DIR else
               SOURCE_DIR if IN_SOURCE_TREE else DATA_HOME / "sortiton")

# The icons travel with the program: a frozen build unpacks them next to the
# executable (sys._MEIPASS).
ASSETS_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_DIR)) / "assets"

AUDIO_EXTENSIONS = {
    ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wav", ".wma",
    ".opus", ".ape", ".mpc", ".wv",
}

# A few more formats a read-only feature may look at (MP4/Ogg-Audio and AIFF)
# but that the tag/rename/sort paths must leave alone - they would otherwise
# touch video files. Only read-only features use READ_EXTENSIONS; every writing
# command keeps using AUDIO_EXTENSIONS.
READ_EXTENSIONS = AUDIO_EXTENSIONS | {".oga", ".mp4", ".aiff", ".aif"}

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

# Where "sortiton export" puts its reports and where fingerprints are cached.
EXPORT_DIR = Path(os.environ.get("SORTITON_EXPORT_DIR", PROJECT_DIR / "exports"))
CACHE_DIR = Path(os.environ.get("SORTITON_CACHE_DIR", PROJECT_DIR / "cache"))

# yt-dlp's download archive: it keeps the same track from being loaded twice.
# A restore removes its line again when it deletes a download (step 4.4).
FETCH_ARCHIVE = Path(os.environ.get("SORTITON_FETCH_ARCHIVE",
                                    PROJECT_DIR / "fetch_archive.txt"))

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
