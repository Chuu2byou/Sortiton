#!/usr/bin/env python3
"""Smoke test for the Sortiton (no extra packages required).

Covers the public interface, both translation catalogs, the cleaning rules, the
custom rules, the CLI and the GUI. Without a display the GUI part is skipped.

Run:  python3 tests/smoke.py
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

BASE = Path(__file__).resolve().parents[1]

# Keep the test away from the real settings/rules/logs of the user.
_TMP = Path(tempfile.mkdtemp(prefix="sortiton-smoke-"))
os.environ["SORTITON_SETTINGS"] = str(_TMP / "settings.ini")
os.environ["SORTITON_RULES"] = str(_TMP / "my_rules.ini")
os.environ["SORTITON_LOG_DIR"] = str(_TMP / "logs")
os.environ["SORTITON_EXPORT_DIR"] = str(_TMP / "exports")
os.environ["SORTITON_CACHE_DIR"] = str(_TMP / "cache")
os.environ.pop("SORTITON_LANG", None)

sys.path.insert(0, str(BASE))

import sortiton as ms                        # noqa: E402
from sortiton import config, files, i18n, journal, output, rules, settings   # noqa: E402
from sortiton.tags import probe_tags, write_tags   # noqa: E402
from sortiton.tasks import cmd_restore, cmd_scan   # noqa: E402

FAILURES: list[str] = []
SKIPPED: list[str] = []
KEY_RE = re.compile(r"""i18n\.t\(\s*["']([A-Za-z0-9_.-]+)["']""")


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'ok ' if ok else 'FAIL'}] {name}{(' - ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(name)


def skip(name: str, detail: str = "") -> None:
    """Record a check that could not run (no display, missing tool …).

    A skip keeps the suite green, but it is counted and named at the end - a
    silently skipped check is a check that nobody notices is missing.
    """
    print(f"  [skip] {name}{(' - ' + detail) if detail else ''}")
    SKIPPED.append(name)


def test_import() -> None:
    print("import / public interface")
    check("__all__ is not empty", bool(ms.__all__))
    missing = [name for name in ms.__all__ if not hasattr(ms, name)]
    check("__all__ names exist", not missing, ", ".join(missing))


def test_version() -> None:
    print("version and entry points")
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


def test_catalogs() -> None:
    print("translation catalogs")
    en, de = i18n.catalog("en"), i18n.catalog("de")
    check("both catalogs non-empty", bool(en) and bool(de))

    only_en = sorted(set(en) - set(de))
    only_de = sorted(set(de) - set(en))
    check("same keys in en/de", not only_en and not only_de,
          f"en only: {only_en[:5]} de only: {only_de[:5]}")

    raw: set[str] = set()
    for path in sorted(BASE.glob("sortiton/**/*.py")) + [BASE / "sortiton.py"]:
        raw |= set(KEY_RE.findall(path.read_text(encoding="utf-8")))

    # Without this the two checks below would pass on a project that calls
    # i18n differently - nothing found is not the same as nothing wrong.
    check("i18n.t() calls were found at all", bool(raw))

    # Dynamic keys such as i18n.t("gui.confirm." + page + ".title") are found as
    # a bare prefix and can only be checked for having entries at all.
    used = {key for key in raw if not key.endswith(".")}
    prefixes = sorted(key for key in raw if key.endswith("."))
    unknown = sorted(used - set(en))
    check("every used key exists", not unknown, ", ".join(unknown[:8]))

    empty_prefixes = [prefix for prefix in prefixes
                      if not any(key.startswith(prefix) for key in en)]
    check("dynamic key prefixes exist", not empty_prefixes, ", ".join(empty_prefixes))


def test_rules() -> None:
    print("cleaning rules")
    check("genre keeps J-Pop", rules.clean_genre("Jpop") == "J-Pop")
    check("genre splits at comma", rules.clean_genre("Rock,Pop") == "Rock; Pop")
    check("artist splits at &", rules.clean_artist("Sample Band & Guest") == "Sample Band; Guest")
    check("artist feat", rules.clean_artist("Sample Band feat. Guest") == "Sample Band; Guest")
    check("artist idempotent",
          rules.clean_artist(rules.clean_artist("Sample Band & Guest")) == "Sample Band; Guest")
    check("builtin overview has content", len(rules.builtin_rules_text().splitlines()) > 40)
    check("template contains both sections",
          "[Artist]" in rules.rules_template() and "[Protected]" in rules.rules_template())


def test_custom_rules() -> None:
    print("custom rules (my_rules.ini)")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "my_rules.ini"
        path.write_text(
            "[Artist]\n"
            "DJ Example = Example DJ\n"
            "\n"
            "[Artist Regex]\n"
            "(?i)\\bexample\\s+group\\b = Example Group\n"
            "\n"
            "[Genre]\n"
            "junkgenre = \n"
            "\n"
            "[Protected]\n"
            "Demo & Co\n"
            "Foo/Bar = Foo / Bar\n",
            encoding="utf-8")

        warnings = rules.load_custom_rules(path)
        check("no warnings", not warnings, str(warnings))
        check("simple replacement", rules.clean_artist("dj example") == "Example DJ")
        check("regex replacement", rules.clean_artist("example  group") == "Example Group")
        check("protected is not split", rules.clean_artist("Demo & Co") == "Demo & Co")
        check("protected spelling", rules.clean_artist("Foo/Bar") == "Foo / Bar")
        check("empty genre deletes", rules.clean_genre("junkgenre") == "")

    rules.load_custom_rules()   # back to the real state (no file in the test env)


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


def test_external_tools() -> None:
    print("external tools")
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

    # Every hint key exists in both catalogs.
    for tool in (external.FFPROBE, external.FPCALC, external.MUTAGEN):
        ok = (tool.hint_key in i18n.catalog("en")
              and tool.hint_key in i18n.catalog("de"))
        check(f"hint key {tool.hint_key} in en+de", ok)
    check("external.error.missing in en+de",
          "external.error.missing" in i18n.catalog("en")
          and "external.error.missing" in i18n.catalog("de"))


def test_features_base() -> None:
    print("feature description (base)")
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
    """Step 1.9: the registry is well-formed and every key is translated."""
    print("feature registry")
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
        for key in (feature.title_key, feature.help_key):
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


def test_features_isolation() -> None:
    """Step 1.9: a feature must stay loadable without the GUI or the tasks.

    Scans every module of ``sortiton/features`` for imports of the GUI or
    ``tasks`` and for ``print``/``sys.exit``/``global QUIET`` - the rules that
    keep a feature a loose plugin.
    """
    print("feature isolation")
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


def test_packages_complete() -> None:
    """Step 1.9: every package of ``sortiton`` is listed for the wheel (P9)."""
    print("wheel packages")
    import tomllib

    text = (BASE / "pyproject.toml").read_text(encoding="utf-8")
    listed = set(tomllib.loads(text)["tool"]["setuptools"]["packages"])
    needed = {path.parent.relative_to(BASE).as_posix().replace("/", ".")
              for path in (BASE / "sortiton").rglob("__init__.py")}
    missing = sorted(needed - listed)
    check("pyproject lists every package with an __init__.py", not missing,
          ", ".join(missing))


def test_read_extensions() -> None:
    """Step 2.2: reading accepts more formats than writing touches (P2)."""
    print("read extensions")
    check("AUDIO_EXTENSIONS keeps the read-only formats out",
          not {".mp4", ".oga", ".aif"} & config.AUDIO_EXTENSIONS,
          str(sorted(config.AUDIO_EXTENSIONS)))


def test_export_public_api() -> None:
    """Step 1.9: the export entry point and progress are part of the public API."""
    print("export public interface")
    check("ms.cmd_export is public", hasattr(ms, "cmd_export") and "cmd_export" in ms.__all__)
    check("ms.progress is public", hasattr(ms, "progress") and "progress" in ms.__all__)


class _FakeTTY:
    """A stream that claims to be a terminal and records what was written."""

    def __init__(self) -> None:
        self.text = ""

    def write(self, data: str) -> int:
        self.text += data
        return len(data)

    def flush(self) -> None:
        """No-op: nothing is buffered."""

    def isatty(self) -> bool:
        return True


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
        skip("export fixture present", "missing - run tools/make_export_fixture.py")
        return
    total = sum(item.stat().st_size for item in fixture.rglob("*") if item.is_file())
    check("export fixture is under 300 kB", total < 300_000, f"{total} bytes")
    if importlib.util.find_spec("mutagen") is None:
        skip("export fixture matches the script", "mutagen is missing")
        return
    result = subprocess.run([sys.executable, str(script), "--check"],
                            capture_output=True, text=True, check=False)
    check("export fixture matches the script", result.returncode == 0,
          (result.stdout or result.stderr).strip().splitlines()[-1][:120])


def _load_export_helper():
    """Load ``tests/export_golden.py`` by path (it is not an installed module)."""
    target = BASE / "tests" / "export_golden.py"
    spec = importlib.util.spec_from_file_location("export_golden", target)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _export_texts(directory: Path, helper,
                  keep: tuple[str, ...] = ()) -> dict[str, str]:
    """Normalized text of every stored file, optionally limited to a prefix."""
    texts: dict[str, str] = {}
    for path in sorted(directory.iterdir()):
        if path.is_file() and (not keep or path.name.startswith(keep)):
            texts[path.name] = helper.normalize_export_text(
                path.read_text(encoding="utf-8"))
    return texts


def _first_difference(left: dict[str, str], right: dict[str, str]) -> str:
    """Name the first differing file, so a failure stays readable."""
    if sorted(left) != sorted(right):
        return f"files: {sorted(left)} != {sorted(right)}"
    for name in sorted(left):
        if left[name] != right[name]:
            return f"first difference in {name}"
    return ""


def _export_args(fixture: Path, outdir: Path, **overrides) -> SimpleNamespace:
    """Arguments for ``cmd_export`` the way the CLI would deliver them.

    ``cmd_export`` fills every field it does not find with the option default
    (:func:`sortiton.features.base.resolve_args`), so a test only sets what it
    means to change.
    """
    values = {"folder": str(fixture), "output": str(outdir)}
    values.update(overrides)
    return SimpleNamespace(**values)


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
        skip("export golden", "fixture missing")
        return
    if importlib.util.find_spec("mutagen") is None:
        skip("export golden", "mutagen not installed")
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
        skip("export golden english", "fixture missing")
        return
    if not golden_dir.is_dir():
        skip("export golden english", "tests/golden/export/base_en is missing")
        return
    if importlib.util.find_spec("mutagen") is None:
        skip("export golden english", "mutagen not installed")
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


def _export_columns(directory: Path, columns: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    """The given TSV columns of every row, keyed by path (chunking independent)."""
    rows: dict[str, tuple[str, ...]] = {}
    for path in sorted(directory.glob("tracks_part*.tsv")):
        lines = path.read_text(encoding="utf-8").splitlines()
        head = lines[0].split("\t")
        index = [head.index(name) for name in columns]
        for line in lines[1:]:
            if line:
                cells = line.split("\t")
                rows[cells[index[0]]] = tuple(cells[i] for i in index)
    return rows


def _genre_values(value: str) -> frozenset[str]:
    """Genre as a set: mutagen joins with ``" | "``, ffprobe with ``";"``."""
    return frozenset(part.strip() for part in re.split(r"[;|]", value) if part.strip())


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
        skip("export ffprobe reader", "fixture missing")
        return
    if shutil.which("ffprobe") is None:
        skip("export ffprobe reader", "ffprobe not installed")
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
        skip("export fingerprint", "fixture missing")
        return
    if shutil.which("fpcalc") is None:
        skip("export fingerprint", "fpcalc not installed")
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


def _tree_digest(root: Path) -> list[tuple[str, int, int, str]]:
    """Path, size, mtime (ns) and SHA-256 of every file under ``root``."""
    import hashlib

    digest: list[tuple[str, int, int, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            stat = path.stat()
            digest.append((path.relative_to(root).as_posix(), stat.st_size,
                           stat.st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest()))
    return digest


def test_export_source_untouched() -> None:
    """Step 1.9: the export is read-only - the source tree stays untouched."""
    print("export leaves the source alone")
    import unittest.mock as mock

    from sortiton.features.export import cmd_export

    helper = _load_export_helper()
    fixture = helper.FIXTURE_DIR
    if not fixture.is_dir():
        skip("export source untouched", "fixture missing")
        return
    if importlib.util.find_spec("mutagen") is None:
        skip("export source untouched", "mutagen not installed")
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

        def fake_fpcalc(path, secs):
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


def _restore_args(path, *, apply: bool = False, keep_copies: bool = False,
                  list_journals: bool = False):
    """The argument set cmd_restore expects (CLI: argparse, here a namespace)."""
    return SimpleNamespace(journal=path, apply=apply, backup=False,
                           keep_copies=keep_copies, list_journals=list_journals)


def _open_journal(work: Path, day: int):
    """Open a journal for a synthetic run under ``work``; the caller closes it.

    ``day`` only keeps the file names of the runs apart.
    """
    log = work / f"sortiton_2026-01-{day:02d}_00-00-00.log"
    log.write_text("", encoding="utf-8")
    return journal.open_for(log)


def _make_flac(path: Path) -> bool:
    """Build a short, silent FLAC with ffmpeg (False when ffmpeg is missing)."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "anullsrc=r=8000:cl=mono", "-t", "0.2", str(path)],
            capture_output=True, check=False)
    except OSError:
        return False
    return result.returncode == 0 and path.is_file()


def test_journal() -> None:
    print("run journal")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        log = work / "sortiton_2026-01-01_00-00-00.log"
        log.write_text("", encoding="utf-8")

        journal.close()
        target = work / "a.mp3"
        target.write_bytes(b"x")

        opened = journal.open_for(log)
        check("journal is created next to the log",
              opened is not None and opened.suffix == ".jsonl", str(opened))
        check("journal knows it is open", journal.is_open())
        check("its path is remembered", journal.latest_path() == opened)
        if opened is None:
            return          # the checks above already failed - nothing to read

        journal.record_tags(target, {"artist": "Old"}, {"artist": "New"})
        journal.record_move("rename", target, work / "b.mp3")
        journal.close()

        events = list(journal.read_journal(opened))
        check("a header is written", bool(events) and events[0]["op"] == "run",
              str(events[:1]))
        check("events are readable",
              [event["op"] for event in events] == ["run", "tags", "rename"],
              str([event["op"] for event in events]))
        check("the header carries argv and cwd",
              "argv" in events[0] and "cwd" in events[0])
        check("schema version is stored",
              journal.schema_version(opened) == journal.SCHEMA)

        planned = journal.plan_restore(opened)
        check("undo runs newest first",
              [event["op"] for event in planned] == ["rename", "tags"],
              str([event["op"] for event in planned]))
        check("summary counts per operation",
              journal.summarize(planned) == {"rename": 1, "tags": 1},
              str(journal.summarize(planned)))

        # A preview must not leave a journal behind: record() on a closed
        # journal does nothing, so no file appears next to the log path.
        preview_log = work / "sortiton_2026-01-01_01-00-00.log"
        check("no journal while closed", not journal.is_open())
        journal.record("tags")      # must simply do nothing
        check("a closed journal writes nothing",
              not journal.journal_path_for(preview_log).exists())

        broken = work / "broken.jsonl"
        broken.write_text('{"v": 1, "op": "run"}\nnot json\n\n'
                          '{"v": 1, "op": "tags"}\n', encoding="utf-8")
        check("broken lines are skipped",
              len(list(journal.read_journal(broken))) == 2)
        check("a missing journal reads as empty",
              list(journal.read_journal(work / "nope.jsonl")) == [])
        check("unknown operations are named",
              journal.summarize([{"op": "rmfile"}]) == {"rmfile": 1})

        # A run must never be offered its own journal as "the last one to undo".
        older = journal.open_for(config.LOG_DIR / "sortiton_2026-01-01_02-00-00.log")
        journal.record_move("rename", target, work / "c.mp3")
        journal.close()
        newer = journal.open_for(config.LOG_DIR / "sortiton_2026-01-01_03-00-00.log")
        check("the journal of the running run is skipped",
              journal.latest_journal() == older, str(journal.latest_journal()))
        journal.close()
        check("afterwards the newest journal is the last run",
              journal.latest_journal() == newer, str(journal.latest_journal()))


class _FrozenClock(datetime):
    """A clock that stands still, so two runs start in the same second."""

    @classmethod
    def now(cls, tz=None):
        return cls(2026, 1, 1, 12, 0, 0)


def _png_header(width: int, height: int) -> bytes:
    """A PNG header of the given size - the guard reads nothing else."""
    return (b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR"
            + width.to_bytes(4, "big") + height.to_bytes(4, "big")
            + b"\x08\x06\x00\x00\x00")


def test_screenshot_guard() -> None:
    """The screenshot run must never store anything but the Sortiton window."""
    print("screenshot guard")
    target = BASE / "tools" / "make_screenshots.py"
    spec = importlib.util.spec_from_file_location("make_screenshots", target)
    assert spec is not None and spec.loader is not None
    shots = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shots)

    window, screen = (1040, 900), (1920, 1080)
    with tempfile.TemporaryDirectory() as tmp:
        def store(name: str, size: tuple[int, int]) -> Path:
            path = Path(tmp) / name
            path.write_bytes(_png_header(*size))
            return path

        check("the window itself is accepted",
              shots.looks_like_window(store("a.png", window), window, screen))
        check("a decorated window is accepted",
              shots.looks_like_window(store("b.png", (1044, 934)), window, screen))
        check("the whole screen is rejected",
              not shots.looks_like_window(store("c.png", screen), window, screen))
        check("another window is rejected",
              not shots.looks_like_window(store("d.png", (1600, 1000)), window, screen))
        check("a missing file is rejected",
              not shots.looks_like_window(Path(tmp) / "gone.png", window, screen))
        check("an empty file is rejected",
              not shots.looks_like_window(store("e.png", (0, 0)), window, screen))


def test_logs() -> None:
    print("log files")
    output.close_log_file()

    with tempfile.TemporaryDirectory() as tmp:
        taken = Path(tmp) / "sortiton_2026-01-01_12-00-00.log"
        check("a free name is left alone", files.free_path(taken) == taken)
        taken.write_text("first\n", encoding="utf-8")
        moved = files.free_path(taken)
        check("a taken name moves to ' (2)'",
              moved.name == "sortiton_2026-01-01_12-00-00 (2).log", moved.name)

    # A second run in the same second must not cut the first log short.
    real_clock = output.datetime
    output.datetime = _FrozenClock
    try:
        first = output.open_log_file("first run")
        second = output.open_log_file("second run")
        output.close_log_file()
    finally:
        output.datetime = real_clock

    check("the second run gets a log of its own",
          first is not None and second is not None and first != second,
          f"{first} / {second}")
    first_text = first.read_text(encoding="utf-8") if first else ""
    second_text = second.read_text(encoding="utf-8") if second else ""
    check("the first log survives complete", "first run" in first_text)
    check("both logs name their own run",
          "second run" in second_text and "first run" not in second_text)


def test_restore() -> None:
    print("undo (restore)")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)

        # moves and copies; no audio file needed for these
        music = work / "music"
        music.mkdir()
        track = music / "track.mp3"
        track.write_bytes(b"\x00" * 64)

        moved_to = work / "library" / "Demo - Song.mp3"
        moved_to.parent.mkdir()
        shutil.move(str(track), str(moved_to))
        copied_to = work / "copies" / "Demo - Song.mp3"
        copied_to.parent.mkdir()
        shutil.copy2(moved_to, copied_to)

        jrn = _open_journal(work, 1)
        journal.record_move("rename", track, moved_to)
        journal.record_move("copy", moved_to, copied_to, mode="copy")
        journal.close()

        check("preview runs", cmd_restore(_restore_args(jrn)) == 0)
        check("preview changes nothing",
              moved_to.exists() and copied_to.exists() and not track.exists())
        check("preview counts both changes",
              output.last_stats("restore").get("changed") == 2,
              str(output.last_stats("restore")))
        check("preview does not write",
              not output.last_stats("restore").get("applied"))

        check("apply runs", cmd_restore(_restore_args(jrn, apply=True)) == 0)
        check("moved file is back", track.exists() and not moved_to.exists())
        check("the copy is gone", not copied_to.exists())
        stats = output.last_stats("restore")
        check("nothing was skipped", stats.get("skipped") == 0, str(stats))
        check("no errors", stats.get("errors") == 0, str(stats))
        check("apply is reported", bool(stats.get("applied")))

        # --keep-copies: a copy run stays where it is
        keep_dir = work / "keep"
        keep_dir.mkdir()
        original = keep_dir / "orig.mp3"
        original.write_bytes(b"\x00" * 64)
        kept = keep_dir / "kept.mp3"
        shutil.copy2(original, kept)
        jrn_keep = _open_journal(work, 2)
        journal.record_move("copy", original, kept, mode="copy")
        journal.close()
        cmd_keep = cmd_restore(_restore_args(jrn_keep, apply=True, keep_copies=True))
        check("--keep-copies run works", cmd_keep == 0)
        check("--keep-copies keeps the copy", kept.exists())

        # the last copy is the only file left - do not delete it
        only = work / "only"
        only.mkdir()
        last_copy = only / "last.mp3"
        last_copy.write_bytes(b"\x00" * 64)
        jrn_only = _open_journal(work, 3)
        journal.record_move("copy", only / "gone.mp3", last_copy, mode="copy")
        journal.close()
        cmd_restore(_restore_args(jrn_only, apply=True))
        check("the only copy survives", last_copy.exists())
        check("that case is counted as skipped",
              output.last_stats("restore").get("skipped") == 1,
              str(output.last_stats("restore")))

        # the old name is taken again: nothing may be overwritten
        clash = work / "clash"
        clash.mkdir()
        old_name = clash / "old.mp3"
        new_name = clash / "new.mp3"
        new_name.write_bytes(b"\x00" * 64)
        old_name.write_bytes(b"\x01" * 64)     # something new took the name
        jrn_clash = _open_journal(work, 4)
        journal.record_move("rename", old_name, new_name)
        journal.close()
        cmd_restore(_restore_args(jrn_clash, apply=True))
        check("a taken name is not overwritten",
              new_name.read_bytes() == b"\x00" * 64 and old_name.exists())

        # for tags we need a real audio file
        tag_dir = work / "tags"
        tag_dir.mkdir()
        song = tag_dir / "song.flac"
        if not _make_flac(song):
            skip("undo/tags", "ffmpeg is missing - cannot build a test file")
        else:
            write_tags(song, {"artist": "Demo Orchestra"})
            jrn_tags = _open_journal(work, 5)
            journal.record_tags(song, {"artist": "Demo Orchestra"},
                                {"artist": "Demo"})
            journal.close()
            write_tags(song, {"artist": "Demo"})
            check("the tag was changed", probe_tags(song)["artist"] == "Demo",
                  probe_tags(song)["artist"])

            check("tag undo runs",
                  cmd_restore(_restore_args(jrn_tags, apply=True)) == 0)
            check("the old tag is back",
                  probe_tags(song)["artist"] == "Demo Orchestra",
                  probe_tags(song)["artist"])

        # a failed event is reported, not hidden
        jrn_missing = _open_journal(work, 6)
        journal.record_failure("tags", "boom", path=str(tag_dir / "x.flac"))
        journal.close()
        check("a failed event is skipped",
              cmd_restore(_restore_args(jrn_missing, apply=True)) == 0
              and output.last_stats("restore").get("skipped") == 1,
              str(output.last_stats("restore")))

        check("a missing journal is an error",
              cmd_restore(_restore_args(work / "nope.jsonl")) == 2)
        check("--list runs", cmd_restore(_restore_args(None, list_journals=True)) == 0)


def test_gui() -> None:
    print("gui")
    try:
        import tkinter as tk
    except ImportError:
        check("tkinter available", False, "install tk")
        return
    try:
        root = tk.Tk()
    except tk.TclError as error:
        skip("gui/no display", str(error))
        return

    from sortiton.gui import app as gui_app
    from sortiton.gui.app import SortitonGUI
    try:
        gui = SortitonGUI(root)
        root.update()
        region = gui._content_canvas.bbox("all")
        content_overflows = (region is not None
                             and region[3] - region[1]
                             > gui._content_canvas.winfo_height() + 1)
        check("scrollbar visibility matches content overflow",
              gui._content_scrollbar.winfo_ismapped() == content_overflows)
        check("result panel keeps its configured height",
              gui._result_area.winfo_height() >= gui_app.RESULT_HEIGHT)
        previous_geometry = root.geometry()
        root.geometry("900x460")
        root.update()
        region = gui._content_canvas.bbox("all")
        if (region is not None and region[3] - region[1]
                > gui._content_canvas.winfo_height() + 1):
            gui._content_canvas.yview_moveto(1)
            root.update_idletasks()
            position = gui._content_canvas.yview()[0]
            gui._update_content_scrollbar()
            root.update_idletasks()
            check("layout refresh preserves scroll position",
                  abs(gui._content_canvas.yview()[0] - position) < 0.01)
        else:
            check("small window creates scrollable content", False)
        gui._content_canvas.yview_moveto(0)
        root.geometry(previous_geometry)
        root.update()
        for page in ("tags", "rename", "sort", "all"):
            gui._show_page(page)
            root.update()
            check(f"{page} action bar is visible",
                  gui._action_frames[page].winfo_ismapped())
        check("all pages exist",
              set(gui.pages) == {"tags", "rename", "sort", "all"},
              ", ".join(sorted(gui.pages)))
        check("content viewport exists", gui._content_canvas.winfo_exists())
        check("window icon loaded", gui._icon_large is not None)

        gui._log_line("marker-123")
        gui._language_changed("de")
        root.update()
        check("switch to de", i18n.get_language() == "de")
        check("german window title",
              root.title() == i18n.catalog("de")["gui.window.title"], root.title())
        gui._language_changed("en")
        root.update()
        check("switch to en", i18n.get_language() == "en")
        check("log survived rebuild", "marker-123" in gui._log_history
              and "marker-123" in gui.logbox.get("1.0", "end-1c"))

        # The changing action must stay locked until a preview for exactly
        # these inputs has run (wishlist: preview -> check -> write).
        check("action locked without a preview",
              not gui._execute_buttons["tags"].enabled)
        gui._plans["tags"] = {"kind": "tags", "files": 3, "changes_total": 5,
                              "fields": {"artist": {"count": 3,
                                                    "examples": [("OLD", "New")]}},
                              "examples": [], "source": "", "target": "",
                              "signature": gui._signature("tags")}
        gui._render_preview("tags")
        root.update()
        check("action unlocked by a matching preview",
              gui._execute_buttons["tags"].enabled)
        gui.var_tags_folder.set(str(Path(tempfile.gettempdir())))
        gui._refresh_preview_states()
        root.update()
        check("action locked again when an input changed",
              not gui._execute_buttons["tags"].enabled)

        check("log view is hidden by default", not gui._log_shown)
        gui._show_log_view()
        root.update()
        check("log view opens", gui._log_shown)
        gui._show_result_view()
        root.update()
        check("log view closes again", not gui._log_shown)

        # The undo window must build without a journal and must not block; the
        # restore run itself goes through the normal page machinery.
        from sortiton.gui.restore import MAX_ROWS, RestoreWindow, undo_rows, undo_summary
        window = RestoreWindow(root, lambda _path, _keep: None, gui.var_backup)
        root.update()
        check("undo window builds", bool(window.winfo_exists()))
        window.destroy()
        root.update()
        check("undo keeps its list short",
              len(undo_rows([{"op": "tags", "path": "/x/a.flac"}] * (MAX_ROWS + 2)))
              == MAX_ROWS + 1)
        check("undo summary names the count",
              "6" in undo_summary([{"op": "tags"}] * 6))
        check("restore has no page of its own", "restore" not in gui.pages)
        check("a restore signature can be built", bool(gui._signature("restore")))

        check("home is shortened", gui_app._pretty_path(Path.home() / "Musik") == "~/Musik")
        check("numbers use separators", gui_app._fmt_number(1842) == "1.842")
    finally:
        root.destroy()


def main() -> int:
    settings.apply_language()
    for test in (test_import, test_version, test_catalogs, test_rules, test_custom_rules, test_cli,
                 test_german_cli, test_external_tools, test_features_base, test_features_registry,
                 test_features_isolation, test_packages_complete, test_read_extensions,
                 test_scan,
                 test_export_fixture, test_export_golden, test_export_golden_en,
                 test_export_ffprobe_loose,
                 test_export_fingerprint, test_export_source_untouched, test_export_errors,
                 test_export_cli, test_export_cache_migration, test_export_public_api,
                 test_console_progress, test_journal, test_logs, test_screenshot_guard,
                 test_restore, test_gui):
        test()
    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    if SKIPPED:
        print(f"all checks passed ({len(SKIPPED)} skipped: {', '.join(SKIPPED)})")
        return 0
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
