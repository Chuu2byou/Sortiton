"""Pytest setup: keep the suite away from the user's real files.

The ``SORTITON_*`` variables have to be in place before anything imports
:mod:`sortiton`, because ``config`` resolves the paths at import time.  That is
why this module sets them at the top and not in a fixture.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="sortiton-pytest-"))
os.environ["SORTITON_SETTINGS"] = str(_TMP / "settings.ini")
os.environ["SORTITON_RULES"] = str(_TMP / "my_rules.ini")
os.environ["SORTITON_LOG_DIR"] = str(_TMP / "logs")
os.environ["SORTITON_EXPORT_DIR"] = str(_TMP / "exports")
os.environ["SORTITON_CACHE_DIR"] = str(_TMP / "cache")
os.environ["SORTITON_BACKUP_DIR"] = str(_TMP / "backups")
os.environ["SORTITON_FETCH_ARCHIVE"] = str(_TMP / "fetch_archive.txt")
os.environ.pop("SORTITON_LANG", None)

# ``_support`` is a sibling module, not an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _suite_environment():
    """Activate the language once and remove the temp folder at the end."""
    from sortiton import i18n, journal, output, settings  # noqa: WPS433

    settings.apply_language()
    yield
    journal.close()
    output.close_log_file()
    i18n.set_language("en")
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(autouse=True)
def _no_blocking_dialogs(monkeypatch):
    """Ein modaler Dialog ohne Nutzer hängt den Lauf bis zum Timeout.

    Auf dem CI-Runner fehlen ``kdialog`` und ``zenity``, deshalb fällt
    ``sortiton.gui.dialogs._ask_yes_no`` auf ``tkinter.messagebox`` zurück und
    wartet auf eine Antwort, die nie kommt - belegt durch den faulthandler-Dump
    des GUI-Jobs (``_llm_rules_apply`` -> ``_rules_editor`` -> ``askyesno``).
    Tests, die eine Rückfrage brauchen, patchen die Funktion in ihrem Modul;
    alles andere scheitert hier sofort mit einer lesbaren Meldung.
    """
    try:
        from tkinter import filedialog, messagebox  # noqa: WPS433
    except ImportError:  # Tkinter fehlt (headless build) - nichts zu schützen
        return

    def refuse(name: str):
        def _blocked(*_args, **_kwargs):
            raise RuntimeError(
                f"modal tkinter dialog {name}() would block the test run - "
                "patch the caller's dialog function instead")
        return _blocked

    patched = (
        (messagebox, ("askyesno", "askokcancel", "askretrycancel", "askquestion",
                      "showinfo", "showwarning", "showerror")),
        (filedialog, ("askopenfilename", "askopenfilenames", "asksaveasfilename",
                      "askdirectory")),
    )
    for module, names in patched:
        for name in names:
            monkeypatch.setattr(module, name, refuse(name), raising=False)
