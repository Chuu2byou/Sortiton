"""Rules: built-in tables, your own rules (my_rules.ini) and the text cleanup.

Built-ins are generic and always active; artist- or collection-specific fixes
belong in my_rules.ini and run afterwards.
"""

from __future__ import annotations

import configparser
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

# Built-in artist/text fixes: (regex, literal replacement). THE ORDER MATTERS.
# Only generic rules belong here - artist names and spellings go into
# my_rules.ini ([Artist] for literals, [Artist Regex] for patterns).
ARTIST_FIXES: tuple[tuple[str, str], ...] = (
    (r"\s+from\s+", "; "),
    (r"\s+with\s+", "; "),
    (r"  +", " "),
    (r"nu{16,}", "nunununununununu"),
)

_ARTIST_FIXES_COMPILED: tuple[tuple[re.Pattern, str], ...] = tuple(
    (re.compile(pattern), replacement) for pattern, replacement in ARTIST_FIXES
)

# Compatibility mirrors of the active custom rules (the GUI reads them).
# Internally the workers use one immutable snapshot (_custom_rules()), so a
# reload while a run is active can never mix two rule sets.
CUSTOM_ARTISTS: list[tuple[re.Pattern, str]] = []
CUSTOM_ARTIST_REGEX: list[tuple[re.Pattern, str]] = []
CUSTOM_GENRES: dict[str, str] = {}
CUSTOM_PROTECTED: list[tuple[re.Pattern, str]] = []

# Section names work in English and German; a broken file never aborts a run -
# bad lines are skipped and reported as warnings.


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


def _set_custom_rules(rules: CustomRules) -> None:
    """Swap the active rule set atomically and refresh the compatibility names."""
    global _CUSTOM, CUSTOM_ARTISTS, CUSTOM_ARTIST_REGEX, CUSTOM_GENRES, CUSTOM_PROTECTED
    with _custom_lock:
        _CUSTOM = rules
    CUSTOM_ARTISTS = list(rules.artists)
    CUSTOM_ARTIST_REGEX = list(rules.regex)
    CUSTOM_GENRES = dict(rules.genres)
    CUSTOM_PROTECTED = list(rules.protected)


# First ```ini fenced block of an LLM answer; without a closing fence the rest
# of the answer counts (models sometimes truncate).
_INI_BLOCK = re.compile(r"```[ \t]*ini[ \t]*\r?\n(.*?)(?:```|\Z)",
                        re.DOTALL | re.IGNORECASE)


def extract_ini_block(text: str) -> str:
    """The INI part of an LLM answer: the first ```ini block, else the whole text.

    The GUI uses this before :func:`parse_custom_rules`, so a chatty answer
    ("Sure, here are the rules: …") is reduced to what can be parsed.
    """
    match = _INI_BLOCK.search(text or "")
    if match:
        return match.group(1).strip("\r\n")
    return (text or "").strip("\r\n")


def parse_custom_rules(text: str,
                       file_name: str = RULES_FILE.name) -> tuple[CustomRules, list[str]]:
    """Parse the content of a my_rules.ini - without touching the file system.

    This is the working half of :func:`load_custom_rules`; the GUI uses it to
    check a pasted LLM answer before it reaches the rules editor. Returns the
    parsed rules and the warnings (empty = all good); bad entries are skipped.
    """
    artists: list[tuple[re.Pattern, str]] = []
    artist_regex: list[tuple[re.Pattern, str]] = []
    genres: dict[str, str] = {}
    protected_rules: list[tuple[re.Pattern, str]] = []
    warnings: list[str] = []

    # An indented line would count as a continuation of the line above (INI quirk).
    content = "\n".join(line.lstrip() for line in text.splitlines())

    parser = configparser.ConfigParser(allow_no_value=True, interpolation=None, strict=False)
    parser.optionxform = lambda optionstr: optionstr  # keep key spelling
    try:
        parser.read_string(content)
    except configparser.Error as error:
        warnings.append(i18n.t("rules.warn.invalid", file=file_name, error=error))
        return CustomRules(artists, artist_regex, genres, protected_rules), warnings

    # Section names are accepted in English and German: the shipped
    # my_rules.ini uses German headings, the generated template English ones.
    def section(*names: str) -> configparser.SectionProxy | None:
        for present in parser.sections():
            if present.strip().lower() in names:
                return parser[present]
        return None

    # [Artist] / [Künstler] - simple replacements, case insensitive
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

    # [Artist Regex] / [Künstler Regex] - replacements using a regular expression
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
            try:
                checker = re.compile(pattern)
                checker.sub(new, "")              # validate the replacement too
            except re.error as error:
                warnings.append(i18n.t("rules.warn.regex_invalid", rule=pattern, error=error))
                continue
            artist_regex.append((checker, new))

    # [Genre] - spellings; an empty value deletes the genre
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

    # [Protected] / [Geschützt] - names that stay as they are (optional spelling)
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
    """Read the custom rules file and swap in the new rule set.

    Returns the warnings (empty = all good); bad entries are skipped. The swap
    is atomic: a run that is already working keeps its old snapshot.
    """
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

        # "(?i:...)" is NOT a capture group - the content is group(1).
        match = re.match(r"^(?i:CV[_.:：]?)\s*(.*)$", inside)
        if match:
            return match.group(1).strip()

        # The bracketed part is the actor; both names stay for feat./ft.
        # "featuring" has to come first in the alternation - otherwise "ft."
        # would match inside it and leave "uring …" behind.
        match = re.match(r"^(?i:featuring|feat\.?|ft\.?)(?=\s|$)\s*(.*)$", inside)
        if match:
            return f"{outside}; {match.group(1).strip()}"

        # idol groups like "... (46)" keep the bracket
        if re.search(r"\d+$", inside):
            return f"{outside}; {inside}"

        # otherwise only the inside survives
        return inside

    return CV_REGEX.sub(replacement, value)


