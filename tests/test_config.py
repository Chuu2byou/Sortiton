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
