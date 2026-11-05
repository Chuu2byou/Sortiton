"""Window, header and the shared workspace.

:mod:`.pages` builds the pages and their form elements; this mixin only knows
the frame around them.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ... import config
from .. import translations as i18n
from ...features import get as feature_by_key
from .. import design
from ..common import ROW_CONTENT, ROW_LINE_TOP, ROW_TABS
from ..design import (ACCENT, ACCENT_TEXT, BACKGROUND, BORDER, CARD, FIELD,
                      FIELD_ACTIVE, LOG_BG, SCROLLBAR, SCROLLBAR_ACTIVE,
                      TEXT, TEXT_MUTED)
from ..widgets import RoundButton, Segments
from .pages import PageMixin

# Arbeitsbereich: Zwei Spalten ab 1200 logischen Pixeln, einklappbare
# Konfiguration zwischen 900 und 1199, darunter Konfiguration über der Vorschau.
WIDE_MIN = 1200
MID_MIN = 900
CONFIG_MIN = 320       # kleinste Breite (Anwender verkleinert per Griff)
CONFIG_MAX = 560       # größte sinnvolle Formularbreite
# Startbreite: die Konfigurationsleiste beginnt immer in Maximalbreite.
CONFIG_DEFAULT = CONFIG_MAX
CONTENT_CAP = 720      # Maximalbreite für Lesetexte/Eingaben im Stapelmodus
SCROLLBAR_WIDTH = 13   # Platz der vertikalen Scrollbar, auch ohne Überlauf


class LayoutMixin(PageMixin):
    """Main window frame: header, workspace and page switching."""


    def _outer_inset(self) -> int:
        """Der gemeinsame Außenabstand: Formular, Kopf und Fuß teilen die Kanten."""
        return design.px(design.SPACE_XL)

    def _align_fixed_rows(self, event=None) -> None:
        """Gleiche Außenkanten für Kopfzeile, Ergebnis und Fuß; passt zudem den
        Arbeitsbereich (Zwei-Spalten/Stapel-Modus) an die Fensterbreite an."""
        if event is not None and event.widget is not self.root:
            return
        inset = self._outer_inset()
        for frame in getattr(self, "_fixed_rows", []):
            try:
                if frame.winfo_manager() == "grid":
                    frame.grid_configure(padx=inset)
            except tk.TclError:
                pass
        self._apply_workspace_mode()

    def _build_all(self) -> None:
        """Fenster beim Start oder beim Wechsel des Erscheinungsbilds aufbauen."""
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
        self._reset_pages()
        self._workspace_mode = None
        self._config_collapsed = False
        self._config_toggle = None
        # Referenzen aus dem vorherigen Aufbau entsorgen, damit Zwischenrufe
        # wie _apply_minsize nicht auf bereits zerstörte Widgets zugreifen.
        self._tabs_bar = None
        self._footer = None
        self._result_area = None
        self._build_window(keep_geometry=self._placed)
        self._placed = True
        self._set_style()
        self._load_icon()
        self._build_tabs()
        self._bind_shortcuts()
        self._build_result_area()
        self._build_footer()
        self._fixed_rows = [self._tabs_bar, self._result_area, self._footer]
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
        i18n.bind_title(self.root, i18n.t("gui.window.title"))
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
        if not keep_geometry:
            try:
                self.root.attributes("-zoomed", True)
            except tk.TclError:
                try:
                    self.root.state("zoomed")
                except tk.TclError:
                    pass
        self.root.configure(bg=BACKGROUND)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(ROW_CONTENT, weight=1)

    def _apply_minsize(self) -> None:
        """Mindestbreite: Tabs plus Freigabe oben, Status plus Fußzeile unten."""
        bar = getattr(self, "_tabs_bar", None)
        tabs = getattr(self, "_tabs", None)
        if bar is None or tabs is None:
            return
        needs = tabs.winfo_reqwidth() + design.px(44)
        # Kopfzeile: Tabs links, Freigabe rechts (der Hinweis weicht zuerst).
        actions_area = getattr(self, "_actions_area", None)
        if actions_area is not None:
            # Für die Mindestbreite zählt die breiteste Knopfreihe ohne den
            # erklärenden Hinweis; der darf bei Platzmangel weichen. Dadurch
            # bleibt die Mindestbreite beim Tabwechsel stabil.
            widths = []
            for key, frame in getattr(self, "_action_frames", {}).items():
                try:
                    width = frame.winfo_reqwidth()
                except tk.TclError:
                    continue
                note = self._preview_notes.get(key)
                if note is not None and note.winfo_manager() == "pack":
                    width -= note.winfo_reqwidth() + design.px(14)
                widths.append(width)
            actions_needed = max(widths, default=actions_area.winfo_reqwidth())
            needs += max(actions_needed, 1) + design.px(12)
        needed = needs
        # Fußzeile: Einstellungen, Status und Schnellzugriffe müssen zusammenpassen.
        # Für die Mindestbreite zählen nur die unverzichtbaren Teile; die
        # Schnellzugriffe weichen bei schmalen Fenstern (siehe _fit_footer).
        footer = getattr(self, "_footer", None)
        if footer is not None:
            try:
                quick = {getattr(self, "_footer_undo", None),
                         getattr(self, "_footer_logs", None)}
                cancel = getattr(self, "_cancel_button", None)
                footer_needed = 0
                for child in footer.winfo_children():
                    if child in quick or (child is cancel
                                          and not child.winfo_manager()):
                        continue
                    footer_needed += child.winfo_reqwidth()
                footer_needed += design.px(60)  # Abstände der Basisspalten
                # Die Fußzeile liegt beidseitig um den Außenabstand eingerückt.
                needed = max(needed, footer_needed + 2 * self._outer_inset())
            except tk.TclError:
                pass  # Fußzeile beim Neuaufbau noch nicht vorhanden
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = min(max(design.px(680), needed), screen_width - design.px(24))
        self.root.minsize(width, min(design.px(460), screen_height - design.px(48)))

    def _fit_top_bar(self, event=None) -> None:
        """Hinweis neben der Freigabe ausblenden, wenn die Kopfzeile eng wird.

        Tabs und die beiden Aktionsknöpfe bleiben immer sichtbar; nur die
        erklärende Zeile daneben weicht, sobald der Platz nicht reicht.
        """
        bar = getattr(self, "_tabs_bar", None)
        actions = getattr(self, "_actions_area", None)
        tabs = getattr(self, "_tabs", None)
        if bar is None or actions is None or tabs is None:
            return
        width = bar.winfo_width()
        if width <= 1:
            return
        note = self._preview_notes.get(self.var_page.get())
        if note is None:
            # Nur-Lese-Werkzeuge haben keinen Hinweis; die Fläche muss trotzdem
            # auf die aktive Knopfreihe zugeschnitten werden.
            self._size_actions_area()
            return
        note_width = note.winfo_reqwidth() + design.px(14)
        packed = note.winfo_manager() == "pack"
        base = actions.winfo_reqwidth() - (note_width if packed else 0)
        needed = tabs.winfo_reqwidth() + base + design.px(2 * design.SPACE_L)
        if packed and needed + note_width > width:
            note.pack_forget()
        elif not packed and needed + note_width <= width:
            note.pack(side="left", padx=(design.px(14), 0))
        self._size_actions_area()

    def _size_actions_area(self) -> None:
        """Aktionsfläche auf die Knopfreihe der sichtbaren Seite zuschneiden.

        Alle Knopfreihen bleiben dauerhaft gemappt und liegen übereinander.
        Die Fläche bekommt trotzdem nur die Größe der aktiven Reihe, damit die
        Kopfzeile nicht dauerhaft den Platz der breitesten Reihe reserviert.
        """
        area = getattr(self, "_actions_area", None)
        if area is None:
            return
        frame = self._action_frames.get(self.var_page.get())
        if frame is None:
            return
        try:
            width = max(frame.winfo_reqwidth(), 1)
            height = max(frame.winfo_reqheight(), 1)
        except tk.TclError:
            return
        if width <= 1 or height <= 1:
            # Eine gerade erst erzeugte Reihe hat ihre angeforderte Größe noch
            # nicht; Tk berechnet sie erst im nächsten Idle-Lauf.
            if not getattr(self, "_actions_size_retry", False):
                self._actions_size_retry = True
                self.root.after_idle(self._retry_actions_size)
            return
        self._actions_size_retry = False
        if (area.winfo_reqwidth(), area.winfo_reqheight()) == (width, height):
            return
        area.configure(width=width, height=height)
        self._apply_minsize()

    def _retry_actions_size(self) -> None:
        """Zweiter Versuch, sobald Tk die Größe einer neuen Knopfreihe kennt."""
        self._actions_size_retry = False
        self._fit_top_bar()

    def _set_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        for orientation in ("Vertical", "Horizontal"):
            name = f"Dark.{orientation}.TScrollbar"
            style.configure(name, gripcount=0, width=design.px(SCROLLBAR_WIDTH),
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
        """Header, workspace and pages in the order the window shows them."""
        self._build_top_bar()
        tk.Frame(self.root, bg=BORDER, height=1).grid(row=ROW_LINE_TOP, column=0,
                                                      sticky="ew", pady=(design.px(14), 0))
        workspace = self._build_workspace()
        content = self._build_config_pane(workspace)
        self._build_split_handle(workspace)
        self._build_preview_pane(workspace)
        self._build_pages(content)
        self._align_fixed_rows()

    def _build_top_bar(self) -> None:
        """Header: the tabs on the left, preview/apply on the right."""
        bar = tk.Frame(self.root, bg=BACKGROUND)
        bar.grid(row=ROW_TABS, column=0, sticky="ew", padx=self._outer_inset(),
                 pady=(design.px(design.SPACE_L), 0))
        bar.columnconfigure(2, weight=1)
        self._tabs_bar = bar
        tabs = Segments(bar,
                        [("tags", i18n.t("gui.tab.tags")), ("rename", i18n.t("gui.tab.rename")),
                         ("sort", i18n.t("gui.tab.sort")), ("all", i18n.t("gui.tab.all")),
                         ("tools", i18n.t("gui.tab.tools"))],
                        self.var_page, command=self._show_page,
                        height=design.CONTROL_HEIGHT, stretch=False, surface=BACKGROUND,
                        navigation=True)
        tabs.grid(row=0, column=0, sticky="w")
        self._tabs = tabs
        # Der Ein-/Ausklappknopf entsteht nur im Mittelbereich (900–1199 px).
        self._config_toggle = None
        # Einstellungen sitzen in der Fußzeile (siehe _build_footer).
        self._settings_button = None
        # Freigabe (Vorschau/Anwenden) rechts in der Kopfzeile; die Fläche
        # hängt am Root, in_= setzt sie in die Leiste der Tabs.
        self._actions_area = tk.Frame(self.root, bg=BACKGROUND)
        self._actions_area.columnconfigure(0, weight=1)
        self._actions_area.grid_propagate(False)
        self._actions_area.grid(row=0, column=3, sticky="e", in_=bar)
        self._actions_area.lift()
        bar.bind("<Configure>", self._fit_top_bar, add="+")
        self._actions_area.bind("<Configure>", self._fit_top_bar, add="+")
        self._apply_minsize()
        self.root.after_idle(self._fit_top_bar)

    def _build_workspace(self) -> tk.Frame:
        """Shared workspace: configuration on the left, preview on the right."""
        workspace = tk.Frame(self.root, bg=BACKGROUND)
        workspace.grid(row=ROW_CONTENT, column=0, sticky="nsew",
                       padx=self._outer_inset(),
                       pady=(design.px(design.SPACE_M), design.px(design.SPACE_S)))
        workspace.columnconfigure(2, weight=1)
        workspace.rowconfigure(0, weight=1)
        self._workspace = workspace
        return workspace

    def _build_config_pane(self, workspace: tk.Frame) -> tk.Frame:
        """Scrollable configuration column; returns the frame that holds the pages."""
        config_area = tk.Frame(workspace, bg=CARD)
        config_area.columnconfigure(0, weight=1)
        # Die Scrollbar-Spalte bleibt auch ohne Überlauf reserviert. Sonst
        # ändert sich beim Seitenwechsel die Breite der Konfiguration und der
        # Vorschau, sobald der Balken erscheint oder verschwindet.
        config_area.columnconfigure(1, minsize=design.px(SCROLLBAR_WIDTH))
        config_area.rowconfigure(0, weight=1)
        self._config_area = config_area
        canvas = tk.Canvas(config_area, bg=CARD, highlightthickness=0, bd=0,
                           width=design.px(CONFIG_DEFAULT))
        scrollbar = ttk.Scrollbar(config_area, orient="vertical", command=canvas.yview,
                                  style="Dark.Vertical.TScrollbar")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        scrollbar.grid_remove()
        content = tk.Frame(canvas, bg=CARD)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")
        self._content_canvas = canvas
        self._content_window = content_window
        self._content_scrollbar = scrollbar
        self._content = content
        content.bind("<Configure>", lambda _event: self._update_content_scrollbar())
        canvas.bind("<Configure>", lambda event: self._sync_content_width())
        self.root.bind_all("<MouseWheel>", self._scroll_content)
        self.root.bind_all("<Button-4>", self._scroll_content)
        self.root.bind_all("<Button-5>", self._scroll_content)
        return content

    def _build_split_handle(self, workspace: tk.Frame) -> None:
        """Grip that resizes the configuration column (CONFIG_MIN–CONFIG_MAX)."""
        handle = tk.Canvas(workspace, bg=BACKGROUND, width=design.px(design.SPACE_S),
                           height=1, highlightthickness=0, bd=0,
                           cursor="sb_h_double_arrow")
        handle.bind("<Configure>", lambda _event: self._draw_split_grip())
        handle.bind("<ButtonPress-1>", self._split_press)
        handle.bind("<B1-Motion>", self._split_drag)
        self._split_handle = handle

    def _build_preview_pane(self, workspace: tk.Frame) -> None:
        """Right column that holds the preview card of the active page."""
        preview_area = tk.Frame(workspace, bg=BACKGROUND)
        preview_area.columnconfigure(0, weight=1)
        preview_area.rowconfigure(0, weight=1)
        # Leere Fläche für nur lesende Werkzeuge. Sie bleibt wie alle Karten
        # dauerhaft gemappt; sichtbar ist immer die oberste Karte.
        blank = tk.Frame(preview_area, bg=BACKGROUND)
        blank.grid(row=0, column=0, sticky="nsew")
        self._preview_blank = blank
        self._preview_area = preview_area

    def _build_pages(self, content: tk.Frame) -> None:
        """Create all five pages and show the remembered one."""
        self.pages = {
            "tags":   self._page_tags(content),
            "rename": self._page_rename(content),
            "sort":   self._page_sort(content),
            "all":    self._page_all(content),
            "tools":  self._page_tools(content),
        }
        for page in self.pages.values():
            # Alle Seiten bleiben gemappt und liegen übereinander. Nur die
            # aktive Seite wird nach vorne geholt; das vermeidet das schwarze
            # Aufblitzen beim Unmap/Map-Wechsel.
            page.place(x=0, y=0, relwidth=1, relheight=1)
            page.bind("<Configure>", self._page_configured, add="+")
        self._show_page(self.var_page.get())

    def _window_logical_width(self) -> int:
        """Fensterbreite in logischen Pixeln (Skalierung herausgerechnet)."""
        try:
            return int(round(self.root.winfo_width() / design.UI_SCALE))
        except (tk.TclError, ZeroDivisionError):
            return 0

    def _apply_workspace_mode(self) -> None:
        """Arbeitsbereich an die Fensterbreite anpassen (breit/mittel/schmal)."""
        if getattr(self, "_workspace", None) is None:
            return
        width = self._window_logical_width()
        mode = ("wide" if width >= WIDE_MIN
                else "mid" if width >= MID_MIN else "narrow")
        if mode != getattr(self, "_workspace_mode", None):
            self._workspace_mode = mode
            self._grid_workspace(mode)
        self._refresh_config_toggle()
        self._sync_content_width()

    def _grid_workspace(self, mode: str) -> None:
        """Ordne Konfiguration, Griff und Vorschau für den Modus an."""
        workspace = self._workspace
        config_area = self._config_area
        preview_area = self._preview_area
        handle = self._split_handle
        collapsed = getattr(self, "_config_collapsed", False) and mode == "mid"
        for widget in (config_area, handle, preview_area):
            widget.grid_forget()
        workspace.columnconfigure(0, weight=0)
        workspace.columnconfigure(1, weight=0)
        workspace.columnconfigure(2, weight=1)
        workspace.rowconfigure(1, weight=0)
        if mode == "narrow":
            # Konfiguration oberhalb der Vorschau, beides ohne Horizontal-Scroll.
            config_area.grid(row=0, column=0, columnspan=3, sticky="nsew")
            preview_area.grid(row=1, column=0, columnspan=3, sticky="ew",
                              pady=(design.px(design.SPACE_M), 0))
            workspace.rowconfigure(0, weight=1)
            return
        if collapsed:
            # Eingeclippt: die Vorschau nutzt die volle Arbeitsbereichsbreite.
            preview_area.grid(row=0, column=0, columnspan=3, sticky="nsew")
            return
        config_area.grid(row=0, column=0, sticky="ns")
        handle.grid(row=0, column=1, sticky="ns")
        preview_area.grid(row=0, column=2, sticky="nsew",
                          padx=(design.px(design.SPACE_M), 0))

    def _refresh_config_toggle(self) -> None:
        """Ein-/Ausklappknopf nur im Mittelbereich (900–1199 px) zeigen."""
        old = getattr(self, "_config_toggle", None)
        if old is not None:
            old.destroy()
            self._config_toggle = None
        if getattr(self, "_workspace_mode", None) != "mid":
            return
        collapsed = getattr(self, "_config_collapsed", False)
        text = i18n.t("gui.button.show_config" if collapsed else "gui.button.hide_config")
        toggle = RoundButton(self._tabs_bar, text, self._toggle_config, style="quiet",
                             height=28)
        toggle.grid(row=1, column=0, columnspan=4, sticky="w",
                pady=(design.px(design.SPACE_S), 0))
        self._config_toggle = toggle
        self._apply_minsize()

    def _toggle_config(self) -> None:
        """Konfigurationsspalte im Mittelbereich ein- oder ausklappen."""
        self._config_collapsed = not getattr(self, "_config_collapsed", False)
        self._refresh_config_toggle()
        self._grid_workspace(self._workspace_mode)

    def _split_press(self, event) -> None:
        """Startpunkt des Griffs merken."""
        self._split_start_x = event.x_root

    def _draw_split_grip(self) -> None:
        """Gummlinien des Griffs über die volle Höhe zeichnen."""
        handle = self._split_handle
        handle.delete("all")
        height = max(handle.winfo_height(), 1)
        for offset in (2, 5):
            handle.create_line(design.px(offset), 0, design.px(offset), height,
                               fill=BORDER, width=1)

    def _split_drag(self, event) -> None:
        """Konfigurationsbreite per Griff ändern, geklemmt auf CONFIG_MIN–CONFIG_MAX."""
        canvas = self._content_canvas
        try:
            new = event.x_root - self._config_area.winfo_rootx()
        except tk.TclError:
            return
        new = min(max(new, design.px(CONFIG_MIN)), design.px(CONFIG_MAX))
        if new != canvas.winfo_width():
            canvas.configure(width=new)
            self._sync_content_width()

    def _sync_content_width(self, *_args) -> None:
        """Inhaltsbreite der Konfigurationsspalte ohne altes 1120-px-Limit;
        im Stapelmodus bekommen Lesetexte und Eingaben ein Lesemaximum."""
        canvas = getattr(self, "_content_canvas", None)
        window = getattr(self, "_content_window", None)
        if canvas is None or window is None:
            return
        width = canvas.winfo_width()
        if getattr(self, "_workspace_mode", "wide") == "narrow":
            width = min(width, design.px(CONTENT_CAP))
        canvas.itemconfigure(window, width=max(width, 1))
        canvas.coords(window, 0, 0)
        self.root.after_idle(self._refresh_content_layout)

    def _bind_shortcuts(self) -> None:
        """Ctrl+1 … Ctrl+5 pick a page, right where the tabs are."""
        for index, page in enumerate(("tags", "rename", "sort", "all", "tools"), start=1):
            self.root.bind(f"<Control-Key-{index}>",
                           lambda _event, name=page: self._show_page(name))

    def _update_content_scrollbar(self) -> None:
        """Scrollbereich und Balken an der aktiven Seite ausrichten.

        Die Seiten liegen übereinander und füllen gemeinsam die höchste
        angeforderte Höhe. Gescrollt wird trotzdem nur bis zum Ende der
        sichtbaren Seite, damit darunter keine verdeckten Seiten erscheinen.
        """
        canvas = self._content_canvas
        region = canvas.bbox("all")
        if region is None:
            return
        page = getattr(self, "_active_page", None)
        try:
            content_height = max(page.winfo_reqheight(), 1) if page is not None else 1
        except tk.TclError:
            content_height = region[3] - region[1]
        canvas.configure(scrollregion=(0, 0, region[2] - region[0], content_height))
        if content_height > canvas.winfo_height() + 1:
            self._content_scrollbar.grid(row=0, column=1, sticky="ns")
        else:
            self._content_scrollbar.grid_remove()

    def _fit_content_height(self) -> None:
        """Platz für die höchste Seite reservieren, ohne bei jedem Wechsel zu resizen."""
        content = getattr(self, "_content", None)
        if content is None:
            return
        heights = []
        for page in self.pages.values():
            try:
                heights.append(page.winfo_reqheight())
            except tk.TclError:
                continue
        height = max(heights, default=1)
        if height == getattr(self, "_content_height", 0):
            return
        self._content_height = height
        content.configure(height=height)

    def _refresh_content_layout(self) -> None:
        """Reservierte Höhe und Scrollbalken nach Layoutänderungen nachziehen."""
        self._fit_content_height()
        self._update_content_scrollbar()

    def _page_configured(self, event) -> None:
        """Nach einer Größenänderung den reservierten Platz nachziehen."""
        self._fit_content_height()
        if event.widget is getattr(self, "_active_page", None):
            self._update_content_scrollbar()

    def _show_page(self, value: str) -> None:
        """Wechselt die Seite, ohne Fenster zu unmapen oder neu zu mappen.

        Alle Seiten und Vorschaukarten bleiben dauerhaft gemappt und liegen
        übereinander. Sichtbar ist immer die nach vorne geholte Seite. Ein
        Aus- und wieder Einhängen würde dagegen für einen Zeichenzyklus eine
        leere (im dunklen Thema schwarze) Fläche hinterlassen.
        """
        if self.var_page.get() != value:
            self.var_page.set(value)

        page = self.pages.get(value)
        if page is not None:
            self._active_page = page
            self._fit_content_height()
            page.tkraise()

        frame = self._action_frames.get(value)
        if frame is not None:
            frame.tkraise()
        self._size_actions_area()

        # In der rechten Spalte ist nur die Karte der aktiven Funktion sichtbar;
        # ein nur lesendes Werkzeug zeigt die leere Fläche (kein Schreiben,
        # keine Vorschau). Auch hier wird nichts ausgehängt, nur nach vorne
        # geholt.
        tool_feature = (feature_by_key(self.var_tool_choice.get())
                        if value == "tools" else None)
        previews = getattr(self, "_previews", {})
        card = previews.get(value)
        if value == "tools" and tool_feature is not None and not tool_feature.writes:
            card = None
        shown = card if card is not None else getattr(self, "_preview_blank", None)
        if shown is not None:
            shown.tkraise()

        canvas = getattr(self, "_content_canvas", None)
        if canvas is not None:
            canvas.yview_moveto(0)
            self.root.after_idle(self._refresh_content_layout)
        self.root.after_idle(self._fit_top_bar)
        if getattr(self, "_footer", None) is not None:
            self.root.after_idle(self._fit_footer)

    def _scroll_content(self, event) -> str | None:
        """Scroll the central viewport only while the pointer is over it."""
        canvas = self._content_canvas
        if not self._content_scrollbar.winfo_ismapped():
            return None  # kein Überlauf, nichts zu scrollen
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
