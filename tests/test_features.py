"""Feeds features, fetch pipeline, isolation and CSV fixes."""

from __future__ import annotations

import pytest

from _support import (
    BASE,
    Path,
    SimpleNamespace,
    _fake_ytdlp_env,
    _make_flac,
    _open_journal,
    _restore_args,
    argparse,
    check,
    cmd_restore,
    config,
    contextlib,
    i18n,
    io,
    journal,
    os,
    output,
    shutil,
    skip,
    subprocess,
    tempfile,
    threading,
    write_tags,
)


def test_external_tools() -> None:
    import unittest.mock as mock

    from sortiton import external

    # available() mirrors shutil.which for programs - both branches, patched.
    with mock.patch.object(external.shutil, "which", return_value="/usr/bin/ffprobe"):
        check("available(FFPROBE) sees a program on PATH",
              external.available(external.FFPROBE))
    with mock.patch.object(external.shutil, "which", return_value=None):
        check("available(FFPROBE) reports a missing program",
              not external.available(external.FFPROBE))

    # Unpatched it has to agree with the real PATH.
    check("available(FFPROBE) matches shutil.which",
          external.available(external.FFPROBE) == (shutil.which("ffprobe") is not None))

    # mutagen follows config.MUTAGEN_AVAILABLE (tests switch it off there).
    with mock.patch.object(config, "MUTAGEN_AVAILABLE", False):
        check("available(MUTAGEN) follows config (off)",
              not external.available(external.MUTAGEN))
    with mock.patch.object(config, "MUTAGEN_AVAILABLE", True):
        check("available(MUTAGEN) follows config (on)",
              external.available(external.MUTAGEN))

    # Die Registry listet jedes Werkzeug einmal, und yt-dlp gehört dazu.
    keys = [tool.key for tool in external.TOOLS]
    check("TOOLS lists every tool once", len(keys) == len(set(keys)), ", ".join(keys))
    check("TOOLS contains yt-dlp", external.YT_DLP in external.TOOLS)

    # version(): the first flag that exits cleanly wins, any error gives "".
    ok_run = subprocess.CompletedProcess(args=["yt-dlp", "--version"], returncode=0,
                                         stdout="2024.08.06\n", stderr="")
    with mock.patch.object(external.shutil, "which", return_value="/usr/bin/yt-dlp"), \
            mock.patch.object(external.subprocess, "run", return_value=ok_run):
        got = external.version(external.YT_DLP)
        check("version() reads the program output", got == "2024.08.06", repr(got))

    with mock.patch.object(external.shutil, "which", return_value=None):
        check("version() is empty without the program",
              external.version(external.YT_DLP) == "")

    def _two_flags(argv, **_kwargs):
        """fpcalc/ffprobe reject --version but answer -version."""
        if argv[1] == "--version":
            return subprocess.CompletedProcess(argv, 2, "", "ERROR: Unknown option")
        return subprocess.CompletedProcess(argv, 0, "fpcalc version 1.6.1\n", "")

    with mock.patch.object(external.shutil, "which", return_value="/usr/bin/fpcalc"), \
            mock.patch.object(external.subprocess, "run", side_effect=_two_flags):
        got = external.version(external.FPCALC)
        check("version() falls back to the single-dash flag", got == "1.6.1", repr(got))

    banner = subprocess.CompletedProcess(
        args=["ffprobe"], returncode=0,
        stdout="ffprobe version 9.0.2 Copyright (c) 2026 the FFmpeg developers\n", stderr="")
    with mock.patch.object(external.shutil, "which", return_value="/usr/bin/ffprobe"), \
            mock.patch.object(external.subprocess, "run", return_value=banner):
        got = external.version(external.FFPROBE)
        check("version() reduces a banner to the number", got == "9.0.2", repr(got))

    for problem in (subprocess.TimeoutExpired("yt-dlp", 3), OSError("boom")):
        with mock.patch.object(external.shutil, "which", return_value="/usr/bin/yt-dlp"), \
                mock.patch.object(external.subprocess, "run", side_effect=problem):
            check(f"version() survives {type(problem).__name__}",
                  external.version(external.YT_DLP) == "")

    # The real program, when present, answers. The skip names the tool so the
    # end-of-run list shows which program was missing.
    if external.available(external.YT_DLP):
        real = external.version(external.YT_DLP)
        check("version(yt-dlp) on the real program", real != "", repr(real))
    else:
        skip("external.version for yt-dlp", "yt-dlp not installed")

    # Every hint key exists in both catalogs.
    for tool in external.TOOLS:
        ok = (tool.hint_key in i18n.catalog("en")
              and tool.hint_key in i18n.catalog("de"))
        check(f"hint key {tool.hint_key} in en+de", ok)
    check("external.error.missing in en+de",
          "external.error.missing" in i18n.catalog("en")
          and "external.error.missing" in i18n.catalog("de"))

    # format_missing names the missing tool(s) and adds their install hints.
    text = external.format_missing([external.Requirement((external.YT_DLP,))])
    flat = text.replace("\n", " / ")
    check("format_missing names yt-dlp", "yt-dlp" in text, flat)
    check("format_missing adds the yt-dlp hint", i18n.t("external.hint.ytdlp") in text, flat)
    both = external.format_missing(
        [external.Requirement((external.FFPROBE, external.FPCALC))])
    check("format_missing lists every tool of a requirement",
          "ffprobe" in both and "fpcalc" in both)


