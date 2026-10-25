"""Rules card, rules editor and the LLM import dialog."""

from __future__ import annotations

from ...fileops import atomic_write_text
from ..common import (
    ACCENT,
    BACKGROUND,
    BORDER,
    CARD,
    GREEN,
    LOG_BG,
    LOG_TEXT,
    Pill,
    RoundButton,
    TEXT,
    TEXT_MUTED,
    YELLOW,
    _ask_yes_no,
    _show_error,
    ask_choice,
    config,
    design,
    i18n,
    rules,
    tk,
    ttk,
)
from .base import GuiBase


class RulesMixin(GuiBase):
    """Rules card, rules editor and the LLM import dialog."""

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
                Pill(pills, i18n.t(key, count=count), GREEN)
                shown += 1
        if not shown:
            tk.Label(pills, text=i18n.t("gui.pill.none"), bg=CARD, fg=TEXT_MUTED,
                     font=design.FONT_SMALL)

        builtin = status["builtin_artists"] + status["builtin_genres"]
        Pill(pills, i18n.t("gui.pill.builtin", count=builtin),
             YELLOW if warnings else TEXT_MUTED)
        if warnings:
            Pill(pills, i18n.t("gui.pill.warnings", count=warnings), YELLOW)
        self._layout_rule_pills()

    def _layout_rule_pills(self, _event=None) -> None:
        """Wrap rule badges to the available card width instead of clipping them."""
        pills = getattr(self, "_rules_pills", None)
        if pills is None:
            return
        width = pills.winfo_width()
        if width <= 1:
            return
        children = pills.winfo_children()
        if not children:
            return

        gap = design.px(8)
        row_height = max(child.winfo_reqheight() for child in children)
        x = 0
        y = 0
        for child in children:
            child_width = child.winfo_reqwidth()
            if x and x + child_width > width:
                x = 0
                y += row_height + gap
            child.place(x=x, y=y)
            x += child_width + gap
        pills.configure(height=y + row_height)

    def _rules_editor(self, prefill: str | None = None, restored: bool = False) -> None:
        """Small editor window for my_rules.ini."""
        if self._rules_window is not None:
            try:
                if self._rules_window.winfo_exists():
                    self._rules_window.lift()
                    self._rules_window.focus_set()
                    if prefill is not None:
                        current = self._rules_text.get("1.0", "end-1c") \
                            if self._rules_text is not None else ""
                        if current.strip() and not _ask_yes_no(
                                i18n.t("gui.rules.confirm_replace.title"),
                                i18n.t("gui.rules.confirm_replace.text")):
                            return
                        self._set_editor_text(prefill)
                        self._set_rules_status(i18n.t("gui.rules.status.prefilled"), YELLOW)
                    return
            except tk.TclError:
                pass
            self._rules_window = None

        window = tk.Toplevel(self.root)
        self._rules_window = window
        window.title(i18n.t("gui.rules.editor.title"))
        window.configure(bg=BACKGROUND)
        window.transient(self.root)
        width, height = design.px(860), design.px(640)
        x = max(self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2, 0)
        y = max(self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2, 0)
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.minsize(design.px(640), design.px(440))
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)

        header = tk.Frame(window, bg=BACKGROUND)
        header.grid(row=0, column=0, sticky="ew", padx=design.px(20),
                    pady=(design.px(16), design.px(8)))
        tk.Label(header, text=i18n.t("gui.rules.editor.heading"), font=design.FONT_SECTION,
                 bg=BACKGROUND, fg=TEXT).grid(row=0, column=0, sticky="w")
        tk.Label(header, text=i18n.t("gui.rules.editor.hint", path=config.RULES_FILE),
                 font=design.FONT_SMALL, bg=BACKGROUND, fg=TEXT_MUTED,
                 wraplength=design.px(800), justify="left").grid(
                     row=1, column=0, sticky="w", pady=(design.px(2), 0))

        frame = tk.Frame(window, bg=LOG_BG, highlightthickness=1,
                         highlightbackground=BORDER, bd=0)
        frame.grid(row=1, column=0, sticky="nsew", padx=design.px(20))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self._rules_text = tk.Text(frame, wrap="none", undo=True, bg=LOG_BG, fg=LOG_TEXT,
                                   insertbackground=TEXT, selectbackground=ACCENT,
                                   relief="flat", bd=0, highlightthickness=0,
                                   font=design.FONT_MONO, padx=design.px(12),
                                   pady=design.px(10))
        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=self._rules_text.yview,
                                 style="Dark.Vertical.TScrollbar")
        x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=self._rules_text.xview,
                                 style="Dark.Horizontal.TScrollbar")
        self._rules_text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self._rules_text.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        disk_text = self._read_rules_file() or ""
        self._rules_disk_text = disk_text
        content = prefill if prefill is not None else disk_text
        generated_template = not content.strip() and prefill is None
        if generated_template:
            content = rules.rules_template()
        self._rules_text.insert("1.0", content)
        if generated_template:
            # The template is a starting point, not an unsaved user change.
            self._rules_disk_text = content

        footer = tk.Frame(window, bg=BACKGROUND)
        footer.grid(row=2, column=0, sticky="ew", padx=design.px(20),
                    pady=(design.px(10), design.px(16)))
        footer.columnconfigure(0, weight=1)
        self._rules_status = tk.StringVar(value="")
        self._rules_status_label = tk.Label(footer, textvariable=self._rules_status,
                                            bg=BACKGROUND, fg=TEXT_MUTED,
                                            font=design.FONT_SMALL)
        self._rules_status_label.grid(row=0, column=0, sticky="w")
        if prefill is not None and not restored:
            self._set_rules_status(i18n.t("gui.rules.status.prefilled"), YELLOW)

        buttons = tk.Frame(footer, bg=BACKGROUND)
        buttons.grid(row=1, column=0, sticky="e", pady=(design.px(10), 0))
        RoundButton(buttons, i18n.t("gui.button.insert_template"), self._insert_template,
                    style="quiet", height=34).pack(side="left")
        RoundButton(buttons, i18n.t("gui.button.builtin_rules"), self._insert_builtin,
                    style="quiet", height=34).pack(side="left", padx=(design.px(8), 0))
        RoundButton(buttons, i18n.t("gui.button.reload"), self._reload_rules,
                    style="quiet", height=34).pack(side="left", padx=(design.px(8), 0))
        RoundButton(buttons, i18n.t("gui.button.system_editor"), self._open_system_editor,
                    style="quiet", height=34).pack(side="left", padx=(design.px(8), 0))
        RoundButton(buttons, i18n.t("gui.button.cancel"), self._close_rules_editor,
                    style="normal", height=34).pack(side="left", padx=(design.px(8), 0))
        RoundButton(buttons, i18n.t("gui.button.save"), self._save_rules,
                    style="primary", height=34).pack(side="left", padx=(design.px(8), 0))

        window.protocol("WM_DELETE_WINDOW", self._close_rules_editor)
        window.bind("<Escape>", lambda _e: self._close_rules_editor())
        window.bind("<Control-s>", lambda _e: self._save_rules())

    def _set_rules_status(self, text: str, colour: str | None = None) -> None:
        if self._rules_status is not None:
            self._rules_status.set(text)
        if self._rules_status_label is not None:
            try:
                self._rules_status_label.configure(
                    fg=TEXT_MUTED if colour is None else colour)
            except tk.TclError:
                pass

    def _set_editor_text(self, text: str) -> None:
        """Replace the whole rules editor content with ``text``."""
        if self._rules_text is None:
            return
        self._rules_text.delete("1.0", "end")
        self._rules_text.insert("1.0", text)

    def _read_rules_file(self) -> str | None:
        """Current file content, or None when it is missing/unreadable."""
        try:
            return config.RULES_FILE.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            return None

    def _editor_content(self) -> str:
        """The text currently in the rules editor."""
        if self._rules_text is None:
            return ""
        try:
            return self._rules_text.get("1.0", "end-1c")
        except tk.TclError:
            return ""

    def _editor_dirty(self) -> bool:
        """True when the editor differs from the last loaded/saved content."""
        return self._editor_content().rstrip() != getattr(
            self, "_rules_disk_text", "").rstrip()

    def _close_rules_editor(self) -> None:
        """Close the editor, asking first when unsaved changes would be lost."""
        window = self._rules_window
        if window is None:
            return
        if self._editor_dirty() and not _ask_yes_no(
                i18n.t("gui.rules.confirm_discard.title"),
                i18n.t("gui.rules.confirm_discard.text")):
            return
        try:
            window.destroy()
        except tk.TclError:
            pass
        self._rules_window = None
        self._rules_text = None
        self._rules_status = None
        self._rules_status_label = None

    def _reload_rules(self) -> None:
        """Replace the editor content with the current file from disk."""
        disk = self._read_rules_file()
        if disk is None:
            self._set_rules_status(i18n.t("gui.rules.status.missing"), YELLOW)
            return
        if self._editor_dirty() and not _ask_yes_no(
                i18n.t("gui.rules.confirm_discard.title"),
                i18n.t("gui.rules.confirm_discard.text")):
            return
        self._set_editor_text(disk)
        self._rules_disk_text = disk
        self._set_rules_status(i18n.t("gui.rules.status.reloaded"), GREEN)

    def _llm_rules_import(self) -> None:
        """Paste dialog: an LLM answer -> its INI block -> the rules editor."""
        if self._llm_window is not None:
            try:
                if self._llm_window.winfo_exists():
                    self._llm_window.lift()
                    self._llm_window.focus_set()
                    return
            except tk.TclError:
                pass
            self._llm_window = None

        window = tk.Toplevel(self.root)
        self._llm_window = window
        window.title(i18n.t("gui.llm.title"))
        window.configure(bg=BACKGROUND)
        window.transient(self.root)
        width, height = design.px(780), design.px(520)
        x = max(self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2, 0)
        y = max(self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2, 0)
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.minsize(design.px(560), design.px(340))
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)

        header = tk.Frame(window, bg=BACKGROUND)
        header.grid(row=0, column=0, sticky="ew", padx=design.px(20),
                    pady=(design.px(16), design.px(8)))
        tk.Label(header, text=i18n.t("gui.llm.hint"), font=design.FONT_SMALL,
                 bg=BACKGROUND, fg=TEXT_MUTED, wraplength=design.px(720),
                 justify="left").grid(row=0, column=0, sticky="w")

        frame = tk.Frame(window, bg=LOG_BG, highlightthickness=1,
                         highlightbackground=BORDER, bd=0)
        frame.grid(row=1, column=0, sticky="nsew", padx=design.px(20))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self._llm_text = tk.Text(frame, wrap="none", undo=True, bg=LOG_BG, fg=LOG_TEXT,
                                 insertbackground=TEXT, selectbackground=ACCENT,
                                 relief="flat", bd=0, highlightthickness=0,
                                 font=design.FONT_MONO, padx=design.px(12),
                                 pady=design.px(10))
        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=self._llm_text.yview,
                                 style="Dark.Vertical.TScrollbar")
        x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=self._llm_text.xview,
                                 style="Dark.Horizontal.TScrollbar")
        self._llm_text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self._llm_text.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        footer = tk.Frame(window, bg=BACKGROUND)
        footer.grid(row=2, column=0, sticky="ew", padx=design.px(20),
                    pady=(design.px(10), design.px(16)))
        footer.columnconfigure(0, weight=1)
        self._llm_status = tk.StringVar(value="")
        self._llm_status_label = tk.Label(footer, textvariable=self._llm_status,
                                          bg=BACKGROUND, fg=TEXT_MUTED,
                                          font=design.FONT_SMALL,
                                          wraplength=design.px(720), justify="left")
        self._llm_status_label.grid(row=0, column=0, sticky="w")

        buttons = tk.Frame(footer, bg=BACKGROUND)
        buttons.grid(row=1, column=0, sticky="e", pady=(design.px(10), 0))
        RoundButton(buttons, i18n.t("gui.button.cancel"), window.destroy,
                    style="normal", height=34).pack(side="left")
        RoundButton(buttons, i18n.t("gui.button.apply_rules"), self._llm_rules_apply,
                    style="primary", height=34).pack(side="left", padx=(design.px(8), 0))

        window.bind("<Escape>", lambda _e: window.destroy())
        window.bind("<Control-Return>", lambda _e: self._llm_rules_apply())

    def _set_llm_status(self, text: str, colour: str = TEXT_MUTED) -> None:
        if self._llm_status is not None:
            self._llm_status.set(text)
        if self._llm_status_label is not None:
            try:
                self._llm_status_label.configure(fg=colour)
            except tk.TclError:
                pass

    def _llm_rules_apply(self) -> None:
        """Take the pasted answer, check its INI block and open the editor."""
        text = self._llm_text.get("1.0", "end-1c") if self._llm_text is not None else ""
        block = rules.extract_ini_block(text)
        if not block.strip():
            self._set_llm_status(i18n.t("gui.llm.status.empty"), YELLOW)
            return
        _parsed, warnings = rules.parse_custom_rules(block)
        for warning in warnings:
            self._log_line(i18n.t("gui.log.rule_warning", text=warning))
        if warnings:
            self._set_llm_status(i18n.t("gui.llm.status.warnings", count=len(warnings)),
                                 YELLOW)
        else:
            self._set_llm_status(i18n.t("gui.llm.status.ok"), GREEN)
        self._rules_editor(block)

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

        disk = self._read_rules_file()
        if disk is not None and disk != getattr(self, "_rules_disk_text", ""):
            choice = ask_choice(
                self.root,
                title=i18n.t("gui.rules.conflict.title"),
                heading=i18n.t("gui.rules.conflict.title"),
                text=i18n.t("gui.rules.conflict.text"),
                choices=[("reload", i18n.t("gui.button.reload")),
                         ("overwrite", i18n.t("gui.button.overwrite")),
                         ("cancel", i18n.t("gui.button.cancel"))])
            if choice == "cancel":
                return
            if choice == "reload":
                self._set_editor_text(disk)
                self._rules_disk_text = disk
                self._set_rules_status(i18n.t("gui.rules.status.reloaded"), YELLOW)
                return

        try:
            atomic_write_text(config.RULES_FILE, content)
        except OSError as error:
            _show_error(i18n.t("gui.dialog.save_failed.title"),
                        i18n.t("gui.dialog.save_failed.text", error=error))
            return
        self._rules_disk_text = content

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
        self._inputs_changed()

    def _open_system_editor(self) -> None:
        """Save and open the rules file in the system's default editor."""
        self._save_rules()
        if config.RULES_FILE.is_file():
            self._xdg_open(config.RULES_FILE)
            self._inputs_changed()
