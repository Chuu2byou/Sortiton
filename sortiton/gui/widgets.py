"""Hand-drawn widgets - no extra packages.

RoundButton, Pill (status chip), Segments (tab/switcher) and ProgressBar.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import Callable, TypedDict

from . import design
from .design import (ACCENT, ACCENT_LIGHT, ACCENT_TEXT, APPLY, APPLY_LIGHT, BORDER, CARD,
                     DANGER, DANGER_LIGHT, FIELD, FIELD_ACTIVE, BACKGROUND, TEXT,
                     TEXT_DISABLED, TEXT_MUTED)


def _blend(colour_a: str, colour_b: str, ratio: float) -> str:
    """Blend two #rrggbb colours (ratio: 0 = a, 1 = b)."""
    a = [int(colour_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(colour_b[i:i + 2], 16) for i in (1, 3, 5)]
    c = [round(x + (y - x) * ratio) for x, y in zip(a, b)]
    return "#{:02x}{:02x}{:02x}".format(*c)


def _bg_of(widget: tk.Misc) -> str:
    """Background colour of a widget (fallback: window colour)."""
    try:
        return str(widget.cget("bg"))
    except tk.TclError:
        return BACKGROUND


def _rounded_shape(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float,
                   radius: float, **options) -> int:
    """Draw a rounded rectangle (smooth polygon, no extra packages)."""
    r = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1,
        x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2,
        x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **options)


class _ButtonStyle(TypedDict):
    """Colour values of a button style (bg = None: background of the parent)."""
    bg: str | None
    hover: str
    text: str
    hover_text: str | None
    border: str


