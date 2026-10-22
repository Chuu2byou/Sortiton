#!/usr/bin/env python3
"""Smoke test for the Sortiton (no extra packages required).

Covers the public interface, both translation catalogs, the cleaning rules, the
custom rules, the CLI and the GUI. Without a display the GUI part is skipped.

Run:  python3 tests/smoke.py
"""

from __future__ import annotations

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
                 test_german_cli, test_scan, test_journal, test_logs,
                 test_screenshot_guard, test_restore, test_gui):
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
