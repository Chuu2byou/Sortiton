"""Settings window: external tools status and language."""

from __future__ import annotations

import tkinter as tk

from .. import external, i18n
from . import design
from .design import (BACKGROUND, BORDER, CARD, GREEN, TEXT, TEXT_FAINT, TEXT_MUTED,
                     YELLOW)
from .widgets import Pill, RoundButton, Segments


class PreferencesWindow:
    """Toplevel showing the external tools and the language switch."""

    def __init__(self, parent: tk.Misc, language: tk.StringVar, on_language) -> None:
        self.window = tk.Toplevel(parent)
        self.window.title(i18n.t("gui.settings.title"))
        self.window.configure(bg=BACKGROUND)
        self.window.transient(parent.winfo_toplevel())
        self.window.resizable(False, False)
        self.window.columnconfigure(0, weight=1)

        body = tk.Frame(self.window, bg=BACKGROUND)
        body.grid(row=0, column=0, sticky="nsew", padx=20, pady=18)
        body.columnconfigure(0, weight=1)

        tk.Label(body, text=i18n.t("gui.settings.heading"), bg=BACKGROUND, fg=TEXT,
                 font=design.FONT_SECTION, anchor="w").grid(row=0, column=0, sticky="w")

        self._tools_card(body, 1)
        self._language_card(body, 2, language, on_language)

        footer = tk.Frame(body, bg=BACKGROUND)
        footer.grid(row=3, column=0, sticky="e", pady=(16, 0))
        RoundButton(footer, i18n.t("gui.button.close"), self.window.destroy,
                    style="normal", height=34).pack()

        self.window.bind("<Escape>", lambda _event: self.window.destroy())
        self.window.update_idletasks()
        width = max(self.window.winfo_reqwidth(), 420)
        x = max(parent.winfo_rootx() + (parent.winfo_width() - width) // 2, 0)
        y = max(parent.winfo_rooty() + (parent.winfo_height() - 260) // 3, 0)
        self.window.geometry(f"{width}x{self.window.winfo_reqheight()}+{x}+{y}")

    def _card(self, parent: tk.Misc, row: int) -> tk.Frame:
        outer = tk.Frame(parent, bg=CARD, highlightthickness=1,
                         highlightbackground=BORDER, bd=0)
        outer.grid(row=row, column=0, sticky="ew", pady=(14, 0))
        outer.columnconfigure(0, weight=1)
        inner = tk.Frame(outer, bg=CARD)
        inner.grid(row=0, column=0, sticky="ew", padx=16, pady=14)
        inner.columnconfigure(0, weight=1)
        return inner

    def _tools_card(self, parent: tk.Misc, row: int) -> None:
        """One pill per tool from :data:`external.TOOLS`, plus install hints.

        The list is built from the registry, never per program, so a new tool
        only has to be added to ``external.TOOLS``.
        """
        card = self._card(parent, row)
        tk.Label(card, text=i18n.t("gui.settings.tools").upper(), bg=CARD,
                 fg=TEXT_FAINT, font=design.FONT_LABEL, anchor="w").grid(
                     row=0, column=0, sticky="w")

        pills = tk.Frame(card, bg=CARD)
        pills.grid(row=1, column=0, sticky="w", pady=(8, 0))
        missing: list[external.Tool] = []
        for tool in external.TOOLS:
            if external.available(tool):
                version = external.version(tool)
                text = (i18n.t("gui.chip.tool_ok", tool=tool.key, version=version)
                        if version else i18n.t("gui.chip.tool_ok_noversion", tool=tool.key))
                Pill(pills, text, GREEN).pack(side="left", padx=(0, 8))
            else:
                Pill(pills, i18n.t("gui.chip.tool_missing", tool=tool.key),
                     YELLOW).pack(side="left", padx=(0, 8))
                missing.append(tool)

        tk.Label(card, text=i18n.t("gui.settings.tools_hint"), bg=CARD,
                 fg=TEXT_MUTED, font=design.FONT_SMALL, anchor="w", justify="left",
                 wraplength=380).grid(row=2, column=0, sticky="w", pady=(8, 0))

        hint_row = 3
        for tool in missing:
            if not tool.hint_key:
                continue
            tk.Label(card, text=i18n.t(tool.hint_key).strip(), bg=CARD, fg=YELLOW,
                     font=design.FONT_SMALL, anchor="w", justify="left",
                     wraplength=380).grid(row=hint_row, column=0, sticky="w", pady=(6, 0))
            hint_row += 1

    def _language_card(self, parent: tk.Misc, row: int, language: tk.StringVar,
                       on_language) -> None:
        card = self._card(parent, row)
        tk.Label(card, text=i18n.t("gui.settings.language").upper(), bg=CARD,
                 fg=TEXT_FAINT, font=design.FONT_LABEL, anchor="w").grid(
                     row=0, column=0, sticky="w")
        Segments(card, [("en", i18n.t("gui.language.en")), ("de", i18n.t("gui.language.de"))],
                 language, command=on_language, height=32,
                 font=design.FONT_SMALL).grid(row=1, column=0, sticky="w", pady=(8, 0))
        tk.Label(card, text=i18n.t("gui.settings.language_hint"), bg=CARD,
                 fg=TEXT_MUTED, font=design.FONT_SMALL, anchor="w", justify="left",
                 wraplength=380).grid(row=2, column=0, sticky="w", pady=(8, 0))