class RoundButton(tk.Canvas):
    """Rounded button with hover, press and disabled states."""

    STYLES: dict[str, _ButtonStyle] = {
        "primary": {"bg": ACCENT, "hover": ACCENT_LIGHT, "text": ACCENT_TEXT,
                    "hover_text": None, "border": ""},
        "apply":   {"bg": APPLY, "hover": APPLY_LIGHT, "text": ACCENT_TEXT,
                    "hover_text": None, "border": ""},
        "danger":  {"bg": DANGER, "hover": DANGER_LIGHT, "text": ACCENT_TEXT,
                    "hover_text": None, "border": ""},
        "normal":  {"bg": FIELD, "hover": FIELD_ACTIVE, "text": TEXT,
                    "hover_text": None, "border": BORDER},
        "quiet":   {"bg": None, "hover": FIELD, "text": TEXT_MUTED,
                    "hover_text": TEXT, "border": ""},
    }

    def __init__(self, parent: tk.Misc, text: str, command: Callable[[], None] | None = None,
                 style: str = "normal", height: int = 34, radius: int = 10) -> None:
        self._style = style
        self._command: Callable[[], None] | None = command
        self._parent_bg = _bg_of(parent)
        self._text = text
        self._radius = radius
        self._enabled = True
        self._hover = False
        self._pressed = False
        width = tkfont.Font(font=design.FONT_BUTTON).measure(text) + 30
        super().__init__(parent, width=width, height=height, bg=self._parent_bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    def _on_enter(self, _event) -> None:
        if self._enabled:
            self._hover = True
            self._draw()

    def _on_leave(self, _event) -> None:
        self._hover = False
        self._pressed = False
        self._draw()

    def _on_press(self, _event) -> None:
        if self._enabled:
            self._pressed = True
            self._draw()

    def _on_release(self, _event) -> None:
        command = self._command
        triggered = self._pressed and self._hover and self._enabled and command is not None
        self._pressed = False
        self._draw()
        if triggered and command is not None:
            command()

    @property
    def enabled(self) -> bool:
        """True while the button reacts to clicks."""
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        if self._enabled != enabled:
            self._enabled = enabled
            self._hover = False
            self._pressed = False
            self.configure(cursor="hand2" if enabled else "arrow")
            self._draw()

    def _colours(self) -> tuple[str, str, str]:
        style = self.STYLES[self._style]
        base = style["bg"] or self._parent_bg
        if not self._enabled:
            bg = _blend(self._parent_bg, base, 0.22) if style["bg"] else self._parent_bg
            return bg, TEXT_DISABLED, style["border"]
        if self._pressed:
            return _blend(base, "#000000", 0.18), style["text"], style["border"]
        if self._hover:
            return style["hover"], style["hover_text"] or style["text"], style["border"]
        return base, style["text"], style["border"]

    def _draw(self) -> None:
        self.delete("all")
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        bg, fg, border = self._colours()
        _rounded_shape(self, 1, 1, width - 1, height - 1, self._radius,
                       fill=bg, outline=border or bg)
        self.create_text(width / 2, height / 2, text=self._text,
                         fill=fg, font=design.FONT_BUTTON, anchor="center")


class Pill(tk.Canvas):
    """Small status pill (chip) with a coloured dot."""

    def __init__(self, parent: tk.Misc, text: str, colour: str = TEXT_MUTED,
                 dot: bool = True) -> None:
        self._colour = colour
        self._dot = dot
        self._parent_bg = _bg_of(parent)
        width = tkfont.Font(font=design.FONT_SMALL).measure(text) + (34 if dot else 20)
        super().__init__(parent, width=width, height=24, bg=self._parent_bg,
                         highlightthickness=0, bd=0)
        self._text = text
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        _rounded_shape(self, 0.5, 0.5, width - 0.5, height - 0.5, height / 2,
                       fill=CARD, outline=BORDER)
        x = 11
        if self._dot:
            self.create_oval(x - 3, height / 2 - 3, x + 3, height / 2 + 3,
                             fill=self._colour, outline="")
            x += 13
        self.create_text(x, height / 2, text=self._text, fill=TEXT,
                         font=design.FONT_SMALL, anchor="w")


class Segments(tk.Canvas):
    """Segmented choice (like modern tab/switch controls).

    With ``stretch=True`` the segments share the full width of their cell.
    """

    def __init__(self, parent: tk.Misc, items: list[tuple[str, str]], variable: tk.StringVar,
                 command: Callable[[str], None] | None = None, height: int = 36,
                 radius: int = 10, surface: str = CARD, font=None,
                 stretch: bool = False) -> None:
        self._variable = variable
        self._command: Callable[[str], None] | None = command
        self._font = font or design.FONT_BUTTON
        self._radius = radius
        self._surface = surface
        self._inner = 2
        self._hover_index: int | None = None
        self._items: list[tuple[str, str]] = []
        self._widths: list[int] = []
        self._trace = ""
        super().__init__(parent, bg=_bg_of(parent), highlightthickness=0, bd=0, cursor="hand2")
        self.set_items(items, height=height)
        self._trace = self._variable.trace_add("write", self._on_change)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda _e: self._set_hover(None))
        self.bind("<Destroy>", self._on_destroy)
        if stretch:
            self.bind("<Configure>", self._on_configure)

    def _on_configure(self, event) -> None:
        """Spread the segments evenly over the available width."""
        if not self._items or event.width <= 1:
            return
        usable = event.width - 2 * self._inner
        each = max(usable // len(self._items), 1)
        widths = [each] * len(self._items)
        widths[-1] = max(usable - each * (len(self._items) - 1), 1)
        if widths != self._widths:
            self._widths = widths
            self._draw()

    def _on_destroy(self, event) -> None:
        """Drop the variable trace so a rebuild does not draw on a dead canvas."""
        if event.widget is not self:
            return
        if self._trace:
            try:
                self._variable.trace_remove("write", self._trace)
            except (tk.TclError, ValueError):
                pass
            self._trace = ""

    def set_items(self, items: list[tuple[str, str]], height: int | None = None) -> None:
        """Replace the segments (used for the language switch)."""
        self._items = list(items)
        measurer = tkfont.Font(font=self._font)
        self._widths = [measurer.measure(text) + 36 for _, text in self._items]
        self.configure(width=sum(self._widths) + 2 * self._inner)
        if height is not None:
            self.configure(height=height)
        self._hover_index = None
        self._draw()

    def _segment_at(self, x: float) -> int | None:
        pos = self._inner
        for index, width in enumerate(self._widths):
            if pos <= x < pos + width:
                return index
            pos += width
        return None

    def _on_click(self, event) -> None:
        index = self._segment_at(event.x)
        if index is None:
            return
        value = self._items[index][0]
        if self._variable.get() != value:
            self._variable.set(value)
            if self._command:
                self._command(value)

    def _on_motion(self, event) -> None:
        self._set_hover(self._segment_at(event.x))

    def _set_hover(self, index: int | None) -> None:
        if index != self._hover_index:
            self._hover_index = index
            self._draw()

    def _on_change(self, *_args) -> None:
        self._draw()

    def _container_width(self) -> int:
        """Cover the whole cell: ``stretch`` spreads the segments over it."""
        return max(self.winfo_reqwidth(), self.winfo_width())

    def _draw(self) -> None:
        self.delete("all")
        width = self._container_width()
        height = self.winfo_reqheight()
        _rounded_shape(self, 0.5, 0.5, width - 0.5, height - 0.5, self._radius,
                       fill=self._surface, outline=BORDER)
        x = self._inner
        for index, (value, text) in enumerate(self._items):
            segment_width = self._widths[index]
            active = self._variable.get() == value
            if active:
                _rounded_shape(self, x + 1, self._inner + 1, x + segment_width - 1,
                               height - self._inner - 1, self._radius - 3,
                               fill=ACCENT, outline="")
                colour = ACCENT_TEXT
            elif self._hover_index == index:
                _rounded_shape(self, x + 1, self._inner + 1, x + segment_width - 1,
                               height - self._inner - 1, self._radius - 3,
                               fill=FIELD_ACTIVE, outline="")
                colour = TEXT
            else:
                colour = TEXT_MUTED
            self.create_text(x + segment_width / 2, height / 2, text=text,
                             fill=colour, font=self._font, anchor="center")
            x += segment_width


class ProgressBar(tk.Canvas):
    """Slim, rounded progress bar (determinate + indeterminate)."""

    def __init__(self, parent: tk.Misc, width: int = 230, height: int = 8,
                 radius: int = 4) -> None:
        super().__init__(parent, width=width, height=height, bg=_bg_of(parent),
                         highlightthickness=0, bd=0)
        self._width = width
        self._height = height
        self._radius = radius
        self._value = 0.0
        self._max = 1.0
        self._indeterminate = False
        self._pos = 0.0
        self._direction = 1.0
        self._job: str | None = None
        self._alive = True
        self.bind("<Destroy>", self._on_destroy)
        self._draw()

    def _on_destroy(self, event) -> None:
        """Stop the animation when the widget goes away (language rebuild)."""
        if event.widget is not self:
            return
        self._alive = False
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def start(self) -> None:
        self._indeterminate = True
        self._direction = 1.0
        self._pos = 0.0
        if self._job is None:
            self._tick()

    def stop(self) -> None:
        self._indeterminate = False
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        self._value = 0.0
        self._draw()

    def set_value(self, current: int, total: int) -> None:
        if self._indeterminate:
            self._indeterminate = False
            if self._job is not None:
                self.after_cancel(self._job)
                self._job = None
        self._value = float(current)
        self._max = float(max(total, 1))
        self._draw()

    def _tick(self) -> None:
        if not self._alive:
            self._job = None
            return
        pill_width = self._width * 0.32
        self._pos += 11 * self._direction
        if self._pos <= 0:
            self._pos = 0.0
            self._direction = 1.0
        elif self._pos >= self._width - pill_width:
            self._pos = self._width - pill_width
            self._direction = -1.0
        self._draw()
        self._job = self.after(16, self._tick)

    def _draw(self) -> None:
        self.delete("all")
        _rounded_shape(self, 0, 0, self._width, self._height, self._radius,
                       fill=FIELD, outline="")
        if self._indeterminate:
            pill_width = self._width * 0.32
            _rounded_shape(self, self._pos, 0, self._pos + pill_width, self._height,
                           self._radius, fill=ACCENT, outline="")
        elif self._value > 0:
            ratio = min(self._value / self._max, 1.0)
            filled = max(self._width * ratio, self._height)
            _rounded_shape(self, 0, 0, filled, self._height, self._radius,
                           fill=ACCENT, outline="")
