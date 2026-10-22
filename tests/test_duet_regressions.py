"""Regressionen zu den vier Befunden aus dem Duet-Auftrag (Export/Fetch/Fixes).

Jeder Test deckt genau den gemeldeten Fehlerpfad ab:

- Export löschte fremde Dateien im Ausgabeordner (``_clear_reports``).
- Ein kaputter Fingerprint-Cache-Eintrag brach den Export mit ``AttributeError`` ab.
- ``fixes._prepare`` engte einen ``None``-Pfad nicht ein.
- ``fetch.download`` journalisierte fremde, nur gemeldete Pfade.
"""

from __future__ import annotations

import hashlib
import json
import unittest.mock as mock

import pytest

from _support import BASE, Path, SimpleNamespace, check, shutil, tempfile

MANIFEST = ".sortiton-export.json"


def _export_helper():
    """Das Hilfsmodul der Export-Tests (Fixture-Pfade, Textnormalisierung)."""
    from _support import _load_export_helper

    return _load_export_helper()


def _foreign_report_files(directory: Path) -> dict[str, bytes]:
    """Dateien, die wie Berichte heißen, aber dem Nutzer gehören.

    Bewusst keine Namen, die ein normaler Lauf selbst schreibt
    (``01_*``/``02_*``/``tracks_partNN.tsv``/``00_prompt.md``): dort wäre ein
    Überschreiben unvermeidbar und kein Herkunftsfehler.
    """
    personal = {
        "tracks_part_privat.tsv": b"meine\tnotizen\n",
        "03_duplikate.md": b"# meine eigene Notiz\n",
        "tracks_part_2024.tsv": b"archiv\n",
    }
    for name, content in personal.items():
        (directory / name).write_bytes(content)
    return personal


def _unchanged(directory: Path, personal: dict[str, bytes]) -> bool:
    return all((directory / name).read_bytes() == content
               for name, content in personal.items())


@pytest.mark.external
@pytest.mark.slow
def test_export_keeps_foreign_files_when_source_is_output() -> None:
    """Befund 1: Quelle = Ausgabe darf keine fremde TSV/Berichte löschen.

    Vor dem Fix löschte ``_clear_reports`` feste Namen und alles, was auf
    ``tracks_part*.tsv`` passt - ohne zu prüfen, wer die Datei geschrieben hat.
    """
    from sortiton.features.export import cmd_export

    helper = _export_helper()
    fixture = helper.FIXTURE_DIR
    if not fixture.is_dir():
        pytest.skip("export fixture missing")
    if not (BASE / "tests" / "fixtures" / "export_library").is_dir():
        pytest.skip("export library missing")

    with tempfile.TemporaryDirectory() as tmp:
        music = Path(tmp) / "music"
        shutil.copytree(fixture, music)
        personal = _foreign_report_files(music)

        with mock.patch("sortiton.output.message"):
            rc = cmd_export(SimpleNamespace(folder=str(music), output=str(music),
                                            chunk_chars=1500, examples=5))
        check("export with source == output works", rc == 0, str(rc))
        check("foreign files survive the export", _unchanged(music, personal))
        check("the run wrote its own reports", (music / "00_prompt.md").is_file())
        check("the run wrote a provenance manifest", (music / MANIFEST).is_file())


@pytest.mark.external
@pytest.mark.slow
def test_export_replaces_only_manifest_files() -> None:
    """Befund 1: ein früherer Lauf wird ersetzt, Fremdes bleibt (A2).

    Das alte Manifest nennt einen überzähligen TSV-Teil und ``03_duplikate.md``;
    beide stammen aus einem Sortiton-Lauf und müssen verschwinden. Die fremde
    Datei mit Berichtsnamen steht in keinem Manifest und bleibt.
    """
    from sortiton.features.export import cmd_export

    helper = _export_helper()
    fixture = helper.FIXTURE_DIR
    if not fixture.is_dir() or not (BASE / "tests" / "fixtures" / "export_library").is_dir():
        pytest.skip("export fixture missing")

    with tempfile.TemporaryDirectory() as tmp:
        music = Path(tmp) / "music"
        shutil.copytree(fixture, music)
        out = Path(tmp) / "out"
        out.mkdir()
        personal = _foreign_report_files(out)

        stale = {"tracks_part99.tsv": b"alt\n", "03_duplikate.md.stale": b"alt\n"}
        for name, content in stale.items():
            (out / name).write_bytes(content)
        old_manifest = ["tracks_part99.tsv", "03_duplikate.md.stale"]
        (out / MANIFEST).write_text(json.dumps({"version": 1, "files": old_manifest}),
                                    encoding="utf-8")

        with mock.patch("sortiton.output.message"):
            first = cmd_export(SimpleNamespace(folder=str(music), output=str(out),
                                               chunk_chars=1000, examples=5))
            check("the first run works", first == 0, str(first))
            check("the stale report of the earlier run is gone",
                  not (out / "tracks_part99.tsv").exists()
                  and not (out / "03_duplikate.md.stale").exists())

            second = cmd_export(SimpleNamespace(folder=str(music), output=str(out),
                                                chunk_chars=60000, examples=5))
        check("the second run works", second == 0, str(second))
        check("only one TSV part remains after the smaller run",
              sorted(p.name for p in out.glob("tracks_part[0-9]*.tsv"))
              == ["tracks_part01.tsv"],
              str(sorted(p.name for p in out.glob("tracks_part*.tsv"))))
        check("the stale manifest is replaced, not appended",
              json.loads((out / MANIFEST).read_text(encoding="utf-8"))["files"]
              == ["01_zusammenfassung.md", "02_auffaelligkeiten.md",
                  "tracks_part01.tsv", "00_prompt.md"],
              (out / MANIFEST).read_text(encoding="utf-8"))
        check("foreign files survive the second run", _unchanged(out, personal))


