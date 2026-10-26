"""The "Tools" tab: one form per registered feature, built from ``FEATURES``."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import config, i18n, settings
from ..features import FEATURES
from ..features.base import Feature, Option
from . import design
from .design import (ACCENT, BACKGROUND, BORDER, CARD, FIELD, FIELD_ACTIVE, TEXT,
                     TEXT_MUTED, YELLOW)
from .widgets import Pill, RoundButton, Segments, Switch

SEGMENT_LIMIT = 3

_ACTION_FLAGS = {"apply", "backup", "confirm"}

_INT_MAX = 1_000_000
_FLOAT_STEP = 0.05

_SECTION_TITLES = {
    "files": "gui.tools.section.files",
    "report": "gui.tools.section.report",
    "advanced": "gui.tools.section.advanced",
}

_DEFAULT_SECTION = "options"
_DEFAULT_SECTION_TITLE = "gui.section.options"

_LLM_FEATURES = {"export"}

FINE_TUNING_SECTIONS = ("report", "advanced")

_SECTION_OF = {
    "folder": "files", "output": "files", "file": "files", "root": "files",
    "chunk_chars": "report", "examples": "report", "jsonl": "report",
    "check_case": "report", "report_lang": "report",
    "fingerprint": "advanced", "fp_seconds": "advanced", "fp_threshold": "advanced",
    "threads": "advanced",
}

_SECTION_ORDER = ("files", "report", "advanced", _DEFAULT_SECTION)


def section_title(section: str) -> str:
    """Translated card title of a section (generic "Options" as fallback)."""
    return i18n.t(_SECTION_TITLES.get(section, _DEFAULT_SECTION_TITLE))


def feature_label(feature: Feature) -> str:
    """Short name for the picker (falls back to the part before the dash)."""
    key = f"gui.tool.{feature.key}"
    text = i18n.t(key)
    if text != key:
        return text
    title = i18n.t(feature.title_key)
    for separator in (" – ", " - ", " — "):
        if separator in title:
            return title.split(separator, 1)[0].strip()
    return title


def feature_run_label(feature: Feature | None) -> str:
    """Label of the single run button ("Start export" instead of "Run")."""
    if feature is None:
        return i18n.t("gui.button.run_tool")
    key = f"gui.tool.{feature.key}.run"
    text = i18n.t(key)
    return text if text != key else i18n.t("gui.button.run_tool")


def _sections(feature: Feature, wanted: tuple[str, ...]) -> list[tuple[str, list[Option]]]:
    """Group the visible options of ``feature`` into the cards named in ``wanted``."""
    table: dict[str, list[Option]] = {}
    for option in feature.options:
        if option.kind == "bool" and option.name in _ACTION_FLAGS:
            continue
        section = _SECTION_OF.get(option.name, _DEFAULT_SECTION)
        if section not in wanted:
            continue
        table.setdefault(section, []).append(option)
    return [(section, table[section]) for section in _SECTION_ORDER if table.get(section)]


def form_sections(feature: Feature) -> list[tuple[str, list[Option]]]:
    """The cards of the tools tab (everything that belongs to one run)."""
    return _sections(feature, tuple(name for name in _SECTION_ORDER
                                    if name not in FINE_TUNING_SECTIONS))


def fine_tuning_sections(feature: Feature) -> list[tuple[str, list[Option]]]:
    """The cards of the settings window (report length, duplicates, speed)."""
    return _sections(feature, FINE_TUNING_SECTIONS)


def fine_tuning_cards() -> list[tuple[Feature, str, list[Option]]]:
    """Fine-tuning cards of every feature: (feature, section, options)."""
    return [(feature, section, options)
            for feature in FEATURES
            for section, options in fine_tuning_sections(feature)]


def fine_tuning_items() -> list[tuple[Feature, Option]]:
    """Every option that lives in the settings instead of the tools form."""
    return [(feature, option)
            for feature, _section, options in fine_tuning_cards()
            for option in options]


def _stored_key(feature: Feature, option: Option) -> str:
    """Key of one fine-tuning value in the [tools] section of settings.ini."""
    return f"{feature.key}.{option.name}"


def _stored_text(option: Option, value: object) -> str:
    """A typed option value as the text that goes into settings.ini."""
    if option.kind == "bool":
        return "true" if value else "false"
    return str(value)


def _stored_value(option: Option, raw: str) -> str | bool | None:
    """Parse one stored value; ``None`` when it does not fit the option."""
    text = raw.strip()
    if option.kind == "bool":
        return text.lower() in ("1", "true", "yes", "on")
    if option.kind == "int":
        try:
            return str(int(text))
        except ValueError:
            return None
    if option.kind == "float":
        try:
            return str(float(text))
        except ValueError:
            return None
    if option.kind == "choice":
        return text if text in option.choices else None
    return text


def apply_stored(var_tool: dict[str, dict[str, tk.Variable]]) -> None:
    """Seed the fine-tuning variables from settings.ini."""
    stored = settings.read_tool_values()
    for feature, option in fine_tuning_items():
        raw = stored.get(_stored_key(feature, option))
        if raw is None:
            continue
        value = _stored_value(option, raw)
        if value is not None:
            var_tool[feature.key][option.name].set(value)


def stored_values(var_tool: dict[str, dict[str, tk.Variable]]) -> dict[str, str]:
    """The fine-tuning values as the text settings.save_tool_values() expects."""
    return {_stored_key(feature, option):
            _stored_text(option, tool_value(option, var_tool[feature.key][option.name]))
            for feature, option in fine_tuning_items()}


def _choice_label(option: Option, value: str) -> str:
    """Human label of a choice value (translated when a key exists)."""
    key = f"gui.choice.{option.name}.{value or 'ui'}"
    text = i18n.t(key)
    return text if text != key else value


def _layout(options: list[Option]) -> list[tuple[Option, int, int, int]]:
    """Place the options on a two-column grid: (option, row, column, span)."""
    cells: list[tuple[Option, int, int, int]] = []
    row = 0
    column = 0
    for option in options:
        if option.kind == "bool":
            if column:
                row += 2
                column = 0
            cells.append((option, row, 0, 2))
            row += 1
            continue
        if option.kind in ("folder", "text"):
            if column:
                row += 2
                column = 0
            cells.append((option, row, 0, 2))
            row += 2
            continue
        cells.append((option, row, column, 1))
        if column == 0:
            column = 1
        else:
            column = 0
            row += 2
    return cells


def make_tool_vars() -> dict[str, dict[str, tk.Variable]]:
    """One ``tk`` variable per feature option."""
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
    """Read one widget back as the type the feature expects."""
    raw = variable.get()
    if option.kind == "bool":
        return bool(raw)
    text = str(raw).strip()
    if option.kind == "int":
        try:
            value = int(text)
        except ValueError:
            return option.default
        if option.minimum is not None:
            value = max(value, int(option.minimum))
        if option.maximum is not None:
            value = min(value, int(option.maximum))
        return value
    if option.kind == "float":
        try:
            value = float(text)
        except ValueError:
            return option.default
        if option.minimum is not None:
            value = max(value, float(option.minimum))
        if option.maximum is not None:
            value = min(value, float(option.maximum))
        return value
    return text


class OptionForm:
    """Paints option cards into a body frame; shared by tab and settings."""

    def __init__(self, app, width: int | None = None) -> None:
        self.app = app
        base = width or design.px(640)
        self._wide = base
        self._narrow = max(base // 2 - design.px(20), design.px(120))

    def fields(self, body: tk.Frame, feature: Feature, options: list[Option]) -> None:
        """Draw ``options`` as a two-column grid inside the card body."""
        body.columnconfigure(0, weight=1, uniform="form")
        body.columnconfigure(1, weight=1, uniform="form")
        for option, grid_row, column, span in _layout(options):
            if option.kind == "bool":
                self._switch_row(body, grid_row, feature, option, span)
            else:
                self._field_cell(body, grid_row, column, span, feature, option)

    def _bind_responsive_wrap(self, parent: tk.Frame, label: tk.Label, *,
                              columns: int = 1, reserve: int = 24) -> None:
        """Adapt a form label's wrapping to the width of its grid cell."""
        def resize(event) -> None:
            available = max(event.width - design.px(reserve), design.px(120))
            label.configure(wraplength=max(design.px(120), available // columns))

        parent.bind("<Configure>", resize, add="+")

    def _field_cell(self, body: tk.Frame, row: int, column: int, span: int,
                    feature: Feature, option: Option) -> None:
        """Label above the input; long fields span both columns."""
        variable = self.app.var_tool[feature.key][option.name]
        if feature.key == "export" and option.name == "output":
            label = i18n.t("gui.export.output",
                           path=config.display_path(config.EXPORT_DIR))
        else:
            label = i18n.t(option.help_key) if option.help_key else option.name
        wrap = self._wide if span == 2 else self._narrow
        pad_right = design.px(14) if span == 1 and column == 0 else 0
        field_label = tk.Label(body, text=label, bg=CARD, fg=TEXT_MUTED,
                               font=design.FONT_SMALL, anchor="w", justify="left",
                               wraplength=wrap)
        self._bind_responsive_wrap(body, field_label,
                                   columns=2 if span == 1 else 1)
        field_label.grid(row=row, column=column, columnspan=span, sticky="ew",
                         padx=(0, pad_right), pady=(0, design.px(5)))
        widget = self._input(body, option, variable)
        widget.grid(row=row + 1, column=column, columnspan=span, sticky="ew",
                    padx=(0, pad_right), pady=(0, design.px(12)))
        self.app._tool_widgets[(feature.key, option.name)] = widget

    def _switch_row(self, body: tk.Frame, row: int, feature: Feature,
                    option: Option, span: int) -> None:
        """A switch that belongs to a full-width, clickable row."""
        variable = self.app.var_tool[feature.key][option.name]
        label = i18n.t(option.help_key) if option.help_key else option.name
        line = tk.Frame(body, bg=CARD)
        line.grid(row=row, column=0, columnspan=span, sticky="ew",
                  pady=(0, design.px(8)))
        line.columnconfigure(0, weight=1)
        text = tk.Label(line, text=label, bg=CARD, fg=TEXT, font=design.FONT_SMALL,
                        anchor="w", justify="left", wraplength=self._wide,
                        cursor="hand2")
        self._bind_responsive_wrap(line, text, reserve=80)
        text.grid(row=0, column=0, sticky="ew", padx=(0, design.px(12)))
        switch = Switch(line, variable)
        switch.grid(row=0, column=1, sticky="e")
        text.bind("<Button-1>", lambda _event: switch.toggle())
        self.app._tool_widgets[(feature.key, option.name)] = switch

    def _input(self, parent: tk.Frame, option: Option, variable: tk.Variable) -> tk.Widget:
        if option.kind == "bool":
            return Switch(parent, variable)
        if option.kind in ("int", "float"):
            return self._spinbox(parent, option, variable)
        if option.kind == "choice":
            return self._choice_input(parent, option, variable)
        if option.kind == "folder" or option.name == "file":
            return self._path_line(parent, option, variable)
        return self.app._path_entry(parent, variable)

    def _choice_input(self, parent: tk.Frame, option: Option,
                      variable: tk.Variable) -> tk.Widget:
        """Read-only dropdown that shows labels while the variable keeps values."""
        values = list(option.choices)
        labels = [_choice_label(option, value) for value in values]
        display = tk.StringVar(value=_choice_label(option, str(variable.get())))
        box = ttk.Combobox(parent, textvariable=display, values=labels, state="readonly",
                           font=design.FONT, width=12)
        by_label = dict(zip(labels, values))

        def on_select(_event=None) -> None:
            variable.set(by_label.get(display.get(), values[0]))

        def on_value(*_args) -> None:
            try:
                label = _choice_label(option, str(variable.get()))
                if display.get() != label:
                    display.set(label)
            except tk.TclError:
                pass

        box.bind("<<ComboboxSelected>>", on_select)
        trace = variable.trace_add("write", on_value)

        def on_destroy(event) -> None:
            if event.widget is not box:
                return
            try:
                variable.trace_remove("write", trace)
            except (tk.TclError, ValueError):
                pass

        box.bind("<Destroy>", on_destroy)
        return box

    def _path_line(self, parent: tk.Frame, option: Option,
                   variable: tk.Variable) -> tk.Frame:
        """Path field plus the matching picker button."""
        line = tk.Frame(parent, bg=CARD)
        line.columnconfigure(0, weight=1)
        entry = self.app._path_entry(line, variable)
        entry.grid(row=0, column=0, sticky="ew", ipady=design.px(7))
        if option.kind == "folder":
            RoundButton(line, i18n.t("gui.button.choose_folder"),
                        lambda: self.app._choose_folder(variable),
                        style="normal").grid(row=0, column=1, padx=(design.px(10), 0))
        else:
            RoundButton(line, i18n.t("gui.button.choose_file"),
                        lambda: self.app._choose_file(variable),
                        style="normal").grid(row=0, column=1, padx=(design.px(10), 0))
        return line

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
                          highlightcolor=ACCENT, font=design.FONT, width=10,
                          justify="right")


class ToolsTab(tk.Frame):
    """Feature picker, a description line and the form of the selected feature."""

    def __init__(self, app, parent: tk.Frame) -> None:
        super().__init__(parent, bg=BACKGROUND)
        self.app = app
        self.columnconfigure(0, weight=1)
        self._form = OptionForm(app)
        self._forms: dict[str, tk.Frame] = {}
        self._description: tk.Label | None = None
        self._badge: Pill | None = None
        self._build()

    def _build(self) -> None:
        row = 0
        if FEATURES:
            self._selection(row)
            row += 1
        row = self._description_row(row)
        for feature in FEATURES:
            self._forms[feature.key] = self._feature_form(feature, row)
            row += 1
        self.bind("<Configure>", self._resize_description)
        self._show(self.app.var_tool_choice.get())

    def _selection(self, row: int) -> None:
        """The feature picker: segments for a few features, else a combobox."""
        titles = [(feature.key, feature_label(feature)) for feature in FEATURES]
        if len(titles) <= SEGMENT_LIMIT:
            Segments(self, titles, self.app.var_tool_choice, command=self._show,
                     height=40, surface=FIELD, stretch=True).grid(
                         row=row, column=0, sticky="ew", pady=(0, design.px(12)))
            return

        current = self.app.var_tool_choice.get()
        by_key = dict(titles)
        labels = [text for _key, text in titles]
        by_label = {text: key for key, text in titles}
        display = tk.StringVar(value=by_key.get(current, labels[0]))
        box = ttk.Combobox(self, state="readonly", values=labels, textvariable=display,
                           width=max(len(text) for text in labels), font=design.FONT)
        box.grid(row=row, column=0, sticky="ew", pady=(0, design.px(12)))
        box.bind("<<ComboboxSelected>>",
                 lambda _event: self._show(by_label.get(display.get(), FEATURES[0].key)))

    def _description_row(self, row: int) -> int:
        """One sentence about the selected feature plus a read-only/writes badge."""
        frame = tk.Frame(self, bg=BACKGROUND)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, design.px(14)))
        frame.columnconfigure(0, weight=1)
        self._description = tk.Label(frame, text="", bg=BACKGROUND, fg=TEXT_MUTED,
                                     font=design.FONT, anchor="w", justify="left")
        self._description.grid(row=0, column=0, sticky="w")
        self._badge = Pill(frame, "", TEXT_MUTED)
        self._badge.grid(row=0, column=1, sticky="e", padx=(design.px(12), 0))
        return row + 1

    def _resize_description(self, event) -> None:
        """Keep the description on one block next to the badge."""
        if self._description is None or self._badge is None:
            return
        width = event.width - self._badge.winfo_reqwidth() - design.px(28)
        self._description.configure(wraplength=max(width, design.px(180)))

    def _secondary_row(self, parent: tk.Frame, row: int, feature: Feature) -> None:
        """Fine-tuning hint on the left, the matching buttons on the right."""
        frame = tk.Frame(parent, bg=BACKGROUND)
        frame.grid(row=row, column=0, sticky="ew", pady=(design.px(4), 0))
        frame.columnconfigure(0, weight=1)
        if fine_tuning_sections(feature):
            tk.Label(frame, text=i18n.t("gui.tools.fine_tuning_hint"), bg=BACKGROUND,
                     fg=TEXT_MUTED, font=design.FONT_SMALL, anchor="w", justify="left",
                     wraplength=design.px(420)).grid(row=0, column=0, sticky="w")
        column = 1
        if feature.key in _LLM_FEATURES:
            RoundButton(frame, i18n.t("gui.button.paste_llm"), self.app._llm_rules_import,
                        style="normal", height=34).grid(row=0, column=column,
                                                        sticky="e", padx=(design.px(12), 0))
            column += 1
        if fine_tuning_sections(feature):
            RoundButton(frame, i18n.t("gui.button.fine_tuning"),
                        self.app._open_preferences, style="normal", height=34).grid(
                            row=0, column=column, sticky="e", padx=(design.px(10), 0))

    def _feature_form(self, feature: Feature, row: int) -> tk.Frame:
        """One card per form section; the holder is shown or hidden."""
        holder = tk.Frame(self, bg=BACKGROUND)
        holder.grid(row=row, column=0, sticky="ew")
        holder.columnconfigure(0, weight=1)
        sections = form_sections(feature)
        for index, (section, options) in enumerate(sections):
            self._section_card(holder, index, feature, section, options)
        if fine_tuning_sections(feature) or feature.key in _LLM_FEATURES:
            self._secondary_row(holder, len(sections), feature)
        return holder

    def _section_card(self, holder: tk.Frame, row: int, feature: Feature,
                      section: str, options: list[Option]) -> None:
        body = self.app._card(holder, row, section_title(section))
        self._form.fields(body, feature, options)

    def _show(self, key: str) -> None:
        """Show the form of ``key`` and hide the others."""
        self.app.var_tool_choice.set(key)
        for feature_key, holder in self._forms.items():
            if feature_key == key:
                holder.grid()
            else:
                holder.grid_remove()
        feature = next((item for item in FEATURES if item.key == key), None)
        self._show_description(feature)
        self.app._tools_actions()

    def _show_description(self, feature: Feature | None) -> None:
        """Short explanation and "read only"/"writes files" badge of ``feature``."""
        if self._description is not None:
            text = ""
            if feature is not None:
                hint_key = f"gui.hint.{feature.key}"
                hint = i18n.t(hint_key)
                text = "" if hint == hint_key else hint
            self._description.configure(text=text)
        if self._badge is not None and feature is not None:
            self._badge.set_text(
                i18n.t("gui.tools.badge.writes" if feature.writes
                       else "gui.tools.badge.readonly"),
                YELLOW if feature.writes else ACCENT)
