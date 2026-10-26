"""Preview card (what will happen) and result panel (counters + recent lines)."""

from __future__ import annotations

import tkinter as tk

from .. import i18n
from . import design
from .design import (BORDER, BORDER_SOFT, CARD, GREEN, SURFACE, TEXT, TEXT_FAINT,
                     TEXT_MUTED, YELLOW)

MAX_VALUE_LENGTH = 44


def _short(text: str, limit: int = MAX_VALUE_LENGTH) -> str:
    """Shorten ``text`` to ``limit`` characters, cutting at the front."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return "…" + text[-(limit - 1):]


def section_label(parent: tk.Misc, text: str, bg: str | None = None) -> tk.Label:
    """Abschnittstitel in normaler Schreibweise."""
    bg = CARD if bg is None else bg
    return tk.Label(parent, text=text, bg=bg, fg=TEXT,
                    font=design.FONT_LABEL, anchor="w")


class PreviewCard(tk.Frame):
    """Card with the aggregated result of the last preview."""

    def __init__(self, parent: tk.Misc, title: str) -> None:
        super().__init__(parent, bg=CARD, highlightthickness=0,
                         highlightbackground=BORDER, bd=0)
        self.columnconfigure(0, weight=1)

        inner = tk.Frame(self, bg=CARD)
        inner.grid(row=0, column=0, sticky="ew", padx=design.px(16), pady=design.px(14))
        inner.columnconfigure(0, weight=1)

        head = tk.Frame(inner, bg=CARD)
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)
        section_label(head, title).grid(row=0, column=0, sticky="w")
        self._summary = tk.Label(head, text="", bg=CARD, fg=TEXT_MUTED,
                                 font=design.FONT_SMALL, anchor="w")
        self._summary.grid(row=1, column=0, sticky="w", pady=(design.px(6), 0))

        self._body = tk.Frame(inner, bg=CARD, highlightthickness=0,
                              highlightbackground=BORDER_SOFT, bd=0)
        self._body.grid(row=1, column=0, sticky="ew", pady=(design.px(10), 0))
        self._body.columnconfigure(0, weight=1)
        self.hint("")

    def hint(self, text: str, colour: str | None = None) -> None:
        """Show only a hint line (no preview yet, no changes, outdated …)."""
        colour = TEXT_FAINT if colour is None else colour
        self._reset_body(CARD, BORDER_SOFT)
        self._summary.configure(text="", fg=TEXT_MUTED)
        tk.Label(self._body, text=text, bg=CARD, fg=colour, font=design.FONT_SMALL,
                 anchor="w", justify="left").grid(row=0, column=0, sticky="w",
                                                   padx=design.px(12),
                                                   pady=design.px(10))

    def show(self, summary: str, rows: list[tuple[str, str, str, str]],
             empty_text: str) -> None:
        """Show the aggregated plan; ``rows`` may be empty (= nothing to do)."""
        self._summary.configure(text="", fg=TEXT_MUTED)
        if not rows:
            self.hint(empty_text)
            return

        self._reset_body(CARD, BORDER_SOFT)
        table = tk.Frame(self._body, bg=CARD)
        table.grid(row=0, column=0, sticky="ew", pady=design.px(10))
        table.columnconfigure(4, weight=1)

        for index, (field, old, new, extra) in enumerate(rows):
            top = 0
            row_bg = SURFACE if index % 2 == 0 else CARD
            table.rowconfigure(index, minsize=design.px(design.ROW_HEIGHT))
            tk.Frame(table, bg=row_bg).grid(row=index, column=0, columnspan=5,
                                            sticky="nsew")
            tk.Label(table, text=field, bg=row_bg, fg=TEXT_MUTED, font=design.FONT_SMALL,
                     anchor="w", width=11).grid(row=index, column=0, sticky="w", pady=(top, 0))
            tk.Label(table, text=_short(old), bg=row_bg, fg=TEXT_MUTED,
                     font=design.FONT_SMALL, anchor="w").grid(
                         row=index, column=1, sticky="w", padx=(design.px(10), 0),
                         pady=(top, 0))
            tk.Label(table, text="→", bg=row_bg, fg=TEXT_FAINT,
                     font=design.FONT_SMALL).grid(row=index, column=2,
                                                  padx=design.px(10), pady=(top, 0))
            tk.Label(table, text=_short(new), bg=row_bg, fg=GREEN,
                     font=design.FONT_SMALL, anchor="w").grid(
                         row=index, column=3, sticky="w", pady=(top, 0))
            if extra:
                tk.Label(table, text=extra, bg=row_bg, fg=TEXT_FAINT,
                         font=design.FONT_SMALL, anchor="e").grid(
                             row=index, column=4, sticky="e", padx=(design.px(12), 0),
                             pady=(top, 0))

        if summary:
            self._summary.configure(text=summary)

    def mark_outdated(self, text: str) -> None:
        """Flag the shown preview as outdated (inputs changed since then)."""
        self._summary.configure(text=text, fg=YELLOW)

    def _reset_body(self, bg: str, border: str) -> None:
        for child in self._body.winfo_children():
            child.destroy()
        self._body.configure(bg=bg, highlightbackground=border)


class ResultPanel(tk.Frame):
    """Counters of the last run and the newest log lines."""

    def __init__(self, parent: tk.Misc, title: str, recent_title: str,
                 recent_lines: int = 4) -> None:
        super().__init__(parent, bg=CARD, highlightthickness=1,
                         highlightbackground=BORDER, bd=0)
        self.columnconfigure(0, weight=1)
        self._recent_lines = recent_lines

        inner = tk.Frame(self, bg=CARD)
        inner.grid(row=0, column=0, sticky="nsew", padx=design.px(16), pady=design.px(12))
        inner.columnconfigure(0, weight=1)
        inner.rowconfigure(1, weight=1)

        head = tk.Frame(inner, bg=CARD)
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(1, weight=1)
        section_label(head, title).grid(row=0, column=0, sticky="w")
        self.header_right = tk.Frame(head, bg=CARD)
        self.header_right.grid(row=0, column=1, sticky="e")

        columns = tk.Frame(inner, bg=CARD)
        columns.grid(row=1, column=0, sticky="nsew", pady=(design.px(10), 0))
        columns.columnconfigure(0, weight=1)

        self._counters = tk.Frame(columns, bg=CARD)
        self._counters.grid(row=0, column=0, sticky="nw")
        self.set_counters([])

        recent = tk.Frame(columns, bg=CARD)
        recent.grid(row=0, column=1, sticky="nw", padx=(design.px(24), 0))
        tk.Label(recent, text=recent_title, bg=CARD, fg=TEXT_FAINT,
                 font=design.FONT_LABEL, anchor="w").grid(row=0, column=0, sticky="w")
        self._recent = tk.Label(recent, text="", bg=CARD, fg=TEXT_MUTED,
                                font=design.FONT_MONO, anchor="nw", justify="left")
        self._recent.grid(row=1, column=0, sticky="w", pady=(design.px(6), 0))

    def set_counters(self, rows: list[tuple[str, str, str, str]]) -> None:
        """Fill the counter column: (colour, glyph, value, label) per row."""
        for child in self._counters.winfo_children():
            child.destroy()
        if not rows:
            tk.Label(self._counters, text=i18n.t("gui.result.none"), bg=CARD,
                     fg=TEXT_FAINT, font=design.FONT_SMALL, anchor="w").grid(
                         row=0, column=0, columnspan=3, sticky="w")
            return
        for index, (colour, glyph, value, label) in enumerate(rows):
            top = 0 if index == 0 else design.px(4)
            tk.Label(self._counters, text=glyph, bg=CARD, fg=colour,
                     font=design.FONT_SMALL).grid(row=index, column=0, sticky="w",
                                                  pady=(top, 0))
            tk.Label(self._counters, text=value, bg=CARD, fg=TEXT, width=9,
                     font=design.FONT_SMALL, anchor="e").grid(
                         row=index, column=1, sticky="e",
                         padx=(design.px(8), design.px(10)), pady=(top, 0))
            tk.Label(self._counters, text=label, bg=CARD, fg=TEXT_MUTED,
                     font=design.FONT_SMALL, anchor="w").grid(
                         row=index, column=2, sticky="w", pady=(top, 0))

    def set_recent(self, lines: list[str]) -> None:
        """Show the newest log lines (the last ``recent_lines`` are kept)."""
        kept: list[str] = []
        for line in lines:
            text = line.strip()
            if not text or set(text) <= set("=#-"):
                continue
            kept.append(text)
        kept = kept[-self._recent_lines:]
        self._recent.configure(text="\n".join(_short(line, 46) for line in kept))
