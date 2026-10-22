"""Regressionen zu den Befunden der Code-Review vom 2026-10-22.

Je Test genau ein gemeldeter Fehlerpfad, geprüft über das nach außen sichtbare
Verhalten (Rückgabecode, geschriebene Dateien, Ausnahmen) statt über Interna:

- H1: ein Schreibfehler im Export endete mit Traceback statt mit Code 2.
- H2: der Export überschrieb eine gleichnamige Fremddatei im Ausgabeordner.
- M1: ``tags --apply`` startete ohne Schreibprogramm (nur mit Leser).
- M2: ``write_tags`` ließ ``FileNotFoundError`` durch, statt ``RuntimeError``.
- M4: ``cmd_scan`` war als einziges Kommando nicht abbrechbar.
- M5: beim Tag-Schreiben wurde jeder Wert an ``;`` getrennt (auch ein Titel).
- M6: ``resolve_args`` scheiterte an einem Mapping mit irreführendem ``vars()``.
"""

from __future__ import annotations

import importlib.util
import shutil
import unittest.mock as mock

import pytest

from _support import BASE, Path, SimpleNamespace, check, tempfile

FIXTURE = BASE / "tests" / "fixtures" / "export_library"
FLAC_SAMPLE = FIXTURE / "Artist A" / "Album One" / "01 - Song One.flac"


def _reader_available() -> bool:
    """Ob der Export überhaupt laufen kann (mutagen oder ffprobe)."""
    from sortiton import external

    return any(external.available(tool) for tool in (external.MUTAGEN, external.FFPROBE))


def _library() -> Path:
    """Die Fixture-Bibliothek oder ein Skip, wenn sie fehlt."""
    if not FIXTURE.is_dir():
        pytest.skip("export fixture missing")
    return FIXTURE


@pytest.mark.external
@pytest.mark.slow
def test_export_write_error_is_a_clean_failure() -> None:
    """H1: ein Schreibfehler endet mit Meldung und Code 2, nicht mit Traceback."""
    from sortiton.features.export import cmd_export, report

    if not _reader_available():
        pytest.skip("no tag reader available")

    def boom(_sections, _write):
        raise PermissionError(13, "Permission denied")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir()
        with mock.patch.object(report, "write_report", boom), \
                mock.patch("sortiton.output.message") as say:
            rc = cmd_export(SimpleNamespace(folder=str(_library()), output=str(out),
                                            chunk_chars=60000, examples=5))

        check("a write failure returns 2", rc == 2, str(rc))
        printed = " ".join(str(call.args[0]) for call in say.call_args_list)
        check("the failure is reported", "ERROR" in printed.upper() or "FEHLER" in printed,
              printed)
        check("no half-written report claims a name",
              not (out / "01_zusammenfassung.md").exists())


@pytest.mark.external
@pytest.mark.slow
def test_export_never_overwrites_a_foreign_report() -> None:
    """H2: liegt eine eigene ``01_zusammenfassung.md`` im Zielordner, weicht der Export aus.

    Vorher schrieb ``write_report`` feste Namen und ersetzte die Datei ohne
    Rückfrage - obwohl der Sortierpfad die Zusage "nichts wird überschrieben"
    über ``free_target`` einhält.
    """
    from sortiton.features.export import cmd_export

    if not _reader_available():
        pytest.skip("no tag reader available")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir()
        mine = out / "01_zusammenfassung.md"
        mine.write_text("meine Notizen\n", encoding="utf-8")

        with mock.patch("sortiton.output.message"):
            rc = cmd_export(SimpleNamespace(folder=str(_library()), output=str(out),
                                            chunk_chars=60000, examples=5))

        check("the export works", rc == 0, str(rc))
        check("the foreign report survives untouched",
              mine.read_text(encoding="utf-8") == "meine Notizen\n",
              mine.read_text(encoding="utf-8"))
        check("our report uses a free name",
              (out / "01_zusammenfassung (2).md").is_file(),
              str(sorted(p.name for p in out.iterdir())))


