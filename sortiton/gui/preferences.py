"""Settings window: external tools, fine-tuning of the tools and language.

The fine-tuning cards (report length, duplicate check, reader count) are drawn
from the feature descriptions, with the same :class:`~sortiton.gui.tools.OptionForm`
the tools tab uses - only the card split differs: what belongs to one run stays
in the tab, what belongs to the program lives here.

The window scrolls instead of growing past the screen edge: the cards are
generated, so their number follows the feature list and not this layout.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import external, i18n
from . import design
from .design import (BACKGROUND, BORDER, CARD, GREEN, TEXT, TEXT_FAINT, TEXT_MUTED,
                     YELLOW)
from .tools import OptionForm, feature_label, fine_tuning_cards, section_title
from .widgets import Pill, RoundButton, Segments


class PreferencesWindow:
    """Toplevel showing the external tools, the fine-tuning and the language."""

    def __init__(self, app) -> None:
        self.app = app
        parent = app.root
        self.window = tk.Toplevel(parent)
        self.window.title(i18n.t("gui.settings.title"))
        self.window.configure(bg=BACKGROUND)
        self.window.transient(parent.winfo_toplevel())
        self.window.resizable(True, True)
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

        viewport = tk.Frame(self.window, bg=BACKGROUND)
        viewport.grid(row=0, column=0, sticky="nsew")
        viewport.columnconfigure(0, weight=1)
        viewport.rowconfigure(0, weight=1)
        self._canvas = tk.Canvas(viewport, bg=BACKGROUND, highlightthickness=0, bd=0)
        self._scrollbar = ttk.Scrollbar(viewport, orient="vertical",
                                        command=self._canvas.yview,
                                        style="Dark.Vertical.TScrollbar")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._canvas.bind("<Configure>", self._resize_canvas)

        body = tk.Frame(self._canvas, bg=BACKGROUND)
        self._body_window = self._canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda _event: self._sync_scrollbar())

        self._content = tk.Frame(body, bg=BACKGROUND)
        self._content.pack(fill="both", expand=True, padx=design.px(20),
                           pady=design.px(18))
        self._content.columnconfigure(0, weight=1)

        self._head(self._content, 0)
        self._tools_card(self._content, 1)
        row = self._fine_tuning_cards(self._content, 2)
        self._language_card(self._content, row, app.var_language, app._language_changed)

        footer = tk.Frame(self._content, bg=BACKGROUND)
        footer.grid(row=row + 1, column=0, sticky="e", pady=(design.px(16), 0))
        RoundButton(footer, i18n.t("gui.button.close"), self.window.destroy,
                    style="normal", height=34).pack()

        # The wheel is bound on the window, not globally: this handler dies with
        # it, and the main window keeps its own scrolling.
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.window.bind(sequence, self._on_wheel, add="+")
        self.window.bind("<Escape>", lambda _event: self.window.destroy())

        self._place(parent)

    # -- window frame ---------------------------------------------------

    def _place(self, parent: tk.Misc) -> None:
        """Size the window to its content, but never past the screen edge."""
        self.window.update_idletasks()
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        content_width = self._content.winfo_reqwidth()
        content_height = self._content.winfo_reqheight()
        width = min(max(content_width, design.px(560)), screen_width - design.px(24))
        height = min(content_height, int(screen_height * 0.82))
        self.window.minsize(min(design.px(440), screen_width - design.px(24)),
                            min(design.px(320), height))
        x = max(parent.winfo_rootx() + (parent.winfo_width() - width) // 2, 0)
        y = max(parent.winfo_rooty() + (parent.winfo_height() - height) // 3, 0)
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.window.after_idle(self._sync_scrollbar)

    def _resize_canvas(self, event) -> None:
        """Let the cards take the full width and re-check the scrollbar."""
        self._canvas.itemconfigure(self._body_window, width=event.width)
        self._sync_scrollbar()

    def _sync_scrollbar(self) -> None:
        """Show a scrollbar only when the cards exceed the viewport."""
        region = self._canvas.bbox("all")
        if region is None:
            return
        self._canvas.configure(scrollregion=region)
        if region[3] - region[1] > self._canvas.winfo_height() + 1:
            self._scrollbar.grid(row=0, column=1, sticky="ns")
        else:
            self._scrollbar.grid_remove()

    def _on_wheel(self, event) -> str:
        """Scroll the settings window with the mouse wheel."""
        number = getattr(event, "num", None)
        if number == 4:
            amount = -1
        elif number == 5:
            amount = 1
        else:
            amount = -1 if getattr(event, "delta", 0) > 0 else 1
        self._canvas.yview_scroll(amount, "units")
        return "break"

    def _head(self, parent: tk.Misc, row: int) -> None:
        head = tk.Frame(parent, bg=BACKGROUND)
        head.grid(row=row, column=0, sticky="ew")
        tk.Label(head, text=i18n.t("gui.settings.heading"), bg=BACKGROUND, fg=TEXT,
                 font=design.FONT_SECTION, anchor="w").grid(row=0, column=0, sticky="w")
        tk.Label(head, text=i18n.t("gui.settings.scale",
                                   percent=round(design.UI_SCALE * 100)),
                 bg=BACKGROUND, fg=TEXT_FAINT, font=design.FONT_SMALL,
                 anchor="w").grid(row=1, column=0, sticky="w",
                                  pady=(design.px(2), 0))

    def _card(self, parent: tk.Misc, row: int, title: str = "") -> tk.Frame:
        outer = tk.Frame(parent, bg=CARD, highlightthickness=1,
                         highlightbackground=BORDER, bd=0)
        outer.grid(row=row, column=0, sticky="ew", pady=(design.px(14), 0))
        outer.columnconfigure(0, weight=1)
        inner = tk.Frame(outer, bg=CARD)
        inner.grid(row=0, column=0, sticky="ew", padx=design.px(16), pady=design.px(14))
        inner.columnconfigure(0, weight=1)
        if not title:
            return inner
        tk.Label(inner, text=title.upper(), bg=CARD, fg=TEXT_FAINT,
                 font=design.FONT_LABEL, anchor="w").grid(row=0, column=0, sticky="w")
        body = tk.Frame(inner, bg=CARD)
        body.grid(row=1, column=0, sticky="ew", pady=(design.px(12), 0))
        body.columnconfigure(0, weight=1)
        return body

    # -- cards ----------------------------------------------------------

    def _tools_card(self, parent: tk.Misc, row: int) -> None:
        """One pill per tool from :data:`external.TOOLS`, plus install hints.

        The list is built from the registry, never per program, so a new tool
        only has to be added to ``external.TOOLS``.
        """
        card = self._card(parent, row, i18n.t("gui.settings.tools"))

        pills = tk.Frame(card, bg=CARD)
        pills.grid(row=0, column=0, sticky="w")
        missing: list[external.Tool] = []
        for tool in external.TOOLS:
            if external.available(tool):
                version = external.version(tool)
                text = (i18n.t("gui.chip.tool_ok", tool=tool.key, version=version)
                        if version else i18n.t("gui.chip.tool_ok_noversion", tool=tool.key))
                Pill(pills, text, GREEN).pack(side="left", padx=(0, design.px(8)))
            else:
                Pill(pills, i18n.t("gui.chip.tool_missing", tool=tool.key),
                     YELLOW).pack(side="left", padx=(0, design.px(8)))
                missing.append(tool)

        tk.Label(card, text=i18n.t("gui.settings.tools_hint"), bg=CARD,
                 fg=TEXT_MUTED, font=design.FONT_SMALL, anchor="w", justify="left",
                 wraplength=design.px(400)).grid(row=1, column=0, sticky="w",
                                                 pady=(design.px(8), 0))

        hint_row = 2
        for tool in missing:
            if not tool.hint_key:
                continue
            tk.Label(card, text=i18n.t(tool.hint_key).strip(), bg=CARD, fg=YELLOW,
                     font=design.FONT_SMALL, anchor="w", justify="left",
                     wraplength=design.px(400)).grid(row=hint_row, column=0, sticky="w",
                                                     pady=(design.px(6), 0))
            hint_row += 1

    def _fine_tuning_cards(self, parent: tk.Misc, row: int) -> int:
        """One card per fine-tuning section; returns the next free row.

        The form is generated from the feature descriptions, so a second
        feature with fine-tuning only needs a new entry in ``_SECTION_OF``.
        With more than one feature the card title names its owner.
        """
        cards = fine_tuning_cards()
        if not cards:
            return row
        owners = {feature.key for feature, _section, _options in cards}
        form = OptionForm(self.app, width=design.px(520))
        for feature, section, options in cards:
            title = section_title(section)
            if len(owners) > 1:
                title = f"{feature_label(feature)} · {title}"
            body = self._card(parent, row, title)
            form.fields(body, feature, options)
            row += 1
        return row

    def _language_card(self, parent: tk.Misc, row: int, language: tk.StringVar,
                       on_language) -> None:
        card = self._card(parent, row, i18n.t("gui.settings.language"))
        Segments(card, [("en", i18n.t("gui.language.en")), ("de", i18n.t("gui.language.de"))],
                 language, command=on_language, height=34,
                 font=design.FONT_SMALL).grid(row=0, column=0, sticky="w")
        tk.Label(card, text=i18n.t("gui.settings.language_hint"), bg=CARD,
                 fg=TEXT_MUTED, font=design.FONT_SMALL, anchor="w", justify="left",
                 wraplength=design.px(400)).grid(row=1, column=0, sticky="w",
                                                 pady=(design.px(8), 0))
