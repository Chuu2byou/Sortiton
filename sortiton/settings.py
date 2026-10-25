"""User settings (settings.ini) - language, backup switch and fine-tuning."""

from __future__ import annotations

import configparser
import os
import re

from . import i18n
from .config import DEFAULT_LANGUAGE, OFF_VALUES, SETTINGS_FILE
from .fileops import atomic_write_text

SECTION = "general"
KEY_LANGUAGE = "language"
KEY_BACKUP = "backup"
KEY_TRACK_FORMAT = "track_format"
KEY_THEME = "theme"

#: How track/disc numbers are normalised when tags are cleaned.
#: ``keep`` leaves them alone, ``number`` turns ``1/11`` into ``1`` and
#: ``padded`` turns ``1`` into ``01``.
TRACK_FORMATS = ("keep", "number", "padded")
THEME_MODES = ("auto", "light", "dark")

SECTION_TOOLS = "tools"

#: ``key<sep>value`` einer Zeile; ``sep`` bleibt beim Ersetzen erhalten.
_KEY_LINE = re.compile(r"^(?P<key>[^=:#\s][^=:]*?)(?P<sep>\s*[=:]\s*)(?P<value>.*)$")


def _parser() -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(SETTINGS_FILE, encoding="utf-8")
    except (OSError, configparser.Error):
        pass
    return parser


def _merge_settings(text: str, parser: configparser.ConfigParser) -> str:
    """Ersetzt Werte in ``text`` und ergänzt fehlende Schlüssel.

    ``ConfigParser.write`` würde die Datei neu formatieren und dabei alle
    Kommentare und die Reihenfolge verlieren - ``settings.ini`` darf aber von
    Hand gepflegt werden. Deshalb bleiben alle anderen Zeilen unangetastet:
    nur der Wert bekannter Schlüssel wird ausgetauscht, Schlüssel, die der
    Parser nicht mehr kennt, fallen weg (das ist das "Ersetzen" von
    ``[tools]``), und fehlende Zeilen werden am Abschnittsende angehängt.
    """
    wanted = {section: dict(parser.items(section)) for section in parser.sections()}
    done: set[tuple[str, str]] = set()
    seen: set[str] = set()
    out: list[str] = []
    current: str | None = None

    def flush() -> None:
        """Fehlende Schlüssel des laufenden Abschnitts anhängen."""
        if current is None or current not in wanted:
            return
        for key, value in wanted[current].items():
            if (current, key) not in done:
                out.append(f"{key} = {value}")
                done.add((current, key))

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            flush()
            current = stripped[1:-1].strip()
            seen.add(current)
            out.append(line)
            continue
        match = _KEY_LINE.match(stripped) if current in wanted else None
        if match is not None and not line[:1].isspace():
            key = match.group("key").strip()
            if key.lower() not in wanted[current]:
                continue  # absichtlich entfernt (z. B. altes Werkzeug-Option)
            out.append(f"{key}{match.group('sep')}{wanted[current][key.lower()]}")
            done.add((current, key.lower()))
            continue
        out.append(line)
    flush()
    for name, values in wanted.items():
        if name in seen:
            continue
        if out:
            out.append("")
        out.append(f"[{name}]")
        out.extend(f"{key} = {value}" for key, value in values.items())
    return "\n".join(out).rstrip("\n") + "\n"


def _write(parser: configparser.ConfigParser) -> bool:
    """Write the parser back to settings.ini. False if that failed."""
    try:
        try:
            text = SETTINGS_FILE.read_text(encoding="utf-8")
        except OSError:
            text = ""
        atomic_write_text(SETTINGS_FILE, _merge_settings(text, parser))
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


def resolve_track_format() -> str:
    """Active track/disc format: settings.ini, falling back to ``keep``."""
    stored = read_value(KEY_TRACK_FORMAT, "").strip().lower()
    return stored if stored in TRACK_FORMATS else "keep"


def save_track_format(value: str) -> bool:
    """Remember the track/disc format in settings.ini."""
    return write_value(KEY_TRACK_FORMAT, value if value in TRACK_FORMATS else "keep")


def resolve_theme() -> str:
    """Selected theme mode, falling back to system appearance."""
    stored = read_value(KEY_THEME, "").strip().lower()
    return stored if stored in THEME_MODES else "auto"


def save_theme(value: str) -> bool:
    """Remember the selected theme mode in settings.ini."""
    return write_value(KEY_THEME, value if value in THEME_MODES else "auto")