def test_features_base() -> None:
    from sortiton.features import base, get

    def _noop(args) -> int:
        return 0

    feature = base.Feature(
        key="dummy",
        title_key="",
        help_key="",
        run=_noop,
        options=(
            base.Option("folder", "folder", positional=True),
            base.Option("text", "text", "x", flags=("--text",)),
            base.Option("flag", "bool", False, flags=("--flag",)),
            base.Option("count", "int", 3, flags=("--count",)),
            base.Option("ratio", "float", 0.5, flags=("--ratio",)),
            base.Option("mode", "choice", "a", flags=("--mode",), choices=("a", "b")),
        ),
    )

    parser = argparse.ArgumentParser(prog="dummy")
    sub = parser.add_subparsers(dest="command", required=True)
    base.add_feature_parser(sub, feature)

    given = parser.parse_args(["dummy", "FOLDER", "--text", "hi", "--flag",
                               "--count", "5", "--ratio", "0.25", "--mode", "b"])
    check("folder (positional) parsed", given.folder == "FOLDER")
    check("text parsed", given.text == "hi")
    check("bool parsed", given.flag is True)
    check("int parsed", given.count == 5)
    check("float parsed", given.ratio == 0.25)
    check("choice parsed", given.mode == "b")

    defaults = parser.parse_args(["dummy", "FOLDER"])
    check("folder positional is required", defaults.folder == "FOLDER")
    check("bool default", defaults.flag is False)
    check("text default", defaults.text == "x")
    check("int default", defaults.count == 3)
    check("float default", defaults.ratio == 0.5)
    check("choice default", defaults.mode == "a")

    check("run wired as func", defaults.func is _noop)
    check("feature wired on the namespace", defaults.feature is feature)

    # resolve_args fills the options a GUI namespace left out, keeps the rest.
    resolved = base.resolve_args(feature, SimpleNamespace(folder="FOLDER"))
    check("resolve_args fills defaults",
          resolved.flag is False and resolved.text == "x" and resolved.count == 3
          and resolved.ratio == 0.5 and resolved.mode == "a")
    check("resolve_args keeps given values",
          base.resolve_args(feature, SimpleNamespace(folder="FOLDER", count=9)).count == 9)
    check("resolve_args keeps the folder", resolved.folder == "FOLDER")

    # A bool option that defaults to True is refused, not built wrongly.
    stubborn = base.Feature(key="bad", title_key="", help_key="", run=_noop,
                            options=(base.Option("x", "bool", True, flags=("--x",)),))
    raised = False
    try:
        base.add_feature_parser(sub, stubborn)
    except NotImplementedError:
        raised = True
    check("bool default True is refused", raised)

    # The registry answers, and an unknown key gives None.
    check("features.get on an unknown key returns None", get("nope") is None)


def test_features_registry() -> None:
    """Die Registry ist wohlgeformt und jeder Schlüssel ist übersetzt."""
    from sortiton.features import FEATURES

    keys = [feature.key for feature in FEATURES]
    check("feature keys are unique", len(keys) == len(set(keys)), ", ".join(keys))

    problems: list[str] = []
    missing_keys: list[str] = []
    en, de = i18n.catalog("en"), i18n.catalog("de")

    for feature in FEATURES:
        if not callable(feature.run):
            problems.append(f"{feature.key}: run is not callable")
        names = [option.name for option in feature.options]
        if len(names) != len(set(names)):
            problems.append(f"{feature.key}: duplicate option name")
        flags = [flag for option in feature.options for flag in option.flags]
        if len(flags) != len(set(flags)):
            problems.append(f"{feature.key}: duplicate flag")
        for key in (feature.title_key, feature.help_key,
                    f"gui.hint.{feature.key}", f"gui.job.{feature.key}"):
            if key not in en or key not in de:
                missing_keys.append(key)
        for option in feature.options:
            if option.help_key and (option.help_key not in en or option.help_key not in de):
                missing_keys.append(option.help_key)
        for requirement in feature.requires:
            for tool in requirement.any_of:
                if tool.hint_key and (tool.hint_key not in en or tool.hint_key not in de):
                    missing_keys.append(tool.hint_key)

    check("option names and flags are unique", not problems, "; ".join(problems))
    check("every feature/option/tool key exists in en+de", not missing_keys,
          ", ".join(sorted(set(missing_keys))))


