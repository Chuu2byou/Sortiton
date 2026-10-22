"""Öffentliche Schnittstelle, Version, Einstiegspunkte und Wheel-Inhalt."""

from __future__ import annotations

from _support import (
    BASE,
    check,
    config,
    importlib,
    ms,
    re,
)


def test_import() -> None:
    check("__all__ is not empty", bool(ms.__all__))
    missing = [name for name in ms.__all__ if not hasattr(ms, name)]
    check("__all__ names exist", not missing, ", ".join(missing))


def test_version() -> None:
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


def test_packages_complete() -> None:
    """Jedes Paket von ``sortiton`` steht in der Paketliste für das Wheel."""
    import tomllib

    text = (BASE / "pyproject.toml").read_text(encoding="utf-8")
    listed = set(tomllib.loads(text)["tool"]["setuptools"]["packages"])
    needed = {path.parent.relative_to(BASE).as_posix().replace("/", ".")
              for path in (BASE / "sortiton").rglob("__init__.py")}
    missing = sorted(needed - listed)
    check("pyproject lists every package with an __init__.py", not missing,
          ", ".join(missing))


def test_read_extensions() -> None:
    """Lesen akzeptiert mehr Formate, als das Schreiben anfasst."""
    check("AUDIO_EXTENSIONS keeps the read-only formats out",
          not {".mp4", ".oga", ".aif"} & config.AUDIO_EXTENSIONS,
          str(sorted(config.AUDIO_EXTENSIONS)))
