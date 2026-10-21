"""Result area, log view, footer and the open-* actions."""

from __future__ import annotations

from ..common import (
    ACCENT,
    BACKGROUND,
    BORDER,
    GREEN,
    LOG_BG,
    LOG_TEXT,
    Path,
    ProgressBar,
    RED,
    ROW_FOOTER,
    ROW_LINE_BOTTOM,
    ROW_RESULT,
    RestoreWindow,
    ResultPanel,
    RoundButton,
    TEXT,
    TEXT_FAINT,
    TEXT_MUTED,
    _ERROR_MARKERS,
    _INFO_MARKERS,
    _LOG_MAX_LINES,
    _LOG_TRIM_LINES,
    _OK_MARKERS,
    config,
    design,
    i18n,
    output,
    subprocess,
    tk,
    ttk,
)


class LogMixin:
    """Result area, log view, footer and the open-* actions."""

    def _build_result_area(self) -> None:
        """One area, two views: the result counters or the full log.

        Both live in the same grid cell, so ``self.logbox`` always exists (a
        language switch rebuilds it instead of losing it).
        """
        self._result_area = tk.Frame(self.root, bg=BACKGROUND, height=self._result_height)
        self._result_area.grid(row=ROW_RESULT, column=0, sticky="nsew", padx=design.px(22),
                               pady=(design.px(4), design.px(6)))
        self._result_area.columnconfigure(0, weight=1)
        self._result_area.rowconfigure(0, weight=1)
        self._result_area.grid_propagate(False)

        self.result_panel = ResultPanel(self._result_area, i18n.t("gui.section.result"),
                                        i18n.t("gui.label.last_entries"), recent_lines=3)
        self.result_panel.grid(row=0, column=0, sticky="nsew")
        self._last_backup: Path | None = None
        last_kind = getattr(self, "_last_result_kind", None)
        last_values = getattr(self, "_last_result_values", None)
        if last_kind and last_values is not None:
            # A language switch (or a theme rebuild) must not wipe the card of
            # the last run; the counters are still valid.
            self._render_stats(last_kind, last_values)
        else:
            self._rebuild_result_header()

        view = tk.Frame(self._result_area, bg=LOG_BG, highlightthickness=1,
                        highlightbackground=BORDER, bd=0)
        self._log_view = view
        view.columnconfigure(0, weight=1)
        view.rowconfigure(1, weight=1)

        header = tk.Frame(view, bg=LOG_BG)
        header.grid(row=0, column=0, sticky="ew", padx=design.px(12),
                    pady=(design.px(10), design.px(6)))
        header.columnconfigure(1, weight=1)
        tk.Label(header, text=i18n.t("gui.label.log").upper(), bg=LOG_BG, fg=TEXT_FAINT,
                 font=design.FONT_LABEL).grid(row=0, column=0, sticky="w")
        RoundButton(header, i18n.t("gui.button.back"), self._show_result_view,
                    style="quiet", height=28).grid(row=0, column=2, sticky="e")
        RoundButton(header, i18n.t("gui.button.clear"), self._clear_log, style="quiet",
                    height=28).grid(row=0, column=3, sticky="e", padx=(design.px(8), 0))

        frame = tk.Frame(view, bg=LOG_BG)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.logbox = tk.Text(frame, wrap="word", state="disabled", height=6, bg=LOG_BG,
                              fg=LOG_TEXT, insertbackground=TEXT, selectbackground=ACCENT,
                              relief="flat", bd=0, highlightthickness=0, font=design.FONT_MONO,
                              padx=design.px(12), pady=design.px(10), spacing1=1,
                              spacing3=1)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.logbox.yview,
                               style="Dark.Vertical.TScrollbar")
        self.logbox.configure(yscrollcommand=scroll.set)
        self.logbox.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        self.logbox.tag_configure("err", foreground=RED)
        self.logbox.tag_configure("ok", foreground=GREEN)
        self.logbox.tag_configure("info", foreground=ACCENT)
        self.logbox.tag_configure("dim", foreground=TEXT_MUTED)
        self._log_lines = 0

    def _show_log_view(self) -> None:
        """Switch the result area to the full log and let it take the space."""
        self.result_panel.grid_remove()
        self._log_view.grid(row=0, column=0, sticky="nsew")
        self._log_shown = True
        self._resize_result_area(self._log_height, weight=1)
        self.logbox.see("end")

    def _show_result_view(self) -> None:
        """Switch back to the counters."""
        self._log_view.grid_remove()
        self.result_panel.grid(row=0, column=0, sticky="nsew")
        self._log_shown = False
        self._resize_result_area(self._result_height, weight=0)
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
        self._log_lines += 1
        if self._log_lines > _LOG_MAX_LINES:
            self.logbox.delete("1.0", f"{_LOG_TRIM_LINES + 1}.0")
            self._log_lines -= _LOG_TRIM_LINES
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def _replay_log(self) -> None:
        for line in self._log_history:
            self._insert_log(line)

    def _clear_log(self) -> None:
        self._log_history = []
        self._log_lines = 0
        self.logbox.configure(state="normal")
        self.logbox.delete("1.0", "end")
        self.logbox.configure(state="disabled")
        self._refresh_recent()

    def _build_footer(self) -> None:
        """Status dot, status text, progress with percentage, quick links."""
        tk.Frame(self.root, bg=BORDER, height=1).grid(row=ROW_LINE_BOTTOM, column=0,
                                                      sticky="ew")
        footer = tk.Frame(self.root, bg=BACKGROUND)
        footer.grid(row=ROW_FOOTER, column=0, sticky="ew", padx=design.px(22),
                    pady=(design.px(8), design.px(14)))
        footer.columnconfigure(2, weight=1)
        self._footer = footer

        self._state_dot = tk.Canvas(footer, width=design.px(12), height=design.px(12),
                                    bg=BACKGROUND, highlightthickness=0, bd=0)
        self._state_dot.grid(row=0, column=0, sticky="w")
        self._set_state(TEXT_MUTED)

        tk.Label(footer, textvariable=self.status_var, bg=BACKGROUND, fg=TEXT_MUTED,
                 font=design.FONT_SMALL).grid(row=0, column=1, sticky="w",
                                              padx=(design.px(8), 0))
        # The bar stretches (and gives way) instead of pushing the buttons out.
        progress_holder = tk.Frame(footer, bg=BACKGROUND)
        progress_holder.grid(row=0, column=2, sticky="ew",
                             padx=(design.px(16), design.px(8)))
        progress_holder.columnconfigure(0, weight=1)
        self.progress = ProgressBar(progress_holder, width=180)
        self.progress.grid(row=0, column=0, sticky="ew")
        self.progress_label = tk.Label(footer, text="", bg=BACKGROUND, fg=TEXT_FAINT,
                                       font=design.FONT_SMALL)
        self.progress_label.grid(row=0, column=3, sticky="w",
                                 padx=(0, design.px(8)))

        self._cancel_button = RoundButton(footer, i18n.t("gui.button.cancel"),
                                          self._cancel_run, style="normal", height=30)
        self._cancel_button.grid(row=0, column=4, sticky="e", padx=(0, design.px(6)))
        self._cancel_button.grid_remove()

        RoundButton(footer, i18n.t("gui.button.undo"), self._open_restore,
                    style="normal", height=30).grid(row=0, column=5, sticky="e")
        RoundButton(footer, i18n.t("gui.button.open_logs"), self._open_logs,
                    style="quiet", height=30).grid(row=0, column=6, sticky="e",
                                                    padx=(design.px(6), 0))
        RoundButton(footer, i18n.t("gui.button.open_folder"), self._open_last,
                    style="quiet", height=30).grid(row=0, column=7, sticky="e",
                                                    padx=(design.px(6), 0))

    def _set_state(self, colour: str) -> None:
        """Colour the small dot in the status bar (idle / busy / problem)."""
        try:
            self._state_dot.delete("all")
            self._state_dot.create_oval(2, 2, 10, 10, fill=colour, outline="")
        except tk.TclError:
            pass

    def _rebuild_result_header(self, backup: str = "", export_dir: str = "") -> None:
        """Buttons of the result card: log details, the export, the backup."""
        for child in self.result_panel.header_right.winfo_children():
            child.destroy()
        RoundButton(self.result_panel.header_right, i18n.t("gui.button.details"),
                    self._show_log_view, style="quiet", height=28).pack(side="right")
        if export_dir:
            RoundButton(self.result_panel.header_right, i18n.t("gui.button.open_export"),
                        self._open_last, style="quiet", height=28).pack(
                            side="right", padx=(0, design.px(8)))
            RoundButton(self.result_panel.header_right, i18n.t("gui.button.copy_prompt"),
                        self._copy_prompt, style="quiet", height=28).pack(
                            side="right", padx=(0, design.px(8)))
        if backup:
            self._last_backup = Path(backup)
            RoundButton(self.result_panel.header_right, i18n.t("gui.button.open_backup"),
                        self._open_backup, style="quiet", height=28).pack(
                            side="right", padx=(0, design.px(8)))

    def _copy_prompt(self) -> None:
        """Put ``00_prompt.md`` of the last export on the clipboard.

        The button only exists after a successful export, so the file is there;
        a read error is swallowed rather than interrupting the interface.
        """
        outdir = output.last_stats("export").get("outdir")
        if not outdir:
            return
        try:
            text = (Path(outdir) / "00_prompt.md").read_text(encoding="utf-8")
        except OSError:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _xdg_open(self, path: Path) -> None:
        """Hand a file or folder to the desktop - no output, no waiting."""
        try:
            subprocess.Popen(["xdg-open", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

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
        if self._restore_window is not None:
            try:
                if self._restore_window.winfo_exists():
                    self._restore_window.lift()
                    self._restore_window.focus_set()
                    return
            except tk.TclError:
                pass
            self._restore_window = None
        window = RestoreWindow(self.root, self._run_restore, self.var_backup)
        self._restore_window = window
        window.bind("<Destroy>", self._restore_closed, add="+")

    def _restore_closed(self, event) -> None:
        """Forget the undo window once it is really gone."""
        if self._restore_window is not None and event.widget is self._restore_window:
            self._restore_window = None