def clean_artist(value: str) -> str:
    """Artist / album artist cleanup (idempotent)."""
    if not value:
        return value or ""

    custom = _custom_rules()
    new = strip_cv_notation(value)

    # Park protected names: they keep their spelling and are restored 1:1 below.
    new, protect_table = _mask_protected(new, custom)

    new = re.sub(r"[\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]", "", new)

    # Full-width characters from Japanese taggers.
    new = new.replace("\uFF06", "&")      # ＆
    new = new.replace("\uFF1B", ";")      # ；
    new = new.replace("\uFF0C", ",")      # ，
    new = new.replace("\u3001", "; ")     # 、

    # "・" only outside single letters (A・B・C).
    if not re.match(r"^[A-Za-z0-9\u3040-\u30FF]{1,3}(·|・)[A-Za-z0-9\u3040-\u30FF]", new):
        new = new.replace("\u30FB", "; ")

    # Built-in fixes - literal replacement (lambda), so special characters are
    # never treated as regex backreferences.
    for pattern, replacement in _ARTIST_FIXES_COMPILED:
        new = pattern.sub(lambda _m, e=replacement: e, new)

    # Custom rules: literals first, then regex - they run after the built-ins.
    for pattern, replacement in custom.artists:
        new = pattern.sub(lambda _m, e=replacement: e, new)
    for pattern, replacement in custom.regex:
        new = pattern.sub(replacement, new)

    # Normalise separators.
    new = re.sub(r"\s*/\s*", "; ", new)
    new = re.sub(r"\s+&\s+", "; ", new)
    new = re.sub(r"\s+[xX×]\s+", "; ", new)
    new = re.sub(r"\s*,\s*", "; ", new)
    new = re.sub(r"(?i)\s+(feat\.?|ft\.?|featuring|meets)\s+", "; ", new)

    # Drop empties and duplicates.
    if ";" in new:
        parts: list[str] = []
        for part in new.split(";"):
            part = part.strip()
            if part and part not in parts:
                parts.append(part)
        new = "; ".join(parts)

    # Restore protected names 1:1 (even with ";" in the name).
    for placeholder, original in protect_table.items():
        new = new.replace(placeholder, original)

    new = re.sub(r"\s*;\s*", "; ", new)
    new = re.sub(r"  +", " ", new)
    new = new.strip()

    # Single correction for a name the built-in rules leave garbled -
    # the overview shows it as artist_f9.
    if new == "Orchestr; a; Plays":
        new = "Orchestra Plays"

    return new


def clean_genre(value: str) -> str:
    """Genre cleanup: normalise spellings, never split at "-".

    Only ";" and "," split, so "J-Pop" stays intact.
    """
    if not value:
        return value or ""

    new = clean_text_field(value)
    custom = _custom_rules()

    parts: list[str] = []
    for part in re.split(r"[;,，、]\s*", new):
        part = part.strip()
        if not part:
            continue
        key = part.lower()
        if key in custom.genres:
            part = custom.genres[key]
            if not part:
                continue          # custom rule with an empty value deletes the genre
        else:
            part = GENRE_ALIASES.get(key, part)
        if part not in parts:
            parts.append(part)

    return "; ".join(parts)
