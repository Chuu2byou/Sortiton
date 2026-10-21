"""Tkinter window and screenshot guard; needs a display for the window."""

from __future__ import annotations

import pytest

from _support import (
    BASE,
    Path,
    _load_export_helper,
    _png_header,
    check,
    config,
    i18n,
    importlib,
    output,
    settings,
    skip,
    tempfile,
)


@pytest.fixture(autouse=True)
def _restore_gui_globals():
    """The window installs global output hooks; later tests get the old ones."""
    saved = (output._sink, output._progress_sink, output._plan_sink,
             output._stats_sink, i18n.get_language())
    yield
    output.set_logger(saved[0])
    output.set_progress(saved[1])
    output.set_plan_sink(saved[2])
    output.set_stats_sink(saved[3])
    i18n.set_language(saved[4])


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


@pytest.mark.gui
def test_gui() -> None:
    print("gui")
    try:
        import tkinter as tk
    except ImportError:
        pytest.skip("tkinter not installed")
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"gui/no display: {error}")

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
              gui._result_area.winfo_height() >= gui._result_height)
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
        for page in ("tags", "rename", "sort", "all", "tools"):
            gui._show_page(page)
            root.update()
            check(f"{page} action bar is visible",
                  gui._action_frames[page].winfo_ismapped())
        check("all pages exist",
              set(gui.pages) == {"tags", "rename", "sort", "all", "tools"},
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

        # Step 3.2: the tools tab generates a form from the feature list, has no
        # write button and runs the (read-only) export from a single button.
        from sortiton import external
        from sortiton.features import FEATURES as feature_list
        from sortiton.gui import tools as gui_tools
        export = feature_list[0]
        form_options = [option for _section, options in gui_tools.form_sections(export)
                        for option in options]
        check("tools form has a widget per run option",
              all((export.key, option.name) in gui._tool_widgets
                  for option in form_options),
              ", ".join(sorted(name for key, name in gui._tool_widgets if key == export.key)))
        check("fine-tuning is not part of the tools form",
              all((feature.key, option.name) not in gui._tool_widgets
                  for feature, option in gui_tools.fine_tuning_items()))
        check("the export keeps its fine-tuning options", bool(
            [option for feature, option in gui_tools.fine_tuning_items()
             if feature.key == export.key]))
        check("tools tab has no write button", "tools" not in gui._execute_buttons)
        check("tools signature can be built", gui._signature("tools")[0] == "tools")

        # The fine-tuning cards live in the settings window; opening it fills
        # the same widgets registry, so the tab and the window stay in sync.
        gui._open_preferences()
        root.update()
        prefs = gui._prefs_window
        check("settings window builds",
              prefs is not None and bool(prefs.window.winfo_exists()))
        check("settings has a widget per fine-tuning option",
              all((feature.key, option.name) in gui._tool_widgets
                  for feature, option in gui_tools.fine_tuning_items()),
              ", ".join(sorted(name for key, name in gui._tool_widgets
                               if key == export.key)))
        prefs.window.destroy()
        root.update()
        check("settings window closes again", gui._prefs_window is None)

        # Step 3.4: a writing feature (fixes) turns the tools bar into the
        # normal preview/write pair; the export keeps its single button.
        fixes_key = next(feature.key for feature in feature_list if feature.writes)
        gui.var_tool_choice.set(fixes_key)
        gui._tools_actions()
        root.update()
        check("a writing tool gets a write button", "tools" in gui._execute_buttons)
        check("the write button waits for a preview",
              not gui._execute_buttons["tools"].enabled)
        gui.var_tool_choice.set(export.key)
        gui._tools_actions()
        root.update()
        check("switching back to a read-only tool removes the write button",
              "tools" not in gui._execute_buttons)

        gui.var_tool[export.key]["examples"].set("7")
        gui._language_changed("de")
        root.update()
        check("language switch keeps tool input",
              gui.var_tool[export.key]["examples"].get() == "7",
              gui.var_tool[export.key]["examples"].get())
        gui._language_changed("en")
        root.update()
        check("tools form is rebuilt after a language switch",
              (export.key, "folder") in gui._tool_widgets)

        # Fine-tuning is stored in settings.ini (temp file in this run) and
        # seeds a fresh variable table again - that is the restart path.
        gui._save_fine_tuning()
        stored = settings.read_tool_values()
        check("fine-tuning is stored in settings.ini",
              stored.get(f"{export.key}.examples") == "7", str(stored))
        fresh = gui_tools.make_tool_vars()
        gui_tools.apply_stored(fresh)
        check("settings.ini seeds the fine-tuning",
              fresh[export.key]["examples"].get() == "7",
              fresh[export.key]["examples"].get())
        gui.var_tool[export.key]["examples"].set("40")
        gui._save_fine_tuning()
        check("fine-tuning resets cleanly",
              settings.read_tool_values().get(f"{export.key}.examples") == "40")

        fixture = _load_export_helper().FIXTURE_DIR
        if not fixture.is_dir():
            skip("tools export run", "fixture missing")
        elif not (external.available(external.MUTAGEN) or external.available(external.FFPROBE)):
            skip("tools export run", "mutagen and ffprobe missing")
        else:
            import queue as queue_module
            import time as time_module
            with tempfile.TemporaryDirectory() as tmp:
                outdir = Path(tmp) / "export"
                gui.var_tool[export.key]["folder"].set(str(fixture))
                gui.var_tool[export.key]["output"].set(str(outdir))
                gui.var_tool[export.key]["chunk_chars"].set("1500")
                gui._run_tools()
                deadline = time_module.monotonic() + 120
                while gui.running and time_module.monotonic() < deadline:
                    try:
                        kind, value = gui.queue.get(timeout=0.1)
                    except queue_module.Empty:
                        continue
                    gui._dispatch(kind, value)
                root.update()
                stats = output.last_stats("export")
                check("tools export run finishes", not gui.running)
                check("tools export reports its folder",
                      stats.get("outdir") == str(outdir.resolve()), str(stats))
                check("tools export points Open folder at the report",
                      gui.last_path == outdir.resolve(), str(gui.last_path))
                check("tools export wrote a report", (outdir / "00_prompt.md").is_file())

        # Step 3.3: a pasted LLM answer is checked and handed to the rules
        # editor; my_rules.ini is only written when the user presses Save there.
        rules_file = config.RULES_FILE
        existed = rules_file.exists()
        gui._llm_rules_import()
        root.update()
        check("llm paste dialog builds",
              gui._llm_window is not None and bool(gui._llm_window.winfo_exists()))
        gui._llm_text.delete("1.0", "end")
        gui._llm_text.insert(
            "1.0", "Sure:\n\n```ini\n[Artist]\nDJ Example = Example DJ\n```\n")
        gui._llm_rules_apply()
        root.update()
        check("llm apply opens the pre-filled rules editor",
              gui._rules_text is not None
              and "DJ Example = Example DJ" in gui._rules_text.get("1.0", "end-1c"))
        check("llm apply never saves on its own", rules_file.exists() == existed)

        gui._llm_text.delete("1.0", "end")
        gui._llm_text.insert("1.0", "```ini\n[Genre]\nbroken\n```\n")
        gui._llm_rules_apply()
        root.update()
        check("llm apply reports warnings in the log",
              any("broken" in line for line in gui._log_history))

        if gui._llm_window is not None and gui._llm_window.winfo_exists():
            gui._llm_window.destroy()
        if gui._rules_window is not None and gui._rules_window.winfo_exists():
            gui._rules_window.destroy()

        # WM_DELETE_WINDOW: a running task is cancelled, not killed mid-write.
        from sortiton.cancel import CancelToken
        import unittest.mock as mock

        check("a close handler is registered",
              bool(root.protocol("WM_DELETE_WINDOW")))
        gui.running = True
        gui._cancel = CancelToken()
        with mock.patch.object(gui_app, "_ask_yes_no", return_value=False):
            gui._on_window_close()
        check("closing is refused while the user says no",
              not gui._closing and not gui._cancel.is_set())
        with mock.patch.object(gui_app, "_ask_yes_no", return_value=True):
            gui._on_window_close()
        check("closing cancels a running task",
              gui._closing and gui._cancel.is_set())
        check("the window waits for the task to stop",
              bool(root.winfo_exists()) and gui.running)

        # Now the task ends: _finish destroys the window only afterwards.
        def window_alive() -> bool:
            try:
                return bool(root.winfo_exists())
            except tk.TclError:
                return False

        gui._finish(130)
        try:
            root.update()
        except tk.TclError:
            pass
        check("the window is destroyed once the task stopped", not window_alive())
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