def test_fetch() -> None:
    """Das fetch-Feature ist registriert und seine Optionen parsen sauber.

    Der Netzteil (Vorschau, Bestätigung, Download) wird in ``test_fetch_run``
    geprüft; hier geht es nur um die Beschreibung, nie um yt-dlp selbst.
    """
    from sortiton import external
    from sortiton.features import base, get
    from sortiton.features.fetch import AUDIO_FORMATS, FEATURE

    check("fetch is registered", get("fetch") is FEATURE)
    check("fetch is a writing feature", FEATURE.writes is True)
    check("fetch requires yt-dlp",
          any(external.YT_DLP in requirement.any_of for requirement in FEATURE.requires))

    names = [option.name for option in FEATURE.options]
    check("fetch has url and target as positionals",
          all(option.positional for option in FEATURE.options
              if option.name in ("url", "target")) and "url" in names and "target" in names)
    check("fetch audio formats are the yt-dlp subset",
          AUDIO_FORMATS == ("mp3", "m4a", "opus", "flac"), ", ".join(AUDIO_FORMATS))
    audio = next(option for option in FEATURE.options if option.name == "audio_format")
    check("audio format is a choice with those formats",
          audio.kind == "choice" and audio.choices == AUDIO_FORMATS)

    # The CLI builds the sub-command from the Option list, exactly like the
    # other features; parse a full call and the defaults.
    parser = argparse.ArgumentParser(prog="fetch-test")
    sub = parser.add_subparsers(dest="command", required=True)
    base.add_feature_parser(sub, FEATURE)

    given = parser.parse_args(["fetch", "https://example.org/watch?v=x", "/music",
                               "--audio-format", "opus", "--playlist", "--no-archive",
                               "--apply", "--confirm"])
    check("url (positional) parsed", given.url == "https://example.org/watch?v=x")
    check("target (positional) parsed", given.target == "/music")
    check("audio format choice parsed", given.audio_format == "opus")
    check("playlist flag parsed", given.playlist is True)
    check("no_archive flag parsed", given.no_archive is True)
    check("apply flag parsed", given.apply is True)
    check("confirm flag parsed", given.confirm is True)

    defaults = parser.parse_args(["fetch", "URL", "/music"])
    check("audio format default is mp3", defaults.audio_format == "mp3")
    check("playlist default is False", defaults.playlist is False)
    check("no_archive default is False", defaults.no_archive is False)
    check("apply default is False", defaults.apply is False)
    check("confirm default is False", defaults.confirm is False)

    # Ein Audioformat außerhalb der Auswahlliste lehnt argparse ab; yt-dlp
    # selbst könnte auch aac/alac/vorbis/wav/best.
    refused = False
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            parser.parse_args(["fetch", "URL", "/music", "--audio-format", "ogg"])
        except SystemExit:
            refused = True
    check("an unknown audio format is refused", refused)


@pytest.mark.external
def test_fetch_run() -> None:
    """Vorschau, Bestätigungs-Gate, Download und Journal.

    Das Fake-yt-dlp (``tests/fixtures/fake_ytdlp/yt-dlp``) vertritt das echte
    Programm: die Vorschau druckt eine Metadatenzeile, der Download schreibt
    eine kleine Datei und meldet Fortschritt plus fertigen Pfad. Kein Netz,
    kein echtes yt-dlp.
    """
    import unittest.mock as mock

    from sortiton import external, journal, output
    from sortiton.features.fetch import cmd_fetch

    plans: list[tuple] = []
    progresses: list[tuple] = []
    recorded: list[tuple] = []

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        target = work / "music"
        target.mkdir()
        url = "https://example.org/watch?v=abc"
        env = _fake_ytdlp_env()

        output.set_plan_sink(lambda kind, data: plans.append((kind, data)))
        output.set_progress(lambda current, total, text="":
                            progresses.append((current, total, text)))
        try:
            with mock.patch.dict(os.environ, env):
                # 1) The preview reports the plan and downloads nothing.
                rc = cmd_fetch(SimpleNamespace(url=url, target=str(target)))
                check("fetch preview returns 0", rc == 0, str(rc))
                check("fetch preview reports a fetch plan",
                      any(kind == "fetch" for kind, _ in plans), str(plans[:2]))
                check("fetch preview names the title",
                      any(data.get("title") == "Fake Song" for _, data in plans))
                check("fetch preview downloads nothing", not list(target.iterdir()))

                # 2) --apply without --confirm must not download either.
                plans.clear()
                rc = cmd_fetch(SimpleNamespace(url=url, target=str(target),
                                               apply=True))
                check("fetch refuses without --confirm", rc == 2, str(rc))
                check("an unconfirmed download writes nothing",
                      not list(target.iterdir()))

                # 3) --apply --confirm downloads and writes the journal entry.
                plans.clear()
                with mock.patch.object(journal, "record",
                                       lambda op, **data: recorded.append((op, data))):
                    rc = cmd_fetch(SimpleNamespace(url=url, target=str(target),
                                                   apply=True, confirm=True))
                files = list(target.iterdir())
                check("a confirmed download returns 0", rc == 0, str(rc))
                check("a confirmed download writes one file", len(files) == 1,
                      ", ".join(str(item) for item in files))
                check("the download journal entry is written",
                      any(op == "download" for op, _ in recorded), str(recorded))
                check("the journal entry points at the file",
                      any(str(data.get("path", "")).endswith("Fake Song.mp3")
                          for _, data in recorded), str(recorded))
                check("progress is reported up to 100",
                      bool(progresses) and progresses[-1][0] == 100, str(progresses[:3]))
                check("fetch reports its stats",
                      output.last_stats("fetch").get("files") == 1,
                      str(output.last_stats("fetch")))

                # 4) Without yt-dlp the command stops with code 2 and a hint.
                messages: list[str] = []
                with mock.patch.object(external.shutil, "which", return_value=None), \
                        mock.patch.object(output, "message",
                                          side_effect=messages.append):
                    rc = cmd_fetch(SimpleNamespace(url=url, target=str(target)))
                check("a missing yt-dlp returns 2", rc == 2, str(rc))
                check("the missing-tool message names yt-dlp",
                      any("yt-dlp" in text for text in messages), str(messages[:2]))
        finally:
            output.set_plan_sink(None)
            output.set_progress(None)


