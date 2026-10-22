"""The export report: goldens, fingerprints, output files and errors."""

from __future__ import annotations

import json

import pytest

from _support import (
    BASE,
    Path,
    SimpleNamespace,
    _export_args,
    _export_columns,
    _export_texts,
    _first_difference,
    _genre_values,
    _load_export_helper,
    _tree_digest,
    check,
    importlib,
    ms,
    os,
    output,
    shutil,
    subprocess,
    sys,
    tempfile,
)

MANIFEST = ".sortiton-export.json"


def _reader_available() -> bool:
    """Ob der Export überhaupt laufen kann (mutagen oder ffprobe)."""
    from sortiton import external

    return any(external.available(tool) for tool in (external.MUTAGEN, external.FFPROBE))


def _library() -> Path:
    """Die Fixture-Bibliothek oder ein Skip, wenn sie fehlt."""
    fixture = _load_export_helper().FIXTURE_DIR
    if not fixture.is_dir():
        pytest.skip("export fixture missing")
    return fixture


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


def test_export_public_api() -> None:
    """Der Export-Einstiegspunkt und der Fortschritt sind Teil der öffentlichen API."""
    check("ms.cmd_export is public", hasattr(ms, "cmd_export") and "cmd_export" in ms.__all__)
    check("ms.progress is public", hasattr(ms, "progress") and "progress" in ms.__all__)


def test_export_fixture() -> None:
    fixture = BASE / "tests" / "fixtures" / "export_library"
    script = BASE / "tools" / "make_export_fixture.py"
    if not fixture.is_dir():
        pytest.skip("export fixture present", "missing - run tools/make_export_fixture.py")
        return
    total = sum(item.stat().st_size for item in fixture.rglob("*") if item.is_file())
    check("export fixture is under 300 kB", total < 300_000, f"{total} bytes")
    if importlib.util.find_spec("mutagen") is None:
        pytest.skip("export fixture matches the script", "mutagen is missing")
        return
    result = subprocess.run([sys.executable, str(script), "--check"],
                            capture_output=True, text=True, check=False)
    check("export fixture matches the script", result.returncode == 0,
          (result.stdout or result.stderr).strip().splitlines()[-1][:120])


@pytest.mark.slow
def test_export_golden() -> None:
    """Der deutsche Bericht entspricht dem Golden aus Phase 1 (``base``).

    Variante A ist der einfache Lauf, dessen gesamte Ausgabe unter
    ``tests/golden/export/base``
    liegt; Variante B setzt zusätzlich ``check_case``, dort sind nur
    ``01_*``/``02_*`` gespeichert. Beide laufen mit ``report_lang="de"``,
    damit das (unveränderte) deutsche Golden weiter passt; das englische
    Gegenstück ist ``test_export_golden_en``. Verglichen wird nach
    ``normalize_export_text`` (Ordner und Zeitstempel).
    """
    import unittest.mock as mock

    from sortiton.features.export import cmd_export

    helper = _load_export_helper()
    fixture = helper.FIXTURE_DIR
    if not fixture.is_dir():
        pytest.skip("export golden", "fixture missing")
        return
    if importlib.util.find_spec("mutagen") is None:
        pytest.skip("export golden", "mutagen not installed")
        return

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)

        out = work / "base"
        with mock.patch.object(output, "message"):
            rc = cmd_export(_export_args(fixture, out, chunk_chars=1500,
                                         examples=5, jsonl=True, report_lang="de"))
        check("golden base run works", rc == 0, "" if rc == 0 else str(rc))
        produced = _export_texts(out, helper)
        golden = _export_texts(helper.GOLDEN_DIR / "base", helper)
        same_names = sorted(produced) == sorted(golden)
        check("golden base file list matches", same_names,
              "" if same_names else f"{sorted(produced)} != {sorted(golden)}")
        check("golden base output matches", produced == golden,
              _first_difference(produced, golden))
        for name in sorted(golden):
            check(f"golden base/{name}", produced.get(name) == golden.get(name))

        # Variant B: only the 01_* and 02_* files were stored.
        case_out = work / "case"
        with mock.patch.object(output, "message"):
            rc_case = cmd_export(_export_args(fixture, case_out, chunk_chars=1500,
                                              examples=5, jsonl=True, check_case=True,
                                              report_lang="de"))
        check("golden case run works", rc_case == 0, "" if rc_case == 0 else str(rc_case))
        case_produced = _export_texts(case_out, helper, ("01_", "02_"))
        case_golden = _export_texts(helper.GOLDEN_DIR / "case", helper)
        for name in sorted(case_golden):
            check(f"golden case/{name}", case_produced.get(name) == case_golden.get(name))


