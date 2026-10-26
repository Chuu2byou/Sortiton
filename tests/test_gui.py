"""Tkinter window and screenshot guard; needs a display for the window."""

from __future__ import annotations

import pytest
from sortiton.gui.mixins.layout import CONFIG_DEFAULT, CONFIG_MAX

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


@pytest.fixture
def tk_root():
    tkinter = pytest.importorskip("tkinter")
    try:
        root = tkinter.Tk()
    except tkinter.TclError as error:
        pytest.skip(f"gui/no display: {error}")
    yield root
    try:
        root.destroy()
    except tkinter.TclError:
        pass


@pytest.mark.parametrize("rc", [0, 1, 130, 99])
@pytest.mark.parametrize("applied", [False, True])
def test_gui_finish_invalidates_previews_after_every_applied_run(rc: int, applied: bool) -> None:
    """Auch Teilfehler und Abbruch eines Schreiblaufs entwerten andere Vorschauen."""
    from types import SimpleNamespace
    from typing import cast
    from unittest.mock import Mock

    from sortiton.gui.mixins.run import RunMixin

    app = SimpleNamespace(
        progress=Mock(), progress_label=Mock(), running=True, _cancel=None,
        _cancel_button=None, _job_page="tags", _job_applied=applied,
        _job_signature="current preview", _closing=False,
        _plans={"tags": {"signature": None}, "sort": {"signature": "old preview"}},
        _set_buttons=Mock(), _refresh_preview_states=Mock(), _set_state=Mock(),
        status_var=Mock())

    RunMixin._finish(cast(RunMixin, app), rc)

    check("other previews are invalidated after any applied run",
          app._plans["sort"]["signature"] == (None if applied else "old preview"))
    check("only a successful preview receives its signature",
          app._plans["tags"]["signature"]
          == ("current preview" if rc == 0 and not applied else None))
    check("the run finishes", not app.running and app._cancel is None)
    app._refresh_preview_states.assert_called_once_with()


