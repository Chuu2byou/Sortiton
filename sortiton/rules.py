"""Rules: built-in tables, your own rules (my_rules.ini) and the text cleanup."""

from __future__ import annotations

import configparser
import importlib
import re
import threading
from dataclasses import dataclass
from pathlib import Path

from . import i18n
from .config import INVISIBLE, RULES_FILE

GENRE_ALIASES = {
    "jpop": "J-Pop", "j pop": "J-Pop", "j-pop": "J-Pop",
    "jrock": "J-Rock", "j rock": "J-Rock", "j-rock": "J-Rock",
    "kpop": "K-Pop", "k pop": "K-Pop", "k-pop": "K-Pop",
    "cpop": "C-Pop", "c pop": "C-Pop", "c-pop": "C-Pop",
    "vtuber": "VTuber", "vocaloid": "Vocaloid",
}

ARTIST_FIXES: tuple[tuple[str, str], ...] = (
    (r"\s+from\s+", "; "),
    (r"\s+with\s+", "; "),
    (r"  +", " "),
    (r"nu{16,}", "nunununununununu"),
)

_ARTIST_FIXES_COMPILED: tuple[tuple[re.Pattern, str], ...] = tuple(
    (re.compile(pattern), replacement) for pattern, replacement in ARTIST_FIXES
)

MAX_CUSTOM_REGEX_LENGTH = 500
MAX_CUSTOM_REGEX_INPUT = 512


def builtin_rules_text() -> str:
    """Commented overview of ALL built-in rules (template, GUI and CLI)."""
    lines = [
        i18n.t("rules.overview.header1"),
        i18n.t("rules.overview.header2"),
        i18n.t("rules.overview.header3"),
        i18n.t("rules.overview.header4"),
        i18n.t("rules.overview.header5"),
        "#",
        i18n.t("rules.overview.genre_title"),
    ]
    for old, new in GENRE_ALIASES.items():
        lines.append(f"#      {old} = {new}")
    lines += [
        i18n.t("rules.overview.genre_fixed"),
        i18n.t("rules.overview.genre_f1"),
        i18n.t("rules.overview.genre_f2"),
        i18n.t("rules.overview.genre_f3"),
        "#",
        i18n.t("rules.overview.artist_title"),
        i18n.t("rules.overview.artist_sub1"),
        i18n.t("rules.overview.artist_sub2"),
        i18n.t("rules.overview.artist_sub3"),
    ]
    for pattern, replacement in ARTIST_FIXES:
        lines.append(f'#      "{pattern}" = "{replacement}"')
    lines += [
        i18n.t("rules.overview.artist_fixed"),
        i18n.t("rules.overview.artist_f1"),
        i18n.t("rules.overview.artist_f2"),
        i18n.t("rules.overview.artist_f3"),
        i18n.t("rules.overview.artist_f4"),
        i18n.t("rules.overview.artist_f5"),
        i18n.t("rules.overview.artist_f6"),
        i18n.t("rules.overview.artist_f7"),
        i18n.t("rules.overview.artist_f8"),
        i18n.t("rules.overview.artist_f9"),
        "#",
        i18n.t("rules.overview.protected_title"),
        "#      Example & Co",
        "#      Foo/Bar = Foo / Bar",
    ]
    return "\n".join(lines)


def rules_template() -> str:
    """Template for my_rules.ini (GUI button and ``rules --template``)."""
    return i18n.t("rules.template.header") + "\n\n" + builtin_rules_text() + "\n"


def rules_summary() -> str:
    """Short description of the loaded custom rules (empty = none loaded)."""
    custom = _custom_rules()
    parts: list[str] = []
    if custom.artists:
        parts.append(_count(len(custom.artists), "rules.summary.artists",
                            "rules.summary.artists_plural"))
    if custom.regex:
        parts.append(i18n.t("rules.summary.regex", count=len(custom.regex)))
    if custom.genres:
        parts.append(i18n.t("rules.summary.genre", count=len(custom.genres)))
    if custom.protected:
        parts.append(i18n.t("rules.summary.protected", count=len(custom.protected)))
    return ", ".join(parts)


