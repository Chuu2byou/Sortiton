"""The export report: readers, goldens, fingerprints and errors."""

from __future__ import annotations

import pytest

from _support import (
    BASE,
    Path,
    SimpleNamespace,
    _INFO_TO_RECORD,
    _export_args,
    _export_columns,
    _export_texts,
    _first_difference,
    _genre_values,
    _load_export_helper,
    _tree_digest,
    check,
    cmd_scan,
    importlib,
    ms,
    os,
    output,
    probe_tags,
    shutil,
    skip,
    subprocess,
    sys,
    tempfile,
)


@pytest.mark.external
@pytest.mark.skipif(importlib.util.find_spec("mutagen") is None, reason="mutagen not installed")
def test_tag_reader() -> None:
    """Step 2.3: ``read_info`` reads all eight fields for every format.

    One fixture file per format (flac, mp3, ogg, opus, m4a); the values are
    checked against the golden ``alle_tags.jsonl``, so the raw-frame reader
    stays in step with the report. Runs only with mutagen installed.
    """
    print("tag reader (read_info)")
    import json

    from sortiton.tags import TAG_FIELDS, TrackInfo, read_info

    helper = _load_export_helper()
    fixture = helper.FIXTURE_DIR
    golden_file = helper.GOLDEN_DIR / "base" / "alle_tags.jsonl"
    if not fixture.is_dir() or not golden_file.is_file():
        pytest.skip("tag reader", "fixture or golden missing")
        return
    if importlib.util.find_spec("mutagen") is None:
        pytest.skip("tag reader", "mutagen not installed")
        return

    records = {}
    for line in golden_file.read_text(encoding="utf-8").splitlines():
        if line:
            rec = json.loads(line)
            records[rec["path"]] = rec

    samples = ("Artist A/Album One/01 - Song One.flac",
               "Sampler/01.mp3",
               "Artist B/Album Two/01 Song (Official Video).ogg",
               "Artist B/Album Two/02 - snake_case_title.opus",
               "Artist B/Album Two/03 - Same Song (2).m4a")
    for rel in samples:
        info = read_info(fixture / rel)
        ext = Path(rel).suffix.lstrip(".")
        check(f"read_info reads {ext}", isinstance(info, TrackInfo) and not info.error,
              info.error)
        if info.error:
            continue
        wrong = {field: (info.joined(field, " | "), records[rel][_INFO_TO_RECORD[field]])
                 for field in TAG_FIELDS
                 if info.joined(field, " | ") != records[rel][_INFO_TO_RECORD[field]]}
        check(f"read_info fills all eight fields ({ext})", not wrong, str(wrong))


@pytest.mark.external
@pytest.mark.skipif(importlib.util.find_spec("mutagen") is None, reason="mutagen not installed")
def test_probe_tags_unchanged() -> None:
    """Step 2.3: ``probe_tags`` keeps its five fields and the ``"; "`` separator.

    The expected values were captured before the reader merge; this is the
    regression guard for the tag/rename/sort/scan commands.
    """
    print("probe_tags (regression)")
    from sortiton.tags import probe_tags

    fixture = _load_export_helper().FIXTURE_DIR
    if not fixture.is_dir():
        pytest.skip("probe_tags regression", "fixture missing")
        return
    if importlib.util.find_spec("mutagen") is None:
        pytest.skip("probe_tags regression", "mutagen not installed")
        return

    expected = {
        "Artist A/Album One/01 - Song One.flac":
            {"artist": "Artist A", "album_artist": "Artist A", "album": "Album One",
             "title": "Song One", "genre": "Rock"},
        "Sampler/01.mp3":
            {"artist": "Alpha", "album_artist": "", "album": "Sampler",
             "title": "Alpha One", "genre": "Pop"},
        "Artist E/Album Five/01 - Cherry.flac":
            {"artist": "Artist E", "album_artist": "Artist E", "album": "Album Five",
             "title": "Cherry", "genre": "J-Pop; Rock"},
        "Ünïcode/ぼ.flac":
            {"artist": "Unicode", "album_artist": "Unicode", "album": "Ünïcode Album",
             "title": "ぼ", "genre": "J-Pop"},
    }
    for rel, want in expected.items():
        got = probe_tags(fixture / rel)
        check(f"probe_tags keeps the five fields ({Path(rel).name})", got == want,
              f"{got} != {want}")