def test_screenshot_guard() -> None:
    """The screenshot run must never store anything but the Sortiton window."""
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
def test_gui(tk_root) -> None:
    import tkinter as tk
    import unittest.mock as mock

    root = tk_root

    from sortiton.gui import app as gui_app
    from sortiton.gui.app import SortitonGUI
    from sortiton.gui.mixins import run as gui_run
    try:
        gui = SortitonGUI(root)
        root.update()
        check("clean tags starts with matching source and target",
              gui.var_tags_target.get() == gui.var_tags_folder.get())
        check("rename starts with matching source and target",
              gui.var_ren_target.get() == gui.var_ren_folder.get())
        region = gui._content_canvas.bbox("all")
        content_overflows = (region is not None
                             and region[3] - region[1]
                             > gui._content_canvas.winfo_height() + 1)
        check("scrollbar visibility matches content overflow",
              gui._content_scrollbar.winfo_ismapped() == content_overflows)
        # Die Vorschau füllt den freien Raum und wächst mit der Fensterhöhe;
        # der Ergebnisbereich öffnet sich bedarfsgerecht statt als fester Block.
        preview_before = gui._preview_area.winfo_height()
        check("preview fills the remaining window height", preview_before > 100,
              str(preview_before))
        taller = f"{root.winfo_width()}x{root.winfo_height() + 240}"
        root.geometry(taller)
        root.update()
        check("preview grows with the window height",
              gui._preview_area.winfo_height() > preview_before + 100,
              f"{preview_before} -> {gui._preview_area.winfo_height()}")
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

        gui._plans["tags"]["signature"] = gui._signature("tags")
        gui._render_preview("tags")
        root.update()
        check("action unlocked with updated signature", gui._execute_buttons["tags"].enabled)
        gui.var_tags_target.set("/custom/target")
        gui._refresh_preview_states()
        root.update()
        check("action locked when target changed", not gui._execute_buttons["tags"].enabled)

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
        rows = undo_rows([{"op": "tags", "path": "/x/a.flac"}] * (MAX_ROWS + 2))
        check("undo keeps its list short", len(rows) == MAX_ROWS + 1, str(len(rows)))
        check("the short list ends in a counter for the rest",
              rows[-1] == ("", "", "", i18n.t("gui.restore.more", count=2)),
              str(rows[-1]))
        summary = undo_summary([{"op": "tags"}] * 6)
        check("undo summary names the count",
              summary == i18n.t("gui.restore.summary", total=6,
                                parts=f"{i18n.t('gui.restore.op.tags')} 6"),
              summary)
        dedupe_rows = undo_rows([{"op": "dedupe", "source": "/x/b.mp3",
                                  "target": "/x/.duplicates/b.mp3"}])
        check("undo shows dedupe moves as moves",
              dedupe_rows[0][0] == i18n.t("gui.restore.op.move")
              and dedupe_rows[0][1] == "b.mp3", str(dedupe_rows))
        check("the undo summary understands dedupe",
              undo_summary([{"op": "dedupe"}])
              == i18n.t("gui.restore.summary", total=1,
                        parts=f"{i18n.t('gui.restore.op.move')} 1"),
              undo_summary([{"op": "dedupe"}]))
        check("restore has no page of its own", "restore" not in gui.pages)
        check("a restore signature can be built", bool(gui._signature("restore")))

        check("home is shortened", gui_app._pretty_path(Path.home() / "Musik") == "~/Musik")
        spoken = i18n.get_language()
        i18n.set_language("en")
        check("numbers use separators (en)", gui_app._fmt_number(1842) == "1,842",
              gui_app._fmt_number(1842))
        i18n.set_language("de")
        check("numbers use separators (de)", gui_app._fmt_number(1842) == "1.842",
              gui_app._fmt_number(1842))
        i18n.set_language(spoken)

        # Der Tools-Tab erzeugt ein Formular aus der Feature-Liste, hat keinen
        # Schreibknopf und startet den (nur lesenden) Export über einen Knopf.
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
        output_field = gui._tool_widgets[(export.key, "output")]
        check("export output hint shows the configured path",
              any(isinstance(child, tk.Label)
                  and config.display_path(config.EXPORT_DIR) in child.cget("text")
                  for child in output_field.master.winfo_children()))
        check("fine-tuning is not part of the tools form",
              all((feature.key, option.name) not in gui._tool_widgets
                  for feature, option in gui_tools.fine_tuning_items()))
        check("the export keeps its fine-tuning options", bool(
            [option for feature, option in gui_tools.fine_tuning_items()
             if feature.key == export.key]))
        check("tools tab has no write button", "tools" not in gui._execute_buttons)
        check("tools signature can be built", gui._signature("tools")[0] == "tools")
        dedupe = next(feature for feature in feature_list if feature.key == "dedupe")
        check("dedupe is part of the tools forms",
              (dedupe.key, "by") in gui._tool_widgets and
              (dedupe.key, "folder") in gui._tool_widgets)
        from sortiton.gui.mixins import run as gui_run

        gui._plans["tools"] = {"files": 2, "source": "/music"}
        with mock.patch.object(gui_run, "ask_confirm",
                               return_value=(True, {})) as confirm:
            check("the dedupe confirmation accepts",
                  gui._confirm_dedupe() is True)
        dedupe_text = confirm.call_args.kwargs["text"]
        check("the dedupe confirmation counts the moves",
              "2" in dedupe_text and ".duplicates" in dedupe_text, dedupe_text)

        # The fine-tuning cards live in the settings window; opening it fills
        # the same widgets registry, so the tab and the window stay in sync.
        gui._open_preferences()
        root.update()
        prefs = gui._prefs_window
        check("settings window builds",
              prefs is not None and bool(prefs.window.winfo_exists()))
        center_x = (root.winfo_rootx() + root.winfo_width() // 2)
        settings_center_x = (prefs.window.winfo_rootx()
                             + prefs.window.winfo_width() // 2)
        check("settings window is horizontally centered",
              abs(center_x - settings_center_x) <= 4,
              f"{center_x} != {settings_center_x}")
        if prefs.window.winfo_height() <= root.winfo_height():
            center_y = root.winfo_rooty() + root.winfo_height() // 2
            settings_center_y = (prefs.window.winfo_rooty()
                                 + prefs.window.winfo_height() // 2)
            check("settings window is vertically centered",
                  abs(center_y - settings_center_y) <= 4,
                  f"{center_y} != {settings_center_y}")
        check("settings has a widget per fine-tuning option",
              all((feature.key, option.name) in gui._tool_widgets
                  for feature, option in gui_tools.fine_tuning_items()),
              ", ".join(sorted(name for key, name in gui._tool_widgets
                               if key == export.key)))

        def label_texts(widget):
            for child in widget.winfo_children():
                try:
                    text = child.cget("text")
                except tk.TclError:
                    text = ""
                if text:
                    yield str(text)
                yield from label_texts(child)

        check("settings offers the track & disc formats",
              any(i18n.t("gui.settings.numbers").upper() == text
                  for text in label_texts(prefs.window)),
              i18n.t("gui.settings.numbers"))
        check("settings offers the appearance modes",
              any(i18n.t("gui.settings.theme").upper() == text
                  for text in label_texts(prefs.window)),
              i18n.t("gui.settings.theme"))
        check("the appearance starts with a valid mode",
              prefs._theme_variable.get() in settings.THEME_MODES,
              prefs._theme_variable.get())
        from sortiton.gui import design

        old_theme = settings.resolve_theme()
        old_effective_theme = design.theme()
        prefs._theme_changed("dark")
        check("the appearance selection is stored",
              settings.resolve_theme() == "dark", settings.resolve_theme())
        check("the running application changes to dark",
              design.theme() == "dark", design.theme())
        check("the rebuilt main window uses the new palette",
              gui.root.cget("bg") == design.BACKGROUND, gui.root.cget("bg"))
        check("settings remain open after a theme change",
              gui._prefs_window is not None and gui._prefs_window.window.winfo_exists())
        prefs = gui._prefs_window
        check("the new settings window reflects the selected theme",
              prefs._theme_variable.get() == "dark", prefs._theme_variable.get())
        from sortiton.gui.panels import section_label
        label_probe = section_label(prefs.window, "Theme")
        check("section labels use the current card colour",
              label_probe.cget("bg") == design._DARK["CARD"],
              label_probe.cget("bg"))
        label_probe.destroy()
        from sortiton.gui.widgets import RoundButton
        button_probe = RoundButton(gui.root, "Theme", style="normal")
        check("buttons use the current palette",
              button_probe._colours()[0] == design._DARK["FIELD"],
              button_probe._colours()[0])
        button_probe.destroy()
        gui._theme_changed(old_theme)
        prefs = gui._prefs_window
        check("the previous effective theme is restored immediately",
              design.theme() == old_effective_theme, design.theme())
        check("the track format starts with a valid mode",
              gui.var_track_format.get() in settings.TRACK_FORMATS,
              gui.var_track_format.get())
        old_format = gui.var_track_format.get()
        gui.var_track_format.set("padded")
        gui._track_format_changed("padded")
        check("the track format is stored", settings.resolve_track_format() == "padded",
              settings.resolve_track_format())
        gui.var_track_format.set(old_format)
        gui._track_format_changed(old_format)
        check("the track format can be reset",
              settings.resolve_track_format() == old_format,
              settings.resolve_track_format())

        if prefs.window.winfo_screenwidth() >= design.px(1100):
            root.update()
            check("settings start wide enough for two card columns",
                  prefs.window.winfo_width() >= design.px(900),
                  str(prefs.window.winfo_width()))
            check("settings cards use two columns on a wide window",
                  prefs._cards_wide is True, str(prefs._cards_wide))
            prefs.window.geometry("720x600")
            root.update()
            check("settings cards collapse to one column when narrowed",
                  prefs._cards_wide is False, str(prefs._cards_wide))
            prefs.window.geometry("1000x700")
            root.update()
            check("settings cards spread to two columns when widened",
                  prefs._cards_wide is True, str(prefs._cards_wide))

        prefs.window.destroy()
        root.update()
        check("settings window closes again", gui._prefs_window is None)

        # Ein schreibendes Feature (fixes) macht aus der Tools-Leiste das
        # übliche Paar Vorschau/Schreiben; der Export behält seinen einen Knopf.
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
                # 30 s genug fuer ein Fixture mit einer Handvoll Dateien; ein
                # Haenger soll nicht zwei Minuten bis zur Fehlermeldung kosten.
                deadline = time_module.monotonic() + 30
                while gui.running and time_module.monotonic() < deadline:
                    try:
                        kind, value = gui.queue.get(timeout=0.1)
                    except queue_module.Empty:
                        continue
                    gui._dispatch(kind, value)
                root.update()
                stats = output.last_stats("export")
                check("tools export run finishes", not gui.running,
                      " | ".join(gui._log_history[-3:]))
                check("tools export reports its folder",
                      stats.get("outdir") == str(outdir.resolve()), str(stats))
                check("tools export points Open folder at the report",
                      gui.last_path == outdir.resolve(), str(gui.last_path))
                check("tools export wrote a report", (outdir / "00_prompt.md").is_file())

        # Eine eingefügte LLM-Antwort wird geprüft und an den Regel-Editor
        # übergeben; my_rules.ini wird erst beim Speichern dort geschrieben.
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

        # Der zweite Import landet in einem bereits offenen Editor und fragt
        # vorher nach ("Text ersetzen?"). Ohne Nutzer wartet diese Rückfrage
        # endlos: im CI blieb der Lauf hier stehen, bis der Timeout ihn
        # abbrach. Die Antworten gibt deshalb der Test, nicht ein Dialog.
        from sortiton.gui.mixins import rules as gui_rules

        gui._llm_text.delete("1.0", "end")
        gui._llm_text.insert("1.0", "```ini\n[Genre]\nbroken\n```\n")
        with mock.patch.object(gui_rules, "_ask_yes_no", return_value=True) as confirm:
            gui._llm_rules_apply()
            root.update()
        check("llm apply asks before it replaces the editor text", confirm.called)
        # Die Warnung wird vor der Rückfrage protokolliert; erst der Vergleich
        # des Editorinhalts belegt, dass der Block wirklich übergeben wurde.
        check("llm apply reports warnings in the log",
              any("broken" in line for line in gui._log_history))
        editor_text = gui._rules_text.get("1.0", "end-1c")
        check("a confirmed import replaces the editor text",
              "broken" in editor_text and "DJ Example" not in editor_text,
              editor_text)

        gui._llm_text.delete("1.0", "end")
        gui._llm_text.insert("1.0", "```ini\n[Artist]\nOther = Artist\n```\n")
        with mock.patch.object(gui_rules, "_ask_yes_no", return_value=False):
            gui._llm_rules_apply()
            root.update()
        editor_text = gui._rules_text.get("1.0", "end-1c")
        check("a declined import keeps the editor text",
              "broken" in editor_text and "Other = Artist" not in editor_text,
              editor_text)
        check("the rules editor is never saved automatically",
              rules_file.exists() == existed)

        if gui._llm_window is not None and gui._llm_window.winfo_exists():
            gui._llm_window.destroy()
        if gui._rules_window is not None and gui._rules_window.winfo_exists():
            gui._rules_window.destroy()

        # WM_DELETE_WINDOW: a running task is cancelled, not killed mid-write.
        from sortiton.cancel import CancelToken

        check("a close handler is registered",
              bool(root.protocol("WM_DELETE_WINDOW")))
        gui.running = True
        gui._cancel = CancelToken()
        with mock.patch.object(gui_run, "_ask_yes_no", return_value=False):
            gui._on_window_close()
        check("closing is refused while the user says no",
              not gui._closing and not gui._cancel.is_set())
        with mock.patch.object(gui_run, "_ask_yes_no", return_value=True):
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


@pytest.mark.gui
def test_gui_aux_windows_follow_language(tk_root) -> None:
    """Language switch reopens Toplevels in the new language, keeping content."""
    import tkinter as tk
    import unittest.mock as mock

    from sortiton.gui.app import SortitonGUI
    import sortiton.gui.app as gui_app

    with tempfile.TemporaryDirectory() as tmp:
        root = tk_root
        gui = None
        try:
            with mock.patch.object(gui_app.config, "MUTAGEN_AVAILABLE", False):
                gui = SortitonGUI(root)
            root.update()

            # Automatic folder statistics must not start a slow ffprobe scan.
            gui.var_tags_folder.set(tmp)
            gui._refresh_folder_stats("tags", manual=False)
            check("startup statistics do not scan without mutagen",
                  gui._scan_page is None)
            check("the label asks for a manual refresh",
                  gui._stats_labels["tags"].cget("text")
                  == i18n.t("gui.stats.press_refresh"),
                  gui._stats_labels["tags"].cget("text"))

            gui._rules_editor()
            gui._set_editor_text("# keep this text\n")
            gui._llm_rules_import()
            gui._llm_text.insert("1.0", "pasted answer")
            root.update()
            gui._open_restore()
            root.update()
            check("the restore window is open", gui._restore_window is not None)
            gui._open_preferences()
            root.update()
            old_prefs = gui._prefs_window
            check("the settings window is open", old_prefs is not None)

            gui._language_changed("de")
            root.update()

            check("the rules editor uses the new language",
                  gui._rules_window is not None
                  and gui._rules_window.title() == i18n.t("gui.rules.editor.title"),
                  gui._rules_window.title() if gui._rules_window else "-")
            check("the rules text survived",
                  gui._rules_text is not None
                  and "# keep this text" in gui._rules_text.get("1.0", "end-1c"))
            check("the LLM dialog uses the new language",
                  gui._llm_window is not None
                  and gui._llm_window.title() == i18n.t("gui.llm.title"),
                  gui._llm_window.title() if gui._llm_window else "-")
            check("the pasted LLM text survived",
                  gui._llm_text is not None
                  and "pasted answer" in gui._llm_text.get("1.0", "end-1c"))
            check("the restore window uses the new language",
                  gui._restore_window is not None
                  and gui._restore_window.title() == i18n.t("gui.restore.title"),
                  gui._restore_window.title() if gui._restore_window else "-")
            check("the settings window was rebuilt with the new language",
                  gui._prefs_window is not None
                  and gui._prefs_window is not old_prefs
                  and gui._prefs_window.window.title() == i18n.t("gui.settings.title"),
                  gui._prefs_window.window.title() if gui._prefs_window else "-")
        finally:
            if getattr(gui, "_prefs_window", None) is not None:
                try:
                    gui._prefs_window.window.destroy()
                except tk.TclError:
                    pass
            for window in (getattr(gui, "_llm_window", None),
                           getattr(gui, "_rules_window", None),
                           getattr(gui, "_restore_window", None)):
                try:
                    if window is not None:
                        window.destroy()
                except tk.TclError:
                    pass
            try:
                root.destroy()
            except tk.TclError:
                pass


def test_dialog_timeout_falls_back_to_tkinter() -> None:
    """Ein hängender nativer Dialog fällt auf Tkinter zurück statt zu blockieren."""
    import subprocess
    import unittest.mock as mock

    from sortiton.gui import dialogs

    timeout = subprocess.TimeoutExpired(cmd="kdialog", timeout=1)
    with mock.patch.object(dialogs, "_command_available", return_value=True), \
            mock.patch.object(dialogs.subprocess, "run", side_effect=timeout) as run, \
            mock.patch.object(dialogs.messagebox, "askyesno", return_value=True) as fallback:
        answer = dialogs._ask_yes_no("Title", "Text")
    check("dialog timeout falls back", answer is True and fallback.called,
          f"answer={answer}, calls={run.call_count}")
    check("dialog timeout is passed to subprocess",
          run.call_count == 2 and all(call.kwargs.get("timeout") for call in run.call_args_list),
          str(run.call_args_list))


def _gui_on_size(tk_root, size: tuple[int, int]) -> tuple[object, object, bool]:
    """Fenster auf eine Größe bringen; False, wenn Screen oder WM das verhindern."""
    root = tk_root
    if (root.winfo_screenwidth() < size[0] or root.winfo_screenheight() < size[1]):
        return None, None, False
    from sortiton.gui.app import SortitonGUI
    gui = SortitonGUI(root)
    root.geometry(f"{size[0]}x{size[1]}+0+0")
    root.update()
    # Fenstermanager oder Minsize können die Wunschgröße verwerfen; dann ist
    # der Modus nicht vergleichbar und der Fall wird übersprungen.
    comparable = abs(root.winfo_width() - size[0]) <= 8
    return gui, root, comparable


@pytest.mark.gui
@pytest.mark.parametrize("size", [(1280, 720), (1920, 1080), (2560, 1440)])
def test_gui_wide_workspace(tk_root, size) -> None:
    """Breite Arbeitsfläche: zwei Spalten, volle Breite, gemeinsame Außenkanten."""
    import tkinter as tk

    gui, root, comparable = _gui_on_size(tk_root, size)
    if not comparable:
        pytest.skip(f"window cannot be sized to {size[0]}x{size[1]}")
    try:
        from sortiton.gui import design
        check(f"window {size[0]}x{size[1]} uses the wide mode",
              gui._workspace_mode == "wide",
              f"width={root.winfo_width()}, mode={gui._workspace_mode}")
        check("configuration and preview sit side by side",
              gui._config_area.winfo_ismapped()
              and gui._preview_area.winfo_ismapped()
              and gui._config_area.winfo_rootx() < gui._preview_area.winfo_rootx())
        check("the config column keeps its adjustable width",
              design.px(CONFIG_DEFAULT) <= gui._content_canvas.winfo_width()
              <= design.px(CONFIG_MAX) + 2,
              str(gui._content_canvas.winfo_width()))
        pills = gui._rules_pills
        check("active rule badges fit inside their card",
              all(child.winfo_rootx() + child.winfo_width()
                  <= pills.winfo_rootx() + pills.winfo_width() + 2
                  and child.winfo_rooty() + child.winfo_height()
                  <= pills.winfo_rooty() + pills.winfo_height() + 2
                  for child in pills.winfo_children()))
        check("the workspace spans the full window width (no 1120 px cap)",
              gui._preview_area.winfo_rootx() + gui._preview_area.winfo_width()
              >= root.winfo_rootx() + root.winfo_width() - gui._outer_inset() - 2)
        check("tabs stay visible",
              gui._tabs.winfo_ismapped())
        check("navigation uses exactly one active underline",
              len(gui._tabs.find_withtag("active-tab")) == 1)
        check("configuration is a continuous surface",
              gui.pages["tags"].cget("bg") == gui._config_area.cget("bg"))
        check("the empty result stays hidden after resizing",
              not gui._result_area.winfo_ismapped())
        check("the release bar sits in the header, right of the tabs",
              gui._actions_area.winfo_ismapped()
              and gui._tabs.winfo_rootx() + gui._tabs.winfo_width()
              <= gui._actions_area.winfo_rootx()
              and gui._actions_area.winfo_rootx() + gui._actions_area.winfo_width()
              <= gui._tabs_bar.winfo_rootx() + gui._tabs_bar.winfo_width() + 2
              and gui._actions_area.winfo_rooty()
              >= gui._tabs_bar.winfo_rooty() - 2,
              str((gui._tabs.winfo_rootx() + gui._tabs.winfo_width(),
                   gui._actions_area.winfo_rootx(),
                   gui._actions_area.winfo_width())))
        check("the release bar stays above the workspace",
              gui._actions_area.winfo_rooty() + gui._actions_area.winfo_height()
              <= gui._workspace.winfo_rooty(),
              str((gui._actions_area.winfo_rooty(),
                   gui._workspace.winfo_rooty())))
        footer_children = gui._footer.winfo_children()
        check("the footer keeps all controls inside the window",
              sum(child.winfo_reqwidth() for child in footer_children)
              <= gui._footer.winfo_width() + 2)
        check("settings sit in the footer, left of the status line",
              gui._settings_button.winfo_ismapped()
              and gui._settings_button.winfo_rooty() >= gui._workspace.winfo_rooty()
              and gui._settings_button.winfo_rootx()
              <= gui._state_dot.winfo_rootx())
        check("the progress bar stays compact on wide windows",
              gui.progress.winfo_width() <= design.px(260),
              str(gui.progress.winfo_width()))
        placed = sorted([child for child in footer_children if child.winfo_ismapped()],
                        key=lambda widget: widget.winfo_rootx())
        check("footer controls do not overlap",
              all(left.winfo_rootx() + left.winfo_width()
                  <= right.winfo_rootx()
                  for left, right in zip(placed, placed[1:])),
              str([(widget.winfo_class(), widget.winfo_rootx(),
                    widget.winfo_width()) for widget in placed]))
        check("the status group ends at the right edge",
              placed[-1].winfo_rootx() + placed[-1].winfo_width()
              >= gui._footer.winfo_rootx() + gui._footer.winfo_width() - 2,
              str(placed[-1].winfo_rootx() + placed[-1].winfo_width()))
        inset = gui._outer_inset()
        edges = {name: getattr(gui, name).winfo_rootx() - root.winfo_rootx()
                 for name in ("_tabs_bar", "_workspace", "_footer")}
        check("tabs, workspace and footer share the outer edges",
              all(edge == inset for edge in edges.values()), str(edges))
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


@pytest.mark.gui
def test_gui_config_column_starts_at_max_width(tk_root) -> None:
    """Die Konfigurationsleiste startet immer in ihrer maximalen Breite."""
    import tkinter as tk

    from sortiton.gui import design

    gui, root, comparable = _gui_on_size(tk_root, (1280, 720))
    if not comparable or gui._workspace_mode != "wide":
        pytest.skip("window too small for the two-column layout")
    try:
        width = gui._content_canvas.winfo_width()
        check("start width equals the maximum width", CONFIG_DEFAULT == CONFIG_MAX,
              f"default={CONFIG_DEFAULT}, max={CONFIG_MAX}")
        check("the config column starts at its maximum width",
              abs(width - design.px(CONFIG_MAX)) <= 2, str(width))
        gui._content_canvas.configure(width=design.px(CONFIG_MAX - 120))
        gui._sync_content_width()
        root.update()
        check("the handle stays usable below the maximum",
              gui._content_canvas.winfo_width() < design.px(CONFIG_MAX))
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


@pytest.mark.gui
def test_gui_rule_chips_have_vertical_padding(tk_root) -> None:
    """Regel-Chips: fester Innenabstand oben/unten, Punkt als glattes Textzeichen."""
    import tkinter as tk

    from sortiton.gui import design
    from sortiton.gui.app import SortitonGUI

    gui = SortitonGUI(tk_root)
    tk_root.update()
    try:
        pill = next(child for child in gui._rules_pills.winfo_children()
                    if type(child).__name__ == "Pill")
        line = pill._font.metrics("linespace")
        check("the chip keeps its padding above and below the text",
              pill.winfo_reqheight() >= line + 2 * design.px(6) - 1,
              f"height={pill.winfo_reqheight()}, linespace={line}")
        kinds = [pill.type(item) for item in pill.find_all()]
        check("the status dot is text, so it is drawn smooth",
              kinds.count("text") == 2, str(kinds))
        check("the chip surface stays one polygon",
              kinds.count("polygon") == 1, str(kinds))
    finally:
        try:
            tk_root.destroy()
        except tk.TclError:
            pass


@pytest.mark.gui
def test_gui_buttons_keep_their_vertical_padding(tk_root) -> None:
    """Knöpfe wachsen mit der Schrift, statt die Beschriftung einzuklemmen."""
    import tkinter as tk

    from sortiton.gui import design
    from sortiton.gui.app import SortitonGUI

    gui = SortitonGUI(tk_root)
    tk_root.update()
    try:
        button = next(child for child in gui._footer.winfo_children()
                      if type(child).__name__ == "RoundButton")
        line = button._font.metrics("linespace")
        check("buttons keep padding above and below the label",
              button.winfo_reqheight() >= line + 2 * design.px(7) - 1,
              f"height={button.winfo_reqheight()}, linespace={line}")
        check("buttons keep their side padding",
              button.winfo_reqwidth()
              >= button._font.measure(button._text) + 2 * design.px(15) - 1,
              str(button.winfo_reqwidth()))
    finally:
        try:
            tk_root.destroy()
        except tk.TclError:
            pass


@pytest.mark.gui
@pytest.mark.parametrize("size", [(1100, 780), (820, 660)])
def test_gui_narrow_workspace(tk_root, size) -> None:
    """Schmales Fenster: Konfiguration eingeklappt bzw. oberhalb, ohne Scrollen."""
    import tkinter as tk

    gui, root, comparable = _gui_on_size(tk_root, size)
    if not comparable:
        pytest.skip(f"window cannot be sized to {size[0]}x{size[1]}")
    try:
        from sortiton.gui import design
        from sortiton.gui.mixins.layout import CONTENT_CAP, MID_MIN
        check(f"window {size[0]}x{size[1]} leaves the wide mode",
              gui._workspace_mode != "wide",
              f"width={root.winfo_width()}, mode={gui._workspace_mode}")
        if root.winfo_width() >= design.px(MID_MIN):
            check("the middle width offers the collapse toggle",
                  gui._workspace_mode == "mid" and gui._config_toggle is not None)
            gui._toggle_config()
            root.update()
            check("the collapsed config frees the full width",
                  not gui._config_area.winfo_ismapped()
                  and gui._preview_area.winfo_ismapped()
                  and gui._preview_area.winfo_width()
                  >= gui._workspace.winfo_width() - 2)
        else:
            check("the narrow width stacks the config above the preview",
                  gui._workspace_mode == "narrow"
                  and gui._config_area.winfo_ismapped()
                  and gui._preview_area.winfo_ismapped()
                  and gui._config_area.winfo_rooty() < gui._preview_area.winfo_rooty())
            check("narrow reading texts keep their length cap",
                  int(gui._content_canvas.itemcget(gui._content_window, "width"))
                  <= design.px(CONTENT_CAP) + 2,
                  gui._content_canvas.itemcget(gui._content_window, "width"))
        check("nothing extends past the window (no horizontal scrolling)",
              gui._workspace.winfo_rootx() + gui._workspace.winfo_width()
              <= root.winfo_rootx() + root.winfo_width() + 2)
        footer = gui._footer
        check("the footer fits the narrow window without overlapping",
              all(widget.winfo_rootx() + widget.winfo_width()
                  <= footer.winfo_rootx() + footer.winfo_width() + 2
                  for widget in footer.winfo_children()
                  if widget.winfo_ismapped()),
              str([(widget.winfo_class(), widget.winfo_rootx(),
                    widget.winfo_width())
                   for widget in footer.winfo_children()
                   if widget.winfo_ismapped()]))
        check("tabs stay visible on narrow windows",
              gui._tabs.winfo_ismapped()
              and gui._tabs.winfo_rootx() + gui._tabs.winfo_width()
              <= root.winfo_rootx() + root.winfo_width())
        check("header actions stay inside the narrow window",
              gui._actions_area.winfo_ismapped()
              and gui._actions_area.winfo_rootx() + gui._actions_area.winfo_width()
              <= root.winfo_rootx() + root.winfo_width())
        check("settings stay fully visible on narrow windows",
              gui._settings_button.winfo_rootx() + gui._settings_button.winfo_width()
              <= root.winfo_rootx() + root.winfo_width())
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def _inside_column(widget, limit: int) -> list[tuple[str, int, int]]:
    """Alle sichtbaren Kinder, die über die rechte Kante hinausragen."""
    outside: list[tuple[str, int, int]] = []
    for child in widget.winfo_children():
        if not child.winfo_ismapped():
            continue
        right = child.winfo_rootx() + child.winfo_width()
        if right > limit:
            outside.append((child.winfo_class(), child.winfo_rootx(), child.winfo_width()))
        outside += _inside_column(child, limit)
    return outside


@pytest.mark.gui
def test_gui_tools_tab_fits_the_config_column(tk_root) -> None:
    """Werkzeug-Reiter: Umschalter, Badge und Knopfreihe bleiben in der Spalte."""
    import tkinter as tk

    from sortiton.gui import design
    from sortiton.gui.app import SortitonGUI
    from sortiton.gui.mixins.layout import CONFIG_MAX, CONFIG_MIN

    gui = SortitonGUI(tk_root)
    tk_root.update()
    app = gui
    try:
        app._show_page("tools")
        tab = next(child for child in app.pages["tools"].winfo_children()
                   if type(child).__name__ == "ToolsTab")
        for key in list(tab._forms):
            tab._show(key)
            for logical in (CONFIG_MIN, 420, CONFIG_MAX):
                app._content_canvas.configure(width=design.px(logical))
                app._sync_content_width()
                tk_root.update()
                canvas = app._content_canvas
                limit = canvas.winfo_rootx() + canvas.winfo_width() + 2
                outside = _inside_column(tab, limit)
                check(f"{key} fits the {logical} px column",
                      not outside, str(outside))
        pill = tab._badge
        if pill is not None:
            fills = [pill.itemcget(item, "fill") for item in pill.find_all()
                     if pill.type(item) == "polygon"]
            check("the status chip carries a tinted surface",
                  bool(fills) and fills[0] != design.CARD, str(fills))
            check("the status chip is drawn without spline fragments",
                  len(fills) == 1, str(fills))
    finally:
        try:
            tk_root.destroy()
        except tk.TclError:
            pass