@pytest.mark.external
@pytest.mark.slow
def test_export_removes_its_own_empty_output_folder() -> None:
    """Kleinigkeit: ohne Audiodateien bleibt kein selbst angelegter Leerordner zurück."""
    from sortiton.features.export import cmd_export

    if not _reader_available():
        pytest.skip("no tag reader available")

    with tempfile.TemporaryDirectory() as tmp:
        empty = Path(tmp) / "leer"
        empty.mkdir()
        out = Path(tmp) / "out"  # existiert noch nicht -> wird vom Export angelegt

        with mock.patch("sortiton.output.message"):
            rc = cmd_export(SimpleNamespace(folder=str(empty), output=str(out),
                                            chunk_chars=60000, examples=5))

        check("an empty library is reported", rc == 1, str(rc))
        check("the folder created by this run is gone again", not out.exists())


def test_tags_apply_requires_a_writing_tool() -> None:
    """M1: ``tags --apply`` bricht früh ab, wenn nur ein Leser installiert ist."""
    from sortiton import cli, external

    def available(tool):
        return tool is external.FFPROBE  # lesen ja, schreiben nein

    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.object(external, "available", available), \
                mock.patch("sys.argv", ["sortiton", "tags", tmp, "--apply"]), \
                mock.patch("sortiton.output.message"):
            rc = cli.main()

    check("tags --apply stops before the first file", rc == 2, str(rc))


def test_write_tags_reports_a_missing_writer() -> None:
    """M2: ohne mutagen und ohne ffmpeg wirft ``write_tags`` RuntimeError."""
    from sortiton import tags

    with tempfile.TemporaryDirectory() as tmp:
        song = Path(tmp) / "song.unknown"
        song.write_bytes(b"\x00" * 16)
        with mock.patch.object(tags, "_write_mutagen",
                               side_effect=RuntimeError("no mutagen")), \
                mock.patch.object(tags.subprocess, "run",
                                  side_effect=FileNotFoundError("ffmpeg")):
            with pytest.raises(RuntimeError):
                tags.write_tags(song, {"artist": "X"})


def test_scan_can_be_cancelled() -> None:
    """M4: ``cmd_scan`` prüft den Cancel-Token wie alle anderen Kommandos."""
    from sortiton.cancel import Cancelled, CancelToken
    from sortiton.tasks import cmd_scan

    token = CancelToken()
    token.cancel()
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "a.mp3").write_bytes(b"\x00" * 64)
        with pytest.raises(Cancelled):
            cmd_scan(SimpleNamespace(folder=tmp, cancel=token))


@pytest.mark.skipif(importlib.util.find_spec("mutagen") is None, reason="mutagen not installed")
def test_title_is_not_split_at_semicolons() -> None:
    """M5: nur Mehrfachwert-Felder werden an ``;`` getrennt, ein Titel nicht."""
    from sortiton.tags import read_info, write_tags

    if not FLAC_SAMPLE.is_file():
        pytest.skip("export fixture missing")

    with tempfile.TemporaryDirectory() as tmp:
        song = Path(tmp) / "song.flac"
        shutil.copy2(FLAC_SAMPLE, song)

        check("a title with a semicolon is written", write_tags(song, {"title": "Intro;Outro"}))
        check("the title stays one value", read_info(song).title == ["Intro;Outro"],
              str(read_info(song).title))

        check("a multi-value artist is written", write_tags(song, {"artist": "A; B"}))
        check("the artist still splits into two values",
              read_info(song).artist == ["A", "B"], str(read_info(song).artist))


def test_resolve_args_accepts_a_mapping() -> None:
    """M6: ein Mapping wird gelesen, ein Objekt ohne Attribute klar abgelehnt."""
    from sortiton.features import get as feature_by_key
    from sortiton.features.base import resolve_args

    export = feature_by_key("export")
    options = resolve_args(export, {"folder": "/music"})
    check("the given value is kept", options.folder == "/music", str(vars(options)))
    check("the defaults are filled", options.chunk_chars == 60000, str(vars(options)))

    with pytest.raises(TypeError):
        resolve_args(export, object())


def test_settings_keep_comments_and_order() -> None:
    """Kleinigkeit: ein Schreibvorgang verliert keine Kommentare in settings.ini."""
    from sortiton import settings

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

