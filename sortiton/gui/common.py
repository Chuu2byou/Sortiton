"""Shared imports and GUI helpers."""

# pylint: disable=unused-import

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
from ..cancel import CancelToken, Cancelled
from ..features import FEATURES, get as feature_by_key
from ..tasks import cmd_all, cmd_rename, cmd_restore, cmd_scan, cmd_sort, cmd_tags
from . import design
from .design import (ACCENT, ACCENT_TEXT, BACKGROUND, BORDER, CARD, FIELD, FIELD_ACTIVE,
                     GREEN, LOG_BG, LOG_TEXT, RED, SCROLLBAR, SCROLLBAR_ACTIVE, TEXT,
                     TEXT_FAINT, TEXT_MUTED, YELLOW)
from .confirm import ask_choice, ask_confirm
from .dialogs import _ask_yes_no, _pick_file, _pick_folder, _show_error, _show_warning
from .panels import PreviewCard, ResultPanel, section_label
from .preferences import PreferencesWindow
from .restore import RestoreWindow
from .tools import (ToolsTab, apply_stored, feature_run_label, fine_tuning_items,
                    make_tool_vars, stored_values, tool_value)
from .widgets import Pill, ProgressBar, RoundButton, Segments

_ENV_FOLDER = os.environ.get("SORTITON_FOLDER", "").strip()
DEFAULT_FOLDER = Path(_ENV_FOLDER) if _ENV_FOLDER else config.PROJECT_DIR.parent / "Musik"
if not DEFAULT_FOLDER.is_dir():
    DEFAULT_FOLDER = Path.home() / "Musik"
_ENV_TARGET = os.environ.get("SORTITON_TARGET", "").strip()
TARGET_FOLDER = Path(_ENV_TARGET) if _ENV_TARGET else Path.home() / "Musik"

PATTERN_DEFAULT = "%artist% - %title%"

ROW_TABS, ROW_LINE_TOP, ROW_CONTENT, ROW_ACTIONS, ROW_RESULT = 0, 1, 2, 3, 4
ROW_LINE_BOTTOM, ROW_FOOTER = 5, 6

CONTENT_MAX_WIDTH = 1120

_RESULT_HEIGHT_BASE = 176
_LOG_HEIGHT_BASE = 320

_MAX_PATH_CHARS = 52

_LOG_MAX_LINES = 5000
_LOG_TRIM_LINES = 1000

PLAN_FIELDS = ("artist", "album_artist", "title", "album", "genre",
               "track", "disc", "year")

_ERROR_MARKERS = ("ERROR", "FEHLER")
_OK_MARKERS = ("Done.", "OK:", "Renamed:", "Fertig.", "Umbenannt:")
_INFO_MARKERS = ("->", "PREVIEW", "VORSCHAU")


def _fmt_number(value) -> str:
    """Format a count in the active language (1842 -> 1,842 en / 1.842 de)."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return str(value)
    text = f"{number:,}"
    return text if i18n.get_language() == "en" else text.replace(",", ".")


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
    """Shorten a path for display: the home directory becomes ``~``, very long paths lose their front (keeps the field readable, screenshots free of paths)."""
    text = config.display_path(path)
    if len(text) > _MAX_PATH_CHARS:
        text = "…" + text[-(_MAX_PATH_CHARS - 1):]
    return text
