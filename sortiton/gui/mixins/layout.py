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

# Workspace: two columns from 1200 logical px, collapsible configuration
# between 900 and 1199, and configuration above the preview below that.
WIDE_MIN = 1200
MID_MIN = 900
CONFIG_MIN = 320       # Minimum width (resizable by the user)
CONFIG_MAX = 560       # Maximum practical form width
# Start at the maximum configuration pane width.
CONFIG_DEFAULT = CONFIG_MAX
CONTENT_CAP = 720      # Maximum width for text/inputs in stacked mode
SCROLLBAR_WIDTH = 13   # Reserve space for the vertical scrollbar, even without overflow


class LayoutMixin(PageMixin):
    """Main window frame: header, workspace and page switching."""


    def _outer_inset(self) -> int:
        """Shared outer margin so the form, header and footer align."""
        return design.px(design.SPACE_XL)

    def _align_fixed_rows(self, event=None) -> None:
        """Align the header, result and footer, and adapt the workspace
        (two-column or stacked) to the window width."""
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
        """Build the window at startup or when the appearance changes."""
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
        # Drop references from the previous build so callbacks such as
        # _apply_minsize cannot access widgets that have already been destroyed.
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
        """Minimum width: tabs and approval above, status and footer below."""
        bar = getattr(self, "_tabs_bar", None)
        tabs = getattr(self, "_tabs", None)
        if bar is None or tabs is None:
            return
        needs = tabs.winfo_reqwidth() + design.px(44)
        # Header: tabs on the left, approval on the right (the hint yields first).
        actions_area = getattr(self, "_actions_area", None)
        if actions_area is not None:
            # Use the widest button row without its explanatory hint when
            # calculating the minimum width. The hint can yield when space is
            # tight, keeping the minimum width stable across tab changes.
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
        # Footer: settings, status and shortcuts must fit together.
        # Only essential elements count towards the minimum width; shortcuts
        # yield in narrow windows (see _fit_footer).
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
                footer_needed += design.px(60)  # Base column spacing
                # The footer is inset by the outer margin on both sides.
                needed = max(needed, footer_needed + 2 * self._outer_inset())
            except tk.TclError:
                pass  # Footer is not available during a rebuild.
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = min(max(design.px(680), needed), screen_width - design.px(24))
        self.root.minsize(width, min(design.px(460), screen_height - design.px(48)))

    def _fit_top_bar(self, event=None) -> None:
        """Hide the hint beside approval when the header gets tight.

        Keep the tabs and both action buttons visible; hide only the
        explanatory text when there is not enough room.
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
            # Read-only tools have no hint; still size the area to the active
            # button row.
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
        """Size the action area to the visible page's button row.

        Keep all button rows mapped and stacked. Size the area only to the
        active row so the header does not permanently reserve space for the
        widest row.
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
            # Tk has not calculated the requested size of a newly created row
            # yet; it will do so during the next idle cycle.
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
        """Retry after Tk has calculated the new button row's size."""
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
        # Show the collapse/expand button only at medium widths (900–1199 px).
        self._config_toggle = None
        # Settings are in the footer (see _build_footer).
        self._settings_button = None
        # Approval (Preview/Apply) is on the right of the header. The area is
        # attached to the root; in_= places it in the tab bar.
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
        # Reserve the scrollbar column even without overflow. Otherwise the
        # configuration and preview widths change when switching pages as the
        # scrollbar appears or disappears.
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
        # Empty area for read-only tools. Like all cards, it stays mapped;
        # the topmost card is always visible.
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
            # Keep all pages mapped and stacked. Raise only the active page to
            # avoid a black flash during an unmap/map transition.
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
        """Adapt the workspace to the window width (wide/medium/narrow)."""
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
        """Arrange configuration, divider and preview for the current mode."""
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
            # Put configuration above the preview; neither needs horizontal scrolling.
            config_area.grid(row=0, column=0, columnspan=3, sticky="nsew")
            preview_area.grid(row=1, column=0, columnspan=3, sticky="ew",
                              pady=(design.px(design.SPACE_M), 0))
            workspace.rowconfigure(0, weight=1)
            return
        if collapsed:
            # Collapsed: let the preview use the full workspace width.
            preview_area.grid(row=0, column=0, columnspan=3, sticky="nsew")
            return
        config_area.grid(row=0, column=0, sticky="ns")
        handle.grid(row=0, column=1, sticky="ns")
        preview_area.grid(row=0, column=2, sticky="nsew",
                          padx=(design.px(design.SPACE_M), 0))

    def _refresh_config_toggle(self) -> None:
        """Show the collapse/expand button only at medium widths (900–1199 px)."""
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
        """Collapse or expand the configuration column at medium widths."""
        self._config_collapsed = not getattr(self, "_config_collapsed", False)
        self._refresh_config_toggle()
        self._grid_workspace(self._workspace_mode)

    def _split_press(self, event) -> None:
        """Remember the divider's starting point."""
        self._split_start_x = event.x_root

    def _draw_split_grip(self) -> None:
        """Draw the divider grip lines over the full height."""
        handle = self._split_handle
        handle.delete("all")
        height = max(handle.winfo_height(), 1)
        for offset in (2, 5):
            handle.create_line(design.px(offset), 0, design.px(offset), height,
                               fill=BORDER, width=1)

    def _split_drag(self, event) -> None:
        """Resize the configuration pane, clamped to CONFIG_MIN–CONFIG_MAX."""
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
        """Set the configuration content width without the old 1120 px limit.
        In stacked mode, cap the width of reading text and inputs."""
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
        """Align the scroll region and scrollbar with the active page.

        Pages are stacked and share the maximum requested height. Scrolling
        still stops at the end of the visible page so hidden pages below it
        do not appear.
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
        """Reserve space for the tallest page without resizing on every switch."""
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
        """Update the reserved height and scrollbar after layout changes."""
        self._fit_content_height()
        self._update_content_scrollbar()

    def _page_configured(self, event) -> None:
        """Update the reserved space after a resize."""
        self._fit_content_height()
        if event.widget is getattr(self, "_active_page", None):
            self._update_content_scrollbar()

    def _show_page(self, value: str) -> None:
        """Switch pages without unmapping and remapping their windows.

        Keep all pages and preview cards mapped and stacked. Raise the active
        page to the front. Unmapping and remapping would leave an empty (black
        in dark mode) area for one redraw cycle.
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

        # Show only the active function's card in the right column. Read-only
        # tools show the empty area (no writes and no preview). Keep cards
        # mapped here too; only raise the visible one.
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
            return None  # No overflow; nothing to scroll.
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
