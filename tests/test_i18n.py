"""Check translation catalogs for duplicate and missing keys."""

from __future__ import annotations

import ast
import re

from _support import BASE, Path, check, i18n

# Match literal keys passed to ``i18n.t_in(lang, ...)``.
_T_IN_RE = re.compile(r"""t_in\(\s*[A-Za-z_][A-Za-z0-9_]*\s*,\s*["']([A-Za-z0-9_.-]+)["']""")

# Keys with dynamically generated codes.
_DATE_SAMPLES = (
    ("", "empty"),
    ("1998", "year"),
    ("1998-05-03", "ymd"),
    ("1998.05.03", "ymd_dot"),
    ("1998-05", "ym"),
    ("1998/05/03", "slash_ymd"),
    ("1998/05", "slash_ym"),
    ("03.05.1998", "dmy"),
    ("1998-05-03 10:00", "iso"),
    ("1998-2000", "range"),
    ("irgendwas", "other"),
)
_FP_BUCKETS = ("sehr_wahrscheinlich", "wahrscheinlich", "pruefen", "aehnlich")

_SOURCE = (BASE / "sortiton" / "i18n.py").read_text(encoding="utf-8")


def _literal_key_counts(source: str = _SOURCE) -> dict[str, dict[str, int]]:
    """Count literal keys in each translation catalog."""
    counts: dict[str, dict[str, int]] = {}
    for node in ast.parse(source).body:
        name = ""
        value = None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("_EN", "_DE"):
                    name, value = target.id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in ("_EN", "_DE") and isinstance(node.value, ast.Dict):
                name, value = node.target.id, node.value
        if value is None or not isinstance(value, ast.Dict):
            continue
        seen: dict[str, int] = {}
        for key in value.keys:
            if isinstance(key, ast.Constant):
                seen[str(key.value)] = seen.get(str(key.value), 0) + 1
        counts[name] = seen
    return counts


def _python_files() -> list[Path]:
    """Every module of the package plus the two entry scripts."""
    return sorted((BASE / "sortiton").rglob("*.py")) + sorted(BASE.glob("sortiton*.py"))


def test_catalog_has_no_duplicate_keys() -> None:
    """A key written twice loses its first translation without any error."""
    counts = _literal_key_counts()
    check("both catalogs were parsed", set(counts) == {"_EN", "_DE"}, str(sorted(counts)))
    check("both catalogs were read completely",
          all(len(counts[name]) > 100 for name in ("_EN", "_DE")),
          str({name: len(counts[name]) for name in counts}))
    sample = _literal_key_counts('_EN = {"a": "1", "a": "2", "b": "3"}')
    check("the duplicate detector itself works", sample["_EN"].get("a") == 2,
          str(sample))

    for name in ("_EN", "_DE"):
        duplicates = sorted(key for key, count in counts[name].items() if count > 1)
        check(f"{name} defines every key exactly once", not duplicates,
              ", ".join(duplicates))


def test_render_keys_exist_in_both_languages() -> None:
    """``i18n.t_in(lang, "...")`` renders without the English fallback."""
    found: set[str] = set()
    for path in _python_files():
        found |= set(_T_IN_RE.findall(path.read_text(encoding="utf-8")))
    check("t_in() literals were found at all", bool(found))

    en, de = i18n.catalog("en"), i18n.catalog("de")
    for name, catalog in (("en", en), ("de", de)):
        missing = sorted(key for key in found if key not in catalog)
        check(f"every t_in key exists in {name}", not missing, ", ".join(missing[:8]))


def test_dynamic_keys_exist_in_both_languages() -> None:
    """Keys assembled from data stay complete when a variant is added."""
    from sortiton.features.export.analysis import date_fmt
    from sortiton.gui.common import PLAN_FIELDS

    expected_fields = {"artist", "album_artist", "title", "album", "genre",
                       "track", "disc", "year"}
    check("PLAN_FIELDS is the set this test knows", set(PLAN_FIELDS) == expected_fields,
          str(sorted(PLAN_FIELDS)))

    keys = [f"gui.field.{field}" for field in PLAN_FIELDS]
    keys += [f"export.report.fp.bucket.{bucket}" for bucket in _FP_BUCKETS]
    keys += [f"export.report.date.{code}" for _text, code in _DATE_SAMPLES]

    reached = {date_fmt(text) for text, _code in _DATE_SAMPLES}
    check("the date samples cover the expected codes", reached == {code for _t, code
                                                                  in _DATE_SAMPLES},
          str(sorted(reached)))

    en, de = i18n.catalog("en"), i18n.catalog("de")
    for name, catalog in (("en", en), ("de", de)):
        missing = sorted(key for key in keys if key not in catalog)
        check(f"every dynamically built key exists in {name}", not missing,
              ", ".join(missing))


def test_feature_descriptions_are_translated() -> None:
    """``FEATURES`` describes the CLI and the GUI, so its keys have to exist."""
    from sortiton.features import FEATURES

    check("features are registered", bool(FEATURES))
    en, de = i18n.catalog("en"), i18n.catalog("de")

    keys: list[str] = []
    for feature in FEATURES:
        keys += [feature.title_key, feature.help_key]
        keys += [option.help_key for option in feature.options if option.help_key]

    for name, catalog in (("en", en), ("de", de)):
        missing = sorted({key for key in keys if key not in catalog})
        check(f"every feature/option key exists in {name}", not missing,
              ", ".join(missing))
