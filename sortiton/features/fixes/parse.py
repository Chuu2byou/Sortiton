"""Parsing and validation for the fixes CSV (``path;field;old;new``)."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path

FIELD_ALIASES: dict[str, str] = {
    "artist": "artist",
    "albumartist": "album_artist",
    "album_artist": "album_artist",
    "album": "album",
    "title": "title",
    "genre": "genre",
    "track": "track",
    "disc": "disc",
    "year": "year",
}

_HEADER_FIELDS = {"field", "feld"}

_TRACK_RE = re.compile(r"^\d+(/\d+)?$")

_YEAR_RE = re.compile(r"^\d{4}([-./]\d{2}([-./]\d{2})?)?$")


@dataclass
class FixRow:
    """One CSV data line, still without a resolved path."""

    line: int
    path: str
    field_text: str
    old: str
    new: str
    field: str = ""
    error: str = ""
    error_args: dict = dataclass_field(default_factory=dict)


def canonical_field(text: str) -> str:
    """Canonical tag field for a CSV field cell; "" when it is unknown."""
    return FIELD_ALIASES.get(text.strip().casefold(), "")


def value_ok(tag_field: str, value: str) -> bool:
    """Whether a new value is allowed for ``tag_field`` ("" deletes the field)."""
    value = value.strip()
    if value == "":
        return True
    if tag_field in ("track", "disc"):
        return bool(_TRACK_RE.match(value))
    if tag_field == "year":
        return bool(_YEAR_RE.match(value))
    return True


def read_csv(text: str) -> list[FixRow]:
    """Every data line of the CSV in file order."""
    rows: list[FixRow] = []
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff")), delimiter=";")
    for number, cells in enumerate(reader, start=1):
        if not cells or all(not cell.strip() for cell in cells):
            continue
        field_cell = cells[1] if len(cells) > 1 else ""
        if number == 1 and field_cell.strip().casefold() in _HEADER_FIELDS:
            continue
        if len(cells) != 4:
            rows.append(FixRow(number, cells[0].strip() if cells else "", "", "", "",
                               error="fixes.error.columns",
                               error_args={"line": number, "count": len(cells)}))
            continue
        rows.append(FixRow(number, cells[0].strip(), cells[1].strip(),
                           cells[2].strip(), cells[3].strip(),
                           field=canonical_field(cells[1])))
    return rows


def resolve_path(root: Path | None, path_text: str) -> tuple[Path | None, str]:
    """Resolve one CSV path strictly inside ``root``."""
    if not path_text:
        return None, "fixes.error.path"
    raw = Path(path_text).expanduser()
    if not raw.is_absolute():
        if root is None:
            return None, "fixes.error.root_required"
        raw = root / raw
    try:
        resolved = raw.resolve()
    except OSError:
        return None, "fixes.error.path"
    if root is not None:
        try:
            resolved.relative_to(root)
        except ValueError:
            return None, "fixes.error.outside_root"
    return resolved, ""
