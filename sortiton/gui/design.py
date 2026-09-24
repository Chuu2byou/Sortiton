"""Appearance: colours and fonts (modern dark design).

:func:`load_fonts` REBINDS the ``FONT_*`` variables, so other modules must
access them as ``design.FONT_SMALL``. Colours may be imported directly.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

BACKGROUND = "#0f1117"    # window background
CARD       = "#171a21"    # cards / panels
FIELD      = "#1f232c"    # input fields
FIELD_ACTIVE = "#262b36"  # hover / active surfaces
BORDER     = "#2a3040"    # subtle borders
BORDER_SOFT = "#222736"   # even quieter separator (inside cards)
SURFACE    = "#12151c"    # raised surface inside a card (preview / result)
TEXT       = "#e9ecf2"
TEXT_MUTED = "#98a1b3"
TEXT_FAINT = "#6f7889"    # labels that are only decoration
ACCENT     = "#4f8cff"
ACCENT_LIGHT = "#6ea2ff"
ACCENT_TEXT = "#ffffff"
APPLY      = "#2f9e5f"    # positive action: write / rename / sort
APPLY_LIGHT = "#39b76f"
DANGER     = "#c4453d"    # destructive action
DANGER_LIGHT = "#d5584f"
RED        = "#ff6b6b"
GREEN      = "#5fd68a"
YELLOW     = "#f5c451"
LOG_BG     = "#0c0e13"
LOG_TEXT   = "#d9dde5"    # log lines sit a little dimmer than normal text

SCROLLBAR = "#39404f"          # handle of the scrollbars
SCROLLBAR_ACTIVE = "#4a5468"   # while it is grabbed
TEXT_DISABLED = "#5c6370"      # text of a disabled button

# Replaced by :func:`load_fonts` at startup.
FONT           = ("DejaVu Sans", 10)
FONT_SMALL     = ("DejaVu Sans", 9)
FONT_LABEL     = ("DejaVu Sans", 9, "bold")
FONT_TITLE     = ("DejaVu Sans", 17, "bold")
FONT_SECTION   = ("DejaVu Sans", 11, "bold")
FONT_BUTTON    = ("DejaVu Sans", 10)
FONT_MONO      = ("DejaVu Sans Mono", 9)


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
    FONT         = (family, 10)
    FONT_SMALL   = (family, 9)
    FONT_LABEL   = (family, 9, "bold")
    FONT_TITLE   = (family, 17, "bold")
    FONT_SECTION = (family, 11, "bold")
    FONT_BUTTON  = (family, 10)
    FONT_MONO    = (mono, 9)
