"""Preview card (what will happen) and result panel (counters + recent lines).

Fonts are read as ``design.FONT_*`` because :func:`design.load_fonts` rebinds
them.
"""

from __future__ import annotations

import tkinter as tk

from . import design
from .design import (BORDER, BORDER_SOFT, CARD, GREEN, SURFACE, TEXT, TEXT_FAINT,
                     TEXT_MUTED, YELLOW)

# Long values (paths, artist lists) are cut at the front so the meaningful
# end stays visible.
MAX_VALUE_LENGTH = 44


def _short(text: str, limit: int = MAX_VALUE_LENGTH) -> str:
    """Shorten ``text`` to ``limit`` characters, cutting at the front."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return "…" + text[-(limit - 1):]


def section_label(parent: tk.Misc, text: str, bg: str = CARD) -> tk.Label:
    """Small uppercase section title drawn on top of a card."""
    return tk.Label(parent, text=text.upper(), bg=bg, fg=TEXT_FAINT,
                    font=design.FONT_LABEL, anchor="w")


class PreviewCard(tk.Frame):
    """Card with the aggregated result of the last preview.

    Rows are ``(field, old, new, extra)`` - one row per changed field.
    """

    def __init__(self, parent: tk.Misc, title: str) -> None:
        super().__init__(parent, bg=CARD, highlightthickness=1,
                         highlightbackground=BORDER, bd=0)
        self.columnconfigure(0, weight=1)

        inner = tk.Frame(self, bg=CARD)
        inner.grid(row=0, column=0, sticky="ew", padx=16, pady=14)
        inner.columnconfigure(0, weight=1)

        head = tk.Frame(inner, bg=CARD)
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(1, weight=1)
        section_label(head, title).grid(row=0, column=0, sticky="w")
        self._summary = tk.Label(head, text="", bg=CARD, fg=TEXT_MUTED,
                                 font=design.FONT_SMALL, anchor="e")
        self._summary.grid(row=0, column=1, sticky="e")

        self._body = tk.Frame(inner, bg=CARD, highlightthickness=1,
                              highlightbackground=BORDER_SOFT, bd=0)
        self._body.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self._body.columnconfigure(0, weight=1)
        self.hint("")

    def hint(self, text: str, colour: str = TEXT_FAINT) -> None:
        """Show only a hint line (no preview yet, no changes, outdated …)."""
        self._reset_body(CARD, BORDER_SOFT)
        self._summary.configure(text="", fg=TEXT_MUTED)
        tk.Label(self._body, text=text, bg=CARD, fg=colour, font=design.FONT_SMALL,
                 anchor="w", justify="left").grid(row=0, column=0, sticky="w",
                                                  padx=12, pady=10)

    def show(self, summary: str, rows: list[tuple[str, str, str, str]],
             empty_text: str) -> None:
        """Show the aggregated plan; ``rows`` may be empty (= nothing to do)."""
        self._summary.configure(text="", fg=TEXT_MUTED)
        if not rows:
            self.hint(empty_text)
            return

        self._reset_body(SURFACE, BORDER_SOFT)
        table = tk.Frame(self._body, bg=SURFACE)
        table.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        table.columnconfigure(4, weight=1)

        for index, (field, old, new, extra) in enumerate(rows):
            top = 0 if index == 0 else 6
            tk.Label(table, text=field, bg=SURFACE, fg=TEXT_MUTED, font=design.FONT_SMALL,
                     anchor="w", width=11).grid(row=index, column=0, sticky="w", pady=(top, 0))
            tk.Label(table, text=_short(old), bg=SURFACE, fg=TEXT_FAINT,
                     font=design.FONT_SMALL, anchor="w").grid(
                         row=index, column=1, sticky="w", padx=(10, 0), pady=(top, 0))
            tk.Label(table, text="→", bg=SURFACE, fg=TEXT_FAINT,
                     font=design.FONT_SMALL).grid(row=index, column=2, padx=10, pady=(top, 0))
            tk.Label(table, text=_short(new), bg=SURFACE, fg=GREEN,
                     font=design.FONT_SMALL, anchor="w").grid(
                         row=index, column=3, sticky="w", pady=(top, 0))
            if extra:
                tk.Label(table, text=extra, bg=SURFACE, fg=TEXT_FAINT,
                         font=design.FONT_SMALL, anchor="e").grid(
                             row=index, column=4, sticky="e", padx=(12, 0), pady=(top, 0))

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
    """Counters of the last run and the newest log lines.

    ``self.header_right`` is an empty frame the window puts its buttons into.
    """

    def __init__(self, parent: tk.Misc, title: str, recent_title: str,
                 recent_lines: int = 4) -> None:
        super().__init__(parent, bg=CARD, highlightthickness=1,
                         highlightbackground=BORDER, bd=0)
        self.columnconfigure(0, weight=1)
        self._recent_lines = recent_lines

        inner = tk.Frame(self, bg=CARD)
        inner.grid(row=0, column=0, sticky="nsew", padx=16, pady=12)
        inner.columnconfigure(0, weight=1)
        inner.rowconfigure(1, weight=1)

        head = tk.Frame(inner, bg=CARD)
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(1, weight=1)
        section_label(head, title).grid(row=0, column=0, sticky="w")
        self.header_right = tk.Frame(head, bg=CARD)
        self.header_right.grid(row=0, column=1, sticky="e")

        columns = tk.Frame(inner, bg=CARD)
        columns.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        columns.columnconfigure(0, weight=1)

        self._counters = tk.Frame(columns, bg=CARD)
        self._counters.grid(row=0, column=0, sticky="nw")

        recent = tk.Frame(columns, bg=CARD)
        recent.grid(row=0, column=1, sticky="nw", padx=(24, 0))
        tk.Label(recent, text=recent_title, bg=CARD, fg=TEXT_FAINT,
                 font=design.FONT_LABEL, anchor="w").grid(row=0, column=0, sticky="w")
        self._recent = tk.Label(recent, text="", bg=CARD, fg=TEXT_MUTED,
                                font=design.FONT_MONO, anchor="nw", justify="left")
        self._recent.grid(row=1, column=0, sticky="w", pady=(6, 0))

    def set_counters(self, rows: list[tuple[str, str, str, str]]) -> None:
        """Fill the counter column: (colour, glyph, value, label) per row."""
        for child in self._counters.winfo_children():
            child.destroy()
        for index, (colour, glyph, value, label) in enumerate(rows):
            tk.Label(self._counters, text=glyph, bg=CARD, fg=colour,
                     font=design.FONT_SMALL).grid(row=index, column=0, sticky="w",
                                                  pady=(0 if index == 0 else 4, 0))
            tk.Label(self._counters, text=value, bg=CARD, fg=TEXT, width=9,
                     font=design.FONT_SMALL, anchor="e").grid(
                         row=index, column=1, sticky="e", padx=(8, 10),
                         pady=(0 if index == 0 else 4, 0))
            tk.Label(self._counters, text=label, bg=CARD, fg=TEXT_MUTED,
                     font=design.FONT_SMALL, anchor="w").grid(
                         row=index, column=2, sticky="w",
                         pady=(0 if index == 0 else 4, 0))

    def set_recent(self, lines: list[str]) -> None:
        """Show the newest log lines (the last ``recent_lines`` are kept).

        Separator lines are skipped and long lines shortened, so the preview
        keeps its height.
        """
        kept: list[str] = []
        for line in lines:
            text = line.strip()
            if not text or set(text) <= set("=#-"):
                continue
            kept.append(text)
        kept = kept[-self._recent_lines:]
        self._recent.configure(text="\n".join(_short(line, 46) for line in kept))