def test_export_public_api() -> None:
    """Step 1.9: the export entry point and progress are part of the public API."""
    print("export public interface")
    check("ms.cmd_export is public", hasattr(ms, "cmd_export") and "cmd_export" in ms.__all__)
    check("ms.progress is public", hasattr(ms, "progress") and "progress" in ms.__all__)


def test_scan() -> None:
    print("folder scan")
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "track.mp3").write_bytes(b"\x00" * 64)
        rc = cmd_scan(SimpleNamespace(folder=tmp))
        check("scan runs", rc == 0)
        check("scan counts files", output.last_stats("scan").get("files") == 1,
              str(output.last_stats("scan")))
        check("scan of a missing folder fails",
              cmd_scan(SimpleNamespace(folder=str(Path(tmp) / "nope"))) == 2)


def test_export_fixture() -> None:
    print("export fixture library")
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
    """Steps 1.9 and 2.1: the German report reproduces the phase-1 golden.

    Variant A is the plain run whose whole output was stored in
    ``tests/golden/export/base``; variant B adds ``check_case`` and only
    ``01_*``/``02_*`` were stored.  Both run with ``report_lang="de"`` so the
    (unchanged) German golden still matches after the report was localized; the
    English counterpart is ``test_export_golden_en``.  Compared after
    ``normalize_export_text`` (folder and timestamp).
    """
    print("export golden")
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
    """Step 2.1: the English report is pinned to ``tests/golden/export/base_en``.

    Same run as the German base golden, only with ``report_lang="en"``.  A
    missing translation key would show up as the raw key name, so the golden
    also proves that the English catalog is complete.
    """
    print("export golden (english)")
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
    """Step 1.9: without mutagen the ffprobe reader yields the same tag columns.

    Only the columns both readers fill from tags are compared; ``sek``,
    ``kbps``, ``codec`` and ``cover`` come from different tools and may differ.
    ``genre`` is compared as a set of values, because the two readers join
    several genres differently.
    """
    print("export ffprobe reader")
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
    """Step 1.9: a fingerprint run groups the identical pair, not the other file.

    No byte comparison (fpcalc versions produce different fingerprints), only
    the grouping in ``03_duplikate.md``.  The default ``fp_seconds`` is used:
    the fixture chirp is 5.5 s and a shorter window would leave too few
    sub-fingerprints for the comparison.
    """
    print("export fingerprint duplicates")
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
    """Step 1.9: the export is read-only - the source tree stays untouched."""
    print("export leaves the source alone")
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
    """Step 1.9: the documented return codes of ``cmd_export``."""
    print("export error paths")
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

        messages.clear()
        with mock.patch.object(cfg, "MUTAGEN_AVAILABLE", False), \
                mock.patch.object(external.shutil, "which", return_value=None), \
                mock.patch.object(output, "message", side_effect=messages.append):
            rc = cmd_export(_export_args(fixture, out))
        check("without mutagen and ffprobe it is an input error", rc == 2, str(rc))
        check("the missing-tool hint is printed",
              any("mutagen" in text for text in messages), str(messages[:1]))


def test_export_cli() -> None:
    """Step 1.9: the ``export`` sub-command and the German flag aliases."""
    print("export cli")
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
    """Step 1.7: the old fingerprint cache is taken over once.

    The legacy cache lives in ``$XDG_CACHE_HOME/musik_export``, the new one in
    ``SORTITON_CACHE_DIR/fingerprints``. With the old file copied over, a run
    has to serve every file from the cache and call ``fpcalc`` for none of them.
    """
    print("export fingerprint cache migration")
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
    """Step 3.1: a cancelled token stops ``cmd_export`` with code 130.

    The reader is patched to cancel the token after three files. ``scan`` has to
    notice it, drop the remaining reads and let ``cmd_export`` return 130
    without hanging; the half-finished output folder must stay on disk.
    """
    print("cancellation")
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
