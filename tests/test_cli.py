"""Command line, German output and console progress."""

from __future__ import annotations

import pytest

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
    print("command line")
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
    print("german output")
    out = subprocess.run(
        [sys.executable, str(BASE / "sortiton.py"), "rules"],
        capture_output=True, text=True, check=False,
        env={**os.environ, "SORTITON_LANG": "de"})
    check("SORTITON_LANG=de switches", "Regeldatei" in out.stdout)


def test_console_progress() -> None:
    """Step 1.9: the stderr sink throttles, ends the line and obeys ``--quiet``."""
    print("console progress")
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
