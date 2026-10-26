"""Appearance: themes, colours, spacing and typography in one place.

The saved theme mode defaults to the system appearance. ``SORTITON_THEME``
can override it; the palette is resolved at import so every module sees the
same colours.
"""

from __future__ import annotations

import configparser
import os
import subprocess
import sys
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path

from .. import settings

# --- Farbpaletten -----------------------------------------------------------
# Hell (Standard): Hintergrund #F4F5F7 / Karten #FFFFFF, Text #20242B /
# #545D6B, Linien #D8DDE4, Primärakzent Petrol #006B68 mit weißem Text.
_LIGHT: dict[str, str] = {
    "BACKGROUND": "#F4F5F7",
    "CARD":       "#FFFFFF",
    "SURFACE":    "#F7F8FA",
    "FIELD":      "#FFFFFF",
    "FIELD_ACTIVE": "#E8ECEF",
    "BORDER":     "#D8DDE4",
    "BORDER_SOFT": "#E3E7ED",
    "TEXT":       "#20242B",
    "TEXT_MUTED": "#545D6B",
    "TEXT_FAINT": "#6E7786",
    "TEXT_DISABLED": "#9AA3AF",
    "ACCENT":     "#006B68",
    "ACCENT_LIGHT": "#0A7F7B",
    "ACCENT_TEXT": "#FFFFFF",
    "APPLY":      "#187346",
    "APPLY_LIGHT": "#1B8651",
    "DANGER":     "#B42318",
    "DANGER_LIGHT": "#C43A2E",
    "RED":        "#B42318",
    "GREEN":      "#187346",
    "YELLOW":     "#875400",
    "LOG_BG":     "#FFFFFF",
    "LOG_TEXT":   "#20242B",
    "SCROLLBAR":  "#C7CDD5",
    "SCROLLBAR_ACTIVE": "#ADB5BF",
}

# Dunkel (gleichwertige Einstellung, gleiche Rollen wie im hellen Thema).
_DARK: dict[str, str] = {
    "BACKGROUND": "#141819",
    "CARD":       "#1D2325",
    "SURFACE":    "#252D30",
    "FIELD":      "#252D30",
    "FIELD_ACTIVE": "#303A3D",
    "BORDER":     "#3D484C",
    "BORDER_SOFT": "#303A3D",
    "TEXT":       "#e9ecf2",
    "TEXT_MUTED": "#98a1b3",
    "TEXT_FAINT": "#A0AAAE",
    "TEXT_DISABLED": "#5c6370",
    "ACCENT":     "#70D5C9",
    "ACCENT_LIGHT": "#94E2D8",
    "ACCENT_TEXT": "#102C29",
    "APPLY":      "#2f9e5f",
    "APPLY_LIGHT": "#39b76f",
    "DANGER":     "#c4453d",
    "DANGER_LIGHT": "#d5584f",
    "RED":        "#ff6b6b",
    "GREEN":      "#5fd68a",
    "YELLOW":     "#f5c451",
    "LOG_BG":     "#0c0e13",
    "LOG_TEXT":   "#d9dde5",
    "SCROLLBAR":  "#39404f",
    "SCROLLBAR_ACTIVE": "#4a5468",
}

THEME_VARIABLE = "SORTITON_THEME"
THEME = "light"

BACKGROUND: str
CARD: str
SURFACE: str
FIELD: str
FIELD_ACTIVE: str
BORDER: str
BORDER_SOFT: str
TEXT: str
TEXT_MUTED: str
TEXT_FAINT: str
TEXT_DISABLED: str
ACCENT: str
ACCENT_LIGHT: str
ACCENT_TEXT: str
APPLY: str
APPLY_LIGHT: str
DANGER: str
DANGER_LIGHT: str
RED: str
GREEN: str
YELLOW: str
LOG_BG: str
LOG_TEXT: str
SCROLLBAR: str
SCROLLBAR_ACTIVE: str

# --- Raster und Größen (logische Pixel; via design.px() skalieren) ----------
SPACE_XS = 4    # Innenabstände kleiner Elemente
SPACE_S = 8     # Standardlücke
SPACE_M = 12    # Abstand zwischen Gruppen
SPACE_L = 16    # Abstand zwischen Karten
SPACE_XL = 24   # Gemeinsamer Außenabstand des Fensters
CONTROL_HEIGHT = 36   # Höhe von Knöpfen, Eingaben und Umschaltern
ROW_HEIGHT = 32       # Höhe einer Tabellenzeile
RADIUS = 4            # Rundung von Karten und Bedienelementen