@pytest.mark.external
@pytest.mark.slow
def test_export_without_manifest_deletes_nothing() -> None:
    """Befund 1: fehlendes Manifest ist kein Freibrief zum Löschen (A2).

    Nur wenn der Lauf abbricht, bevor er seine Berichte schreibt, zeigt sich
    der Unterschied: mit altem Manifest verschwinden die alten Berichte, ohne
    Manifest bleibt alles liegen.
    """
    from sortiton.features.export import cmd_export, report

    helper = _export_helper()
    fixture = helper.FIXTURE_DIR
    if not fixture.is_dir() or not (BASE / "tests" / "fixtures" / "export_library").is_dir():
        pytest.skip("export fixture missing")

    with tempfile.TemporaryDirectory() as tmp:
        music = Path(tmp) / "music"
        shutil.copytree(fixture, music)

        broken = Path(tmp) / "broken"
        broken.mkdir()
        personal = _foreign_report_files(broken)
        corrupt = Path(tmp) / "corrupt"
        corrupt.mkdir()
        corrupt_personal = _foreign_report_files(corrupt)
        (corrupt / MANIFEST).write_text("{kein json", encoding="utf-8")

        def boom(*_args, **_kwargs):
            raise RuntimeError("Schreibfehler")

        for out, files in ((broken, personal), (corrupt, corrupt_personal)):
            with mock.patch("sortiton.output.message"), \
                    mock.patch.object(report, "write_report", boom):
                try:
                    cmd_export(SimpleNamespace(folder=str(music), output=str(out),
                                               chunk_chars=60000, examples=5))
                except RuntimeError:
                    pass
            check(f"foreign files survive without a usable manifest ({out.name})",
                  _unchanged(out, files))


def test_fingerprint_cache_rejects_invalid_entries() -> None:
    """Befund 2: Liste/falsche Typen im Cache dürfen den Export nicht sprengen (A3).

    Der Cache ist JSON von der Platte: ein Eintrag als Liste ließ ``c.get``
    mit ``AttributeError`` abstürzen, falsche ``meta``/``fp``-Typen kamen
    ungeprüft in die Auswertung.
    """
    from sortiton import config as cfg
    from sortiton.features.export import fingerprint

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        root = work / "music"
        root.mkdir()
        recs = []
        for name in ("a.flac", "b.flac", "c.flac"):
            (root / name).write_bytes(b"\x00" * 64)
            recs.append({"path": name})

        cache_dir = work / "cache"
        fp_dir = cache_dir / "fingerprints"
        fp_dir.mkdir(parents=True)
        key = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
        cache_file = fp_dir / f"fp_{key}.json"
        stat = (root / "c.flac").stat()
        cache_file.write_text(json.dumps({
            "a.flac": ["kein", "dict"],
            "b.flac": {"meta": [64, 0], "k": "len3", "fp": "kein liste"},
            "c.flac": {"meta": [stat.st_size, int(stat.st_mtime)],
                       "k": "len3", "fp": [7, 7, 7]},
        }), encoding="utf-8")

        calls: list[str] = []

        def fake_fpcalc(path, _secs, _cancel=None):
            calls.append(Path(path).name)
            return [1, 2, 3], ""

        with mock.patch.object(cfg, "CACHE_DIR", cache_dir), \
                mock.patch.object(fingerprint, "run_fpcalc", fake_fpcalc), \
                mock.patch("sortiton.output.message"), \
                mock.patch("sortiton.output.progress"):
            fps = fingerprint.compute_fingerprints(recs, root, 3, 1, work)

        check("invalid entries are recomputed", sorted(calls) == ["a.flac", "b.flac"],
              str(calls))
        check("the valid entry is served from the cache",
              fps.get(2) == [7, 7, 7], str(fps))
        check("the recomputed files have fingerprints",
              fps.get(0) == [1, 2, 3] and fps.get(1) == [1, 2, 3], str(fps))

        written = json.loads(cache_file.read_text(encoding="utf-8"))
        check("the cache holds only dictionaries",
              all(isinstance(value, dict) for value in written.values()), str(written))
        check("the recomputed entries are stored",
              written["a.flac"]["fp"] == [1, 2, 3]
              and written["b.flac"]["fp"] == [1, 2, 3], str(written))


