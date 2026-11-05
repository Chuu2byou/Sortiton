"""The five pages and the form elements they consist of.

A page follows the same description as the CLI (``core_features``); the
window, its header and the workspace live in
:mod:`sortiton.gui.mixins.layout`.
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk

from ...core_features import CORE_FEATURES, core_feature
from ...features import get as feature_by_key
from .. import design
from .. import translations as i18n
from ..design import (ACCENT, BACKGROUND, BORDER, CARD, FIELD, TEXT, TEXT_FAINT,
                      TEXT_MUTED)
from ..dialogs import _pick_file, _pick_folder
from ..panels import PreviewCard, section_label
from ..tools import ToolsTab, feature_run_label
from ..widgets import RoundButton, Segments, fit_wraplength
from .base import GuiBase


class FillPreviewCard(PreviewCard):
    """Vorschaukarte, die den freien Raum der rechten Spalte ausfüllt.

    Der Inhalt bleibt oben verankert, die Karte wächst mit der Fensterhöhe.
    """

    def __init__(self, parent: tk.Misc, title: str) -> None:
        super().__init__(parent, title)
        children = self.winfo_children()
        inner = children[0] if children else None
        if inner is not None:
            # Innenrahmen und Tabellenkörper dürfen die volle Höhe nutzen.
            inner.grid_configure(sticky="nsew")
            inner.grid_rowconfigure(1, weight=1)
            self.grid_rowconfigure(0, weight=1)
        if getattr(self, "_body", None) is not None:
            self._body.grid_configure(sticky="nsew")


class PageMixin(GuiBase):
    """Pages with their header, cards, fields and action bars."""

    # Created by the window build (:class:`LayoutMixin`), only extended here.
    action_buttons: list[RoundButton]

    def _reset_pages(self) -> None:
        """Clear the page registries before the pages are rebuilt."""
        self.action_buttons = []
        self._tools_buttons = []
        self._execute_buttons = {}
        self._action_frames = {}
        self._preview_notes = {}
        self._previews = {}
        self._stats_labels = {}
        self._tool_widgets = {}
        self._active_page = None
        self._preview_blank = None
        self._content = None
        self._content_height = 0
        self._actions_size_retry = False

    def _new_page(self, parent: tk.Frame) -> tk.Frame:
        page = tk.Frame(parent, bg=CARD)
        page.columnconfigure(0, weight=1)
        return page

    def _page_header(self, page: tk.Frame, row: int, title: str, hint: str) -> None:
        """Kompakter Seitentitel über dem Auftrag."""
        header = tk.Frame(page, bg=CARD)
        header.grid(row=row, column=0, sticky="ew", padx=design.px(16),
                    pady=(design.px(16), design.px(24)))
        header.columnconfigure(0, weight=1)
        i18n.Label(header, text=title, bg=CARD, fg=TEXT,
                 font=design.FONT_TITLE, anchor="w").grid(row=0, column=0, sticky="w")

    def _core_page(self, parent: tk.Frame, key: str) -> tk.Frame:
        """Eine Kernseite anhand derselben Beschreibung wie die CLI aufbauen."""
        feature = core_feature(key)
        page = self._new_page(parent)
        self._page_header(page, 0, i18n.t(f"gui.tab.{key}"), i18n.t(f"gui.hint.{key}"))
        self._folder_card(page, 1, key, [
            (i18n.t("gui.label.source_folder"), getattr(self, feature.source_var)),
            (i18n.t("gui.label.target_folder"), getattr(self, feature.target_var)),
        ])
        options = self._card(page, 2, i18n.t("gui.section.options"))
        if feature.pattern_var:
            self._pattern_row(options, 0, getattr(self, feature.pattern_var))
        self._mode_row(options, 2 if feature.pattern_var else 0,
                       getattr(self, feature.mode_var))
        if feature.show_pattern_hint:
            self._hint(options, 4, i18n.t("gui.hint.rename_placeholders"))
        if feature.show_rules:
            self._rules_card(page, 3)
        self._preview_card(page, 4 if feature.show_rules else 3, key)
        run = getattr(self, feature.run_method)
        self._actions(key, preview=lambda: run(False), execute=lambda: run(True),
                      execute_text=i18n.t(feature.execute_key))
        return page

    def _page_tags(self, parent: tk.Frame) -> tk.Frame:
        return self._core_page(parent, "tags")

    def _page_rename(self, parent: tk.Frame) -> tk.Frame:
        return self._core_page(parent, "rename")

    def _page_sort(self, parent: tk.Frame) -> tk.Frame:
        return self._core_page(parent, "sort")

    def _page_all(self, parent: tk.Frame) -> tk.Frame:
        return self._core_page(parent, "all")

    def _page_tools(self, parent: tk.Frame) -> tk.Frame:
        """Tools tab: one form per registered feature, with a matching action bar."""
        page = self._new_page(parent)
        self._page_header(page, 0, i18n.t("gui.tab.tools"), i18n.t("gui.hint.tools"))
        tools_view = ToolsTab(self, page)
        tools_view.grid(row=1, column=0, sticky="nsew")
        self._preview_card(page, 2, "tools")
        self._tools_actions()
        return page

    def _tools_actions(self) -> None:
        """Rebuild the tools action bar for the selected feature."""
        old = self._action_frames.pop("tools", None)
        if old is not None:
            for button in self._tools_buttons:
                if button in self.action_buttons:
                    self.action_buttons.remove(button)
            old.destroy()
        self._tools_buttons = []
        self._execute_buttons.pop("tools", None)
        self._preview_notes.pop("tools", None)

        feature = feature_by_key(self.var_tool_choice.get())
        before = len(self.action_buttons)
        if feature is not None and feature.writes:
            self._actions("tools", preview=lambda: self._run_tools(False),
                          execute=lambda: self._run_tools(True),
                          execute_text=feature_run_label(feature))
        else:
            self._actions_single("tools", lambda: self._run_tools(False),
                                 feature_run_label(feature),
                                 note=i18n.t("gui.tools.readonly_note"))
        self._tools_buttons = self.action_buttons[before:]

        card = self._previews.get("tools")
        if self.var_page.get() == "tools":
            shown = card if feature is not None and feature.writes else self._preview_blank
            if shown is not None:
                shown.tkraise()
        # Die neu erzeugte Reihe liegt durch das Grid oben; die aktive Seite
        # muss sie deshalb wieder überdecken, auch wenn die Werkzeuge nicht
        # sichtbar sind.
        active = self._action_frames.get(self.var_page.get())
        if active is not None:
            active.tkraise()
        self._size_actions_area()
        self._render_preview("tools")
        self.root.after_idle(self._fit_top_bar)
        self.root.after_idle(self._refresh_content_layout)

    def _card(self, parent: tk.Frame, row: int, title: str = "") -> tk.Frame:
        """Ungefasster Formularabschnitt auf der gemeinsamen Arbeitsfläche."""
        outer = tk.Frame(parent, bg=CARD, highlightthickness=0, bd=0)
        outer.grid(row=row, column=0, sticky="ew", pady=(0, design.px(24)))
        outer.columnconfigure(0, weight=1)
        inner = tk.Frame(outer, bg=CARD)
        inner.grid(row=0, column=0, sticky="ew", padx=design.px(16))
        inner.columnconfigure(0, weight=1)
        if not title:
            return inner
        section_label(inner, title).grid(row=0, column=0, sticky="w")
        body = tk.Frame(inner, bg=CARD)
        body.grid(row=1, column=0, sticky="ew", pady=(design.px(12), 0))
        body.columnconfigure(0, weight=1)
        return body

    def _folder_card(self, page: tk.Frame, row: int, key: str,
                     rows: list[tuple[str, tk.StringVar]]) -> None:
        """Folder card: path fields, picker, refresh and the statistics."""
        body = self._card(page, row, i18n.t("gui.section.folders"))
        for index, (label, variable) in enumerate(rows):
            self._folder_row(body, index * 3, label, variable)

        footer = tk.Frame(body, bg=CARD)
        footer.grid(row=len(rows) * 3, column=0, sticky="ew", pady=(design.px(10), 0))
        footer.columnconfigure(0, weight=1)
        stats = i18n.Label(footer, text=i18n.t("gui.stats.unknown"), bg=CARD, fg=TEXT_MUTED,
                         font=design.FONT_SMALL, anchor="w")
        stats.grid(row=0, column=0, sticky="w")
        self._stats_labels[key] = stats
        RoundButton(footer, i18n.t("gui.button.refresh"),
                    lambda: self._refresh_folder_stats(key), style="quiet",
                    height=30).grid(row=0, column=1, sticky="e")

    def _path_entry(self, parent: tk.Misc, variable: tk.StringVar) -> tk.Entry:
        """The dark input field used for folders and for patterns.

        ``width=1`` hält die angeforderte Breite klein: das Feld füllt über
        ``sticky="ew"`` die Zelle und schrumpft in schmalen Spalten mit, statt
        den Knopf daneben aus dem Panel zu schieben.
        """
        return tk.Entry(parent, textvariable=variable, bg=FIELD, fg=TEXT,
                        insertbackground=TEXT, relief="flat", bd=0, width=1,
                        highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=ACCENT, font=design.FONT)

    def _folder_row(self, card: tk.Frame, row: int, label: str,
                    variable: tk.StringVar) -> tk.Entry:
        """Label + path field + folder picker; returns the path field."""
        i18n.Label(card, text=label, bg=CARD, fg=TEXT_MUTED, font=design.FONT_SMALL).grid(
            row=row, column=0, sticky="w",
            pady=(0 if row == 0 else design.px(12), design.px(5)))
        line = tk.Frame(card, bg=CARD)
        line.grid(row=row + 1, column=0, sticky="ew")
        line.columnconfigure(0, weight=1)

        entry = self._path_entry(line, variable)
        entry.grid(row=0, column=0, sticky="ew", ipady=design.px(7))
        RoundButton(line, i18n.t("gui.button.choose_folder"),
                    lambda: self._choose_folder(variable),
                    style="normal").grid(row=0, column=1, padx=(design.px(10), 0))
        return entry

    def _rules_card(self, page: tk.Frame, row: int) -> None:
        """Which rules are active - read from the file, not written as prose."""
        body = self._card(page, row, i18n.t("gui.section.active_rules"))
        self._rules_pills = tk.Frame(body, bg=CARD)
        self._rules_pills.grid(row=0, column=0, sticky="ew")
        self._rules_pills.bind("<Configure>", self._layout_rule_pills, add="+")
        RoundButton(body, i18n.t("gui.button.custom_rules"), self._rules_editor,
                    style="normal", height=30).grid(
                        row=1, column=0, sticky="e", pady=(design.px(8), 0))
        self._refresh_rules_card()

    def _preview_card(self, _page: tk.Frame, _row: int, key: str) -> None:
        """Vorschaukarte der rechten Spalte; Titel kennzeichnet die Zusammenfassung."""
        card = FillPreviewCard(self._preview_area,
                               i18n.t("gui.section.preview_summary"))
        card.grid(row=0, column=0, sticky="nsew")
        self._previews[key] = card

    def _pattern_row(self, card: tk.Frame, row: int, variable: tk.StringVar) -> None:
        """Label + pattern field (e.g. %artist% - %title%)."""
        i18n.Label(card, text=i18n.t("gui.label.pattern"), bg=CARD, fg=TEXT_MUTED,
                 font=design.FONT_SMALL).grid(row=row, column=0, sticky="w",
                                              pady=(0, design.px(5)))
        self._path_entry(card, variable).grid(row=row + 1, column=0, sticky="ew",
                                              ipady=design.px(7))

    def _mode_row(self, card: tk.Frame, row: int, variable: tk.StringVar) -> None:
        """Label + copy/move switch."""
        i18n.Label(card, text=i18n.t("gui.label.mode"), bg=CARD, fg=TEXT_MUTED,
                 font=design.FONT_SMALL).grid(row=row, column=0, sticky="w",
                                              pady=(design.px(12), design.px(5)))
        Segments(card, [("copy", i18n.t("gui.mode.copy")), ("move", i18n.t("gui.mode.move"))],
                 variable, height=36, surface=FIELD).grid(row=row + 1, column=0, sticky="w")

    def _hint(self, card: tk.Frame, row: int, text: str) -> None:
        label = i18n.Label(card, text=text, bg=CARD, fg=TEXT_MUTED, font=design.FONT_SMALL,
                         justify="left", anchor="w", wraplength=design.px(660))
        label.grid(row=row, column=0, sticky="w", pady=(design.px(8), 0))
        card.bind("<Configure>",
                  lambda event: fit_wraplength(
                      label, event.width - design.px(4), minimum=160),
                  add="+")

    def _choose_folder(self, variable: tk.StringVar) -> None:
        feature = next((item for item in CORE_FEATURES
                        if getattr(self, item.target_var, None) is variable), None)
        source = (getattr(self, feature.source_var).get().strip() if feature else "")
        start = variable.get().strip()
        fallback = Path(source).expanduser().parent if source else Path.home()
        start_dir = Path(start).expanduser() if start else fallback
        if not start_dir.is_dir():
            start_dir = fallback if fallback.is_dir() else Path.home()
        chosen = _pick_folder(start_dir)
        if chosen and (not source or self._target_outside_source(source, chosen)):
            variable.set(chosen)

    def _choose_file(self, variable: tk.StringVar) -> None:
        """Pick a file (the CSV of the fixes feature) instead of typing it."""
        start = variable.get().strip()
        candidate = Path(start).expanduser() if start else Path.home()
        start_dir = candidate.parent if candidate.suffix else candidate
        if not start_dir.is_dir():
            start_dir = Path.home()
        chosen = _pick_file(start_dir, i18n.t("gui.button.choose_file"))
        if chosen:
            variable.set(chosen)

    def _actions(self, key: str, preview, execute, execute_text: str) -> None:
        """Preview as the primary action, the changing one clearly separated."""
        frame = tk.Frame(self._actions_area, bg=BACKGROUND)
        frame.grid(row=0, column=0, sticky="w")
        self._action_frames[key] = frame

        first = RoundButton(frame, i18n.t("gui.button.preview_create"), preview,
                            style="primary")
        first.pack(side="left")
        second = RoundButton(frame, execute_text, execute, style="apply")
        second.pack(side="left", padx=(design.px(10), 0))

        note = i18n.Label(frame, text="", bg=BACKGROUND, fg=TEXT_FAINT,
                        font=design.FONT_SMALL)
        note.pack(side="left", padx=(design.px(14), 0))

        self.action_buttons.extend([first, second])
        self._execute_buttons[key] = second
        self._preview_notes[key] = note

    def _actions_single(self, key: str, run, text: str, note: str = "") -> None:
        """Action bar with a single button - for a page without preview/write."""
        frame = tk.Frame(self._actions_area, bg=BACKGROUND)
        frame.grid(row=0, column=0, sticky="w")
        self._action_frames[key] = frame

        button = RoundButton(frame, text, run, style="primary")
        button.pack(side="left")
        self.action_buttons.append(button)
        if note:
            i18n.Label(frame, text=note, bg=BACKGROUND, fg=TEXT_FAINT,
                     font=design.FONT_SMALL).pack(side="left",
                                                  padx=(design.px(14), 0))
