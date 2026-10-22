"""Window layout, tabs, pages and their small widgets."""

from __future__ import annotations

from ..common import (
    ACCENT,
    ACCENT_TEXT,
    BACKGROUND,
    BORDER,
    CARD,
    CONTENT_MAX_WIDTH,
    FIELD,
    FIELD_ACTIVE,
    LOG_BG,
    Path,
    PreviewCard,
    ROW_ACTIONS,
    ROW_CONTENT,
    ROW_LINE_TOP,
    ROW_RESULT,
    ROW_TABS,
    RoundButton,
    SCROLLBAR,
    SCROLLBAR_ACTIVE,
    Segments,
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    ToolsTab,
    _pick_file,
    _pick_folder,
    config,
    design,
    feature_by_key,
    feature_run_label,
    i18n,
    section_label,
    tk,
    ttk,
)
from .base import GuiBase


class LayoutMixin(GuiBase):
    """Window layout, tabs, pages and their small widgets."""

    def _content_inset(self) -> int:
        """Left/right inset that lines the fixed rows up with the form column."""
        base = design.px(22)
        width = self.root.winfo_width()
        spare = max(width - 2 * base - design.px(13) - design.px(CONTENT_MAX_WIDTH), 0)
        return base + spare // 2

    def _align_fixed_rows(self, event=None) -> None:
        """Give tabs, action bar, result and footer the same centred column."""
        if event is not None and event.widget is not self.root:
            return
        frames = getattr(self, "_fixed_rows", [])
        if not frames:
            return
        inset = self._content_inset()
        if inset == getattr(self, "_last_inset", None):
            return
        self._last_inset = inset
        for frame in frames:
            try:
                frame.grid_configure(padx=inset)
            except tk.TclError:
                pass

    def _build_all(self) -> None:
        """Build (or rebuild) the whole window - used for the language switch."""
        for variable, identifier in self._traces:
            try:
                variable.trace_remove("write", identifier)
            except (tk.TclError, ValueError):
                pass
        self._traces = []
        prefs = self._prefs_window
        self._prefs_window = None
        if prefs is not None:
            try:
                prefs.window.destroy()
            except tk.TclError:
                pass
        for child in list(self.root.winfo_children()):
            if isinstance(child, tk.Toplevel):
                continue
            child.destroy()
        self.action_buttons = []
        self._tools_buttons = []
        self._execute_buttons = {}
        self._action_frames = {}
        self._preview_notes = {}
        self._previews = {}
        self._stats_labels = {}
        self._tool_widgets = {}
        self._last_inset = None
        self._build_window(keep_geometry=self._placed)
        self._placed = True
        self._set_style()
        self._load_icon()
        self._build_tabs()
        self._bind_shortcuts()
        self._build_result_area()
        self._build_footer()
        self._fixed_rows = [self._tabs_bar, self._actions_area, self._result_area,
                            self._footer]
        self._align_fixed_rows()
        self._watch_inputs()
        self._show_page(self.var_page.get())
        self._replay_log()
        self._show_result_view()
        for page in self.pages:
            self._render_preview(page)
        self.status_var.set(i18n.t("gui.status.running") if self.running
                            else i18n.t("gui.status.ready"))
        self._rebuild_aux_windows()

    def _rebuild_aux_windows(self) -> None:
        """Reopen auxiliary windows so they use the newly selected language."""
        rules_open = False
        rules_text = ""
        if self._rules_window is not None:
            try:
                rules_open = bool(self._rules_window.winfo_exists())
                if rules_open and self._rules_text is not None:
                    rules_text = self._rules_text.get("1.0", "end-1c")
            except tk.TclError:
                rules_open = False
            try:
                self._rules_window.destroy()
            except tk.TclError:
                pass
            self._rules_window = None
            self._rules_text = None
            self._rules_status = None
            self._rules_status_label = None
        if rules_open:
            self._rules_editor(prefill=rules_text, restored=True)

        llm_open = False
        llm_text = ""
        if self._llm_window is not None:
            try:
                llm_open = bool(self._llm_window.winfo_exists())
                if llm_open and self._llm_text is not None:
                    llm_text = self._llm_text.get("1.0", "end-1c")
            except tk.TclError:
                llm_open = False
            try:
                self._llm_window.destroy()
            except tk.TclError:
                pass
            self._llm_window = None
            self._llm_text = None
            self._llm_status = None
            self._llm_status_label = None
        if llm_open:
            self._llm_rules_import()
            if self._llm_text is not None and llm_text:
                self._llm_text.insert("1.0", llm_text)

        restore_window = self._restore_window
        if restore_window is not None:
            chosen = getattr(restore_window, "_chosen", None)
            try:
                restore_open = bool(restore_window.winfo_exists())
            except tk.TclError:
                restore_open = False
            if restore_open:
                try:
                    restore_window.destroy()
                except tk.TclError:
                    pass
                self._restore_window = None
                self._open_restore(preselect=chosen)

    def _build_window(self, keep_geometry: bool = False) -> None:
        """Set up the root window."""
        self.root.title(i18n.t("gui.window.title"))
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        if not keep_geometry:
            width = max(min(design.px(1080), int(screen_width * 0.88),
                            screen_width - design.px(24)), design.px(640))
            height = max(min(design.px(920), int(screen_height * 0.88),
                             screen_height - design.px(24)), design.px(420))
            x = max((screen_width - width) // 2, 0)
            y = max((screen_height - height) // 2, 0)
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(min(design.px(680), screen_width - design.px(24)),
                          min(design.px(460), screen_height - design.px(48)))
        self.root.configure(bg=BACKGROUND)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(ROW_CONTENT, weight=1)
        self.root.rowconfigure(ROW_RESULT, weight=0, minsize=self._result_height)

    def _apply_minsize(self) -> None:
        """Never let the tabs or the settings button get clipped."""
        bar = getattr(self, "_tabs_bar", None)
        tabs = getattr(self, "_tabs", None)
        settings = getattr(self, "_settings_button", None)
        if bar is None or tabs is None:
            return
        needed = tabs.winfo_reqwidth() + design.px(44)
        if settings is not None:
            needed += settings.winfo_reqwidth() + design.px(12)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = min(max(design.px(680), needed), screen_width - design.px(24))
        self.root.minsize(width, min(design.px(460), screen_height - design.px(48)))

    def _set_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        for orientation in ("Vertical", "Horizontal"):
            name = f"Dark.{orientation}.TScrollbar"
            style.configure(name, gripcount=0, width=design.px(13),
                            background=SCROLLBAR, darkcolor=SCROLLBAR,
                            lightcolor=SCROLLBAR, troughcolor=LOG_BG, bordercolor=LOG_BG,
                            arrowcolor=TEXT_MUTED, arrowsize=design.px(15))
            style.map(name, background=[("active", SCROLLBAR_ACTIVE)])
        style.configure("TCombobox", fieldbackground=FIELD, background=FIELD,
                        foreground=TEXT, arrowcolor=TEXT_MUTED, bordercolor=BORDER,
                        lightcolor=FIELD, darkcolor=FIELD, padding=design.px(5),
                        arrowsize=design.px(15))
        style.map("TCombobox",
                  fieldbackground=[("readonly", FIELD)],
                  foreground=[("readonly", TEXT), ("disabled", TEXT_MUTED)],
                  background=[("readonly", FIELD), ("active", FIELD_ACTIVE)],
                  selectbackground=[("readonly", FIELD)],
                  selectforeground=[("readonly", TEXT)])
        self.root.option_add("*TCombobox*Listbox.background", FIELD)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", ACCENT_TEXT)
        self.root.option_add("*TCombobox*Listbox.font", design.FONT)

    def _load_icon(self) -> None:
        """Load the window icon (assets/icon.png, else keep the Tk default)."""
        path = config.ASSETS_DIR / "icon.png"
        if not path.is_file():
            return
        try:
            self._icon_large = tk.PhotoImage(file=str(path))
            self.root.iconphoto(True, self._icon_large)
        except tk.TclError:
            self._icon_large = None

    def _build_tabs(self) -> None:
        bar = tk.Frame(self.root, bg=BACKGROUND)
        bar.grid(row=ROW_TABS, column=0, sticky="ew", padx=design.px(22),
                 pady=(design.px(16), 0))
        bar.columnconfigure(0, weight=1)
        self._tabs_bar = bar
        tabs = Segments(bar,
                        [("tags", i18n.t("gui.tab.tags")), ("rename", i18n.t("gui.tab.rename")),
                         ("sort", i18n.t("gui.tab.sort")), ("all", i18n.t("gui.tab.all")),
                         ("tools", i18n.t("gui.tab.tools"))],
                        self.var_page, command=self._show_page, height=42, stretch=True)
        tabs.grid(row=0, column=0, sticky="ew")
        self._tabs = tabs
        self._settings_button = RoundButton(bar, "⚙  " + i18n.t("gui.button.settings"),
                                            self._open_preferences, style="normal",
                                            height=36)
        self._settings_button.grid(row=0, column=1, sticky="e", padx=(design.px(12), 0))
        self._apply_minsize()

        tk.Frame(self.root, bg=BORDER, height=1).grid(row=ROW_LINE_TOP, column=0,
                                                      sticky="ew", pady=(design.px(14), 0))

        viewport = tk.Frame(self.root, bg=BACKGROUND)
        viewport.grid(row=ROW_CONTENT, column=0, sticky="nsew", padx=design.px(22),
                      pady=(design.px(14), design.px(4)))
        viewport.columnconfigure(0, weight=1)
        viewport.rowconfigure(0, weight=1)
        canvas = tk.Canvas(viewport, bg=BACKGROUND, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=canvas.yview,
                                  style="Dark.Vertical.TScrollbar")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        content = tk.Frame(canvas, bg=BACKGROUND)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")
        self._content_scrollbar = scrollbar
        content.bind("<Configure>", lambda _event: self._update_content_scrollbar())
        canvas.bind("<Configure>", lambda event: self._resize_content_canvas(
            event, content_window))
        self._content_canvas = canvas
        self.root.bind_all("<MouseWheel>", self._scroll_content)
        self.root.bind_all("<Button-4>", self._scroll_content)
        self.root.bind_all("<Button-5>", self._scroll_content)

        self._actions_area = tk.Frame(self.root, bg=BACKGROUND)
        self._actions_area.grid(row=ROW_ACTIONS, column=0, sticky="ew", padx=design.px(22),
                                pady=(0, design.px(6)))
        self._actions_area.columnconfigure(0, weight=1)

        self.pages = {
            "tags":   self._page_tags(content),
            "rename": self._page_rename(content),
            "sort":   self._page_sort(content),
            "all":    self._page_all(content),
            "tools":  self._page_tools(content),
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")
        self._show_page(self.var_page.get())

    def _bind_shortcuts(self) -> None:
        """Ctrl+1 … Ctrl+5 pick a page, right where the tabs are."""
        for index, page in enumerate(("tags", "rename", "sort", "all", "tools"), start=1):
            self.root.bind(f"<Control-Key-{index}>",
                           lambda _event, name=page: self._show_page(name))

    def _resize_content_canvas(self, event, content_window: int) -> None:
        """Fill the viewport up to a readable width and centre the content."""
        width = min(event.width, design.px(1120))
        self._content_canvas.itemconfigure(content_window, width=width)
        self._content_canvas.coords(content_window, max((event.width - width) // 2, 0), 0)
        self.root.after_idle(self._update_content_scrollbar)

    def _update_content_scrollbar(self) -> None:
        """Show a scrollbar only when the active page exceeds the viewport."""
        canvas = self._content_canvas
        region = canvas.bbox("all")
        if region is None:
            return
        canvas.configure(scrollregion=region)
        content_height = region[3] - region[1]
        if content_height > canvas.winfo_height() + 1:
            self._content_scrollbar.grid(row=0, column=1, sticky="ns")
        else:
            self._content_scrollbar.grid_remove()

    def _show_page(self, value: str) -> None:
        self.var_page.set(value)
        for name, page in self.pages.items():
            if name == value:
                page.grid()
            else:
                page.grid_remove()
        for name, frame in self._action_frames.items():
            if name == value:
                frame.grid()
            else:
                frame.grid_remove()
        canvas = getattr(self, "_content_canvas", None)
        if canvas is not None:
            canvas.yview_moveto(0)
            self.root.after_idle(self._update_content_scrollbar)

    def _scroll_content(self, event) -> str | None:
        """Scroll the central viewport only while the pointer is over it."""
        canvas = self._content_canvas
        x, y = event.x_root, event.y_root
        if not (canvas.winfo_rootx() <= x < canvas.winfo_rootx() + canvas.winfo_width()
                and canvas.winfo_rooty() <= y < canvas.winfo_rooty() + canvas.winfo_height()):
            return None
        number = getattr(event, "num", None)
        if number == 4:
            amount = -1
        elif number == 5:
            amount = 1
        else:
            amount = -1 if getattr(event, "delta", 0) > 0 else 1
        canvas.yview_scroll(amount, "units")
        return "break"

    def _new_page(self, parent: tk.Frame) -> tk.Frame:
        page = tk.Frame(parent, bg=BACKGROUND)
        page.columnconfigure(0, weight=1)
        return page

    def _page_header(self, page: tk.Frame, row: int, title: str, hint: str) -> None:
        """Big page title plus one sentence: what this page does."""
        header = tk.Frame(page, bg=BACKGROUND)
        header.grid(row=row, column=0, sticky="ew", pady=(0, design.px(16)))
        header.columnconfigure(0, weight=1)
        tk.Label(header, text=title, bg=BACKGROUND, fg=TEXT,
                 font=design.FONT_TITLE, anchor="w").grid(row=0, column=0, sticky="w")
        hint_label = tk.Label(header, text=hint, bg=BACKGROUND, fg=TEXT_MUTED,
                              font=design.FONT, anchor="w", justify="left",
                              wraplength=design.px(880))
        hint_label.grid(row=1, column=0, sticky="w", pady=(design.px(4), 0))
        header.bind("<Configure>",
                    lambda event: hint_label.configure(
                        wraplength=max(event.width - design.px(4), design.px(200))))

    def _page_tags(self, parent: tk.Frame) -> tk.Frame:
        """Folder -> active rules -> preview -> actions."""
        page = self._new_page(parent)
        self._page_header(page, 0, i18n.t("gui.tab.tags"), i18n.t("gui.hint.tags"))
        self._folder_card(page, 1, "tags", [(i18n.t("gui.label.source_folder"),
                                             self.var_tags_folder),
                                            (i18n.t("gui.label.target_folder"),
                                             self.var_tags_target)])
        options = self._card(page, 2, i18n.t("gui.section.options"))
        self._mode_row(options, 0, self.var_tags_mode)
        self._rules_card(page, 3)
        self._preview_card(page, 4, "tags")
        self._actions("tags", preview=lambda: self._run_tags(False),
                      execute=lambda: self._run_tags(True),
                      execute_text=i18n.t("gui.button.write_tags"))
        return page

    def _page_rename(self, parent: tk.Frame) -> tk.Frame:
        page = self._new_page(parent)
        self._page_header(page, 0, i18n.t("gui.tab.rename"), i18n.t("gui.hint.rename"))
        self._folder_card(page, 1, "rename", [(i18n.t("gui.label.source_folder"),
                                               self.var_ren_folder),
                                              (i18n.t("gui.label.target_folder"),
                                               self.var_ren_target)])
        options = self._card(page, 2, i18n.t("gui.section.options"))
        self._pattern_row(options, 0, self.var_ren_pattern)
        self._mode_row(options, 2, self.var_ren_mode)
        self._hint(options, 4, i18n.t("gui.hint.rename_placeholders"))
        self._preview_card(page, 3, "rename")
        self._actions("rename", preview=lambda: self._run_rename(False),
                      execute=lambda: self._run_rename(True),
                      execute_text=i18n.t("gui.button.rename"))
        return page

    def _page_sort(self, parent: tk.Frame) -> tk.Frame:
        page = self._new_page(parent)
        self._page_header(page, 0, i18n.t("gui.tab.sort"), i18n.t("gui.hint.sort"))
        self._folder_card(page, 1, "sort", [(i18n.t("gui.label.source_folder"),
                                             self.var_source),
                                            (i18n.t("gui.label.target_folder"),
                                             self.var_target)])
        options = self._card(page, 2, i18n.t("gui.section.options"))
        self._pattern_row(options, 0, self.var_sort_pattern)
        self._mode_row(options, 2, self.var_sort_mode)
        self._preview_card(page, 3, "sort")
        self._actions("sort", preview=lambda: self._run_sort(False),
                      execute=lambda: self._run_sort(True),
                      execute_text=i18n.t("gui.button.sort"))
        return page

    def _page_all(self, parent: tk.Frame) -> tk.Frame:
        page = self._new_page(parent)
        self._page_header(page, 0, i18n.t("gui.tab.all"), i18n.t("gui.hint.all"))
        self._folder_card(page, 1, "all", [(i18n.t("gui.label.source_folder"),
                                            self.var_all_source),
                                           (i18n.t("gui.label.target_folder"),
                                            self.var_all_target)])
        options = self._card(page, 2, i18n.t("gui.section.options"))
        self._pattern_row(options, 0, self.var_all_pattern)
        self._mode_row(options, 2, self.var_all_mode)
        self._preview_card(page, 3, "all")
        self._actions("all", preview=lambda: self._run_all(False),
                      execute=lambda: self._run_all(True),
                      execute_text=i18n.t("gui.button.run_all"))
        return page

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
        if card is not None:
            if feature is not None and feature.writes:
                card.grid()
            else:
                card.grid_remove()
        if self.var_page.get() == "tools":
            self._action_frames["tools"].grid()
        self._render_preview("tools")

    def _card(self, parent: tk.Frame, row: int, title: str = "") -> tk.Frame:
        """Panel with a subtle border and an optional section title."""
        outer = tk.Frame(parent, bg=CARD, highlightthickness=1,
                         highlightbackground=BORDER, bd=0)
        outer.grid(row=row, column=0, sticky="ew", pady=(0, design.px(14)))
        outer.columnconfigure(0, weight=1)
        inner = tk.Frame(outer, bg=CARD)
        inner.grid(row=0, column=0, sticky="ew", padx=design.px(18),
                   pady=design.px(15))
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
        stats = tk.Label(footer, text=i18n.t("gui.stats.unknown"), bg=CARD, fg=TEXT_MUTED,
                         font=design.FONT_SMALL, anchor="w")
        stats.grid(row=0, column=0, sticky="w")
        self._stats_labels[key] = stats
        RoundButton(footer, i18n.t("gui.button.refresh"),
                    lambda: self._refresh_folder_stats(key), style="quiet",
                    height=30).grid(row=0, column=1, sticky="e")

    def _path_entry(self, parent: tk.Misc, variable: tk.StringVar) -> tk.Entry:
        """The dark input field used for folders and for patterns."""
        return tk.Entry(parent, textvariable=variable, bg=FIELD, fg=TEXT,
                        insertbackground=TEXT, relief="flat", bd=0,
                        highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=ACCENT, font=design.FONT)

    def _folder_row(self, card: tk.Frame, row: int, label: str,
                    variable: tk.StringVar) -> tk.Entry:
        """Label + path field + folder picker; returns the path field."""
        tk.Label(card, text=label, bg=CARD, fg=TEXT_MUTED, font=design.FONT_SMALL).grid(
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
        line = tk.Frame(body, bg=CARD)
        line.grid(row=0, column=0, sticky="ew")
        line.columnconfigure(0, weight=1)

        self._rules_pills = tk.Frame(line, bg=CARD)
        self._rules_pills.grid(row=0, column=0, sticky="w")
        RoundButton(line, i18n.t("gui.button.custom_rules"), self._rules_editor,
                    style="normal", height=30).grid(row=0, column=1, sticky="e")
        self._refresh_rules_card()

    def _preview_card(self, page: tk.Frame, row: int, key: str) -> None:
        card = PreviewCard(page, i18n.t("gui.section.preview"))
        card.grid(row=row, column=0, sticky="ew", pady=(0, design.px(14)))
        self._previews[key] = card

    def _pattern_row(self, card: tk.Frame, row: int, variable: tk.StringVar) -> None:
        """Label + pattern field (e.g. %artist% - %title%)."""
        tk.Label(card, text=i18n.t("gui.label.pattern"), bg=CARD, fg=TEXT_MUTED,
                 font=design.FONT_SMALL).grid(row=row, column=0, sticky="w",
                                              pady=(0, design.px(5)))
        self._path_entry(card, variable).grid(row=row + 1, column=0, sticky="ew",
                                              ipady=design.px(7))

    def _mode_row(self, card: tk.Frame, row: int, variable: tk.StringVar) -> None:
        """Label + copy/move switch."""
        tk.Label(card, text=i18n.t("gui.label.mode"), bg=CARD, fg=TEXT_MUTED,
                 font=design.FONT_SMALL).grid(row=row, column=0, sticky="w",
                                              pady=(design.px(12), design.px(5)))
        Segments(card, [("copy", i18n.t("gui.mode.copy")), ("move", i18n.t("gui.mode.move"))],
                 variable, height=36, surface=FIELD).grid(row=row + 1, column=0, sticky="w")

    def _hint(self, card: tk.Frame, row: int, text: str) -> None:
        label = tk.Label(card, text=text, bg=CARD, fg=TEXT_MUTED, font=design.FONT_SMALL,
                         justify="left", anchor="w", wraplength=design.px(660))
        label.grid(row=row, column=0, sticky="w", pady=(design.px(8), 0))
        card.bind("<Configure>",
                  lambda event: label.configure(
                      wraplength=max(event.width - design.px(4), design.px(160))),
                  add="+")

    def _choose_folder(self, variable: tk.StringVar) -> None:
        start = variable.get().strip()
        start_dir = Path(start).expanduser() if start else Path.home()
        if not start_dir.is_dir():
            start_dir = Path.home()
        chosen = _pick_folder(start_dir)
        if chosen:
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

        note = tk.Label(frame, text="", bg=BACKGROUND, fg=TEXT_FAINT,
                        font=design.FONT_SMALL)
        note.pack(side="left", padx=(design.px(14), 0))

        self.action_buttons += [first, second]
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
            tk.Label(frame, text=note, bg=BACKGROUND, fg=TEXT_FAINT,
                     font=design.FONT_SMALL).pack(side="left",
                                                  padx=(design.px(14), 0))
