"""Appearance: colours, fonts and the one UI scale factor."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import font as tkfont

BACKGROUND = "#0f1117"
CARD       = "#171a21"
FIELD      = "#1f232c"
FIELD_ACTIVE = "#262b36"
BORDER     = "#2a3040"
BORDER_SOFT = "#222736"
SURFACE    = "#12151c"
TEXT       = "#e9ecf2"
TEXT_MUTED = "#98a1b3"
TEXT_FAINT = "#6f7889"
ACCENT     = "#4f8cff"
ACCENT_LIGHT = "#6ea2ff"
ACCENT_TEXT = "#ffffff"
APPLY      = "#2f9e5f"
APPLY_LIGHT = "#39b76f"
DANGER     = "#c4453d"
DANGER_LIGHT = "#d5584f"
RED        = "#ff6b6b"
GREEN      = "#5fd68a"
YELLOW     = "#f5c451"
LOG_BG     = "#0c0e13"
LOG_TEXT   = "#d9dde5"

SCROLLBAR = "#39404f"
SCROLLBAR_ACTIVE = "#4a5468"
TEXT_DISABLED = "#5c6370"

FONT           = ("DejaVu Sans", 11)
FONT_SMALL     = ("DejaVu Sans", 10)
FONT_LABEL     = ("DejaVu Sans", 10, "bold")
FONT_TITLE     = ("DejaVu Sans", 18, "bold")
FONT_SECTION   = ("DejaVu Sans", 12, "bold")
FONT_BUTTON    = ("DejaVu Sans", 11)
FONT_MONO      = ("DejaVu Sans Mono", 10)

UI_SCALE = 1.0

SCALE_VARIABLE = "SORTITON_UI_SCALE"

_MIN_SCALE, _MAX_SCALE = 1.0, 3.0


def configure(root: tk.Misc) -> float:
    """Detect the UI scale and install it in Tk."""
    global UI_SCALE
    factor = 0.0
    raw = os.environ.get(SCALE_VARIABLE, "").strip().replace(",", ".")
    if raw:
        try:
            factor = float(raw)
        except ValueError:
            factor = 0.0
    if factor <= 0:
        try:
            factor = float(root.winfo_fpixels("1i")) / 96.0
        except (tk.TclError, ValueError):
            factor = 1.0
    UI_SCALE = min(max(factor, _MIN_SCALE), _MAX_SCALE)
    try:
        root.tk.call("tk", "scaling", UI_SCALE * 96.0 / 72.0)
    except tk.TclError:
        pass
    return UI_SCALE


def px(value: float) -> int:
    """A design pixel value as device pixels (``px(12)`` -> 16 at 133 %)."""
    return max(1, int(round(value * UI_SCALE)))


def load_fonts(root: tk.Tk) -> None:
    """Pick the nicest available fonts (Inter → Cantarell → …)."""
    global FONT, FONT_SMALL, FONT_LABEL, FONT_TITLE, FONT_SECTION, FONT_BUTTON, FONT_MONO
    present = {name.lower() for name in tkfont.families(root)}

    def first_available(candidates: list[str], default: str) -> str:
        for name in candidates:
            if name.lower() in present:
                return name
        return default

    family = first_available(["Inter", "Cantarell", "Ubuntu", "Noto Sans", "Open Sans",
                              "DejaVu Sans"],
                             str(tkfont.nametofont("TkDefaultFont").actual("family")))
    mono = first_available(["JetBrains Mono", "Fira Code", "Cascadia Code", "Noto Sans Mono",
                            "DejaVu Sans Mono"],
                           str(tkfont.nametofont("TkFixedFont").actual("family")))
    FONT         = (family, 11)
    FONT_SMALL   = (family, 10)
    FONT_LABEL   = (family, 10, "bold")
    FONT_TITLE   = (family, 18, "bold")
    FONT_SECTION = (family, 12, "bold")
    FONT_BUTTON  = (family, 11)
    FONT_MONO    = (mono, 10)
