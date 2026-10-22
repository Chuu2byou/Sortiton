"""Public interface, version, catalogs and wheel contents."""

from __future__ import annotations

from _support import (
    BASE,
    KEY_RE,
    Path,
    check,
    config,
    files,
    i18n,
    importlib,
    ms,
    re,
    tempfile,
)


def test_import() -> None:
    print("import / public interface")
    check("__all__ is not empty", bool(ms.__all__))
    missing = [name for name in ms.__all__ if not hasattr(ms, name)]
    check("__all__ names exist", not missing, ", ".join(missing))


def test_file_names() -> None:
    """free_target on a case-insensitive file system (FAT32/exFAT/NTFS)."""
    print("file names / free_target")
    import unittest.mock as mock

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        own = folder / "Artist - Track.mp3"
        own.write_bytes(b"x")
        check("a file never blocks its own name",
              files.free_target(own, set(), ignore=own) == own)

        # On a case-insensitive file system the path exists even though only
        # the spelling differs: that must not produce "Artist - Track (2)".
        upper = folder / "ARTIST - TRACK.mp3"
        with mock.patch.object(Path, "exists", return_value=True):
            got = files.free_target(upper, set(), ignore=own)
        check("a case-only difference is not a collision", got == upper, str(got))

        other = folder / "other.mp3"
        other.write_bytes(b"y")
        check("a real collision still gets (2)",
              files.free_target(other, set()) == folder / "other (2).mp3")


def test_version() -> None:
    print("version and entry points")
    text = (BASE / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    check("pyproject.toml names a version", match is not None)
    if match:
        # The release workflow compares the git tag with __version__ and puts it
        # into the file names, so both must say the same.
        found = match.group(1)
        check("version matches sortiton.__version__", found == ms.__version__,
              "" if found == ms.__version__ else f"{found} != {ms.__version__}")

    # Every console script of the wheel points at something that exists.
    for module_name in ("sortiton.cli", "sortiton.gui.launch"):
        spec = importlib.util.find_spec(module_name)
        check(f"entry point module {module_name}",
              spec is not None and hasattr(importlib.import_module(module_name), "main"))


def test_catalogs() -> None:
    print("translation catalogs")
    en, de = i18n.catalog("en"), i18n.catalog("de")
    check("both catalogs non-empty", bool(en) and bool(de))

    only_en = sorted(set(en) - set(de))
    only_de = sorted(set(de) - set(en))
    check("same keys in en/de", not only_en and not only_de,
          f"en only: {only_en[:5]} de only: {only_de[:5]}")

    raw: set[str] = set()
    for path in sorted(BASE.glob("sortiton/**/*.py")) + [BASE / "sortiton.py"]:
        raw |= set(KEY_RE.findall(path.read_text(encoding="utf-8")))

    # Without this the two checks below would pass on a project that calls
    # i18n differently - nothing found is not the same as nothing wrong.
    check("i18n.t() calls were found at all", bool(raw))

    # Dynamic keys such as i18n.t("gui.confirm." + page + ".title") are found as
    # a bare prefix and can only be checked for having entries at all.
    used = {key for key in raw if not key.endswith(".")}
    prefixes = sorted(key for key in raw if key.endswith("."))
    unknown = sorted(used - set(en))
    check("every used key exists", not unknown, ", ".join(unknown[:8]))

    empty_prefixes = [prefix for prefix in prefixes
                      if not any(key.startswith(prefix) for key in en)]
    check("dynamic key prefixes exist", not empty_prefixes, ", ".join(empty_prefixes))


def test_packages_complete() -> None:
    """Step 1.9: every package of ``sortiton`` is listed for the wheel (P9)."""
    print("wheel packages")
    import tomllib

    text = (BASE / "pyproject.toml").read_text(encoding="utf-8")
    listed = set(tomllib.loads(text)["tool"]["setuptools"]["packages"])
    needed = {path.parent.relative_to(BASE).as_posix().replace("/", ".")
              for path in (BASE / "sortiton").rglob("__init__.py")}
    missing = sorted(needed - listed)
    check("pyproject lists every package with an __init__.py", not missing,
          ", ".join(missing))


def test_read_extensions() -> None:
    """Step 2.2: reading accepts more formats than writing touches (P2)."""
    print("read extensions")
    check("AUDIO_EXTENSIONS keeps the read-only formats out",
          not {".mp4", ".oga", ".aif"} & config.AUDIO_EXTENSIONS,
          str(sorted(config.AUDIO_EXTENSIONS)))
