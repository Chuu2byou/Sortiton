"""User settings (settings.ini) - language, backup switch and fine-tuning."""

from __future__ import annotations

import configparser
import io
import os

from . import i18n
from .config import DEFAULT_LANGUAGE, OFF_VALUES, SETTINGS_FILE
from .fileops import atomic_write_text

SECTION = "general"
KEY_LANGUAGE = "language"
KEY_BACKUP = "backup"

SECTION_TOOLS = "tools"


def _parser() -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(SETTINGS_FILE, encoding="utf-8")
    except (OSError, configparser.Error):
        pass
    return parser


def _write(parser: configparser.ConfigParser) -> bool:
    """Write the parser back to settings.ini. False if that failed."""
    try:
        buffer = io.StringIO()
        parser.write(buffer)
        atomic_write_text(SETTINGS_FILE, buffer.getvalue())
    except OSError:
        return False
    return True


def read_value(key: str, default: str = "") -> str:
    """Read a value from the [general] section."""
    parser = _parser()
    if not parser.has_section(SECTION):
        return default
    return parser.get(SECTION, key, fallback=default)


def write_value(key: str, value: str) -> bool:
    """Store a value in the [general] section. False if it could not be written."""
    parser = _parser()
    if not parser.has_section(SECTION):
        parser.add_section(SECTION)
    parser.set(SECTION, key, value)
    return _write(parser)


def read_tool_values() -> dict[str, str]:
    """All stored tool options from the [tools] section (empty if there is none)."""
    parser = _parser()
    if not parser.has_section(SECTION_TOOLS):
        return {}
    return {key: value for key, value in parser.items(SECTION_TOOLS)}


def save_tool_values(values: dict[str, str]) -> bool:
    """Replace the [tools] section with ``values``. False if it could not be written."""
    parser = _parser()
    if parser.has_section(SECTION_TOOLS):
        parser.remove_section(SECTION_TOOLS)
    parser.add_section(SECTION_TOOLS)
    for key, value in values.items():
        parser.set(SECTION_TOOLS, key, value)
    return _write(parser)


def resolve_language() -> str:
    """Active language: SORTITON_LANG, then settings.ini, then the default."""
    aus_env = os.environ.get("SORTITON_LANG", "").strip().lower()
    if aus_env in i18n.available():
        return aus_env
    aus_datei = read_value(KEY_LANGUAGE, "").strip().lower()
    if aus_datei in i18n.available():
        return aus_datei
    return DEFAULT_LANGUAGE


def apply_language() -> str:
    """Activate the resolved language and return it."""
    return i18n.set_language(resolve_language())


def save_language(code: str) -> bool:
    """Remember the chosen language in settings.ini."""
    return write_value(KEY_LANGUAGE, code)


def resolve_backup() -> bool:
    """Whether a backup is written before tags change (default: yes)."""
    from_env = os.environ.get("SORTITON_BACKUP", "").strip().lower()
    if from_env:
        return from_env not in OFF_VALUES
    stored = read_value(KEY_BACKUP, "").strip().lower()
    if stored:
        return stored not in OFF_VALUES
    return True


def save_backup(enabled: bool) -> bool:
    """Remember the backup switch in settings.ini."""
    return write_value(KEY_BACKUP, "true" if enabled else "false")
