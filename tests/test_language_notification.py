"""Gezielte Tests für den Sprachwechsel ohne Fensterneubau."""

import gc
import tkinter as tk
import unittest
import weakref
from unittest.mock import patch
from types import SimpleNamespace

import pytest

from sortiton import i18n
from sortiton.gui import translations
from sortiton.gui.app import SortitonGUI
from sortiton.gui.widgets import RoundButton, Segments
from sortiton.gui.tools import OptionForm


@pytest.mark.gui
class LanguageNotificationTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"gui/no display: {error}")
        self.language = i18n.get_language()
        i18n.set_language("en")
        self.root.withdraw()
        self.patches = [
            patch("sortiton.gui.mixins.settings.settings.save_language"),
            patch("sortiton.gui.app.SortitonGUI._log_rules"),
            patch("sortiton.gui.app.SortitonGUI._refresh_folder_stats"),
            patch("sortiton.gui.app.SortitonGUI._queue_pump"),
            patch("sortiton.gui.restore.journal.find_journals", return_value=[]),
        ]
        for item in self.patches:
            item.start()
        self.gui = SortitonGUI(self.root)
        self.root.update()

    def tearDown(self):
        for job in self.root.tk.call("after", "info"):
            self.root.after_cancel(job)
        self.root.destroy()
        for item in reversed(self.patches):
            item.stop()
        i18n.set_language(self.language)

    def test_fenster_und_eingaben_bleiben_erhalten(self):
        gui = self.gui
        gui._rules_editor()
        gui._llm_rules_import()
        gui._open_restore()
        gui._open_preferences()
        self.root.update()
        windows = (gui._rules_window, gui._llm_window, gui._restore_window,
                   gui._prefs_window, gui.pages["tags"])
        editor = gui._rules_text
        editor.delete("1.0", "end")
        editor.insert("1.0", "nicht gespeicherter Text")
        editor.mark_set("insert", "1.5")
        editor.tag_add("sel", "1.1", "1.4")
        gui._llm_text.insert("1.0", "Eingabe")
        gui.var_page.set("tools")
        gui._show_page("tools")
        plan = {"signature": None}
        gui._plans["tags"] = plan
        tabs = gui._tabs
        trace_count = len(gui.var_page.trace_info())
        gui._prefs_window.window.geometry("720x520+30+40")
        self.root.update()
        geometry = gui._prefs_window.window.geometry()
        gui._language_changed("de")
        self.root.update()
        self.assertEqual(windows, (gui._rules_window, gui._llm_window, gui._restore_window,
                                   gui._prefs_window, gui.pages["tags"]))
        self.assertIs(gui._plans["tags"], plan)
        self.assertEqual(gui.var_page.get(), "tools")
        self.assertEqual(editor.get("1.0", "end-1c"), "nicht gespeicherter Text")
        self.assertEqual(editor.index("insert"), "1.5")
        self.assertEqual((editor.index("sel.first"), editor.index("sel.last")), ("1.1", "1.4"))
        self.assertEqual(gui._llm_text.get("1.0", "end-1c"), "Eingabe")
        self.assertEqual(gui._prefs_window.window.title(), i18n.t("gui.settings.title"))
        self.assertEqual(gui._prefs_window.window.geometry(), geometry)
        self.assertEqual(gui._rules_window.title(), i18n.t("gui.rules.editor.title"))
        self.assertEqual(dict(tabs._items)["tags"], i18n.t("gui.tab.tags"))
        self.assertEqual(gui._settings_button._text, "⚙  " + i18n.t("gui.button.settings"))
        self.assertEqual(len(gui.var_page.trace_info()), trace_count)
        gui._language_changed("en")
        self.assertEqual(dict(tabs._items)["tags"], i18n.t("gui.tab.tags"))

    def test_benachrichtigung_meldet_zerstoerte_widgets_ab(self):
        gc.collect()
        before = len(translations._listeners)
        label = translations.Label(self.root, text=translations.t("gui.button.close"))
        button = RoundButton(self.root, translations.t("gui.button.close"))
        variable = tk.StringVar(master=self.root, value="a")
        segments = Segments(self.root, [("a", translations.t("gui.mode.copy"))], variable)
        self.assertEqual(len(translations._listeners), before + 3)
        refs = [weakref.ref(widget) for widget in (label, button, segments)]
        label.destroy()
        button.destroy()
        segments.destroy()
        del label, button, segments
        gc.collect()
        self.assertTrue(all(ref() is None for ref in refs))
        self.assertEqual(len(translations._listeners), before)
        self.gui._language_changed("de")
        self.assertFalse(variable.trace_info())

    def test_statistik_und_ergebnis_bleiben_erhalten_und_werden_uebersetzt(self):
        gui = self.gui
        gui._show_folder_stats("tags", {"files": 1234, "albums": 2, "artists": 3})
        gui._render_stats("all", {"tags_changed": 1234})
        gui.status_var.set(translations.t("gui.status.failed", rc=7))
        gui._show_log_view()
        gui._log_line("Done.")
        label = gui._stats_labels["tags"]
        counters = gui.result_panel._counters
        number = next(child for child in counters.winfo_children()
                      if isinstance(child, tk.Label) and child.cget("text") == "1,234")
        gui._language_changed("de")
        self.assertIs(gui._stats_labels["tags"], label)
        self.assertIn("1.234", label.cget("text"))
        self.assertEqual(number.cget("text"), "1.234")
        self.assertEqual(gui.status_var.get(), i18n.t("gui.status.failed", rc=7))
        self.assertIn("Done.", gui.logbox.get("1.0", "end-1c"))
        gui._language_changed("en")
        self.assertEqual(number.cget("text"), "1,234")
        self.assertEqual(gui.status_var.get(), i18n.t("gui.status.failed", rc=7))

    def test_einstellungen_mehrfach_oeffnen_und_schliessen(self):
        traces = len(self.gui.var_language.trace_info())
        for language in ("de", "en", "de"):
            self.gui._open_preferences()
            self.root.update()
            prefs = self.gui._prefs_window
            registered = [widget for widget in translations._listeners
                          if widget._root() is self.root
                          and widget.winfo_toplevel() is prefs.window]
            self.assertTrue(registered)
            self.gui._language_changed(language)
            prefs.window.destroy()
            self.root.update()
            self.assertIsNone(self.gui._prefs_window)
            remaining = [widget for widget in registered if widget in translations._listeners]
            self.assertEqual(remaining, [])
        self.assertEqual(len(self.gui.var_language.trace_info()), traces)

    def test_auswahlliste_aktualisiert_text_und_zuordnung(self):
        option = SimpleNamespace(name="report_lang", choices=("", "en", "de"))
        variable = tk.StringVar(master=self.root, value="en")
        box = OptionForm(self.gui)._choice_input(self.root, option, variable)
        box.grid(row=999, column=0)
        self.root.deiconify()
        self.root.update()
        self.gui._language_changed("de")
        self.assertEqual(box.get(), "Englisch")
        self.assertEqual(tuple(box.cget("values")), ("Wie die Oberfläche", "Englisch", "Deutsch"))
        box.current(2)
        box.event_generate("<<ComboboxSelected>>")
        self.root.update()
        self.assertEqual(variable.get(), "de")
        self.gui._language_changed("en")
        self.assertEqual(box.get(), "German")
        box.destroy()
        self.assertFalse(variable.trace_info())

    def test_beschaeftigt_verhindert_sprachwechsel(self):
        self.gui.running = True
        self.gui.var_language.set("de")
        with patch("sortiton.gui.mixins.settings._show_warning") as warning:
            self.gui._language_changed("de")
        warning.assert_called_once()
        self.assertEqual(i18n.get_language(), "en")
        self.assertEqual(self.gui.var_language.get(), "en")


if __name__ == "__main__":
    unittest.main()
