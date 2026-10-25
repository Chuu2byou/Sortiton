"""Command line, German output and console progress."""

from __future__ import annotations

from _support import (
    BASE,
    Path,
    SimpleNamespace,
    _FakeTTY,
    check,
    os,
    output,
    subprocess,
    sys,
    tempfile,
)


def test_cli() -> None:
    help_out = subprocess.run([sys.executable, str(BASE / "sortiton.py"), "--help"],
                              capture_output=True, text=True, check=False)
    check("--help works", help_out.returncode == 0 and "tags" in help_out.stdout)
    check("--help is English", "Clean tags" in help_out.stdout)

    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "track.mp3").write_bytes(b"\x00" * 64)
        prev = subprocess.run(
            [sys.executable, str(BASE / "sortiton.py"), "tags", tmp],
            capture_output=True, text=True, check=False,
            env={**os.environ, "SORTITON_LOG_DIR": str(Path(tmp) / "logs"),
                 "SORTITON_RULES": str(Path(tmp) / "my_rules.ini")})
        check("preview run works", prev.returncode == 0, prev.stderr.strip()[:120])
        check("preview says files", "Files" in prev.stdout)


def test_german_cli() -> None:
    out = subprocess.run(
        [sys.executable, str(BASE / "sortiton.py"), "rules"],
        capture_output=True, text=True, check=False,
        env={**os.environ, "SORTITON_LANG": "de"})
    check("SORTITON_LANG=de switches", "Regeldatei" in out.stdout)


def test_console_progress() -> None:
    """Der stderr-Sink drosselt, beendet die Zeile und beachtet ``--quiet``."""
    import unittest.mock as mock

    from sortiton import cli

    cli._progress_last = 0.0
    cli._progress_open = False
    stream = _FakeTTY()
    with mock.patch.object(cli.sys, "stderr", stream):
        cli.console_progress(1, 3, "a")
        first = stream.text
        cli.console_progress(2, 3, "b")          # too soon after the first
        throttled = stream.text
        cli.console_progress(3, 3, "c")          # last entry: always drawn
        final = stream.text
    check("the sink draws a progress line", first.startswith("\r") and "1/3" in first,
          repr(first))
    check("the sink throttles repeated writes", throttled == first)
    check("the last entry ends the line", final.endswith("3/3  c\n"), repr(final))

    def _run_main(quiet: bool):
        """Call ``cli.main`` with a stub parser; return (rc, set_progress mock)."""
        args = SimpleNamespace(command="export", feature=None, quiet=quiet,
                               func=lambda _args: 0)
        with mock.patch.object(cli, "_build_parser") as build, \
                mock.patch.object(cli.sys, "argv", ["sortiton.py", "export"]), \
                mock.patch.object(cli.sys, "stderr", _FakeTTY()), \
                mock.patch.object(cli, "open_log_file", return_value=None), \
                mock.patch.object(cli, "load_custom_rules", return_value=[]), \
                mock.patch.object(cli, "rules_summary", return_value=""), \
                mock.patch.object(output, "set_progress") as installed:
            build.return_value.parse_args.return_value = args
            rc = cli.main()
        return rc, installed

    cli._progress_last = 0.0
    cli._progress_open = False
    rc, installed = _run_main(False)
    check("main runs on a TTY", rc == 0, str(rc))
    check("a TTY installs the console sink", installed.call_count == 1)
    check("the sink is cli.console_progress",
          installed.call_args is not None
          and installed.call_args.args[0] is cli.console_progress)

    cli._progress_open = False
    rc, installed = _run_main(True)
    check("main runs with --quiet", rc == 0, str(rc))
    check("--quiet installs no progress sink", not installed.called)


def test_cli_tags_and_rename_target() -> None:
    """tags and rename accept an optional target directory and --move."""
    from sortiton import cli

    parser = cli._build_parser()
    args_tags = parser.parse_args(["tags", "/src", "/dst", "--move", "--apply"])
    check("cli tags target parsed", args_tags.target == "/dst")
    check("cli tags move parsed", args_tags.move is True)

    args_number = parser.parse_args(["tags", "/src", "--track-format", "padded"])
    check("cli tags track format parsed", args_number.track_format == "padded")
    args_all = parser.parse_args(["all", "/src", "/dst", "--track-format", "number"])
    check("cli all track format parsed", args_all.track_format == "number")

    args_ren = parser.parse_args(["rename", "/src", "/dst", "--move", "--pattern", "%title%"])
    check("cli rename target parsed", args_ren.target == "/dst")
    check("cli rename move parsed", args_ren.move is True)
    check("cli rename pattern parsed", args_ren.pattern == "%title%")


def test_tags_apply_requires_a_writing_tool() -> None:
    """``tags --apply`` bricht früh ab, wenn nur ein Leser installiert ist."""
    import unittest.mock as mock

    from sortiton import cli, external

    def available(tool):
        return tool is external.FFPROBE  # lesen ja, schreiben nein

    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.object(external, "available", available), \
                mock.patch("sys.argv", ["sortiton", "tags", tmp, "--apply"]), \
                mock.patch("sortiton.output.message"):
            rc = cli.main()

    check("tags --apply stops before the first file", rc == 2, str(rc))


def test_write_command_aborts_when_the_journal_cannot_open() -> None:
    """Ein Schreibkommando startet nicht ohne das erforderliche Journal."""
    import unittest.mock as mock

    from sortiton import cli

    called = []
    args = SimpleNamespace(command="rename", apply=True, quiet=True,
                           func=lambda _args: called.append(True) or 0)
    parser = mock.Mock()
    parser.parse_args.return_value = args
    with mock.patch.object(cli, "_build_parser", return_value=parser), \
            mock.patch.object(cli.external, "available", return_value=True), \
            mock.patch.object(cli, "open_log_file", return_value=None), \
            mock.patch.object(cli.journal, "enabled", return_value=True), \
            mock.patch.object(cli, "message"), \
            mock.patch.object(cli, "close_log_file"):
        rc = cli.main()

    check("the command exits before applying", rc == 2, str(rc))
    check("the write function is not called", not called, str(called))