@pytest.mark.external
def test_fetch_cancel() -> None:
    """Ein Abbruch beendet den laufenden yt-dlp-Prozess.

    Das Fake-yt-dlp schaltet in einen langsamen Modus, schreibt seine PID und
    wartet auf ``SIGTERM``. Der Test startet ``cmd_fetch`` in einem Thread,
    wartet auf die erste Fortschrittszeile, bricht ab und prüft: Code 130, eine
    SIGTERM-Marke vom Fake und einen Prozess, der wirklich weg ist. Kein Netz.
    """
    import unittest.mock as mock

    from sortiton.cancel import CancelToken
    from sortiton.features.fetch import cmd_fetch

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        target = work / "music"
        target.mkdir()
        pidfile = work / "ytdlp.pid"
        termfile = work / "ytdlp.terminated"
        started = threading.Event()
        result: list[int] = []
        token = CancelToken()

        def run() -> None:
            with mock.patch.dict(os.environ, _fake_ytdlp_env(
                    SORTITON_FAKE_YTDLP_SLOW="1",
                    SORTITON_FAKE_YTDLP_PIDFILE=str(pidfile),
                    SORTITON_FAKE_YTDLP_TERMFILE=str(termfile))):
                result.append(cmd_fetch(SimpleNamespace(
                    url="https://example.org/watch?v=abc", target=str(target),
                    apply=True, confirm=True, cancel=token)))

        output.set_progress(lambda *_args: started.set())
        try:
            thread = threading.Thread(target=run)
            thread.start()
            check("the fake yt-dlp started", started.wait(timeout=15.0))
            token.cancel()
            thread.join(timeout=20.0)
        finally:
            output.set_progress(None)

        check("the cancelled fetch returns", not thread.is_alive())
        check("cancellation returns 130", result == [130], str(result))
        check("the fake process got SIGTERM", termfile.exists(),
              termfile.read_text(encoding="utf-8") if termfile.exists() else "missing")
        if pidfile.exists():
            pid = int(pidfile.read_text(encoding="utf-8"))
            gone = True
            try:
                os.kill(pid, 0)
                gone = False
            except ProcessLookupError:
                gone = True
            except PermissionError:
                gone = False
            check("the fake process is really gone", gone, str(pid))


@pytest.mark.external
def test_fetch_restore() -> None:
    """Der Kreis fetch -> restore, angetrieben vom Fake-yt-dlp.

    Ein bestätigter Download schreibt die Datei und eine Archiv-Zeile.
    ``restore`` muss die Datei löschen und die Archiv-Zeile entfernen, damit das
    Archiv einen späteren Lauf nicht blockiert. Kein Netz, kein echtes yt-dlp.
    """
    import unittest.mock as mock

    from sortiton import tasks
    from sortiton.features.fetch import cmd_fetch

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        target = work / "music"
        target.mkdir()
        archive = work / "fetch_archive.txt"
        url = "https://example.org/watch?v=abc"

        journal.close()
        log = work / "sortiton_2026-01-01_00-00-00.log"
        log.write_text("", encoding="utf-8")
        opened = journal.open_for(log)

        with mock.patch.object(config, "FETCH_ARCHIVE", archive), \
                mock.patch.object(tasks, "FETCH_ARCHIVE", archive):
            with mock.patch.dict(os.environ, _fake_ytdlp_env()):
                rc = cmd_fetch(SimpleNamespace(url=url, target=str(target),
                                               apply=True, confirm=True))
            journal.close()

            downloaded = sorted(target.iterdir())
            check("the fake download returns 0", rc == 0, str(rc))
            check("the fake download writes one file", len(downloaded) == 1,
                  ", ".join(str(item) for item in downloaded))
            check("the fake download fills the archive",
                  archive.exists() and "abc123" in archive.read_text(encoding="utf-8"),
                  archive.read_text(encoding="utf-8") if archive.exists() else "missing")

            check("restore of the download runs",
                  cmd_restore(_restore_args(opened, apply=True)) == 0)
            check("restore deletes the downloaded file",
                  bool(downloaded) and not downloaded[0].exists())
            check("restore drops the archive line",
                  "abc123" not in archive.read_text(encoding="utf-8"),
                  archive.read_text(encoding="utf-8"))
            check("restore reports no errors",
                  output.last_stats("restore").get("errors") == 0,
                  str(output.last_stats("restore")))


