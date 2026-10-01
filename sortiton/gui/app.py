"""Window and tasks of the graphical interface.

Calls the same ``cmd_*`` functions as the command line; their results come back
through the hooks of :mod:`sortiton.output` and reach the widgets through
``self.queue`` - worker threads never touch widgets directly.
"""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import threading
import traceback
from pathlib import Path
from types import SimpleNamespace

import tkinter as tk
from tkinter import ttk

from .. import config, i18n, journal, output, rules, settings
from ..tasks import cmd_all, cmd_rename, cmd_restore, cmd_scan, cmd_sort, cmd_tags
from . import design
from .design import (ACCENT, BACKGROUND, BORDER, CARD, FIELD, GREEN, LOG_BG, LOG_TEXT,
                     RED, SCROLLBAR, SCROLLBAR_ACTIVE, TEXT, TEXT_FAINT, TEXT_MUTED,
                     YELLOW)
from .confirm import ask_confirm
from .dialogs import _ask_yes_no, _pick_folder, _show_error, _show_warning
from .panels import PreviewCard, ResultPanel, section_label
from .preferences import PreferencesWindow
from .restore import RestoreWindow
from .widgets import Pill, ProgressBar, RoundButton, Segments

# Default folders: "Musik" next to the project folder (fallback ~/Musik) and the
# library. SORTITON_FOLDER / SORTITON_TARGET override them.
_ENV_FOLDER = os.environ.get("SORTITON_FOLDER", "").strip()
DEFAULT_FOLDER = Path(_ENV_FOLDER) if _ENV_FOLDER else config.PROJECT_DIR.parent / "Musik"
if not DEFAULT_FOLDER.is_dir():
    DEFAULT_FOLDER = Path.home() / "Musik"
_ENV_TARGET = os.environ.get("SORTITON_TARGET", "").strip()
TARGET_FOLDER = Path(_ENV_TARGET) if _ENV_TARGET else Path.home() / "Musik"

PATTERN_DEFAULT = "%artist% - %title%"

# Rows of the root grid (named so the layout can be changed in one place).
ROW_TABS, ROW_LINE_TOP, ROW_CONTENT, ROW_ACTIONS, ROW_RESULT = 0, 1, 2, 3, 4
ROW_LINE_BOTTOM, ROW_FOOTER = 5, 6

RESULT_HEIGHT = 176      # result area in counter mode
LOG_HEIGHT = 320         # … and with the full log open

# Tag fields shown in the preview, in that order.
PLAN_FIELDS = ("artist", "album_artist", "title", "album", "genre")

# Keywords for colouring log lines (both languages).
_ERROR_MARKERS = ("ERROR", "FEHLER")
_OK_MARKERS = ("Done.", "OK:", "Renamed:", "Fertig.", "Umbenannt:")
_INFO_MARKERS = ("->", "PREVIEW", "VORSCHAU")


def _fmt_number(value) -> str:
    """Format a count with thousands separators (1842 -> 1.842)."""
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


def _pretty_path(path) -> str:
    """Shorten a path for display: the home directory becomes ``~``, very long
    paths lose their front (keeps the field readable, screenshots free of paths).
    """
    text = str(path or "").strip()
    if not text:
        return text
    try:
        home = Path.home()
        candidate = Path(text).expanduser()
        if candidate == home:
            text = "~"
        elif home in candidate.parents:
            text = "~/" + str(candidate.relative_to(home))
    except (OSError, ValueError):
        pass
    if len(text) > 52:
        text = "…" + text[-51:]
    return text