@pytest.mark.slow
def test_export_golden_en() -> None:
    """Der englische Bericht ist auf ``tests/golden/export/base_en`` festgenagelt.

    Same run as the German base golden, only with ``report_lang="en"``.  A
    missing translation key would show up as the raw key name, so the golden
    also proves that the English catalog is complete.
    """
    import unittest.mock as mock

    from sortiton.features.export import cmd_export

    helper = _load_export_helper()
    fixture = helper.FIXTURE_DIR
    golden_dir = helper.EN_GOLDEN_DIR
    if not fixture.is_dir():
        pytest.skip("export golden english", "fixture missing")
        return
    if not golden_dir.is_dir():
        pytest.skip("export golden english", "tests/golden/export/base_en is missing")
        return
    if importlib.util.find_spec("mutagen") is None:
        pytest.skip("export golden english", "mutagen not installed")
        return

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "en"
        with mock.patch.object(output, "message"):
            rc = cmd_export(_export_args(fixture, out, chunk_chars=1500, examples=5,
                                         jsonl=True, report_lang="en"))
        check("golden english run works", rc == 0, "" if rc == 0 else str(rc))
        produced = _export_texts(out, helper)
        golden = _export_texts(golden_dir, helper)
        same_names = sorted(produced) == sorted(golden)
        check("golden english file list matches", same_names,
              "" if same_names else f"{sorted(produced)} != {sorted(golden)}")
        check("golden english output matches", produced == golden,
              _first_difference(produced, golden))
        for name in sorted(golden):
            check(f"golden english/{name}", produced.get(name) == golden.get(name))


@pytest.mark.external
@pytest.mark.slow
@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe not installed")
def test_export_ffprobe_loose() -> None:
    """Ohne mutagen liefert der ffprobe-Leser dieselben Tag-Spalten.

    Only the columns both readers fill from tags are compared; ``sek``,
    ``kbps``, ``codec`` and ``cover`` come from different tools and may differ.
    ``genre`` is compared as a set of values, because the two readers join
    several genres differently.
    """
    import unittest.mock as mock

    from sortiton import config as cfg
    from sortiton.features.export import cmd_export

    helper = _load_export_helper()
    fixture = helper.FIXTURE_DIR
    if not fixture.is_dir():
        pytest.skip("export ffprobe reader", "fixture missing")
        return
    if shutil.which("ffprobe") is None:
        pytest.skip("export ffprobe reader", "ffprobe not installed")
        return

    columns = ("path", "artist", "albumartist", "album", "title", "track",
               "disc", "year", "genre")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        with mock.patch.object(cfg, "MUTAGEN_AVAILABLE", False), \
                mock.patch.object(output, "message"):
            rc = cmd_export(_export_args(fixture, out, chunk_chars=1500, examples=5))
        check("ffprobe run works", rc == 0, "" if rc == 0 else str(rc))
        produced = _export_columns(out, columns)
        golden = _export_columns(helper.GOLDEN_DIR / "base", columns)

    check("ffprobe reads every file", sorted(produced) == sorted(golden),
          ", ".join(sorted(set(produced) ^ set(golden))[:3]))
    mismatched = []
    for key in sorted(set(produced) & set(golden)):
        for position, column in enumerate(columns):
            left, right = produced[key][position], golden[key][position]
            same = (_genre_values(left) == _genre_values(right) if column == "genre"
                    else left == right)
            if not same:
                mismatched.append(f"{key}: {column} {left!r} != {right!r}")
    check("ffprobe tag columns match the golden", not mismatched,
          "; ".join(mismatched[:3]))


@pytest.mark.external
@pytest.mark.skipif(shutil.which("fpcalc") is None, reason="fpcalc not installed")
def test_export_fingerprint() -> None:
    """Ein Fingerprint-Lauf gruppiert das identische Paar, nicht die andere Datei.

    No byte comparison (fpcalc versions produce different fingerprints), only
    the grouping in ``03_duplikate.md``.  The default ``fp_seconds`` is used:
    the fixture chirp is 5.5 s and a shorter window would leave too few
    sub-fingerprints for the comparison.
    """
    import unittest.mock as mock

    from sortiton.features.export import cmd_export

    helper = _load_export_helper()
    fixture = helper.FIXTURE_DIR
    if not fixture.is_dir():
        pytest.skip("export fingerprint", "fixture missing")
        return
    if shutil.which("fpcalc") is None:
        pytest.skip("export fingerprint", "fpcalc not installed")
        return

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        with mock.patch.object(output, "message"):
            rc = cmd_export(_export_args(fixture, out, fingerprint=True))
        check("fingerprint run works", rc == 0, "" if rc == 0 else str(rc))
        report = out / "03_duplikate.md"
        check("03_duplikate.md exists", report.is_file())
        text = report.read_text(encoding="utf-8") if report.is_file() else ""
        paired = any("same_a.opus" in line and "same_b.mp3" in line
                     for line in text.splitlines())
        check("the identical pair shares one group", paired)
        check("the different file stays out of the groups", "other.opus" not in text)