def test_fetch_rejects_option_like_url() -> None:
    """Eine "URL", die mit "-" beginnt, läse yt-dlp als Option."""
    import unittest.mock as mock

    from sortiton.features.fetch import cmd_fetch

    with tempfile.TemporaryDirectory() as tmp, \
            mock.patch("sortiton.features.fetch.download.preview",
                       side_effect=AssertionError("yt-dlp must not be called")):
        rc = cmd_fetch(SimpleNamespace(url="--exec=touch x", target=tmp))
    check("an option-like URL is rejected", rc == 2, str(rc))


def test_download_keeps_partial_results() -> None:
    """Eine Playlist, die mittendrin scheitert, meldet trotzdem ihre fertigen Dateien.

    Sonst existieren diese Dateien auf der Platte und im yt-dlp-Archiv, aber
    ohne Journal-Eintrag - ``restore`` könnte sie nicht zurücknehmen.
    """
    import unittest.mock as mock

    from sortiton.features.fetch import download

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "partial.mp3"
        saved: list[Path] = []

        def fake_stream(_argv, _cancel, handle):
            # Nur neu entstandene Dateien kommen ins Journal.
            target.write_bytes(b"audio")
            handle("SORTITON_FILE\t" + str(target))
            return 1, "boom"

        with mock.patch.object(download, "_stream", fake_stream):
            files, error = download.download("https://example.org/x", Path(tmp),
                                             audio_format="mp3", playlist=True,
                                             on_saved=lambda item: saved.append(item.path))

    check("the error is reported", error == "boom", error)
    check("the finished file is returned", [item.path for item in files] == [target],
          str(files))
    check("the callback saw the finished file", saved == [target], str(saved))


def test_fetch_download_drops_foreign_reported_files() -> None:
    """Nur im Lauf entstandene Dateien in ``target`` werden übernommen.

    Der Fake meldet vier Pfade: eine fremde Datei im Ziel, eine neue Datei,
    eine Datei außerhalb des Ziels und einen Pfad, den es nicht gibt. Nur die
    neue Datei darf Ergebnis und Journal erreichen.
    """
    import unittest.mock as mock

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
    """Auch Abbruch und Rückgabecode != 0 übernehmen nichts Fremdes."""
    import unittest.mock as mock

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


def test_resolve_args_accepts_a_mapping() -> None:
    """Ein Mapping wird gelesen, ein Objekt ohne Attribute klar abgelehnt."""
    from sortiton.features import get as feature_by_key
    from sortiton.features.base import resolve_args

    export = feature_by_key("export")
    options = resolve_args(export, {"folder": "/music"})
    check("the given value is kept", options.folder == "/music", str(vars(options)))
    check("the defaults are filled", options.chunk_chars == 60000, str(vars(options)))

    with pytest.raises(TypeError):
        resolve_args(export, object())


def test_fetch_requires_ffmpeg_only_when_applying() -> None:
    """Eine Vorschau fragt nur yt-dlp; ffmpeg ist eine Anforderung des Schreibens."""
    import unittest.mock as mock

    from sortiton import external
    from sortiton.features.fetch import FEATURE

    def available(tool):
        return tool == external.YT_DLP

    with mock.patch.object(external, "available", side_effect=available):
        preview = external.missing(FEATURE, SimpleNamespace(apply=False))
        applied = external.missing(FEATURE, SimpleNamespace(apply=True))

    check("a preview does not need ffmpeg", not preview, str(preview))
    check("an applied fetch needs ffmpeg",
          any(external.FFMPEG in requirement.any_of for requirement in applied),
          str(applied))


