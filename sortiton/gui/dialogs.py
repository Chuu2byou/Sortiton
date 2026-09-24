"""System dialogs: kdialog/zenity preferred, Tkinter as the fallback.

Every call uses ``check=False`` - a missing program simply leads to the next
variant.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from tkinter import filedialog, messagebox

from .. import i18n


def _command_available(name: str) -> bool:
    return shutil.which(name) is not None


def _pick_folder(start_dir: Path) -> str | None:
    """Modern system folder dialog: kdialog (KDE) → zenity (GNOME) → Tkinter."""
    title = i18n.t("gui.dialog.pick_folder")
    if _command_available("kdialog"):
        try:
            result = subprocess.run(
                ["kdialog", "--getexistingdirectory", str(start_dir), "--title", title],
                capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return result.stdout.strip() or None
            if result.returncode == 1:
                return None          # cancelled by the user
        except OSError:
            pass
    if _command_available("zenity"):
        try:
            result = subprocess.run(
                ["zenity", "--file-selection", "--directory",
                 f"--filename={start_dir}/", f"--title={title}"],
                capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return result.stdout.strip() or None
            return None
        except OSError:
            pass
    chosen = filedialog.askdirectory(title=title, initialdir=str(start_dir), mustexist=True)
    return chosen or None


def _ask_yes_no(title: str, text: str) -> bool:
    """Yes/no dialog, native first: kdialog, then zenity, then Tkinter."""
    if _command_available("kdialog"):
        try:
            result = subprocess.run(
                ["kdialog", "--yesno", text, "--title", title, "--defaultno"],
                capture_output=True, text=True, check=False)
            return result.returncode == 0
        except OSError:
            pass
    if _command_available("zenity"):
        try:
            result = subprocess.run(
                ["zenity", "--question", f"--title={title}", f"--text={text}"],
                capture_output=True, text=True, check=False)
            return result.returncode == 0
        except OSError:
            pass
    return messagebox.askyesno(title, text, icon="warning", default="no")


def _show_error(title: str, text: str) -> None:
    if _command_available("kdialog"):
        try:
            subprocess.run(["kdialog", "--error", text, "--title", title],
                           capture_output=True, text=True, check=False)
            return
        except OSError:
            pass
    if _command_available("zenity"):
        try:
            subprocess.run(["zenity", "--error", f"--title={title}", f"--text={text}"],
                           capture_output=True, text=True, check=False)
            return
        except OSError:
            pass
    messagebox.showerror(title, text)


def _show_warning(title: str, text: str) -> None:
    if _command_available("kdialog"):
        try:
            subprocess.run(["kdialog", "--sorry", text, "--title", title],
                           capture_output=True, text=True, check=False)
            return
        except OSError:
            pass
    if _command_available("zenity"):
        try:
            subprocess.run(["zenity", "--warning", f"--title={title}", f"--text={text}"],
                           capture_output=True, text=True, check=False)
            return
        except OSError:
            pass
    messagebox.showwarning(title, text)