def rules_status() -> dict:
    """Counts of the active rules, from the last :func:`load_custom_rules` call."""
    custom = _custom_rules()
    return {
        "artist": len(custom.artists),
        "regex": len(custom.regex),
        "genre": len(custom.genres),
        "protected": len(custom.protected),
        "builtin_artists": len(ARTIST_FIXES),
        "builtin_genres": len(GENRE_ALIASES),
        "custom_total": (len(custom.artists) + len(custom.regex)
                         + len(custom.genres) + len(custom.protected)),
    }


def _count(number: int, singular: str, plural: str) -> str:
    key = singular if number == 1 else plural
    return i18n.t(key, count=number)


@dataclass(frozen=True)
class CustomRules:
    """One parsed my_rules.ini - immutable so workers can share it safely."""
    artists: list[tuple[re.Pattern, str]]
    regex: list[tuple[re.Pattern, str]]
    genres: dict[str, str]
    protected: list[tuple[re.Pattern, str]]


_EMPTY_RULES = CustomRules([], [], {}, [])
_CUSTOM = _EMPTY_RULES
_custom_lock = threading.Lock()


def _custom_rules() -> CustomRules:
    """The active rule set as one consistent snapshot."""
    with _custom_lock:
        return _CUSTOM


def snapshot() -> CustomRules:
    """One rule set for a whole run (the GUI may reload rules mid-run)."""
    return _custom_rules()


def _set_custom_rules(rules: CustomRules) -> None:
    """Die aktive Regelmenge atomar tauschen (Leser sehen alt oder neu, nie halb)."""
    global _CUSTOM  # pylint: disable=global-statement
    with _custom_lock:
        _CUSTOM = rules


def _regex_risk(pattern: str) -> bool:
    """Reject the classic catastrophic-backtracking shapes."""
    try:
        constants = importlib.import_module("re._constants")
        parser = importlib.import_module("re._parser")
        tree = parser.parse(pattern, 0)
    except (ImportError, re.error):
        return False

    repeats = {getattr(constants, "MAX_REPEAT", None),
               getattr(constants, "MIN_REPEAT", None)}
    possessive = getattr(constants, "POSSESSIVE_REPEAT", None)
    if possessive is not None:
        repeats.add(possessive)
    repeats.discard(None)
    branch_op = getattr(constants, "BRANCH", None)
    subpattern_op = getattr(constants, "SUBPATTERN", None)
    groupref_op = getattr(constants, "GROUPREF_EXISTS", None)
    assert_ops = (getattr(constants, "ASSERT", None),
                  getattr(constants, "ASSERT_NOT", None))

    def walk(items, inside_repeat: bool) -> bool:
        for op, argument in items:
            if op in repeats:
                body = argument[2]
                if inside_repeat or any(child_op is branch_op
                                        for child_op, _ in body):
                    return True
                if walk(body, True):
                    return True
            elif op is subpattern_op:
                if walk(argument[3], inside_repeat):
                    return True
            elif op is branch_op:
                if inside_repeat:
                    return True
                for branch in argument[1]:
                    if walk(branch, inside_repeat):
                        return True
            elif op is groupref_op:
                if walk(argument[2], inside_repeat) or walk(argument[3], inside_repeat):
                    return True
            elif op in assert_ops:
                if walk(argument[1], inside_repeat):
                    return True
        return False

    return walk(tree, False)


_INI_BLOCK = re.compile(r"```[ \t]*ini[ \t]*\r?\n(.*?)(?:```|\Z)",
                        re.DOTALL | re.IGNORECASE)


def extract_ini_block(text: str) -> str:
    """The INI part of an LLM answer: the first ```ini block, else the whole text."""
    match = _INI_BLOCK.search(text or "")
    if match:
        return match.group(1).strip("\r\n")
    return (text or "").strip("\r\n")