def test_features_isolation() -> None:
    """Ein Feature bleibt ohne GUI und ohne ``tasks`` ladbar.

    Geprüft wird jedes Modul unter ``sortiton/features`` auf Importe der GUI
    oder von ``tasks`` sowie auf ``print``/``sys.exit``/``global QUIET`` - die
    Regeln, die ein Feature ein loses Plugin bleiben lassen.
    """
    import ast

    imports: list[str] = []
    calls: list[str] = []
    for path in sorted((BASE / "sortiton" / "features").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in {"sortiton.gui", "sortiton.tasks"} or \
                            alias.name.startswith(("sortiton.gui.", "sortiton.tasks.")):
                        imports.append(f"{path.name}:{node.lineno} import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in {"gui", "tasks"} or \
                        module.startswith(("sortiton.gui", "sortiton.tasks")):
                    imports.append(f"{path.name}:{node.lineno} from {module}")
                for alias in node.names:
                    if alias.name in {"gui", "tasks"}:
                        imports.append(f"{path.name}:{node.lineno} imports {alias.name}")
            elif isinstance(node, ast.Call):
                function = node.func
                if isinstance(function, ast.Name) and function.id == "print":
                    calls.append(f"{path.name}:{node.lineno} print()")
                elif isinstance(function, ast.Attribute) and function.attr == "exit" and \
                        isinstance(function.value, ast.Name) and function.value.id == "sys":
                    calls.append(f"{path.name}:{node.lineno} sys.exit()")
            elif isinstance(node, ast.Global) and "QUIET" in node.names:
                calls.append(f"{path.name}:{node.lineno} global QUIET")

    check("features never import gui or tasks", not imports, "; ".join(imports[:3]))
    check("features never print, exit or use global QUIET", not calls,
          "; ".join(calls[:3]))


@pytest.mark.external
def test_fixes() -> None:
    """Die CSV-Korrekturen: Vorschau, Anwenden, Überspringen, Sicherheit, Undo."""
    from sortiton import external
    from sortiton.features.fixes import cmd_fixes, parse
    from sortiton.tags import read_info

    # --- pure parsing / validation (no tools needed) ---
    rows = parse.read_csv("\ufeffpath;field;old;new\r\nA.flac;Track;1;2\n")
    check("BOM and header are handled",
          len(rows) == 1 and rows[0].field == "track" and rows[0].line == 2,
          str([(row.line, row.field) for row in rows]))
    check("albumartist alias maps to album_artist",
          parse.canonical_field("AlbumArtist") == "album_artist")
    check("track values are checked",
          parse.value_ok("track", "3/12") and not parse.value_ok("track", "x"))
    check("year values are checked",
          parse.value_ok("year", "2001-05") and not parse.value_ok("year", "01")
          and parse.value_ok("year", ""))
    wrong = parse.read_csv("a.flac;track;1\n")
    check("a short row becomes a row error",
          len(wrong) == 1 and wrong[0].error == "fixes.error.columns")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "music"
        root.mkdir()
        (root / "keep.flac").write_bytes(b"\x00" * 64)

        # path safety: relative escape, symlink out of the tree, missing root
        resolved, key = parse.resolve_path(root, "../escape.flac")
        check("a relative escape is rejected",
              resolved is None and key == "fixes.error.outside_root")
        outside = Path(tmp) / "outside"
        outside.mkdir()
        (outside / "secret.flac").write_bytes(b"\x00" * 64)
        try:
            os.symlink(outside, root / "link")
            resolved, key = parse.resolve_path(root, "link/secret.flac")
            check("a symlink out of the tree is rejected",
                  resolved is None and key == "fixes.error.outside_root")
        except OSError:
            skip("fixes/symlink", "cannot create a symlink here")
        resolved, key = parse.resolve_path(None, "keep.flac")
        check("a relative path without --root is rejected",
              resolved is None and key == "fixes.error.root_required")

        if not (external.available(external.MUTAGEN)
                or external.available(external.FFPROBE)):
            pytest.skip("fixes run", "no tag reader (mutagen/ffprobe)")
            return
        if shutil.which("ffmpeg") is None:
            pytest.skip("fixes run", "ffmpeg is missing - cannot build a test file")
            return

        song = root / "01 - Song.flac"
        if not _make_flac(song):
            pytest.skip("fixes run", "ffmpeg could not build a test file")
            return
        write_tags(song, {"artist": "Demo", "track": "1"})

        csv_file = Path(tmp) / "fixes.csv"
        csv_file.write_text(
            "path;field;old;new\n"
            "01 - Song.flac;track;1;2\n"               # applies
            "01 - Song.flac;artist;Other;Demo Two\n"   # old value does not match
            "../escape.flac;track;1;2\n"               # rejected: outside --root
            "01 - Song.flac;bogus;x;y\n",              # rejected: unknown field
            encoding="utf-8")

        # preview changes nothing
        rc = cmd_fixes(SimpleNamespace(file=str(csv_file), root=str(root)))
        stats = output.last_stats("fixes")
        check("preview returns 0", rc == 0, str(rc))
        check("preview reports one change", stats.get("changed") == 1, str(stats))
        check("preview is not applied", not stats.get("applied"))
        check("preview counts both row errors", stats.get("errors") == 2, str(stats))
        check("preview left the tags alone",
              read_info(song).joined("track", "; ") == "1",
              read_info(song).joined("track", "; "))

        # apply, and journal it so the undo can be checked
        jrn = _open_journal(Path(tmp), 21)
        rc = cmd_fixes(SimpleNamespace(file=str(csv_file), root=str(root),
                                       apply=True, backup=False))
        journal.close()
        check("apply returns 0", rc == 0, str(rc))
        check("the track was written", read_info(song).joined("track", "; ") == "2",
              read_info(song).joined("track", "; "))
        check("the mismatching value was skipped",
              read_info(song).joined("artist", "; ") == "Demo",
              read_info(song).joined("artist", "; "))

        check("undo runs", cmd_restore(_restore_args(jrn, apply=True)) == 0)
        check("the old track value is back",
              read_info(song).joined("track", "; ") == "1",
              read_info(song).joined("track", "; "))

        # two rows for the same (path, field): both are errors, nothing changes
        dup = Path(tmp) / "dup.csv"
        dup.write_text("01 - Song.flac;track;1;5\n01 - Song.flac;track;1;6\n",
                       encoding="utf-8")
        cmd_fixes(SimpleNamespace(file=str(dup), root=str(root), apply=True,
                                  backup=False))
        check("a duplicate pair is reported as two errors",
              output.last_stats("fixes").get("errors") == 2,
              str(output.last_stats("fixes")))
        check("the duplicate pair wrote nothing",
              read_info(song).joined("track", "; ") == "1",
              read_info(song).joined("track", "; "))

        check("a missing CSV returns 2",
              cmd_fixes(SimpleNamespace(file=str(Path(tmp) / "nope.csv"),
                                        root=str(root))) == 2)


def test_fixes_normalises_exported_multivalues_but_preserves_literal_titles() -> None:
    """Export-Separatoren gelten nur für Mehrfachwerte, nicht für wörtliche Titel."""
    import csv
    import io
    import unittest.mock as mock

    from sortiton.features import fixes
    from sortiton.tags import TrackInfo

    cases = [(field, ["Alice", "Bob"], "Alice | Bob", "Alice | Carol", "Alice; Carol")
             for field in ("artist", "album_artist", "genre")]
    cases += [("title", ["Alice | Bob"], "Alice | Bob", "Song | Remix", "Song | Remix"),
              ("title", ["Alice | Bob"], "Alice; Bob", "Song", None),
              ("artist", ["Alice", "Bob"], "Bob | Alice", "Carol", None)]
    with tempfile.TemporaryDirectory() as tmp:
        song = Path(tmp) / "song.mp3"
        song.write_bytes(b"audio")
        for field, current, old, new, expected in cases:
            csv_text = io.StringIO()
            csv.writer(csv_text, delimiter=";").writerow([song.name, field, old, new])
            rows = fixes.parse.read_csv(csv_text.getvalue())
            info = TrackInfo()
            setattr(info, field, current)
            with mock.patch.object(fixes, "read_info", return_value=info):
                actions, skipped, errors = fixes._prepare(rows, Path(tmp))

            check("CSV values remain valid", not errors, str(errors))
            if expected is None:
                check("a mismatching old value is skipped", not actions and len(skipped) == 1)
                continue
            check("the exported old value matches", len(actions) == 1 and not skipped)
            action = actions[0]
            check("the planned new value is normalised", action.new == expected, action.new)
            with mock.patch.object(fixes, "write_tags", return_value=True) as write, \
                    mock.patch.object(fixes.journal, "record_tags") as record:
                fixes._write(action)
            write.assert_called_once_with(song, {field: expected})
            record.assert_called_once_with(song, {field: "; ".join(current)}, {field: expected})


def test_fixes_counts_only_successful_writes() -> None:
    """Die Zähler zeigen geschriebene Korrekturen, nicht die Größe des Plans."""
    import unittest.mock as mock

    from sortiton.features import fixes

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = root / "first.mp3"
        second = root / "second.mp3"
        first.write_bytes(b"a")
        second.write_bytes(b"b")
        csv_file = root / "fixes.csv"
        csv_file.write_text("path;field;old;new\nfirst.mp3;artist;A;B\n"
                            "second.mp3;title;C;D\n", encoding="utf-8")
        actions = [fixes._Action(2, first, "artist", "A", "B"),
                   fixes._Action(3, second, "title", "C", "D")]

        def write(action):
            if action.path == second:
                raise OSError("write failed")

        args = SimpleNamespace(file=str(csv_file), root=tmp, apply=True,
                               backup=False)
        with mock.patch.object(fixes.external, "missing", return_value=[]), \
                mock.patch.object(fixes, "_prepare", return_value=(actions, [], [])), \
                mock.patch.object(fixes, "_write", side_effect=write):
            rc = fixes.cmd_fixes(args)

    stats = output.last_stats("fixes")
    check("the mixed run reports its failure", rc == 1, str(rc))
    check("only the successful correction is counted", stats.get("changed") == 1, str(stats))
    check("the failed write is counted as an error", stats.get("errors") == 1, str(stats))


def test_fixes_backup_does_not_mix_two_runs_in_one_second() -> None:
    """Zwei ``fixes --backup``-Läufe in derselben Sekunde bekommen getrennte Ordner."""
    from sortiton.features import fixes

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "track.flac"
        source.write_bytes(b"tag data")
        first = fixes._backup_files(root, [source])
        second = fixes._backup_files(root, [source])
        check("the first backup exists", first is not None and first.is_dir(), str(first))
        check("the second backup exists", second is not None and second.is_dir(), str(second))
        check("the two runs do not share a folder", first != second,
              f"{first} == {second}")
        check("the file was copied",
              first is not None and (first / source.name).read_bytes() == b"tag data")


def test_fixes_backup_failure_aborts_before_writing() -> None:
    """``fixes --apply --backup`` schreibt nicht, wenn die Sicherung scheiterte."""
    import unittest.mock as mock

    from sortiton.features import fixes

    with tempfile.TemporaryDirectory() as tmp:
        csv_file = Path(tmp) / "fixes.csv"
        csv_file.write_text("path;field;old;new\n", encoding="utf-8")
        action = fixes._Action(2, Path(tmp) / "a.flac", "artist", "A", "B")
        args = SimpleNamespace(file=str(csv_file), root=tmp, apply=True, backup=True)
        with mock.patch.object(fixes.external, "missing", return_value=[]), \
                mock.patch.object(fixes.parse, "read_csv", return_value=[object()]), \
                mock.patch.object(fixes, "_prepare",
                                  return_value=([action], [], [])), \
                mock.patch.object(fixes, "_backup_files", return_value=None), \
                mock.patch.object(fixes, "_report"), \
                mock.patch.object(fixes, "_write") as writer:
            rc = fixes.cmd_fixes(args)

    check("the run reports an input error", rc == 2, str(rc))
    check("no tag was written", not writer.called, str(writer.call_args_list))


def test_dedupe_content_preview_apply_and_restore() -> None:
    """Exact duplicates move to .duplicates; the journal brings them back."""
    from sortiton.features import dedupe

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        root = work / "music"
        album = root / "Artist" / "Album"
        album.mkdir(parents=True)
        first = album / "a.mp3"
        second = album / "b.mp3"
        different = album / "c.mp3"
        first.write_bytes(b"same")
        second.write_bytes(b"same")
        different.write_bytes(b"diff")       # same size, other content

        preview = dedupe.cmd_dedupe(SimpleNamespace(folder=str(root), by="content",
                                                    apply=False))
        check("preview succeeds", preview == 0, str(preview))
        check("preview leaves both files in place", first.is_file() and second.is_file())
        check("preview does not create .duplicates",
              not (root / ".duplicates").exists())
        check("preview plans one move",
              output.last_stats("dedupe").get("changed") == 1,
              str(output.last_stats("dedupe")))

        jrn = _open_journal(work, 31)
        applied = dedupe.cmd_dedupe(SimpleNamespace(folder=str(root), by="content",
                                                     apply=True))
        journal.close()
        check("apply succeeds", applied == 0, str(applied))
        check("the first name is kept", first.is_file())
        moved = root / ".duplicates" / "Artist" / "Album" / "b.mp3"
        check("the duplicate is moved", moved.is_file())
        check("the original duplicate is gone from the library",
              not second.exists())
        check("a different file is untouched", different.is_file())
        check("the duplicate folder is hidden from the next scan",
              {path.name for path in dedupe.iter_audio(root)} == {"a.mp3", "c.mp3"},
              str(list(dedupe.iter_audio(root))))

        planned = journal.plan_restore(jrn)
        check("the journal records one dedupe move",
              [event.get("op") for event in planned if event.get("op") != "run"]
              == ["dedupe"], str(planned))
        check("restore succeeds", cmd_restore(_restore_args(jrn, apply=True)) == 0)
        check("the duplicate is back", second.is_file() and not moved.exists())


def test_dedupe_tags_mode_keeps_the_best_copy() -> None:
    """The opt-in tag mode groups same tags+duration and keeps the higher bitrate."""
    import unittest.mock as mock

    from sortiton import external
    from sortiton.features import dedupe
    from sortiton.tags import TrackInfo

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "music"
        root.mkdir()
        best = root / "best.mp3"
        worse = root / "worse.mp3"
        other = root / "other.mp3"
        best.write_bytes(b"aaa")
        worse.write_bytes(b"bb")
        other.write_bytes(b"cccc")

        def info_for(path: Path) -> TrackInfo:
            if path.name == "other.mp3":
                return TrackInfo(artist=["Artist"], title=["Other"], album=["Album"],
                                 duration=180.0, bitrate_kbps=128)
            return TrackInfo(artist=["Artist"], title=["Song"], album=["Album"],
                             duration=180.0,
                             bitrate_kbps=320 if path.name == "best.mp3" else 128)

        with mock.patch.object(external, "available", return_value=True), \
                mock.patch.object(dedupe, "read_info", side_effect=info_for):
            rc = dedupe.cmd_dedupe(SimpleNamespace(folder=str(root), by="tags",
                                                   apply=True))

        check("tag-mode dedupe succeeds", rc == 0, str(rc))
        check("the best copy stays", best.is_file())
        check("the worse copy is moved",
              (root / ".duplicates" / "worse.mp3").is_file())
        check("a different title is untouched", other.is_file())


def test_dedupe_is_registered_and_reads_its_options() -> None:
    """The feature is part of the shared registry and the CLI builds its parser."""
    from sortiton import cli
    from sortiton.features import get

    feature = get("dedupe")
    check("dedupe is registered", feature is not None)
    check("dedupe writes files", feature is not None and feature.writes)
    args = cli._build_parser().parse_args(
        ["dedupe", "/music", "--by", "tags", "--apply"])
    check("the folder is parsed", args.folder == "/music")
    check("the mode is parsed", args.by == "tags")
    check("apply is parsed", args.apply is True)


def test_fixes_prepare_handles_unresolved_path() -> None:
    """Ein ``None``-Pfad aus ``resolve_path`` wird als fehlende Datei gemeldet."""
    import unittest.mock as mock

    from sortiton.features.fixes import _prepare
    from sortiton.features.fixes.parse import FixRow

    row = FixRow(1, "kaputt.mp3", "artist", "Alt", "Neu", field="artist")

    with mock.patch("sortiton.features.fixes.parse.resolve_path",
                    return_value=(None, "")):
        actions, skipped, problems = _prepare([row], None)

    check("no action is planned", actions == [], str(actions))
    check("nothing is silently skipped", skipped == [], str(skipped))
    check("the row reports a missing path",
          [(line, key) for line, key, _args in problems] == [(1, "fixes.error.missing_file")],
          str(problems))