class SortitonGUI:
    """Main window of the Sortiton."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.queue: queue.Queue = queue.Queue()
        self.running = False
        self.last_path: Path | None = None
        self.action_buttons: list[RoundButton] = []
        self._icon_large: tk.PhotoImage | None = None
        self._rules_window: tk.Toplevel | None = None
        self._rules_text: tk.Text | None = None
        self._rules_status: tk.StringVar | None = None
        self._rules_status_label: tk.Label | None = None
        self._log_history: list[str] = []
        self.pages: dict[str, tk.Frame] = {}

        # Preview state per tab: the aggregated plan and the signature it was
        # made for (the execute button depends on both).
        self._plans: dict[str, dict] = {}
        self._execute_buttons: dict[str, RoundButton] = {}
        self._preview_notes: dict[str, tk.Label] = {}
        self._previews: dict[str, PreviewCard] = {}
        self._stats_labels: dict[str, tk.Label] = {}
        self._traces: list[tuple[tk.Variable, str]] = []
        self._job_page = "tags"
        self._dirty = False
        self._scan_page: str | None = None
        self._log_shown = False
        self._prefs_window: PreferencesWindow | None = None
        self._backup_for_run = True
        # True as soon as the window got its size/place - a rebuild (language
        # switch) must keep it where it is instead of centring it again.
        self._placed = False

        self.has_ffprobe = shutil.which("ffprobe") is not None
        self.has_mutagen = config.MUTAGEN_AVAILABLE

        design.load_fonts(root)
        self._make_vars()
        self._install_output_hooks()
        self._build_all()
        self._queue_pump()
        self._log_rules(i18n.t("gui.rules.prefix"))
        if not self.has_ffprobe:
            self._log_line(i18n.t("gui.log.ffprobe_missing"))
        self._refresh_folder_stats("tags")

    def _make_vars(self) -> None:
        """Create every StringVar once - they survive a language switch."""
        self.var_tags_folder = tk.StringVar(value=str(DEFAULT_FOLDER))
        self.var_ren_folder = tk.StringVar(value=str(DEFAULT_FOLDER))
        self.var_ren_pattern = tk.StringVar(value=PATTERN_DEFAULT)
        self.var_source = tk.StringVar(value=str(DEFAULT_FOLDER))
        self.var_target = tk.StringVar(value=str(TARGET_FOLDER))
        self.var_sort_pattern = tk.StringVar(value=PATTERN_DEFAULT)
        self.var_sort_mode = tk.StringVar(value="copy")
        self.var_all_source = tk.StringVar(value=str(DEFAULT_FOLDER))
        self.var_all_target = tk.StringVar(value=str(TARGET_FOLDER))
        self.var_all_pattern = tk.StringVar(value=PATTERN_DEFAULT)
        self.var_all_mode = tk.StringVar(value="copy")
        self.var_page = tk.StringVar(value="tags")
        self.var_language = tk.StringVar(value=i18n.get_language())
        self.var_backup = tk.BooleanVar(value=settings.resolve_backup())
        self.status_var = tk.StringVar(value="")

    def _install_output_hooks(self) -> None:
        """Route everything the tasks report into the queue.

        The hooks of :mod:`sortiton.output` are global, so they are installed
        once - a folder scan may still be running.
        """
        output.set_logger(lambda text: self.queue.put(("log", text)))
        output.set_progress(lambda i, n, text: self.queue.put(("prog", (i, n, text))))
        output.set_plan_sink(lambda kind, data: self.queue.put(("plan", (kind, data))))
        output.set_stats_sink(lambda kind, values: self.queue.put(("stats", (kind, values))))

    def _build_all(self) -> None:
        """Build (or rebuild) the whole window - used for the language switch."""
        for variable, identifier in self._traces:
            try:
                variable.trace_remove("write", identifier)
            except (tk.TclError, ValueError):
                pass
        self._traces = []
        for child in self.root.winfo_children():
            child.destroy()
        self.action_buttons = []
        self._execute_buttons = {}
        self._action_frames = {}
        self._preview_notes = {}
        self._previews = {}
        self._stats_labels = {}
        self._prefs_window = None
        # Keep the current size and position: only the very first build places
        # the window, otherwise a rebuild would recentre it (on two monitors
        # that is exactly the gap between the screens).
        self._build_window(keep_geometry=self._placed)
        self._placed = True
        self._set_style()
        self._load_icon()
        self._build_tabs()
        self._build_result_area()
        self._build_footer()
        self._watch_inputs()
        self._show_page(self.var_page.get())
        self._replay_log()
        self._show_result_view()
        for page in self.pages:
            self._render_preview(page)
        self.status_var.set(i18n.t("gui.status.running") if self.running
                            else i18n.t("gui.status.ready"))

    def _build_window(self, keep_geometry: bool = False) -> None:
        """Set up the root window.

        ``keep_geometry`` leaves size, position and state (maximised …) alone -
        used when the window is only rebuilt for another language.
        """
        self.root.title(i18n.t("gui.window.title"))
        if not keep_geometry:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            width = min(1040, max(min(640, screen_width - 40), int(screen_width * 0.86)))
            height = min(900, max(min(420, screen_height - 40), int(screen_height * 0.86)))
            x = max((screen_width - width) // 2, 0)
            y = max((screen_height - height) // 2, 0)
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(min(640, self.root.winfo_screenwidth() - 40),
                          min(420, self.root.winfo_screenheight() - 40))
        self.root.configure(bg=BACKGROUND)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(ROW_CONTENT, weight=1)
        self.root.rowconfigure(ROW_RESULT, weight=0, minsize=RESULT_HEIGHT)

    def _set_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        for orientation in ("Vertical", "Horizontal"):
            name = f"Dark.{orientation}.TScrollbar"
            style.configure(name, gripcount=0,
                            background=SCROLLBAR, darkcolor=SCROLLBAR,
                            lightcolor=SCROLLBAR, troughcolor=LOG_BG, bordercolor=LOG_BG,
                            arrowcolor=TEXT_MUTED, arrowsize=13)
            style.map(name, background=[("active", SCROLLBAR_ACTIVE)])

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

    def _open_preferences(self) -> None:
        """Open the settings window (or raise it when it is already open)."""
        if self._prefs_window is not None:
            try:
                if self._prefs_window.window.winfo_exists():
                    self._prefs_window.window.lift()
                    self._prefs_window.window.focus_set()
                    return
            except tk.TclError:
                pass
            self._prefs_window = None

        self._prefs_window = PreferencesWindow(self.root, self.var_language,
                                              self._language_changed,
                                              ffprobe=self.has_ffprobe,
                                              mutagen=self.has_mutagen)
        self._prefs_window.window.bind("<Destroy>", self._prefs_closed, add="+")

    def _prefs_closed(self, event) -> None:
        """Forget the window once it is closed (so it can be reopened)."""
        if self._prefs_window is not None and event.widget is self._prefs_window.window:
            self._prefs_window = None

    def _language_changed(self, code: str) -> None:
        """Switch the interface language and rebuild the window."""
        if self.running:
            _show_warning(i18n.t("gui.dialog.busy.title"), i18n.t("gui.dialog.busy.text"))
            self.var_language.set(i18n.get_language())
            return
        reopen = self._prefs_window is not None
        i18n.set_language(code)
        settings.save_language(code)
        self._build_all()
        if reopen:
            self._open_preferences()

    def _build_tabs(self) -> None:
        bar = tk.Frame(self.root, bg=BACKGROUND)
        bar.grid(row=ROW_TABS, column=0, sticky="ew", padx=22, pady=(16, 0))
        bar.columnconfigure(0, weight=1)
        tabs = Segments(bar,
                        [("tags", i18n.t("gui.tab.tags")), ("rename", i18n.t("gui.tab.rename")),
                         ("sort", i18n.t("gui.tab.sort")), ("all", i18n.t("gui.tab.all"))],
                        self.var_page, command=self._show_page, height=40, stretch=True)
        tabs.grid(row=0, column=0, sticky="ew")
        RoundButton(bar, "⚙  " + i18n.t("gui.button.settings"), self._open_preferences,
                    style="normal", height=32).grid(row=0, column=1, sticky="e", padx=(12, 0))

        tk.Frame(self.root, bg=BORDER, height=1).grid(row=ROW_LINE_TOP, column=0,
                                                      sticky="ew", pady=(14, 0))

        viewport = tk.Frame(self.root, bg=BACKGROUND)
        viewport.grid(row=ROW_CONTENT, column=0, sticky="nsew", padx=22, pady=(14, 4))
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
        self._actions_area.grid(row=ROW_ACTIONS, column=0, sticky="ew", padx=22,
                                pady=(0, 6))
        self._actions_area.columnconfigure(0, weight=1)

        self.pages = {
            "tags":   self._page_tags(content),
            "rename": self._page_rename(content),
            "sort":   self._page_sort(content),
            "all":    self._page_all(content),
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")
        self._show_page(self.var_page.get())

    def _resize_content_canvas(self, event, content_window: int) -> None:
        self._content_canvas.itemconfigure(content_window, width=event.width)
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

    def _page_tags(self, parent: tk.Frame) -> tk.Frame:
        """Folder -> active rules -> preview -> actions."""
        page = self._new_page(parent)
        self._folder_card(page, 0, "tags", [(i18n.t("gui.label.music_folder"),
                                             self.var_tags_folder)])
        self._rules_card(page, 1)
        self._preview_card(page, 2, "tags")
        self._actions("tags", preview=lambda: self._run_tags(False),
                      execute=lambda: self._run_tags(True),
                      execute_text=i18n.t("gui.button.write_tags"))
        return page

    def _page_rename(self, parent: tk.Frame) -> tk.Frame:
        page = self._new_page(parent)
        self._folder_card(page, 0, "rename", [(i18n.t("gui.label.music_folder"),
                                               self.var_ren_folder)])
        options = self._card(page, 1, i18n.t("gui.section.options"))
        self._pattern_row(options, 0, self.var_ren_pattern)
        self._hint(options, 2, i18n.t("gui.hint.rename_placeholders"))
        self._preview_card(page, 2, "rename")
        self._actions("rename", preview=lambda: self._run_rename(False),
                      execute=lambda: self._run_rename(True),
                      execute_text=i18n.t("gui.button.rename"))
        return page

    def _page_sort(self, parent: tk.Frame) -> tk.Frame:
        page = self._new_page(parent)
        self._folder_card(page, 0, "sort", [(i18n.t("gui.label.source_folder"),
                                             self.var_source),
                                            (i18n.t("gui.label.target_folder"),
                                             self.var_target)])
        options = self._card(page, 1, i18n.t("gui.section.options"))
        self._pattern_row(options, 0, self.var_sort_pattern)
        self._mode_row(options, 2, self.var_sort_mode)
        self._hint(options, 4, i18n.t("gui.hint.sort"))
        self._preview_card(page, 2, "sort")
        self._actions("sort", preview=lambda: self._run_sort(False),
                      execute=lambda: self._run_sort(True),
                      execute_text=i18n.t("gui.button.sort"))
        return page

    def _page_all(self, parent: tk.Frame) -> tk.Frame:
        page = self._new_page(parent)
        self._folder_card(page, 0, "all", [(i18n.t("gui.label.source_folder"),
                                            self.var_all_source),
                                           (i18n.t("gui.label.target_folder"),
                                            self.var_all_target)])
        options = self._card(page, 1, i18n.t("gui.section.options"))
        self._pattern_row(options, 0, self.var_all_pattern)
        self._mode_row(options, 2, self.var_all_mode)
        self._hint(options, 4, i18n.t("gui.hint.all"))
        self._preview_card(page, 2, "all")
        self._actions("all", preview=lambda: self._run_all(False),
                      execute=lambda: self._run_all(True),
                      execute_text=i18n.t("gui.button.run_all"))
        return page

    def _card(self, parent: tk.Frame, row: int, title: str = "") -> tk.Frame:
        """Panel with a subtle border and an optional section title.

        Returns the frame that rows are placed in.
        """
        outer = tk.Frame(parent, bg=CARD, highlightthickness=1,
                         highlightbackground=BORDER, bd=0)
        outer.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        outer.columnconfigure(0, weight=1)
        inner = tk.Frame(outer, bg=CARD)
        inner.grid(row=0, column=0, sticky="ew", padx=16, pady=14)
        inner.columnconfigure(0, weight=1)
        if not title:
            return inner
        section_label(inner, title).grid(row=0, column=0, sticky="w")
        body = tk.Frame(inner, bg=CARD)
        body.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        body.columnconfigure(0, weight=1)
        return body

    def _folder_card(self, page: tk.Frame, row: int, key: str,
                     rows: list[tuple[str, tk.StringVar]]) -> None:
        """Folder card: path fields, picker, refresh and the statistics."""
        body = self._card(page, row, i18n.t("gui.section.music_folder"))
        for index, (label, variable) in enumerate(rows):
            self._folder_row(body, index * 3, label, variable)

        footer = tk.Frame(body, bg=CARD)
        footer.grid(row=len(rows) * 3, column=0, sticky="ew", pady=(10, 0))
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
                    variable: tk.StringVar) -> None:
        """Label + path field + folder picker."""
        tk.Label(card, text=label, bg=CARD, fg=TEXT_MUTED, font=design.FONT_SMALL).grid(
            row=row, column=0, sticky="w", pady=(0 if row == 0 else 12, 5))
        line = tk.Frame(card, bg=CARD)
        line.grid(row=row + 1, column=0, sticky="ew")
        line.columnconfigure(0, weight=1)

        self._path_entry(line, variable).grid(row=0, column=0, sticky="ew", ipady=7)
        RoundButton(line, i18n.t("gui.button.choose_folder"),
                    lambda: self._choose_folder(variable),
                    style="normal").grid(row=0, column=1, padx=(10, 0))

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
        card.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        self._previews[key] = card

    def _pattern_row(self, card: tk.Frame, row: int, variable: tk.StringVar) -> None:
        """Label + pattern field (e.g. %artist% - %title%)."""
        tk.Label(card, text=i18n.t("gui.label.pattern"), bg=CARD, fg=TEXT_MUTED,
                 font=design.FONT_SMALL).grid(row=row, column=0, sticky="w", pady=(0, 5))
        self._path_entry(card, variable).grid(row=row + 1, column=0, sticky="ew",
                                             ipady=7)

    def _mode_row(self, card: tk.Frame, row: int, variable: tk.StringVar) -> None:
        """Label + copy/move switch."""
        tk.Label(card, text=i18n.t("gui.label.mode"), bg=CARD, fg=TEXT_MUTED,
                 font=design.FONT_SMALL).grid(row=row, column=0, sticky="w", pady=(12, 5))
        Segments(card, [("copy", i18n.t("gui.mode.copy")), ("move", i18n.t("gui.mode.move"))],
                 variable, height=34, surface=FIELD).grid(row=row + 1, column=0, sticky="w")

    def _hint(self, card: tk.Frame, row: int, text: str) -> None:
        tk.Label(card, text=text, bg=CARD, fg=TEXT_MUTED, font=design.FONT_SMALL,
                 justify="left", anchor="w", wraplength=660).grid(
            row=row, column=0, sticky="w", pady=(8, 0))

    def _choose_folder(self, variable: tk.StringVar) -> None:
        start = variable.get().strip()
        start_dir = Path(start).expanduser() if start else Path.home()
        if not start_dir.is_dir():
            start_dir = Path.home()
        chosen = _pick_folder(start_dir)
        if chosen:
            variable.set(chosen)

    def _actions(self, key: str, preview, execute, execute_text: str) -> None:
        """Preview as the primary action, the changing one clearly separated.

        The changing button stays disabled until a preview for exactly these
        inputs has run.
        """
        frame = tk.Frame(self._actions_area, bg=BACKGROUND)
        frame.grid(row=0, column=0, sticky="w")
        self._action_frames[key] = frame

        first = RoundButton(frame, i18n.t("gui.button.preview_create"), preview,
                            style="primary")
        first.pack(side="left")
        second = RoundButton(frame, execute_text, execute, style="apply")
        second.pack(side="left", padx=(10, 0))

        note = tk.Label(frame, text="", bg=BACKGROUND, fg=TEXT_FAINT,
                        font=design.FONT_SMALL)
        note.pack(side="left", padx=(14, 0))

        self.action_buttons += [first, second]
        self._execute_buttons[key] = second
        self._preview_notes[key] = note

    def _build_result_area(self) -> None:
        """One area, two views: the result counters or the full log.

        Both live in the same grid cell, so ``self.logbox`` always exists (a
        language switch rebuilds it instead of losing it).
        """
        self._result_area = tk.Frame(self.root, bg=BACKGROUND, height=RESULT_HEIGHT)
        self._result_area.grid(row=ROW_RESULT, column=0, sticky="nsew", padx=22, pady=(4, 6))
        self._result_area.columnconfigure(0, weight=1)
        self._result_area.rowconfigure(0, weight=1)
        self._result_area.grid_propagate(False)

        self.result_panel = ResultPanel(self._result_area, i18n.t("gui.section.result"),
                                        i18n.t("gui.label.last_entries"), recent_lines=3)
        self.result_panel.grid(row=0, column=0, sticky="nsew")
        self._last_backup: Path | None = None
        self._rebuild_result_header()

        view = tk.Frame(self._result_area, bg=LOG_BG, highlightthickness=1,
                        highlightbackground=BORDER, bd=0)
        self._log_view = view
        view.columnconfigure(0, weight=1)
        view.rowconfigure(1, weight=1)

        header = tk.Frame(view, bg=LOG_BG)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        header.columnconfigure(1, weight=1)
        tk.Label(header, text=i18n.t("gui.label.log").upper(), bg=LOG_BG, fg=TEXT_FAINT,
                 font=design.FONT_LABEL).grid(row=0, column=0, sticky="w")
        RoundButton(header, i18n.t("gui.button.back"), self._show_result_view,
                    style="quiet", height=26).grid(row=0, column=2, sticky="e")
        RoundButton(header, i18n.t("gui.button.clear"), self._clear_log, style="quiet",
                    height=26).grid(row=0, column=3, sticky="e", padx=(8, 0))

        frame = tk.Frame(view, bg=LOG_BG)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.logbox = tk.Text(frame, wrap="word", state="disabled", height=6, bg=LOG_BG,
                              fg=LOG_TEXT, insertbackground=TEXT, selectbackground=ACCENT,
                              relief="flat", bd=0, highlightthickness=0, font=design.FONT_MONO,
                              padx=12, pady=10, spacing1=1, spacing3=1)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.logbox.yview,
                               style="Dark.Vertical.TScrollbar")
        self.logbox.configure(yscrollcommand=scroll.set)
        self.logbox.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        self.logbox.tag_configure("err", foreground=RED)
        self.logbox.tag_configure("ok", foreground=GREEN)
        self.logbox.tag_configure("info", foreground=ACCENT)
        self.logbox.tag_configure("dim", foreground=TEXT_MUTED)

    def _show_log_view(self) -> None:
        """Switch the result area to the full log and let it take the space."""
        self.result_panel.grid_remove()
        self._log_view.grid(row=0, column=0, sticky="nsew")
        self._log_shown = True
        self._resize_result_area(LOG_HEIGHT, weight=1)
        self.logbox.see("end")

    def _show_result_view(self) -> None:
        """Switch back to the counters."""
        self._log_view.grid_remove()
        self.result_panel.grid(row=0, column=0, sticky="nsew")
        self._log_shown = False
        self._resize_result_area(RESULT_HEIGHT, weight=0)
        self._refresh_recent()

    def _resize_result_area(self, height: int, weight: int) -> None:
        self._result_area.configure(height=height)
        self.root.rowconfigure(ROW_RESULT, weight=weight, minsize=height)

    def _refresh_recent(self) -> None:
        """Show the newest log lines in the result view (not while it is hidden)."""
        if self._log_shown or not hasattr(self, "result_panel"):
            return
        self.result_panel.set_recent(self._log_history)

    def _log_line(self, line: str = "") -> None:
        self._log_history.append(line)
        if len(self._log_history) > 2000:
            del self._log_history[:1000]
        self._insert_log(line)
        self._refresh_recent()

    def _insert_log(self, line: str) -> None:
        marker = None
        if any(word in line for word in _ERROR_MARKERS):
            marker = "err"
        elif any(word in line for word in _OK_MARKERS):
            marker = "ok"
        elif any(word in line for word in _INFO_MARKERS):
            marker = "info"

        self.logbox.configure(state="normal")
        if marker:
            self.logbox.insert("end", line + "\n", marker)
        else:
            self.logbox.insert("end", line + "\n")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def _replay_log(self) -> None:
        for line in self._log_history:
            self._insert_log(line)

    def _clear_log(self) -> None:
        self._log_history = []
        self.logbox.configure(state="normal")
        self.logbox.delete("1.0", "end")
        self.logbox.configure(state="disabled")
        self._refresh_recent()

    def _build_footer(self) -> None:
        """Status dot, status text, progress with percentage, quick links."""
        tk.Frame(self.root, bg=BORDER, height=1).grid(row=ROW_LINE_BOTTOM, column=0,
                                                      sticky="ew")
        footer = tk.Frame(self.root, bg=BACKGROUND)
        footer.grid(row=ROW_FOOTER, column=0, sticky="ew", padx=22, pady=(8, 14))
        footer.columnconfigure(3, weight=1)

        self._state_dot = tk.Canvas(footer, width=12, height=12, bg=BACKGROUND,
                                    highlightthickness=0, bd=0)
        self._state_dot.grid(row=0, column=0, sticky="w")
        self._set_state(TEXT_MUTED)

        tk.Label(footer, textvariable=self.status_var, bg=BACKGROUND, fg=TEXT_MUTED,
                 font=design.FONT_SMALL).grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.progress = ProgressBar(footer, width=200)
        self.progress.grid(row=0, column=2, sticky="w", padx=(16, 8))
        self.progress_label = tk.Label(footer, text="", bg=BACKGROUND, fg=TEXT_FAINT,
                                       font=design.FONT_SMALL)
        self.progress_label.grid(row=0, column=3, sticky="w")

        RoundButton(footer, i18n.t("gui.button.undo"), self._open_restore,
                    style="normal", height=30).grid(row=0, column=4, sticky="e")
        RoundButton(footer, i18n.t("gui.button.open_logs"), self._open_logs,
                    style="quiet", height=30).grid(row=0, column=5, sticky="e", padx=(6, 0))
        RoundButton(footer, i18n.t("gui.button.open_folder"), self._open_last,
                    style="quiet", height=30).grid(row=0, column=6, sticky="e", padx=(6, 0))

    def _set_state(self, colour: str) -> None:
        """Colour the small dot in the status bar (idle / busy / problem)."""
        try:
            self._state_dot.delete("all")
            self._state_dot.create_oval(2, 2, 10, 10, fill=colour, outline="")
        except tk.TclError:
            pass

    def _rebuild_result_header(self, backup: str = "") -> None:
        """Buttons of the result card: log details and (if any) the backup."""
        for child in self.result_panel.header_right.winfo_children():
            child.destroy()
        RoundButton(self.result_panel.header_right, i18n.t("gui.button.details"),
                    self._show_log_view, style="quiet", height=28).pack(side="right")
        if backup:
            self._last_backup = Path(backup)
            RoundButton(self.result_panel.header_right, i18n.t("gui.button.open_backup"),
                        self._open_backup, style="quiet", height=28).pack(
                            side="right", padx=(0, 8))

    def _xdg_open(self, path: Path) -> None:
        """Hand a file or folder to the desktop - no output, no waiting."""
        subprocess.Popen(["xdg-open", str(path)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _open_last(self) -> None:
        if self.last_path and self.last_path.is_dir():
            self._xdg_open(self.last_path)

    def _open_logs(self) -> None:
        if config.LOG_DIR.is_dir():
            self._xdg_open(config.LOG_DIR)

    def _open_backup(self) -> None:
        if self._last_backup and self._last_backup.is_dir():
            self._xdg_open(self._last_backup)

    def _open_restore(self) -> None:
        """Undo window: pick a journal, check the plan, then undo the run."""
        if self.running:
            return
        RestoreWindow(self.root, self._run_restore, self.var_backup)

    def _run_restore(self, path: Path, keep_copies: bool) -> None:
        """Undo the given journal - the dialog has confirmed everything."""
        settings.save_backup(self.var_backup.get())
        self._start("restore", self._job_name("gui.job.restore", True), cmd_restore,
                    SimpleNamespace(journal=str(path), apply=True,
                                    backup=self.var_backup.get(),
                                    keep_copies=keep_copies),
                    Path(path).parent, source=str(path))

    def _run_tags(self, write: bool) -> None:
        folder = self.var_tags_folder.get().strip()
        if not self._path_ok(folder):
            return
        if write and not self._confirm_write("tags", folder=folder):
            return
        self._start("tags", self._job_name("gui.job.tags", write), cmd_tags,
                    SimpleNamespace(folder=folder, apply=write,
                                    backup=self._backup_for_run),
                    folder, source=folder)

    def _run_rename(self, execute: bool) -> None:
        folder = self.var_ren_folder.get().strip()
        if not self._path_ok(folder):
            return
        pattern = self.var_ren_pattern.get().strip() or PATTERN_DEFAULT
        if execute and not self._confirm_write("rename", folder=folder, pattern=pattern):
            return
        self._start("rename", self._job_name("gui.job.rename", execute), cmd_rename,
                    SimpleNamespace(folder=folder, pattern=pattern, apply=execute),
                    folder, source=folder)

    def _run_sort(self, execute: bool) -> None:
        source = self.var_source.get().strip()
        target = self.var_target.get().strip()
        if not self._path_ok(source) or not self._target_ok(target):
            return
        pattern = self.var_sort_pattern.get().strip() or PATTERN_DEFAULT
        move = self.var_sort_mode.get() == "move"
        if execute and not self._confirm_write("sort", folder=source, target=target):
            return
        self._start("sort", self._job_name("gui.job.sort", execute), cmd_sort,
                    SimpleNamespace(source=source, target=target, pattern=pattern,
                                    move=move, apply=execute), target,
                    source=source, target_root=target)

    def _run_all(self, execute: bool) -> None:
        source = self.var_all_source.get().strip()
        target = self.var_all_target.get().strip()
        if not self._path_ok(source) or not self._target_ok(target):
            return
        pattern = self.var_all_pattern.get().strip() or PATTERN_DEFAULT
        move = self.var_all_mode.get() == "move"
        if execute and not self._confirm_write("all", folder=source, target=target):
            return
        # TODO: unlike the sort page this hands the source folder to "Open
        # folder", although the files end up in the target as well.
        self._start("all", self._job_name("gui.job.all", execute), cmd_all,
                    SimpleNamespace(source=source, target=target, pattern=pattern,
                                    move=move, apply=execute,
                                    backup=self._backup_for_run), source,
                    source=source, target_root=target)

    def _job_name(self, key: str, execute: bool) -> str:
        name = i18n.t(key)
        return i18n.t("gui.job.run", name=name) if execute else i18n.t("gui.job.preview",
                                                                       name=name)

    def _mode_text(self, page: str) -> str:
        variable = self.var_all_mode if page == "all" else self.var_sort_mode
        return (i18n.t("gui.mode.move") if variable.get() == "move"
                else i18n.t("gui.mode.copy"))

    def _confirm_write(self, page: str, **fields) -> bool:
        """Confirmation with the counts of the preview and the backup switch."""
        plan = self._plans.get(page) or {}
        text = self._confirm_text(page, files=_fmt_number(plan.get("files", 0)),
                                  changes=_fmt_number(plan.get("changes_total", 0)),
                                  **fields)
        confirmed, options = ask_confirm(
            self.root,
            title=i18n.t("gui.confirm." + page + ".title"),
            heading=i18n.t("gui.confirm." + page + ".title"),
            text=text,
            note=i18n.t("gui.confirm.note"),
            ok_text=i18n.t("gui.confirm.ok"),
            cancel_text=i18n.t("gui.button.cancel"),
            options=[("backup", i18n.t("gui.confirm.backup"), self.var_backup.get())])
        if confirmed:
            self.var_backup.set(options.get("backup", True))
            settings.save_backup(self.var_backup.get())
        self._backup_for_run = self.var_backup.get()
        return confirmed

    def _confirm_text(self, page: str, *, files: str, changes: str, **fields) -> str:
        if page == "tags":
            return i18n.t("gui.confirm.tags.text", changes=changes, files=files)
        if page == "rename":
            return i18n.t("gui.confirm.rename.text", files=files,
                          pattern=fields.get("pattern", ""))
        if page == "sort":
            return i18n.t("gui.confirm.sort.text", files=files,
                          mode=self._mode_text("sort"),
                          target=_pretty_path(fields.get("target", "")))
        return i18n.t("gui.confirm.all.text", files=files, mode=self._mode_text("all"),
                      target=_pretty_path(fields.get("target", "")))

    def _begin_plan(self, page: str, source: str = "",
                    target_root: str = "") -> None:
        """Reset the aggregated plan of ``page`` before a run starts."""
        self._plans[page] = {"kind": page, "files": 0, "changes_total": 0, "fields": {},
                             "examples": [], "source": source, "target": target_root,
                             "signature": None}

    def _absorb_plan(self, kind: str, data: dict) -> None:
        """Aggregate one planned change - counters plus a few examples only.

        The full list stays in the log, so the card stays readable.
        """
        plan = self._plans.get(self._job_page)
        if plan is None:
            return

        if kind == "tags":
            changes = data.get("changes") or {}
            plan["files"] += 1
            plan["changes_total"] += len(changes)
            for field, pair in changes.items():
                entry = plan["fields"].setdefault(field, {"count": 0, "examples": []})
                entry["count"] += 1
                example = (pair[0], pair[1])
                if example not in entry["examples"]:
                    entry["examples"].append(example)
            return

        source = data.get("source")
        target = data.get("target")
        if source is None or target is None:
            return
        plan["files"] += 1
        if len(plan["examples"]) < 3:
            new = Path(target).name
            root = plan.get("target") or ""
            if root:
                try:
                    new = str(Path(target).relative_to(root))
                except (ValueError, OSError):
                    pass
            plan["examples"].append((Path(source).name, new))

    def _watch_inputs(self) -> None:
        """Invalidate a preview as soon as one of its inputs changes."""
        for variable in (self.var_tags_folder, self.var_ren_folder, self.var_ren_pattern,
                         self.var_source, self.var_target, self.var_sort_pattern,
                         self.var_sort_mode, self.var_all_source, self.var_all_target,
                         self.var_all_pattern, self.var_all_mode):
            self._traces.append((variable,
                                 variable.trace_add("write", self._inputs_changed)))

    def _rules_fingerprint(self) -> str:
        """Cheap check whether my_rules.ini changed since the preview."""
        try:
            stat = config.RULES_FILE.stat()
            return f"{stat.st_mtime_ns}:{stat.st_size}"
        except OSError:
            return "-"

    def _signature(self, page: str) -> tuple:
        """Everything a preview depends on - detects outdated previews."""
        rules_id = (self._rules_fingerprint(), rules.rules_status()["custom_total"])
        if page == "tags":
            return ("tags", self.var_tags_folder.get().strip(), rules_id)
        if page == "rename":
            return ("rename", self.var_ren_folder.get().strip(),
                    self.var_ren_pattern.get().strip(), rules_id)
        if page == "sort":
            return ("sort", self.var_source.get().strip(), self.var_target.get().strip(),
                    self.var_sort_pattern.get().strip(), self.var_sort_mode.get())
        if page == "restore":
            # An undo has no inputs of its own: the journal is fixed when the run
            # starts, so the signature only has to stay stable while it runs.
            return ("restore", str((self._plans.get("restore") or {}).get("source", "")))
        return ("all", self.var_all_source.get().strip(), self.var_all_target.get().strip(),
                self.var_all_pattern.get().strip(), self.var_all_mode.get(), rules_id)

    def _preview_ready(self, page: str) -> bool:
        plan = self._plans.get(page)
        return bool(plan and plan.get("signature") == self._signature(page))

    def _inputs_changed(self, *_args) -> None:
        if self._dirty:
            return
        self._dirty = True
        self.root.after(120, self._refresh_preview_states)

    def _refresh_preview_states(self) -> None:
        self._dirty = False
        for page in self.pages:
            self._render_preview(page)

    def _render_preview(self, page: str) -> None:
        """Draw the aggregated plan of ``page`` and gate its action button."""
        card = self._previews.get(page)
        if card is None:
            return
        button = self._execute_buttons.get(page)
        note = self._preview_notes.get(page)
        plan = self._plans.get(page)

        if button is not None:
            button.set_enabled(self._preview_ready(page) and not self.running)

        if plan is None:
            card.hint(i18n.t("gui.preview.none"))
            if note is not None:
                note.configure(text=i18n.t("gui.preview.run_first"), fg=TEXT_FAINT)
            return

        if plan.get("signature") is None and self.running and page == self._job_page:
            card.hint(i18n.t("gui.preview.running"))
            return

        card.show(self._plan_summary(plan), self._plan_rows(plan),
                  i18n.t("gui.preview.unchanged"))
        if note is not None:
            if self._preview_ready(page):
                note.configure(text="", fg=TEXT_MUTED)
            else:
                note.configure(text=i18n.t("gui.preview.stale"), fg=YELLOW)

    def _plan_summary(self, plan: dict) -> str:
        files = _fmt_number(plan.get("files", 0))
        if plan.get("kind") == "tags":
            return i18n.t("gui.preview.summary_tags",
                          changes=_fmt_number(plan.get("changes_total", 0)), files=files)
        return i18n.t("gui.preview.summary_files", files=files)

    def _plan_rows(self, plan: dict) -> list[tuple[str, str, str, str]]:
        rows: list[tuple[str, str, str, str]] = []
        if plan.get("kind") == "tags":
            for field in PLAN_FIELDS:
                entry = (plan.get("fields") or {}).get(field)
                if not entry or not entry["examples"]:
                    continue
                old, new = entry["examples"][0]
                extra = (i18n.t("gui.preview.more", count=entry["count"] - 1)
                         if entry["count"] > 1 else "")
                rows.append((i18n.t("gui.field." + field), old, new, extra))
            return rows

        examples = plan.get("examples") or []
        if examples:
            old, new = examples[0]
            extra = (i18n.t("gui.preview.more", count=plan["files"] - 1)
                     if plan["files"] > 1 else "")
            rows.append((i18n.t("gui.field.file"), old, new, extra))
        if plan.get("target"):
            rows.append((i18n.t("gui.field.folder"), _pretty_path(plan.get("source", "")),
                         _pretty_path(plan.get("target", "")), ""))
        return rows

    def _folder_var(self, page: str) -> tk.StringVar:
        return {"tags": self.var_tags_folder, "rename": self.var_ren_folder,
                "sort": self.var_source, "all": self.var_all_source}.get(
                    page, self.var_tags_folder)

    def _refresh_folder_stats(self, page: str, manual: bool = True) -> None:
        """Count files/albums/artists in the background and show the result.

        Without mutagen it falls back to ffprobe and can take a minute, so the
        automatic start is skipped in that case.
        """
        label = self._stats_labels.get(page)
        if label is None or self.running or self._scan_page is not None:
            return
        folder = self._folder_var(page).get().strip()
        if not folder or not Path(folder).expanduser().is_dir():
            label.configure(text=i18n.t("gui.stats.unknown"))
            return
        if not manual and not self.has_mutagen:
            label.configure(text=i18n.t("gui.stats.press_refresh"))
            return

        self._scan_page = page
        label.configure(text=i18n.t("gui.stats.scanning"))
        self.status_var.set(i18n.t("gui.status.scanning"))
        self._set_state(YELLOW)

        def worker() -> None:
            rc = 99
            try:
                rc = cmd_scan(SimpleNamespace(folder=folder))
            except Exception:
                output.message(i18n.t("gui.log.error", text=traceback.format_exc()))
            self.queue.put(("scan_done", rc))

        threading.Thread(target=worker, daemon=True).start()

    def _show_folder_stats(self, page: str | None, values: dict) -> None:
        label = self._stats_labels.get(page or "")
        if label is None:
            return
        label.configure(text=i18n.t("gui.stats.summary",
                                    files=_fmt_number(values.get("files", 0)),
                                    albums=_fmt_number(values.get("albums", 0)),
                                    artists=_fmt_number(values.get("artists", 0))))

    def _absorb_stats(self, kind: str, values: dict) -> None:
        """Route the counters: a folder scan fills the line, a run fills the card."""
        if kind == "scan":
            self._show_folder_stats(self._scan_page, values)
            self._scan_page = None
            if not self.running:
                self.progress_label.configure(text="")
                self.status_var.set(i18n.t("gui.status.ready"))
                self._set_state(GREEN if self.has_ffprobe else YELLOW)
            return
        self._render_stats(kind, values)

    def _render_stats(self, kind: str, values: dict) -> None:
        number = _fmt_number
        if kind == "all":
            rows = [
                (GREEN, "✓", number(values.get("tags_changed", 0)),
                 i18n.t("gui.result.tags_changed")),
                (GREEN, "✓", number(values.get("renamed", 0)), i18n.t("gui.result.renamed")),
                (GREEN, "✓", number(values.get("sorted_files", 0)),
                 i18n.t("gui.result.sorted")),
                (RED, "✕", number(values.get("errors", 0)), i18n.t("gui.result.errors")),
            ]
        else:
            changed_key = ("gui.result.changed" if values.get("applied")
                           else "gui.result.planned")
            rows = [
                (GREEN, "✓", number(values.get("changed", 0)), i18n.t(changed_key)),
                (TEXT_MUTED, "•", number(values.get("files", 0)),
                 i18n.t("gui.result.analysed")),
                (YELLOW, "⚠", number(values.get("skipped", 0)),
                 i18n.t("gui.result.skipped")),
                (RED, "✕", number(values.get("errors", 0)), i18n.t("gui.result.errors")),
            ]
        self.result_panel.set_counters(rows)
        self._rebuild_result_header(values.get("backup", ""))
        self._refresh_recent()

    def _start(self, page: str, description: str, function, args, last_path: str | Path,
               source: str = "", target_root: str = "") -> None:
        if self.running:
            return
        self.running = True
        self._job_page = page
        self.last_path = Path(last_path).expanduser()
        self._begin_plan(page, source=source, target_root=target_root)
        self._set_buttons(False)
        self._render_preview(page)
        self.progress.start()
        self.progress_label.configure(text="")
        self._set_state(YELLOW)
        self.status_var.set(i18n.t("gui.status.running"))
        self._log_line("")
        self._log_line(i18n.t("gui.log.job", description=description))
        self._log_rules(i18n.t("gui.rules.prefix"))

        def worker() -> None:
            rc = 99
            try:
                log_file = output.open_log_file(f"{description} · {self.last_path}")
                if log_file:
                    output.message(i18n.t("gui.log.log_file", path=log_file))
                    if getattr(args, "apply", False):
                        # Only a run that writes gets a journal.
                        journal.open_for(log_file)
                rc = function(args)
            except Exception:
                output.message(i18n.t("gui.log.error", text=traceback.format_exc()))
                rc = 99
            finally:
                journal.close()
                output.close_log_file(rc)
                self.queue.put(("done", rc))

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self, rc: int) -> None:
        """A run is over: release the buttons and stamp the preview.

        Only a preview with the current signature enables the execute button.
        """
        self.progress.stop()
        self.progress_label.configure(text="")
        self.running = False
        plan = self._plans.get(self._job_page)
        if plan is not None:
            plan["signature"] = self._signature(self._job_page)
        if self._job_page == "restore":
            # An undo changes tags and file names behind the other pages, so
            # their previews are stale now and have to be created again before
            # anything is written from them.
            for page, other in self._plans.items():
                if page != "restore":
                    other["signature"] = None
        self._set_buttons(True)
        self._refresh_preview_states()
        self._set_state(GREEN if rc == 0 else RED)
        self.status_var.set(i18n.t("gui.status.ready") if rc == 0
                            else i18n.t("gui.status.failed", rc=rc))

    def _queue_pump(self) -> None:
        try:
            while True:
                kind, value = self.queue.get_nowait()
                if kind == "log":
                    self._log_line(value)
                elif kind == "prog":
                    self._set_progress(*value)
                elif kind == "plan":
                    self._absorb_plan(*value)
                elif kind == "stats":
                    self._absorb_stats(*value)
                elif kind == "scan_done":
                    self._scan_finished()
                elif kind == "done":
                    self._finish(value)
        except queue.Empty:
            pass
        self.root.after(80, self._queue_pump)

    def _scan_finished(self) -> None:
        """A folder scan is over (also when it failed and sent no counters)."""
        if self._scan_page is not None and not self.running:
            self._scan_page = None
            self.progress_label.configure(text="")
            self.status_var.set(i18n.t("gui.status.ready"))
            self._set_state(GREEN if self.has_ffprobe else YELLOW)

    def _set_progress(self, current: int, total: int, text: str) -> None:
        self.progress.set_value(current, total)
        if total:
            self.progress_label.configure(
                text=i18n.t("gui.status.percent", current=_fmt_number(current),
                            total=_fmt_number(total),
                            percent=int(current * 100 / total)))
        if text:
            self.status_var.set(text)

    def _log_rules(self, prefix: str) -> None:
        """Reload the rules; update the log and the "active rules" card."""
        warnings = rules.load_custom_rules()
        for warning in warnings:
            self._log_line(i18n.t("gui.log.rule_warning", text=warning))
        summary = rules.rules_summary()
        if summary or warnings:
            self._log_line(i18n.t("gui.log.rules", prefix=prefix,
                                  summary=summary or i18n.t("gui.log.no_rules"),
                                  file=config.RULES_FILE.name))
        self._refresh_rules_card(len(warnings))

    def _refresh_rules_card(self, warnings: int = 0) -> None:
        """Show which rules are active - read from the file, not as prose."""
        pills = getattr(self, "_rules_pills", None)
        if pills is None:
            return
        for child in pills.winfo_children():
            child.destroy()

        status = rules.rules_status()
        own = [("gui.pill.artist", status["artist"]), ("gui.pill.regex", status["regex"]),
               ("gui.pill.genre", status["genre"]),
               ("gui.pill.protected", status["protected"])]
        shown = 0
        for key, count in own:
            if count:
                Pill(pills, i18n.t(key, count=count), GREEN).pack(side="left", padx=(0, 8))
                shown += 1
        if not shown:
            tk.Label(pills, text=i18n.t("gui.pill.none"), bg=CARD, fg=TEXT_MUTED,
                     font=design.FONT_SMALL).pack(side="left", padx=(0, 8))

        builtin = status["builtin_artists"] + status["builtin_genres"]
        Pill(pills, i18n.t("gui.pill.builtin", count=builtin),
             YELLOW if warnings else TEXT_MUTED).pack(side="left", padx=(0, 8))
        if warnings:
            Pill(pills, i18n.t("gui.pill.warnings", count=warnings),
                 YELLOW).pack(side="left")

    def _rules_editor(self) -> None:
        """Small editor window for my_rules.ini."""
        if self._rules_window is not None:
            try:
                if self._rules_window.winfo_exists():
                    self._rules_window.lift()
                    self._rules_window.focus_set()
                    return
            except tk.TclError:
                pass
            self._rules_window = None

        window = tk.Toplevel(self.root)
        self._rules_window = window
        window.title(i18n.t("gui.rules.editor.title"))
        window.configure(bg=BACKGROUND)
        window.transient(self.root)
        width, height = 840, 620
        x = max(self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2, 0)
        y = max(self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2, 0)
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.minsize(640, 440)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)

        header = tk.Frame(window, bg=BACKGROUND)
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        tk.Label(header, text=i18n.t("gui.rules.editor.heading"), font=design.FONT_SECTION,
                 bg=BACKGROUND, fg=TEXT).grid(row=0, column=0, sticky="w")
        tk.Label(header, text=i18n.t("gui.rules.editor.hint", path=config.RULES_FILE),
                 font=design.FONT_SMALL, bg=BACKGROUND, fg=TEXT_MUTED,
                 wraplength=780, justify="left").grid(row=1, column=0, sticky="w", pady=(2, 0))

        frame = tk.Frame(window, bg=LOG_BG, highlightthickness=1,
                         highlightbackground=BORDER, bd=0)
        frame.grid(row=1, column=0, sticky="nsew", padx=20)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self._rules_text = tk.Text(frame, wrap="none", undo=True, bg=LOG_BG, fg=LOG_TEXT,
                                   insertbackground=TEXT, selectbackground=ACCENT,
                                   relief="flat", bd=0, highlightthickness=0,
                                   font=(design.FONT_MONO[0], 10), padx=12, pady=10)
        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=self._rules_text.yview,
                                 style="Dark.Vertical.TScrollbar")
        x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=self._rules_text.xview,
                                 style="Dark.Horizontal.TScrollbar")
        self._rules_text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self._rules_text.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        content = ""
        if config.RULES_FILE.is_file():
            try:
                content = config.RULES_FILE.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                content = ""
        if not content.strip():
            content = rules.rules_template()
        self._rules_text.insert("1.0", content)

        footer = tk.Frame(window, bg=BACKGROUND)
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 16))
        footer.columnconfigure(0, weight=1)
        self._rules_status = tk.StringVar(value="")
        self._rules_status_label = tk.Label(footer, textvariable=self._rules_status,
                                            bg=BACKGROUND, fg=TEXT_MUTED,
                                            font=design.FONT_SMALL)
        self._rules_status_label.grid(row=0, column=0, sticky="w")

        buttons = tk.Frame(footer, bg=BACKGROUND)
        buttons.grid(row=1, column=0, sticky="e", pady=(10, 0))
        RoundButton(buttons, i18n.t("gui.button.insert_template"), self._insert_template,
                    style="quiet", height=32).pack(side="left")
        RoundButton(buttons, i18n.t("gui.button.builtin_rules"), self._insert_builtin,
                    style="quiet", height=32).pack(side="left", padx=(8, 0))
        RoundButton(buttons, i18n.t("gui.button.system_editor"), self._open_system_editor,
                    style="quiet", height=32).pack(side="left", padx=(8, 0))
        RoundButton(buttons, i18n.t("gui.button.cancel"), window.destroy,
                    style="normal", height=32).pack(side="left", padx=(8, 0))
        RoundButton(buttons, i18n.t("gui.button.save"), self._save_rules,
                    style="primary", height=32).pack(side="left", padx=(8, 0))

        window.bind("<Escape>", lambda _e: window.destroy())
        window.bind("<Control-s>", lambda _e: self._save_rules())

    def _set_rules_status(self, text: str, colour: str = TEXT_MUTED) -> None:
        if self._rules_status is not None:
            self._rules_status.set(text)
        if self._rules_status_label is not None:
            try:
                self._rules_status_label.configure(fg=colour)
            except tk.TclError:
                pass

    def _insert_template(self) -> None:
        text = self._rules_text
        if text is None:
            return
        if text.get("1.0", "end-1c").strip() and not _ask_yes_no(
                i18n.t("gui.rules.confirm_template.title"),
                i18n.t("gui.rules.confirm_template.text")):
            return
        text.delete("1.0", "end")
        text.insert("1.0", rules.rules_template())
        self._set_rules_status(i18n.t("gui.rules.status.template"))

    def _insert_builtin(self) -> None:
        """Append the commented overview of all built-in rules."""
        text = self._rules_text
        if text is None:
            return
        marker = i18n.t("rules.overview.header1")[:24]
        if marker in text.get("1.0", "end-1c"):
            self._set_rules_status(i18n.t("gui.rules.status.builtin_present"))
            return
        text.insert("end", "\n\n" + rules.builtin_rules_text() + "\n")
        text.see("end")
        self._set_rules_status(i18n.t("gui.rules.status.builtin_added"))

    def _save_rules(self) -> None:
        text = self._rules_text
        if text is None:
            return
        content = text.get("1.0", "end-1c").rstrip() + "\n"
        try:
            config.RULES_FILE.write_text(content, encoding="utf-8")
        except OSError as error:
            _show_error(i18n.t("gui.dialog.save_failed.title"),
                        i18n.t("gui.dialog.save_failed.text", error=error))
            return

        warnings = rules.load_custom_rules()
        for warning in warnings:
            self._log_line(i18n.t("gui.log.rule_warning", text=warning))
        summary = rules.rules_summary()
        self._log_line(i18n.t("gui.log.rules", prefix=i18n.t("gui.rules.prefix_saved"),
                              summary=summary or i18n.t("gui.log.no_rules"),
                              file=config.RULES_FILE.name))
        if warnings:
            self._set_rules_status(i18n.t("gui.rules.status.saved_warnings",
                                          count=len(warnings)), YELLOW)
        else:
            self._set_rules_status(i18n.t("gui.rules.status.saved",
                                          summary=summary or i18n.t("gui.rules.status.none")),
                                   GREEN)

    def _open_system_editor(self) -> None:
        """Save and open the rules file in the system's default editor."""
        self._save_rules()
        if config.RULES_FILE.is_file():
            self._xdg_open(config.RULES_FILE)

    def _path_ok(self, path: str) -> bool:
        if not path:
            _show_warning(i18n.t("gui.dialog.folder_missing.title"),
                          i18n.t("gui.dialog.folder_missing.text"))
            return False
        target = Path(path).expanduser()
        if not target.is_dir():
            _show_error(i18n.t("gui.dialog.folder_not_found.title"),
                        i18n.t("gui.dialog.folder_not_found.text", path=target))
            return False
        return True

    def _target_ok(self, target: str) -> bool:
        """Sorting and the all-in-one run need a target folder."""
        if target:
            return True
        _show_warning(i18n.t("gui.dialog.target_missing.title"),
                      i18n.t("gui.dialog.target_missing.text"))
        return False

    def _set_buttons(self, enabled: bool) -> None:
        for button in self.action_buttons:
            button.set_enabled(enabled)


def main() -> int:
    settings.apply_language()
    root = tk.Tk()
    SortitonGUI(root)
    root.mainloop()
    return 0
