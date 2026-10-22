"""Confirmation window shown before a run that changes files."""

from __future__ import annotations

import tkinter as tk
from typing import cast

from . import design
from .design import BACKGROUND, FIELD, TEXT, TEXT_MUTED, YELLOW
from .widgets import RoundButton


def ask_confirm(parent: tk.Misc, *, title: str, heading: str, text: str,
                ok_text: str, cancel_text: str,
                options: list[tuple[str, str, bool]] | None = None,
                note: str = "") -> tuple[bool, dict[str, bool]]:
    """Ask for confirmation."""
    result: dict[str, bool] = {}
    window = tk.Toplevel(parent)
    window.withdraw()
    window.title(title)
    window.configure(bg=BACKGROUND)
    window.transient(parent.winfo_toplevel())
    window.resizable(False, False)

    state = {"confirmed": False}

    body = tk.Frame(window, bg=BACKGROUND)
    body.grid(row=0, column=0, sticky="nsew", padx=design.px(20), pady=design.px(18))
    body.columnconfigure(0, weight=1)

    tk.Label(body, text=heading, bg=BACKGROUND, fg=TEXT, font=design.FONT_SECTION,
             anchor="w", justify="left").grid(row=0, column=0, sticky="w")
    tk.Label(body, text=text, bg=BACKGROUND, fg=TEXT_MUTED, font=design.FONT_SMALL,
             anchor="w", justify="left", wraplength=design.px(480)).grid(
                 row=1, column=0, sticky="w", pady=(design.px(8), 0))

    if note:
        tk.Label(body, text=note, bg=BACKGROUND, fg=YELLOW, font=design.FONT_SMALL,
                 anchor="w", justify="left", wraplength=design.px(480)).grid(
                     row=2, column=0, sticky="w", pady=(design.px(8), 0))

    variables: dict[str, tk.BooleanVar] = {}
    if options:
        box = tk.Frame(body, bg=BACKGROUND)
        box.grid(row=3, column=0, sticky="w", pady=(design.px(14), 0))
        for index, (key, label, default) in enumerate(options):
            variable = tk.BooleanVar(value=default)
            variables[key] = variable
            result[key] = bool(default)
            tk.Checkbutton(box, text=label, variable=variable, bg=BACKGROUND, fg=TEXT,
                           font=design.FONT_SMALL, activebackground=BACKGROUND,
                           activeforeground=TEXT, selectcolor=FIELD, bd=0,
                           highlightthickness=0, anchor="w").grid(
                               row=index, column=0, sticky="w", pady=(0, design.px(4)))

    buttons = tk.Frame(body, bg=BACKGROUND)
    buttons.grid(row=4, column=0, sticky="e", pady=(design.px(20), 0))

    def close(confirmed: bool) -> None:
        state["confirmed"] = confirmed
        result.update({key: bool(variable.get())
                       for key, variable in variables.items()})
        window.destroy()

    RoundButton(buttons, cancel_text, lambda: close(False), style="normal",
                height=36).pack(side="left")
    RoundButton(buttons, ok_text, lambda: close(True), style="apply",
                height=36).pack(side="left", padx=(design.px(10), 0))

    window.bind("<Escape>", lambda _event: close(False))
    window.protocol("WM_DELETE_WINDOW", lambda: close(False))

    window.update_idletasks()
    x = max(parent.winfo_rootx() + (parent.winfo_width() - window.winfo_width()) // 2, 0)
    y = max(parent.winfo_rooty() + (parent.winfo_height() - window.winfo_height()) // 3, 0)
    window.geometry(f"+{x}+{y}")
    window.deiconify()
    window.grab_set()
    window.wait_window()

    return state["confirmed"], result
