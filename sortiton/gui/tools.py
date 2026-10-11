"""The "Tools" tab: one form per registered feature, built from ``FEATURES``.

Nothing here knows about the export. A form is generated from the feature's
:class:`~sortiton.features.base.Option` list, so a second feature (phase 4) only
needs a new entry in :mod:`sortiton.features`. The typed values live in
``app.var_tool`` and survive a language switch; this module only draws widgets
and reads them back.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import i18n
from ..features import FEATURES
from ..features.base import Feature, Option
from . import design
from .design import (ACCENT, BACKGROUND, BORDER, CARD, FIELD, FIELD_ACTIVE, TEXT,
                     TEXT_MUTED)
from .widgets import RoundButton, Segments

# Up to this many features are shown as segments; more need a combobox.
SEGMENT_LIMIT = 3

# Bool options driven by the action bar / the confirm dialog, not the form: a
# writing feature gets a preview/write pair and the shared backup switch. The
# fetch feature's "confirm" is the same idea - the GUI asks its own dialog
# before every download, so the raw checkbox stays out of the form.
_ACTION_FLAGS = {"apply", "backup", "confirm"}

# Fallback bounds for the spin boxes when a feature leaves minimum/maximum open.
_INT_MAX = 1_000_000
_FLOAT_STEP = 0.05


def make_tool_vars() -> dict[str, dict[str, tk.Variable]]:
    """One ``tk`` variable per feature option.

    Called once from :meth:`sortiton.gui.app.SortitonGUI._make_vars`; the
    variables are kept across a language switch so nothing the user typed is
    lost (the widgets are rebuilt, the values are not).
    """
    table: dict[str, dict[str, tk.Variable]] = {}
    for feature in FEATURES:
        table[feature.key] = {option.name: _make_var(option)
                              for option in feature.options}
    return table


def _make_var(option: Option) -> tk.Variable:
    """The widget variable for one option, seeded with its default."""
    if option.kind == "bool":
        return tk.BooleanVar(value=bool(option.default))
    return tk.StringVar(value="" if option.default is None else str(option.default))


def tool_value(option: Option, variable: tk.Variable) -> object:
    """Read one widget back as the type the feature expects.

    A number field that does not parse falls back to the option's default; the
    feature validates the range itself (see ``resolve_args``).
    """
    raw = variable.get()
    if option.kind == "bool":
        return bool(raw)
    text = str(raw).strip()
    if option.kind == "int":
        try:
            return int(text)
        except ValueError:
            return option.default
    if option.kind == "float":
        try:
            return float(text)
        except ValueError:
            return option.default
    return text


class ToolsTab(tk.Frame):
    """Feature picker plus the form of the selected feature."""

    def __init__(self, app, parent: tk.Frame) -> None:
        super().__init__(parent, bg=BACKGROUND)
        self.app = app
        self.columnconfigure(0, weight=1)
        self._forms: dict[str, tk.Frame] = {}
        self._build()

    def _build(self) -> None:
        row = 0
        if FEATURES:
            self._selection(row)
            row += 1
        for feature in FEATURES:
            self._forms[feature.key] = self._feature_card(feature, row)
            row += 1
        self._llm_row(row)
        self._show(self.app.var_tool_choice.get())

    def _llm_row(self, row: int) -> None:
        """Button that hands a pasted LLM answer to the rules editor.

        Kept on the tools tab (not in the action bar): it belongs to the
        export cycle, not to a running job.
        """
        frame = tk.Frame(self, bg=BACKGROUND)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        RoundButton(frame, i18n.t("gui.button.paste_llm"), self.app._llm_rules_import,
                    style="normal", height=34).pack(side="left")

    def _selection(self, row: int) -> None:
        """The feature picker: segments for a few features, else a combobox."""
        titles = [(feature.key, i18n.t(feature.title_key)) for feature in FEATURES]
        if len(titles) <= SEGMENT_LIMIT:
            Segments(self, titles, self.app.var_tool_choice, command=self._show,
                     height=34, surface=FIELD).grid(row=row, column=0, sticky="w",
                                                    pady=(0, 12))
            return

        current = self.app.var_tool_choice.get()
        by_key = dict(titles)
        labels = [text for _key, text in titles]
        by_label = {text: key for key, text in titles}
        display = tk.StringVar(value=by_key.get(current, labels[0]))
        box = ttk.Combobox(self, state="readonly", values=labels, textvariable=display,
                           width=max(len(text) for text in labels))
        box.grid(row=row, column=0, sticky="w", pady=(0, 12))
        box.bind("<<ComboboxSelected>>",
                 lambda _event: self._show(by_label.get(display.get(), FEATURES[0].key)))

    def _feature_card(self, feature: Feature, row: int) -> tk.Frame:
        """One card per feature; the holder is what gets shown or hidden."""
        holder = tk.Frame(self, bg=BACKGROUND)
        holder.grid(row=row, column=0, sticky="ew")
        holder.columnconfigure(0, weight=1)
        body = self.app._card(holder, 0, i18n.t(feature.title_key))
        inner = 0
        hint_key = f"gui.hint.{feature.key}"
        if i18n.t(hint_key) != hint_key:
            self.app._hint(body, inner, i18n.t(hint_key))
            inner += 2
        for option in feature.options:
            if option.kind == "bool" and option.name in _ACTION_FLAGS:
                continue        # shown as the action bar / the confirm switch
            inner = self._option_row(body, inner, feature, option)
        return holder

    def _option_row(self, body: tk.Frame, row: int, feature: Feature,
                    option: Option) -> int:
        """Draw one option; returns the next free grid row."""
        variable = self.app.var_tool[feature.key][option.name]
        label = i18n.t(option.help_key) if option.help_key else option.name
        if option.kind == "folder":
            widget = self.app._folder_row(body, row, label, variable)
        else:
            tk.Label(body, text=label, bg=CARD, fg=TEXT_MUTED, font=design.FONT_SMALL,
                     anchor="w", justify="left", wraplength=640).grid(
                         row=row, column=0, sticky="w", pady=(0, 5))
            widget = self._input(body, option, variable)
            widget.grid(row=row + 1, column=0, sticky="ew")
        self.app._tool_widgets[(feature.key, option.name)] = widget
        return row + 2

    def _input(self, parent: tk.Frame, option: Option, variable: tk.Variable) -> tk.Widget:
        if option.kind == "bool":
            return tk.Checkbutton(parent, variable=variable, bg=CARD, fg=TEXT,
                                  activebackground=CARD, activeforeground=TEXT,
                                  selectcolor=FIELD, highlightthickness=0, bd=0)
        if option.kind in ("int", "float"):
            return self._spinbox(parent, option, variable)
        if option.kind == "choice":
            return ttk.Combobox(parent, textvariable=variable,
                                values=list(option.choices), state="readonly")
        return self.app._path_entry(parent, variable)

    def _spinbox(self, parent: tk.Frame, option: Option,
                 variable: tk.Variable) -> tk.Spinbox:
        if option.kind == "float":
            low = 0.0 if option.minimum is None else float(option.minimum)
            high = 1.0 if option.maximum is None else float(option.maximum)
            increment: float = _FLOAT_STEP
        else:
            low = 0 if option.minimum is None else int(option.minimum)
            high = _INT_MAX if option.maximum is None else int(option.maximum)
            increment = 1
        return tk.Spinbox(parent, textvariable=variable, from_=low, to=high,
                          increment=increment, bg=FIELD, fg=TEXT, insertbackground=TEXT,
                          relief="flat", bd=0, buttonbackground=FIELD_ACTIVE,
                          highlightthickness=1, highlightbackground=BORDER,
                          highlightcolor=ACCENT, font=design.FONT, width=12)

    def _show(self, key: str) -> None:
        """Show the form of ``key`` and hide the others."""
        self.app.var_tool_choice.set(key)
        for feature_key, holder in self._forms.items():
            if feature_key == key:
                holder.grid()
            else:
                holder.grid_remove()
        # A writing feature gets preview/write buttons, a read-only one a single
        # run button - the action bar follows the selection.
        self.app._tools_actions()