@pytest.mark.slow
def test_export_source_untouched() -> None:
    """Der Export ist nur lesend - der Quellbaum bleibt unangetastet."""
    import unittest.mock as mock

    from sortiton.features.export import cmd_export

    helper = _load_export_helper()
    fixture = helper.FIXTURE_DIR
    if not fixture.is_dir():
        pytest.skip("export source untouched", "fixture missing")
        return
    if importlib.util.find_spec("mutagen") is None:
        pytest.skip("export source untouched", "mutagen not installed")
        return

    before = _tree_digest(fixture)
    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.object(output, "message"):
            rc = cmd_export(_export_args(fixture, Path(tmp) / "out", chunk_chars=1500,
                                         examples=5, jsonl=True))
    after = _tree_digest(fixture)
    check("export run over the fixture works", rc == 0, "" if rc == 0 else str(rc))
    check("the source tree is byte-identical afterwards", before == after,
          f"{len(before)} file(s) checked")


def test_export_errors() -> None:
    """Die dokumentierten Rückgabecodes von ``cmd_export``."""
    import unittest.mock as mock

    from sortiton import config as cfg, external
    from sortiton.features.export import cmd_export

    helper = _load_export_helper()
    fixture = helper.FIXTURE_DIR

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        out = work / "out"
        messages: list[str] = []

        with mock.patch.object(output, "message", side_effect=messages.append):
            rc = cmd_export(_export_args(fixture, out, fp_threshold=1.5))
        check("a threshold outside 0..1 is an input error", rc == 2, str(rc))

        with mock.patch.object(output, "message", side_effect=messages.append):
            rc = cmd_export(_export_args(work / "missing", out))
        check("a missing folder is an input error", rc == 2, str(rc))

        empty = work / "empty"
        empty.mkdir()
        with mock.patch.object(output, "message", side_effect=messages.append):
            rc = cmd_export(_export_args(empty, out))
        check("an empty folder reports no files", rc == 1, str(rc))
        check("the output folder created by this run is gone again", not out.exists())

        messages.clear()
        with mock.patch.object(cfg, "MUTAGEN_AVAILABLE", False), \
                mock.patch.object(external.shutil, "which", return_value=None), \
                mock.patch.object(output, "message", side_effect=messages.append):
            rc = cmd_export(_export_args(fixture, out))
        check("without mutagen and ffprobe it is an input error", rc == 2, str(rc))
        check("the missing-tool hint is printed",
              any("mutagen" in text for text in messages), str(messages[:1]))


def test_export_cli() -> None:
    """Das ``export``-Unterkommando und die deutschen Options-Aliase."""
    script = BASE / "sortiton.py"
    fixture = _load_export_helper().FIXTURE_DIR
    command = [sys.executable, str(script), "export"]

    help_en = subprocess.run(command + ["--help"], capture_output=True, text=True,
                             check=False)
    check("export --help lists --fp-threshold", "--fp-threshold" in help_en.stdout)

    help_de = subprocess.run(command + ["--help"], capture_output=True, text=True,
                             env={**os.environ, "SORTITON_LANG": "de"}, check=False)
    check("export --help is German with SORTITON_LANG=de",
          "Ähnlichkeitsschwelle" in help_de.stdout)

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        run = subprocess.run(
            command + [str(fixture), "--ausgabe", str(out), "--quiet"],
            capture_output=True, text=True, check=False,
            env={**os.environ, "SORTITON_LOG_DIR": str(Path(tmp) / "logs")})
        check("export --ausgabe (alias) runs", run.returncode == 0,
              "" if run.returncode == 0 else (run.stderr or run.stdout)[-120:])
        check("export wrote its reports", (out / "01_zusammenfassung.md").is_file())