def parse_custom_rules(text: str,
                       file_name: str = RULES_FILE.name) -> tuple[CustomRules, list[str]]:
    """Parse the content of a my_rules.ini - without touching the file system."""
    artists: list[tuple[re.Pattern, str]] = []
    artist_regex: list[tuple[re.Pattern, str]] = []
    genres: dict[str, str] = {}
    protected_rules: list[tuple[re.Pattern, str]] = []
    warnings: list[str] = []

    content = "\n".join(line.lstrip() for line in text.splitlines())

    parser = configparser.ConfigParser(allow_no_value=True, interpolation=None,
                                       strict=False, delimiters=("=",))
    parser.optionxform = lambda optionstr: optionstr
    try:
        parser.read_string(content)
    except configparser.Error as error:
        warnings.append(i18n.t("rules.warn.invalid", file=file_name, error=error))
        return CustomRules(artists, artist_regex, genres, protected_rules), warnings

    def section(*names: str) -> configparser.SectionProxy | None:
        for present in parser.sections():
            if present.strip().lower() in names:
                return parser[present]
        return None

    simple = section("artist", "artists", "künstler", "kuenstler")
    if simple is not None:
        for old, new in simple.items():
            old = old.strip()
            if not old:
                continue
            if new is None:
                warnings.append(i18n.t("rules.warn.artist_no_equals", rule=old))
                continue
            artists.append((re.compile(re.escape(old), re.IGNORECASE), new))

    regex = section("artist regex", "artist-regex", "regex", "künstler regex",
                    "kuenstler regex", "künstler-regex", "kuenstler-regex")
    if regex is not None:
        for pattern, new in regex.items():
            pattern = pattern.strip()
            if not pattern:
                continue
            if new is None:
                warnings.append(i18n.t("rules.warn.regex_no_equals", rule=pattern))
                continue
            if len(pattern) > MAX_CUSTOM_REGEX_LENGTH:
                warnings.append(i18n.t("rules.warn.regex_too_long", rule=pattern))
                continue
            if _regex_risk(pattern):
                warnings.append(i18n.t("rules.warn.regex_unsafe", rule=pattern))
                continue
            try:
                checker = re.compile(pattern)
                checker.sub(new, "")
            except re.error as error:
                warnings.append(i18n.t("rules.warn.regex_invalid", rule=pattern, error=error))
                continue
            artist_regex.append((checker, new))

    genre = section("genre", "genres")
    if genre is not None:
        for old, new in genre.items():
            old = old.strip().lower()
            if not old:
                continue
            if new is None:
                warnings.append(i18n.t("rules.warn.genre_no_equals", rule=old))
                continue
            genres[old] = new

    protected = section("protected", "geschützt", "geschuetzt")
    if protected is not None:
        for word, wanted in protected.items():
            word = word.strip()
            if not word:
                continue
            protected_rules.append(
                (re.compile(re.escape(word), re.IGNORECASE),
                 str(wanted).strip() if wanted else ""))

    return CustomRules(artists, artist_regex, genres, protected_rules), warnings


def load_custom_rules(path: Path | None = None) -> list[str]:
    """Read the custom rules file and swap in the new rule set."""
    file = Path(path) if path is not None else RULES_FILE
    if not file.is_file():
        _set_custom_rules(_EMPTY_RULES)
        return []

    try:
        content = file.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        _set_custom_rules(_EMPTY_RULES)
        return [i18n.t("rules.warn.read", file=file.name, error=error)]

    parsed, warnings = parse_custom_rules(content, file.name)
    _set_custom_rules(parsed)
    return warnings


def _mask_protected(text: str,
                    custom: CustomRules | None = None) -> tuple[str, dict[str, str]]:
    """Swap protected names for placeholders and return the restore table."""
    custom = custom or _custom_rules()
    table: dict[str, str] = {}
    for index, (pattern, wanted) in enumerate(custom.protected):
        counter = 0

        def replace(m: re.Match, index: int = index, wanted: str = wanted) -> str:
            nonlocal counter
            placeholder = f"\uE000{index}.{counter}\uE001"
            counter += 1
            table[placeholder] = wanted or m.group(0)
            return placeholder

        text = pattern.sub(replace, text)
    return text, table


