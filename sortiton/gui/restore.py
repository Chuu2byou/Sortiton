"""Undo window: pick a run journal, see what undoing it would do, then undo it.

Reading a journal is instant, so the preview is drawn straight from the file -
no worker thread and no second task run. Writing goes through the normal task
path (:func:`sortiton.tasks.cmd_restore`), so log window, progress bar and the
result card behave exactly like on the other pages.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable

from .. import i18n, journal
from . import design
from .confirm import ask_confirm
from .design import (ACCENT, ACCENT_TEXT, BACKGROUND, BORDER, CARD, FIELD, TEXT,
                     TEXT_FAINT, TEXT_MUTED)
from .panels import PreviewCard, section_label
from .widgets import RoundButton

# How many concrete undo steps the preview lists before it only counts them.
MAX_ROWS = 4

# A callback of the window: (journal, keep_copies) -> start the undo run.
RunHook = Callable[[Path, bool], None]


def _basename(value: object) -> str:
    """File name of a journal path; empty stays empty."""
    text = str(value or "")
    return Path(text).name if text else ""


def undo_rows(events: list[dict]) -> list[tuple[str, str, str, str]]:
    """Preview rows: one line per undo step, the first few with real names."""
    rows: list[tuple[str, str, str, str]] = []
    for event in events[:MAX_ROWS]:
        op = str(event.get("op"))
        if str(event.get("status") or "ok") == "error":
            rows.append((i18n.t("gui.restore.op.failed"),
                         _basename(event.get("path")), "", ""))
        elif op == "tags":
            values = list((event.get("before") or {}).items())[:2]
            detail = ", ".join(f"{key}: {value}" for key, value in values)
            rows.append((i18n.t("gui.restore.op.tags"),
                         _basename(event.get("path")), detail, ""))
        elif op == "copy":
            rows.append((i18n.t("gui.restore.op.copy"),
                         _basename(event.get("target")), "", ""))
        elif op in ("rename", "sort"):
            rows.append((i18n.t("gui.restore.op.move"),
                         _basename(event.get("target")),
                         _basename(event.get("source")), ""))
        else:
            rows.append((i18n.t("gui.restore.op.other"),
                         _basename(event.get("path")), "", ""))

    if len(events) > MAX_ROWS:
        rows.append(("", "", "",
                     i18n.t("gui.restore.more", count=len(events) - MAX_ROWS)))
    return rows


def undo_summary(events: list[dict]) -> str:
    """One line: how many events of which kind this journal holds."""
    counts = journal.summarize(events)
    parts = ", ".join(f"{op} {count}" for op, count in counts.items())
    return i18n.t("gui.restore.summary", total=len(events), parts=parts or "-")


class RestoreWindow(tk.Toplevel):
    """Pick a journal, look at the plan, undo the run."""

    def __init__(self, parent: tk.Misc, on_run: RunHook,
                 backup: tk.BooleanVar) -> None:
        super().__init__(parent)
        self._on_run = on_run
        self._backup = backup
        self._journals = journal.find_journals()
        self._chosen: Path | None = None

        self.title(i18n.t("gui.restore.title"))
        self.configure(bg=BACKGROUND)
        self.transient(parent)
        width, height = 900, 560
        x = max(parent.winfo_rootx() + (parent.winfo_width() - width) // 2, 0)
        y = max(parent.winfo_rooty() + (parent.winfo_height() - height) // 2, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(720, 460)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = tk.Frame(self, bg=BACKGROUND)
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        tk.Label(header, text=i18n.t("gui.restore.heading"), bg=BACKGROUND, fg=TEXT,
                 font=design.FONT_SECTION).grid(row=0, column=0, sticky="w")
        tk.Label(header, text=i18n.t("gui.restore.note"), bg=BACKGROUND, fg=TEXT_MUTED,
                 font=design.FONT_SMALL, justify="left", wraplength=840).grid(
                     row=1, column=0, sticky="w", pady=(2, 0))

        body = tk.Frame(self, bg=BACKGROUND)
        body.grid(row=1, column=0, sticky="nsew", padx=20)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=CARD, highlightthickness=1,
                        highlightbackground=BORDER, bd=0)
        left.grid(row=0, column=0, sticky="ns")
        section_label(left, i18n.t("gui.restore.journals")).pack(anchor="w", padx=14,
                                                                 pady=(12, 6))
        listing = tk.Frame(left, bg=CARD)
        listing.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self._list = tk.Listbox(listing, bg=FIELD, fg=TEXT, selectbackground=ACCENT,
                                selectforeground=ACCENT_TEXT, activestyle="none",
                                highlightthickness=0, bd=0, width=38, height=14,
                                font=design.FONT_MONO)
        bar = ttk.Scrollbar(listing, orient="vertical", command=self._list.yview,
                            style="Dark.Vertical.TScrollbar")
        self._list.configure(yscrollcommand=bar.set)
        self._list.pack(side="left", fill="both", expand=True)
        bar.pack(side="left", fill="y")
        self._list.bind("<<ListboxSelect>>", self._pick)

        self._card = PreviewCard(body, i18n.t("gui.section.preview"))
        self._card.grid(row=0, column=1, sticky="nsew", padx=(14, 0))

        footer = tk.Frame(self, bg=BACKGROUND)
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 16))
        footer.columnconfigure(0, weight=1)
        self._status = tk.StringVar(value="")
        tk.Label(footer, textvariable=self._status, bg=BACKGROUND, fg=TEXT_FAINT,
                 font=design.FONT_SMALL).grid(row=0, column=0, sticky="w")

        buttons = tk.Frame(footer, bg=BACKGROUND)
        buttons.grid(row=1, column=0, sticky="e", pady=(10, 0))
        RoundButton(buttons, i18n.t("gui.button.close"), self.destroy,
                    style="normal", height=32).pack(side="left")
        self._undo_button = RoundButton(buttons, i18n.t("gui.restore.run"), self._undo,
                                        style="apply", height=32)
        self._undo_button.pack(side="left", padx=(8, 0))

        self.bind("<Escape>", lambda _e: self.destroy())
        self._fill()

    def _fill(self) -> None:
        """List the journals and preselect the newest one."""
        if not self._journals:
            self._card.hint(i18n.t("gui.restore.none"))
            self._undo_button.set_enabled(False)
            self._status.set(i18n.t("gui.restore.none"))
            return

        for path in self._journals:
            events = journal.plan_restore(path)
            counts = ", ".join(f"{op} {count}"
                               for op, count in journal.summarize(events).items())
            entry = f"{path.stem}  ·  {len(events)}"
            self._list.insert("end", entry + (f"  ({counts})" if counts else ""))

        self._list.selection_set(0)
        self._pick()

    def _selected(self) -> Path | None:
        selection = self._list.curselection()
        if not selection:
            return None
        index = int(selection[0])
        return self._journals[index] if index < len(self._journals) else None

    def _pick(self, _event: object = None) -> None:
        """Someone picked a journal: show what undoing it would do."""
        path = self._selected()
        if path is None:
            return
        self._chosen = path
        events = journal.plan_restore(path)

        if not events:
            self._card.hint(i18n.t("gui.restore.empty"))
            self._undo_button.set_enabled(False)
            self._status.set(i18n.t("gui.restore.empty"))
            return

        self._card.show(undo_summary(events), undo_rows(events),
                        i18n.t("gui.restore.empty"))
        self._undo_button.set_enabled(True)
        self._status.set(undo_summary(events))

    def _undo(self) -> None:
        """Ask for confirmation, then hand the journal to the normal task path."""
        path = self._chosen
        if path is None:
            return
        events = journal.plan_restore(path)
        if not events:
            return

        confirmed, options = ask_confirm(
            self,
            title=i18n.t("gui.confirm.restore.title"),
            heading=i18n.t("gui.confirm.restore.title"),
            text=i18n.t("gui.confirm.restore.text", changes=len(events)),
            note=i18n.t("gui.restore.note"),
            ok_text=i18n.t("gui.confirm.ok"),
            cancel_text=i18n.t("gui.button.cancel"),
            options=[("backup", i18n.t("gui.confirm.backup"), self._backup.get()),
                     ("keep_copies", i18n.t("gui.confirm.keep_copies"), False)])
        if not confirmed:
            return

        self._backup.set(bool(options.get("backup", True)))
        keep_copies = bool(options.get("keep_copies", False))
        journal_path = path
        self.destroy()
        self._on_run(journal_path, keep_copies)