def test_export_cache_migration() -> None:
    """Der alte Fingerprint-Cache wird einmalig übernommen.

    The legacy cache lives in ``$XDG_CACHE_HOME/musik_export``, the new one in
    ``SORTITON_CACHE_DIR/fingerprints``. With the old file copied over, a run
    has to serve every file from the cache and call ``fpcalc`` for none of them.
    """
    import hashlib
    import json
    import unittest.mock as mock

    from sortiton import config as cfg
    from sortiton.features.export import fingerprint

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        root = work / "music"
        root.mkdir()
        recs = []
        entries = {}
        for name in ("a.flac", "b.flac"):
            file = root / name
            file.write_bytes(b"\x00" * 128)
            stat = file.stat()
            recs.append({"path": name})
            entries[name] = {"meta": [stat.st_size, int(stat.st_mtime)],
                             "k": "len3", "fp": [1, 2, 3]}

        # The old script kept its cache under $XDG_CACHE_HOME/musik_export.
        fake_xdg = work / "xdg-cache"
        legacy_dir = fake_xdg / "musik_export"
        legacy_dir.mkdir(parents=True)
        key = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
        legacy = legacy_dir / f"fp_{key}.json"
        legacy.write_text(json.dumps(entries), encoding="utf-8")

        new_dir = work / "cache"
        calls: list[str] = []

        def fake_fpcalc(path, secs, cancel=None):
            calls.append(str(path))
            return [9, 9, 9], ""

        with mock.patch.object(cfg, "CACHE_DIR", new_dir), \
                mock.patch.dict(os.environ, {"XDG_CACHE_HOME": str(fake_xdg)}), \
                mock.patch.object(fingerprint, "run_fpcalc", fake_fpcalc):
            fps = fingerprint.compute_fingerprints(recs, root, 3, 1, work)

        migrated = new_dir / "fingerprints" / f"fp_{key}.json"
        check("migration copies the legacy cache into the new place",
              migrated.is_file(), str(migrated))
        check("the legacy cache is kept (copy, not move)", legacy.is_file())
        check("a migrated cache has nothing to compute (todo == 0)",
              calls == [], str(calls))
        check("every file is served from the cache", len(fps) == len(recs), str(fps))
        check("the cached fingerprints are used",
              all(fps.get(i) == [1, 2, 3] for i in range(len(recs))), str(fps))


def test_cancel() -> None:
    """Ein abgebrochener Lauf stoppt ``cmd_export`` mit Code 130.

    The reader is patched to cancel the token after three files. ``scan`` has to
    notice it, drop the remaining reads and let ``cmd_export`` return 130
    without hanging; the half-finished output folder must stay on disk.
    """
    import unittest.mock as mock

    from sortiton import external
    from sortiton.cancel import Cancelled, CancelToken, NO_CANCEL
    from sortiton.features.export import cmd_export, reader

    check("NO_CANCEL is never set", not NO_CANCEL.is_set())

    token = CancelToken()
    raised = False
    try:
        token.check()
    except Cancelled:
        raised = True
    check("check() stays quiet before cancel()", not raised)

    token.cancel()
    raised = False
    try:
        token.check()
    except Cancelled:
        raised = True
    check("check() raises after cancel()", raised and token.is_set())

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        music = work / "music"
        music.mkdir()
        for index in range(10):
            (music / f"{index:02d}.mp3").write_bytes(b"\x00" * 64)

        token = CancelToken()
        calls = {"n": 0}

        def fake_read_file(root, path):
            calls["n"] += 1
            if calls["n"] >= 3:
                token.cancel()
            return {"path": path.relative_to(root).as_posix(), "error": ""}

        outdir = work / "out"
        messages: list[str] = []
        # No reader tool is needed: the reader itself is replaced below.
        with mock.patch.object(external, "missing", return_value=[]), \
                mock.patch.object(reader, "read_file", fake_read_file), \
                mock.patch.object(output, "message", side_effect=messages.append):
            rc = cmd_export(SimpleNamespace(folder=str(music), output=str(outdir),
                                            threads=1, cancel=token))

        check("a cancelled export returns 130", rc == 130, str(rc))
        check("the cancellation is reported",
              any("Cancell" in text or "Abgebroch" in text for text in messages),
              str(messages[:3]))
        check("the partial output is named in the message",
              any(str(outdir.resolve()) in text for text in messages), str(messages[:3]))
        check("the partial output folder is kept", outdir.is_dir())


