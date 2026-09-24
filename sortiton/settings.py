"""User settings (settings.ini) - the UI language and the backup switch."""

from __future__ import annotations

import configparser
import os

from . import i18n
from .config import DEFAULT_LANGUAGE, OFF_VALUES, SETTINGS_FILE

SECTION = "general"
KEY_LANGUAGE = "language"
KEY_BACKUP = "backup"


def _parser() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    try:
        parser.read(SETTINGS_FILE, encoding="utf-8")
    except (OSError, configparser.Error):
        pass
    return parser


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
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with SETTINGS_FILE.open("w", encoding="utf-8") as datei:
            parser.write(datei)
    except OSError:
        return False
    return True


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
    """Whether a backup is written before tags change (default: yes).

    ``SORTITON_BACKUP`` overrides settings.ini (so a test run can switch it off).
    """
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
