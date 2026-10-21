"""Shared imports, constants and formatters for the GUI modules.

Kept out of :mod:`sortiton.gui.app` so the mixins can import them without
creating a cycle back to the class that composes them.
"""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import threading
import traceback
from pathlib import Path
from types import SimpleNamespace

import tkinter as tk
from tkinter import ttk

from .. import config, i18n, journal, output, rules, settings
from ..cancel import CancelToken
from ..features import FEATURES, get as feature_by_key
from ..tasks import cmd_all, cmd_rename, cmd_restore, cmd_scan, cmd_sort, cmd_tags
from . import design
from .design import (ACCENT, ACCENT_TEXT, BACKGROUND, BORDER, CARD, FIELD, FIELD_ACTIVE,
                     GREEN, LOG_BG, LOG_TEXT, RED, SCROLLBAR, SCROLLBAR_ACTIVE, TEXT,
                     TEXT_FAINT, TEXT_MUTED, YELLOW)
from .confirm import ask_confirm
from .dialogs import _ask_yes_no, _pick_file, _pick_folder, _show_error, _show_warning
from .panels import PreviewCard, ResultPanel, section_label
from .preferences import PreferencesWindow
from .restore import RestoreWindow
from .tools import (ToolsTab, apply_stored, feature_run_label, fine_tuning_items,
                    make_tool_vars, stored_values, tool_value)
from .widgets import Pill, ProgressBar, RoundButton, Segments

# Default folders: "Musik" next to the project folder (fallback ~/Musik) and the
# library. SORTITON_FOLDER / SORTITON_TARGET override them.
_ENV_FOLDER = os.environ.get("SORTITON_FOLDER", "").strip()
DEFAULT_FOLDER = Path(_ENV_FOLDER) if _ENV_FOLDER else config.PROJECT_DIR.parent / "Musik"
if not DEFAULT_FOLDER.is_dir():
    DEFAULT_FOLDER = Path.home() / "Musik"
_ENV_TARGET = os.environ.get("SORTITON_TARGET", "").strip()
TARGET_FOLDER = Path(_ENV_TARGET) if _ENV_TARGET else Path.home() / "Musik"

PATTERN_DEFAULT = "%artist% - %title%"

# Rows of the root grid (named so the layout can be changed in one place).
ROW_TABS, ROW_LINE_TOP, ROW_CONTENT, ROW_ACTIONS, ROW_RESULT = 0, 1, 2, 3, 4
ROW_LINE_BOTTOM, ROW_FOOTER = 5, 6

#: Widest the form area gets (design pixels); wider windows centre the column.
CONTENT_MAX_WIDTH = 1120

# Base heights in design pixels; :meth:`SortitonGUI._apply_scale` turns them into
# device pixels once the screen scale is known (the tests read them afterwards).
_RESULT_HEIGHT_BASE = 176      # result area in counter mode
_LOG_HEIGHT_BASE = 320         # … and with the full log open

#: Longest path shown in a form field; the front is dropped beyond this.
_MAX_PATH_CHARS = 52

#: The log widget keeps at most this many lines (the history list is separate
#: and shorter); trimming prevents an endless Text buffer on long runs.
_LOG_MAX_LINES = 5000
_LOG_TRIM_LINES = 1000

# Tag fields shown in the preview, in that order.
PLAN_FIELDS = ("artist", "album_artist", "title", "album", "genre",
               "track", "disc", "year")

# Keywords for colouring log lines (both languages).
_ERROR_MARKERS = ("ERROR", "FEHLER")
_OK_MARKERS = ("Done.", "OK:", "Renamed:", "Fertig.", "Umbenannt:")
_INFO_MARKERS = ("->", "PREVIEW", "VORSCHAU")


def _fmt_number(value) -> str:
    """Format a count with thousands separators (1842 -> 1.842)."""
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


def _fmt_duration(value) -> str:
    """Format a duration in seconds as ``M:SS`` or ``H:MM:SS`` (``?`` if unknown)."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return "?"
    if seconds <= 0:
        return "?"
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _pretty_path(path) -> str:
    """Shorten a path for display: the home directory becomes ``~``, very long
    paths lose their front (keeps the field readable, screenshots free of paths).
    """
    text = str(path or "").strip()
    if not text:
        return text
    try:
        home = Path.home()
        candidate = Path(text).expanduser()
        if candidate == home:
            text = "~"
        elif home in candidate.parents:
            text = "~/" + str(candidate.relative_to(home))
    except (OSError, ValueError):
        pass
    if len(text) > _MAX_PATH_CHARS:
        text = "…" + text[-(_MAX_PATH_CHARS - 1):]
    return text
