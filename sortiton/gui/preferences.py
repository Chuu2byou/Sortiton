"""Settings window: external tools, fine-tuning of the tools and language."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import external, i18n, settings
from . import design
from .design import (BACKGROUND, BORDER, CARD, GREEN, TEXT, TEXT_FAINT, TEXT_MUTED,
                     YELLOW)
from .tools import OptionForm, feature_label, fine_tuning_cards, section_title
from .widgets import Pill, RoundButton, Segments

# Startbreite: breit genug für zwei Formularspalten, aber nie breiter als der
# Bildschirm. Auf großen Monitoren wächst das Fenster mit, bleibt aber lesbar.
MIN_WIDTH = 560
PREFERRED_WIDTH = 1000
WIDTH_RATIO = 0.56
MAX_WIDTH = 1160
MIN_HEIGHT = 420
HEIGHT_RATIO = 0.90
CARDS_TWO_COLUMNS = 840  # ab dieser Inhaltsbreite stehen die Karten zweispaltig


class PreferencesWindow:
    """Toplevel showing the external tools, the fine-tuning and the language."""

    def __init__(self, app) -> None:
        self.app = app
        parent = app.root
        self.window = tk.Toplevel(parent)
        self.window.withdraw()
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

        self._cards: list[tuple[tk.Frame, int]] = []
        self._cards_wide: bool | None = None
        self._height_fitted = False
        self._cards_frame = tk.Frame(self._content, bg=BACKGROUND)
        self._cards_frame.grid(row=1, column=0, sticky="ew")
        self._cards_frame.columnconfigure(0, weight=1)
        self._cards_frame.columnconfigure(1, weight=1)

        self._head(self._content, 0)
        self._theme_card(self._cards_frame)
        self._language_card(self._cards_frame, app.var_language, app._language_changed)
        self._tools_card(self._cards_frame)
        self._fine_tuning_cards(self._cards_frame)
        self._numbers_card(self._cards_frame, app.var_track_format,
                           app._track_format_changed)
        self._layout_cards()

        footer = tk.Frame(self._content, bg=BACKGROUND)
        footer.grid(row=2, column=0, sticky="e", pady=(design.px(16), 0))
        RoundButton(footer, i18n.t("gui.button.close"), self.window.destroy,
                    style="normal", height=34).pack()

        self._content.bind("<Configure>", self._layout_cards, add="+")
        self._cards_frame.bind("<Configure>", self._layout_cards, add="+")

        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.window.bind(sequence, self._on_wheel, add="+")
        self.window.bind("<Escape>", lambda _event: self.window.destroy())
        self.window.bind("<Map>", lambda event: self._center_when_mapped(event, parent),
                 add="+")

        self._place(parent)


    def _theme_card(self, parent: tk.Misc) -> None:
        """Choose the appearance for the running application."""
        card = self._card(parent, i18n.t("gui.settings.theme"))
        self._theme_variable = tk.StringVar(master=self.window,
                                            value=settings.resolve_theme())
        Segments(card,
                 [(mode, i18n.t(f"gui.theme.{mode}"))
                  for mode in settings.THEME_MODES],
                 self._theme_variable, command=self._theme_changed, height=34,
                 font=design.FONT_SMALL, stretch=True).grid(
                     row=0, column=0, sticky="ew")
        hint = self._hint(card, i18n.t("gui.settings.theme_hint"))
        hint.grid(row=1, column=0, sticky="ew", pady=(design.px(8), 0))

    def _theme_changed(self, mode: str) -> None:
        """Delegate live theme changes to the application."""
        self.app._theme_changed(mode)


    def _place(self, parent: tk.Misc) -> None:
        """Size the window generously, but never past the screen edge."""
        self._parent = parent
        self.window.update_idletasks()
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        content_width = self._content.winfo_reqwidth()
        content_height = self._content.winfo_reqheight()
        available_width = max(screen_width - design.px(24), design.px(1))
        preferred = min(max(design.px(PREFERRED_WIDTH),
                            int(screen_width * WIDTH_RATIO)),
                        design.px(MAX_WIDTH))
        width = min(max(content_width, preferred), available_width)
        height = min(max(content_height, design.px(MIN_HEIGHT)),
                     max(int(screen_height * HEIGHT_RATIO), design.px(MIN_HEIGHT)))
        self.window.minsize(min(design.px(MIN_WIDTH), available_width),
                            min(design.px(MIN_HEIGHT), height))
        x = max(parent.winfo_rootx() + (parent.winfo_width() - width) // 2, 0)
        y = max(parent.winfo_rooty() + (parent.winfo_height() - height) // 2, 0)
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.window.deiconify()
        self.window.after_idle(self._center_on_parent, parent)
        self.window.after_idle(self._sync_scrollbar)

    def _center_when_mapped(self, event, parent: tk.Misc) -> None:
        """Re-center after the window manager has placed the mapped dialog."""
        if event.widget is self.window:
            self.window.after_idle(self._center_on_parent, parent)

    def _center_on_parent(self, parent: tk.Misc) -> None:
        """Center the mapped window using its actual size and owner position."""
        if not self.window.winfo_exists():
            return
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        parent_left = parent.winfo_rootx()
        parent_top = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        x = parent_left + (parent_width - width) // 2
        y = parent_top + (parent_height - height) // 2
        # Keep the dialog inside the union of screen and owner. This centers
        # normally but still works when the owner itself extends off-screen.
        x = max(min(0, parent_left),
                min(x, max(screen_width, parent_left + parent_width) - width))
        y = max(min(0, parent_top),
                min(y, max(screen_height, parent_top + parent_height) - height))
        self.window.geometry(f"+{x}+{y}")

    def _resize_canvas(self, event) -> None:
        """Let the cards take the full width and re-check the scrollbar."""
        self._canvas.itemconfigure(self._body_window, width=event.width)
        self._sync_scrollbar()

    def _fit_height(self) -> None:
        """Trim the window to its final content height once after layout."""
        if self._height_fitted or not self.window.winfo_exists():
            return
        if not self.window.winfo_ismapped():
            return
        self._height_fitted = True
        self.window.update_idletasks()
        content_height = self._content.winfo_reqheight()
        screen_height = self.window.winfo_screenheight()
        height = min(max(content_height, design.px(MIN_HEIGHT)),
                     max(int(screen_height * HEIGHT_RATIO), design.px(MIN_HEIGHT)))
        if abs(self.window.winfo_height() - height) > 1:
            self.window.geometry(f"{self.window.winfo_width()}x{height}")
            parent = getattr(self, "_parent", None)
            if parent is not None:
                self.window.after_idle(self._center_on_parent, parent)

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

    def _layout_cards(self, event=None) -> None:
        """Place the cards in one or two columns, depending on the width."""
        if event is not None and event.widget not in (self._content, self._cards_frame):
            return
        try:
            window_width = self.window.winfo_width()
        except tk.TclError:
            return
        if window_width <= 1:
            # Vor dem ersten Mapping: die spätere Fensterbreite abschätzen,
            # damit schon die erste Größenberechnung die richtige Spaltenzahl
            # und Höhe sieht.
            screen_width = self.window.winfo_screenwidth()
            window_width = min(max(design.px(PREFERRED_WIDTH),
                                   int(screen_width * WIDTH_RATIO)),
                               design.px(MAX_WIDTH),
                               screen_width - design.px(24))
        available = max(window_width - design.px(64), design.px(1))
        wide = available >= design.px(CARDS_TWO_COLUMNS)
        if not self._height_fitted:
            self.window.after_idle(self._fit_height)
        if wide == self._cards_wide:
            return
        self._cards_wide = wide

        for card, _span in self._cards:
            card.grid_forget()
        self._cards_frame.columnconfigure(0, weight=1,
                                          uniform="cards" if wide else "")
        self._cards_frame.columnconfigure(1, weight=1 if wide else 0,
                                          uniform="cards" if wide else "")
        if not wide:
            for row, (card, _span) in enumerate(self._cards):
                card.grid(row=row, column=0, columnspan=2, sticky="ew",
                          pady=(design.px(14), 0))
            return

        row = 0
        column = 0
        for card, span in self._cards:
            if span >= 2:
                if column:
                    row += 1
                    column = 0
                card.grid(row=row, column=0, columnspan=2, sticky="ew",
                          pady=(design.px(14), 0))
                row += 1
                continue
            padx = (0, design.px(7)) if column == 0 else (design.px(7), 0)
            card.grid(row=row, column=column, sticky="ew", padx=padx,
                      pady=(design.px(14), 0))
            if column == 0:
                column = 1
            else:
                column = 0
                row += 1

    def _card(self, parent: tk.Misc, title: str = "", span: int = 1) -> tk.Frame:
        """A bordered card; the layout step decides its grid position."""
        outer = tk.Frame(parent, bg=CARD, highlightthickness=1,
                         highlightbackground=BORDER, bd=0)
        outer.columnconfigure(0, weight=1)
        self._cards.append((outer, span))
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

    def _wrap_to_parent(self, label: tk.Label, parent: tk.Misc) -> None:
        """Keep helper text readable as its card changes width."""
        def resize(event) -> None:
            label.configure(wraplength=max(design.px(160),
                                           event.width - design.px(24)))

        parent.bind("<Configure>", resize, add="+")

    def _hint(self, parent: tk.Misc, text: str,
              colour: str = TEXT_MUTED) -> tk.Label:
        """A helper line that wraps with its card instead of fixing its width."""
        label = tk.Label(parent, text=text, bg=CARD, fg=colour,
                         font=design.FONT_SMALL, anchor="w", justify="left",
                         wraplength=design.px(420))
        self._wrap_to_parent(label, parent)
        return label


    def _layout_pills(self, event=None) -> None:
        """Wrap tool pills inside the card instead of clipping them."""
        pills_list = getattr(self, "_tool_pills", None)
        if not pills_list:
            return
        width = event.width if event is not None else None
        if width is None:
            width = self._tool_pills_frame.winfo_width()
        if width <= 1:
            width = design.px(560)
        if width == self._tool_pills_width:
            return
        self._tool_pills_width = width
        gap = design.px(8)
        x = 0
        y = 0
        line_height = 0
        for pill in pills_list:
            pill_width = pill.winfo_reqwidth()
            if x and x + pill_width > width:
                x = 0
                y += line_height + gap
                line_height = 0
            pill.place(x=x, y=y)
            x += pill_width + gap
            line_height = max(line_height, pill.winfo_reqheight())
        self._tool_pills_frame.configure(height=max(y + line_height, 1))

    def _tools_card(self, parent: tk.Misc) -> None:
        """One pill per tool from :data:`external.TOOLS`, plus install hints."""
        card = self._card(parent, i18n.t("gui.settings.tools"), span=2)

        pills = tk.Frame(card, bg=CARD)
        pills.grid(row=0, column=0, sticky="ew")
        self._tool_pills_frame = pills
        self._tool_pills: list[tk.Widget] = []
        self._tool_pills_width = 0
        missing: list[external.Tool] = []
        for tool in external.TOOLS:
            if external.available(tool):
                version = external.version(tool)
                text = (i18n.t("gui.chip.tool_ok", tool=tool.key, version=version)
                        if version else i18n.t("gui.chip.tool_ok_noversion", tool=tool.key))
                pill = Pill(pills, text, GREEN)
            else:
                pill = Pill(pills, i18n.t("gui.chip.tool_missing", tool=tool.key),
                            YELLOW)
                missing.append(tool)
            self._tool_pills.append(pill)
        pills.bind("<Configure>", self._layout_pills, add="+")
        self._layout_pills()

        hint = self._hint(card, i18n.t("gui.settings.tools_hint"))
        hint.grid(row=1, column=0, sticky="ew", pady=(design.px(8), 0))

        hint_row = 2
        for tool in missing:
            if not tool.hint_key:
                continue
            hint = self._hint(card, i18n.t(tool.hint_key).strip(), YELLOW)
            hint.grid(row=hint_row, column=0, sticky="ew",
                      pady=(design.px(6), 0))
            hint_row += 1

    def _fine_tuning_cards(self, parent: tk.Misc) -> None:
        """One card per fine-tuning section."""
        cards = fine_tuning_cards()
        if not cards:
            return
        owners = {feature.key for feature, _section, _options in cards}
        form = OptionForm(self.app, width=design.px(360))
        for feature, section, options in cards:
            title = section_title(section)
            if len(owners) > 1:
                title = f"{feature_label(feature)} · {title}"
            body = self._card(parent, title)
            form.fields(body, feature, options)

    def _language_card(self, parent: tk.Misc, language: tk.StringVar,
                       on_language) -> None:
        card = self._card(parent, i18n.t("gui.settings.language"))
        Segments(card, [("en", i18n.t("gui.language.en")), ("de", i18n.t("gui.language.de"))],
                 language, command=on_language, height=34,
                 font=design.FONT_SMALL, stretch=True).grid(
                     row=0, column=0, sticky="ew")
        hint = self._hint(card, i18n.t("gui.settings.language_hint"))
        hint.grid(row=1, column=0, sticky="ew", pady=(design.px(8), 0))

    def _numbers_card(self, parent: tk.Misc, track_format: tk.StringVar,
                      on_change) -> None:
        """Choose whether track/disc numbers keep their total or are padded."""
        card = self._card(parent, i18n.t("gui.settings.numbers"))
        Segments(card,
                 [(code, i18n.t(f"gui.number.{code}")) for code in settings.TRACK_FORMATS],
                 track_format, command=on_change, height=34,
                 font=design.FONT_SMALL, stretch=True).grid(
                     row=0, column=0, sticky="ew")
        hint = self._hint(card, i18n.t("gui.settings.numbers_hint"))
        hint.grid(row=1, column=0, sticky="ew", pady=(design.px(8), 0))
