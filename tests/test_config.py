"""Pfade (``sortiton/config.py``) und die Nutzereinstellungen (``settings.ini``).

``settings.ini`` ist eine von Hand editierbare Datei: sie muss Kommentare und
Reihenfolge behalten, ``%``-Werte durchreichen und darf bei kaputtem Inhalt
nicht abstürzen.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest.mock as mock

from _support import BASE, Path, check, settings, tempfile


def test_data_dir_environment_wins_in_checkout() -> None:
    """SORTITON_DATA_DIR verschiebt auch den Datenordner einer Quellcode-Kopie."""
    with tempfile.TemporaryDirectory() as data:
        env = dict(os.environ)
        env["SORTITON_DATA_DIR"] = data
        result = subprocess.run(
            [sys.executable, "-c",
             "from sortiton.config import PROJECT_DIR; print(PROJECT_DIR)"],
            cwd=str(BASE), env=env, capture_output=True, text=True, check=False)
    check("the import succeeds", result.returncode == 0, result.stderr[-300:])
    check("SORTITON_DATA_DIR is honoured", result.stdout.strip() == data, result.stdout)


def test_track_format_setting() -> None:
    """track_format defaults to keep, accepts the three modes and ignores junk."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "settings.ini"
        path.write_text("[general]\nlanguage = en\n", encoding="utf-8")
        with mock.patch.object(settings, "SETTINGS_FILE", path):
            check("the default leaves numbers alone",
                  settings.resolve_track_format() == "keep",
                  settings.resolve_track_format())
            check("padded is stored", settings.save_track_format("padded"))
            check("padded is read back", settings.resolve_track_format() == "padded",
                  settings.resolve_track_format())
            check("junk falls back to keep", settings.save_track_format("bogus"))
            check("the fallback is visible", settings.resolve_track_format() == "keep",
                  settings.resolve_track_format())

        text = path.read_text(encoding="utf-8")
        check("the language survives", "language = en" in text, text)
        check("the setting is written", "track_format = keep" in text, text)

def test_theme_setting_and_resolution() -> None:
    """The theme choice persists and Auto resolves the detected system mode."""
    from sortiton.gui import design

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "settings.ini"
        path.write_text("[general]\nlanguage = en\n", encoding="utf-8")
        with mock.patch.object(settings, "SETTINGS_FILE", path), \
                mock.patch.dict(os.environ, {"SORTITON_THEME": ""}):
            check("theme defaults to system", settings.resolve_theme() == "auto",
                  settings.resolve_theme())
            check("dark mode is stored", settings.save_theme("dark"))
            check("dark mode is read", settings.resolve_theme() == "dark",
                  settings.resolve_theme())
            check("invalid theme falls back to system", settings.save_theme("invalid"))
            check("system mode is restored", settings.resolve_theme() == "auto",
                  settings.resolve_theme())

    with mock.patch.object(settings, "resolve_theme", return_value="auto"), \
            mock.patch.object(design, "_system_theme", return_value="dark"), \
            mock.patch.dict(os.environ, {"SORTITON_THEME": ""}):
        check("Auto follows the detected system theme",
              design._resolve_theme() == "dark", design._resolve_theme())
    with mock.patch.object(settings, "resolve_theme", return_value="light"), \
            mock.patch.dict(os.environ, {"SORTITON_THEME": "dark"}):
        check("environment theme override is preserved",
              design._resolve_theme() == "dark", design._resolve_theme())


def test_settings_keep_percent_values() -> None:
    """settings.ini muss einen Wert mit "%" verlustfrei zurückgeben.

    Mit der Standard-Interpolation von configparser warf das Schreiben von "50%"
    einen ValueError, und eine von Hand editierte Datei ließ
    ``read_tool_values`` abstürzen.
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "settings.ini"
        with mock.patch.object(settings, "SETTINGS_FILE", path):
            check("a percent value is written", settings.write_value("language", "50%"))
            check("a percent value is read", settings.read_value("language") == "50%")
            check("tool values are saved",
                  settings.save_tool_values({"ratio": "50%"}))
            check("tool values are read",
                  settings.read_tool_values() == {"ratio": "50%"})


def test_settings_keep_comments_and_order() -> None:
    """Ein Schreibvorgang verliert keine Kommentare in settings.ini."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "settings.ini"
        path.write_text(
            "# meine Notizen\n"
            "[general]\n"
            "# Sprache der Oberfläche\n"
            "language = en\n"
            "backup = true\n"
            "\n"
            "[tools]\n"
            "export.chunk_chars = 40000\n"
            "export.veraltet = 1\n",
            encoding="utf-8")

        with mock.patch.object(settings, "SETTINGS_FILE", path):
            check("the language is stored", settings.save_language("de"))

        text = path.read_text(encoding="utf-8")
        check("the comments survive", "# meine Notizen" in text and "# Sprache" in text, text)
        check("the value is replaced", "language = de" in text, text)
        check("the other value is untouched", "backup = true" in text, text)

        with mock.patch.object(settings, "SETTINGS_FILE", path):
            check("tool values are replaced",
                  settings.save_tool_values({"export.chunk_chars": "50000",
                                             "export.examples": "10"}))
            check("the language is still readable", settings.read_value("language") == "de")

        text = path.read_text(encoding="utf-8")
        check("the tool value is replaced", "export.chunk_chars = 50000" in text, text)
        check("a new tool value is appended", "export.examples = 10" in text, text)
        check("a dropped tool value is gone", "export.veraltet" not in text, text)
        with mock.patch.object(settings, "SETTINGS_FILE", path):
            check("only the new tool values remain",
                  settings.read_tool_values() == {"export.chunk_chars": "50000",
                                                  "export.examples": "10"},
                  str(settings.read_tool_values()))