def _apply_palette(palette: dict[str, str]) -> None:
    """Schreibe die Palette in die Modulvariablen (alle Namen unverändert)."""
    globals().update(palette)


def _command_output(command: list[str]) -> str:
    """Return a short system setting, or an empty string if unavailable."""
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=1, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip().strip("'\"").lower() if result.returncode == 0 else ""


def _system_theme() -> str:
    """Best-effort system appearance detection with a light fallback."""
    if sys.platform == "darwin":
        value = _command_output(["defaults", "read", "-g", "AppleInterfaceStyle"])
        return "dark" if value == "dark" else "light"
    if sys.platform == "win32":
        value = _command_output([
            "reg", "query",
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            "/v", "AppsUseLightTheme",
        ])
        return "dark" if "0x0" in value else "light"

    color_scheme = _command_output([
        "gsettings", "get", "org.gnome.desktop.interface", "color-scheme",
    ])
    if "prefer-dark" in color_scheme:
        return "dark"
    if "prefer-light" in color_scheme:
        return "light"

    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(Path.home() / ".config" / "kdeglobals", encoding="utf-8")
        kde_scheme = parser.get("General", "ColorScheme", fallback="").lower()
    except (configparser.Error, OSError, UnicodeError):
        kde_scheme = ""
    if kde_scheme:
        return "dark" if "dark" in kde_scheme else "light"

    gtk_theme = os.environ.get("GTK_THEME", "").lower()
    if "dark" in gtk_theme:
        return "dark"
    if "light" in gtk_theme:
        return "light"
    return "light"


def _resolve_theme() -> str:
    """Resolve the environment override or saved theme mode."""
    raw = os.environ.get(THEME_VARIABLE, "").strip().lower()
    if raw in ("light", "dark"):
        return raw
    mode = settings.resolve_theme()
    return _system_theme() if mode == "auto" else mode


def apply_theme(mode: str) -> str:
    """Apply a theme mode and update palette imports in loaded GUI modules."""
    global THEME
    if mode not in ("auto", "light", "dark"):
        mode = "auto"
    active = _system_theme() if mode == "auto" else mode
    palette = _LIGHT if active == "light" else _DARK
    previous = {name: globals().get(name) for name in palette}
    _apply_palette(palette)

    for module_name, module in tuple(sys.modules.items()):
        if (module is None or
                (module_name != "sortiton.gui" and
                 not module_name.startswith("sortiton.gui."))):
            continue
        namespace = vars(module)
        for name, old_colour in previous.items():
            if namespace.get(name) == old_colour:
                namespace[name] = palette[name]

    THEME = active
    return active


THEME = apply_theme(_resolve_theme())


def theme() -> str:
    """Der aktive Themenname (``light`` oder ``dark``)."""
    return THEME


FONT           = ("DejaVu Sans", 11)
FONT_SMALL     = ("DejaVu Sans", 10)
FONT_LABEL     = ("DejaVu Sans", 10, "bold")
FONT_TITLE     = ("DejaVu Sans", 15, "bold")
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
    """Verfügbare Desktop-Schriften mit Cantarell als erster Wahl laden."""
    global FONT, FONT_SMALL, FONT_LABEL, FONT_TITLE, FONT_SECTION, FONT_BUTTON, FONT_MONO
    present = {name.lower() for name in tkfont.families(root)}

    def first_available(candidates: list[str], default: str) -> str:
        for name in candidates:
            if name.lower() in present:
                return name
        return default

    family = first_available(["Cantarell", "Noto Sans", "Ubuntu", "Open Sans",
                              "DejaVu Sans"],
                             str(tkfont.nametofont("TkDefaultFont").actual("family")))
    mono = first_available(["JetBrains Mono", "Fira Code", "Cascadia Code", "Noto Sans Mono",
                            "DejaVu Sans Mono"],
                           str(tkfont.nametofont("TkFixedFont").actual("family")))
    FONT         = (family, 11)
    FONT_SMALL   = (family, 10)
    FONT_LABEL   = (family, 10, "bold")
    FONT_TITLE   = (family, 15, "bold")
    FONT_SECTION = (family, 12, "bold")
    FONT_BUTTON  = (family, 11)
    FONT_MONO    = (mono, 10)