def test_fixes_prepare_handles_unresolved_path() -> None:
    """Befund 3: ein ``None``-Pfad aus ``resolve_path`` wird wie bisher gemeldet (A6)."""
    from sortiton.features.fixes import _prepare
    from sortiton.features.fixes.parse import FixRow

    row = FixRow(1, "kaputt.mp3", "artist", "Alt", "Neu", field="artist")
    problems: list[tuple[int, str, dict]] = []

    with mock.patch("sortiton.features.fixes.parse.resolve_path",
                    return_value=(None, "")):
        actions, skipped, problems = _prepare([row], None)

    check("no action is planned", actions == [], str(actions))
    check("nothing is silently skipped", skipped == [], str(skipped))
    check("the row reports a missing path",
          [(line, key) for line, key, _args in problems] == [(1, "fixes.error.missing_file")],
          str(problems))


def test_fetch_download_drops_foreign_reported_files() -> None:
    """Befund 4: nur im Lauf entstandene Dateien in ``target`` werden übernommen (A7).

    Der Fake meldet vier Pfade: eine fremde Datei im Ziel, eine neue Datei,
    eine Datei außerhalb des Ziels und einen Pfad, den es nicht gibt. Nur die
    neue Datei darf Ergebnis und Journal erreichen.
    """
    from sortiton.features.fetch import download

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        target = work / "target"
        target.mkdir()
        foreign = target / "fremd.mp3"
        foreign.write_bytes(b"schon da")
        outside = work / "aussen.mp3"
        outside.write_bytes(b"aussen")
        fresh = target / "neu.mp3"
        saved: list[Path] = []

        def fake_stream(_argv, _cancel, handle):
            fresh.write_bytes(b"frisch")
            for path in (foreign, fresh, outside, target / "fehlt.mp3"):
                handle("SORTITON_FILE\t" + str(path))
            return 0, ""

        with mock.patch.object(download, "_stream", fake_stream):
            files, error = download.download(
                "https://example.org/x", target, audio_format="mp3", playlist=False,
                on_saved=lambda item: saved.append(item.path))

        check("the run reports no error", error == "", error)
        check("only the file created in this run is returned",
              [item.path for item in files] == [fresh], str(files))
        check("the journal callback sees only the own file", saved == [fresh], str(saved))
        check("the foreign file is untouched", foreign.read_bytes() == b"schon da")


def test_fetch_download_drops_foreign_files_on_cancel_and_error() -> None:
    """Befund 4: auch Abbruch und Rückgabecode != 0 übernehmen nichts Fremdes (A7)."""
    from sortiton.cancel import Cancelled
    from sortiton.features.fetch import download

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "target"
        target.mkdir()
        foreign = target / "fremd.mp3"
        foreign.write_bytes(b"schon da")

        def cancelled_stream(_argv, _cancel, handle):
            handle("SORTITON_FILE\t" + str(foreign))
            raise Cancelled

        saved: list[Path] = []
        with mock.patch.object(download, "_stream", cancelled_stream):
            with pytest.raises(Cancelled):
                download.download("https://example.org/x", target, audio_format="mp3",
                                  playlist=False,
                                  on_saved=lambda item: saved.append(item.path))
        check("a cancelled run journals nothing foreign", saved == [], str(saved))

        def failing_stream(_argv, _cancel, handle):
            handle("SORTITON_FILE\t" + str(foreign))
            return 1, "boom"

        saved.clear()
        with mock.patch.object(download, "_stream", failing_stream):
            files, error = download.download("https://example.org/x", target,
                                             audio_format="mp3", playlist=False,
                                             on_saved=lambda item: saved.append(item.path))
        check("a failed run returns nothing foreign", files == [], str(files))
        check("a failed run journals nothing foreign", saved == [], str(saved))
        check("the error is still reported", error == "boom", error)