@pytest.mark.external
@pytest.mark.slow
def test_export_write_error_is_a_clean_failure() -> None:
    """Ein Schreibfehler endet mit Meldung und Code 2, nicht mit Traceback."""
    import unittest.mock as mock

    from sortiton.features.export import cmd_export, report

    if not _reader_available():
        pytest.skip("no tag reader available")
    fixture = _library()

    def boom(_sections, _write):
        raise PermissionError(13, "Permission denied")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir()
        with mock.patch.object(report, "write_report", boom), \
                mock.patch("sortiton.output.message") as say:
            rc = cmd_export(_export_args(fixture, out, chunk_chars=60000, examples=5))

        check("a write failure returns 2", rc == 2, str(rc))
        printed = " ".join(str(call.args[0]) for call in say.call_args_list)
        check("the failure is reported", "ERROR" in printed.upper() or "FEHLER" in printed,
              printed)
        check("no half-written report claims a name",
              not (out / "01_zusammenfassung.md").exists())


@pytest.mark.external
@pytest.mark.slow
def test_export_never_overwrites_a_foreign_report() -> None:
    """Eine eigene ``01_zusammenfassung.md`` im Zielordner bleibt unangetastet.

    Vorher schrieb ``write_report`` feste Namen und ersetzte die Datei ohne
    Rückfrage - obwohl der Sortierpfad die Zusage "nichts wird überschrieben"
    über ``free_target`` einhält.
    """
    import unittest.mock as mock

    from sortiton.features.export import cmd_export

    if not _reader_available():
        pytest.skip("no tag reader available")
    fixture = _library()

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir()
        mine = out / "01_zusammenfassung.md"
        mine.write_text("meine Notizen\n", encoding="utf-8")

        with mock.patch("sortiton.output.message"):
            rc = cmd_export(_export_args(fixture, out, chunk_chars=60000, examples=5))

        check("the export works", rc == 0, str(rc))
        check("the foreign report survives untouched",
              mine.read_text(encoding="utf-8") == "meine Notizen\n",
              mine.read_text(encoding="utf-8"))
        check("our report uses a free name",
              (out / "01_zusammenfassung (2).md").is_file(),
              str(sorted(p.name for p in out.iterdir())))


@pytest.mark.external
@pytest.mark.slow
def test_export_keeps_foreign_files_when_source_is_output() -> None:
    """Quelle = Ausgabe darf keine fremde TSV/Berichte löschen.

    Vor dem Fix löschte ``_clear_reports`` feste Namen und alles, was auf
    ``tracks_part*.tsv`` passt - ohne zu prüfen, wer die Datei geschrieben hat.
    """
    import unittest.mock as mock

    from sortiton.features.export import cmd_export

    fixture = _library()
    if not _reader_available():
        pytest.skip("no tag reader available")

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
    """Ein früherer Lauf wird ersetzt, Fremdes bleibt.

    Das alte Manifest nennt einen überzähligen TSV-Teil und ``03_duplikate.md``;
    beide stammen aus einem Sortiton-Lauf und müssen verschwinden. Die fremde
    Datei mit Berichtsnamen steht in keinem Manifest und bleibt.
    """
    import unittest.mock as mock

    from sortiton.features.export import cmd_export

    fixture = _library()
    if not _reader_available():
        pytest.skip("no tag reader available")

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
    """Ein fehlendes Manifest ist kein Freibrief zum Löschen.

    Nur wenn der Lauf abbricht, bevor er seine Berichte schreibt, zeigt sich
    der Unterschied: mit altem Manifest verschwinden die alten Berichte, ohne
    Manifest bleibt alles liegen - auch bei kaputtem Manifest.
    """
    import unittest.mock as mock

    from sortiton.features.export import cmd_export, report

    fixture = _library()
    if not _reader_available():
        pytest.skip("no tag reader available")

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
    """Liste/falsche Typen im Cache dürfen den Export nicht sprengen.

    Der Cache ist JSON von der Platte: ein Eintrag als Liste ließ ``c.get`` mit
    ``AttributeError`` abstürzen, falsche ``meta``/``fp``-Typen kamen ungeprüft
    in die Auswertung.
    """
    import hashlib
    import unittest.mock as mock

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


def test_fingerprint_index_drops_common_values() -> None:
    """Ein Sub-Fingerprint in zu vielen Dateien wird entfernt statt ewig behalten."""
    import unittest.mock as mock

    from sortiton.features.export import fingerprint

    fps = {0: [7, 8, 9], 1: [7, 8], 2: [7, 8]}
    with mock.patch.object(fingerprint, "FP_MAX_POSTINGS", 2):
        index = fingerprint._build_index(fps)

    check("the common values are gone", 7 not in index and 8 not in index, str(index))
    check("the rare value is kept", list(index.get(9, [])) == [2], str(index))