CV_REGEX = re.compile(r"([^();,&/、＆；，\s][^();,&/、＆；，]*?)\(([^)]+)\)")


def clean_text_field(value: str) -> str:
    """Tidy one field: no invisible characters, no double spaces."""
    if not value:
        return value or ""
    value = INVISIBLE.sub("", value)
    value = re.sub(r"  +", " ", value)
    return value.strip()


def strip_cv_notation(value: str) -> str:
    """Resolve bracket notation, e.g. "Character (CV: Actor)" -> "Actor"."""
    if not value:
        return value

    def replacement(m: re.Match) -> str:
        outside = m.group(1).strip()
        inside = m.group(2).strip()

        match = re.match(r"^(?i:CV[_.:：]?)\s*(.*)$", inside)
        if match:
            return match.group(1).strip()

        match = re.match(r"^(?i:featuring|feat\.?|ft\.?)(?=\s|$)\s*(.*)$", inside)
        if match:
            return f"{outside}; {match.group(1).strip()}"

        if re.search(r"\d+$", inside):
            return f"{outside}; {inside}"

        return inside

    return CV_REGEX.sub(replacement, value)


def clean_artist(value: str, custom: CustomRules | None = None) -> str:
    """Artist / album artist cleanup (idempotent)."""
    if not value:
        return value or ""

    custom = custom or _custom_rules()
    new = strip_cv_notation(value)

    new, protect_table = _mask_protected(new, custom)

    new = re.sub(r"[\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]", "", new)

    new = new.replace("\uFF06", "&")
    new = new.replace("\uFF1B", ";")
    new = new.replace("\uFF0C", ",")
    new = new.replace("\u3001", "; ")

    if not re.match(r"^[A-Za-z0-9\u3040-\u30FF]{1,3}(·|・)[A-Za-z0-9\u3040-\u30FF]", new):
        new = new.replace("\u30FB", "; ")

    for pattern, replacement in _ARTIST_FIXES_COMPILED:
        new = pattern.sub(lambda _m, e=replacement: e, new)

    for pattern, replacement in custom.artists:
        new = pattern.sub(lambda _m, e=replacement: e, new)
    if len(new) <= MAX_CUSTOM_REGEX_INPUT:
        for pattern, replacement in custom.regex:
            new = pattern.sub(replacement, new)

    new = re.sub(r"\s*/\s*", "; ", new)
    new = re.sub(r"\s+&\s+", "; ", new)
    new = re.sub(r"\s+[xX×]\s+", "; ", new)
    new = re.sub(r"\s*,\s*", "; ", new)
    new = re.sub(r"(?i)\s+(feat\.?|ft\.?|featuring|meets)\s+", "; ", new)

    if ";" in new:
        parts: list[str] = []
        for part in new.split(";"):
            part = part.strip()
            if part and part not in parts:
                parts.append(part)
        new = "; ".join(parts)

    for placeholder, original in protect_table.items():
        new = new.replace(placeholder, original)

    new = re.sub(r"\s*;\s*", "; ", new)
    new = re.sub(r"  +", " ", new)
    new = new.strip()

    # Correct a known artist-name split; also listed in --builtin.
    if new == "Orchestr; a; Plays":
        new = "Orchestra Plays"

    return new


def clean_genre(value: str, custom: CustomRules | None = None) -> str:
    """Genre cleanup: normalise spellings, never split at "-"."""
    if not value:
        return value or ""

    new = clean_text_field(value)
    custom = custom or _custom_rules()

    parts: list[str] = []
    for part in re.split(r"[;,，、]\s*", new):
        part = part.strip()
        if not part:
            continue
        key = part.lower()
        if key in custom.genres:
            part = custom.genres[key]
            if not part:
                continue
        else:
            part = GENRE_ALIASES.get(key, part)
        if part not in parts:
            parts.append(part)

    return "; ".join(parts)
