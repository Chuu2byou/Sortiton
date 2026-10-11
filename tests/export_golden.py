"""Shared helpers for the export golden files (steps 0.3 and 2.1).

The export writes two lines that depend on the machine and on the moment it
runs: the absolute source folder and the creation timestamp. Both values are
turned into fixed placeholders before a golden file is stored, and the same
function is used again whenever a later run is compared against it, so both
sides normalise exactly the same way.

The label in front of the value is kept: the German report writes
``Ordner:``/``Erstellt:``, the English one ``Folder:``/``Created:``, so
``tests/golden/export/base`` and ``tests/golden/export/base_en`` each store
their own label.

The generator ``tools/make_export_golden.py`` loads this module by path; the
smoke test imports it like any other test helper.
"""

from __future__ import annotations

import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
FIXTURE_DIR = BASE / "tests" / "fixtures" / "export_library"
GOLDEN_DIR = BASE / "tests" / "golden" / "export"
#: The English report of the same run (step 2.1, ``report_lang="en"``).
EN_GOLDEN_DIR = GOLDEN_DIR / "base_en"

# The exact invocation of step 0.3, variant A.  ``--chunk-zeichen 1500`` is far
# below the size of the whole library on purpose, so the run produces several
# ``tracks_part*.tsv`` files and the "keep a folder together" logic of
# ``write_chunks`` is exercised too.
BASE_ARGS = ("--chunk-zeichen", "1500", "--beispiele", "5", "--jsonl", "--quiet")
# Variant B: the same run plus ``--gross-klein``; only ``01_*`` and ``02_*``
# are stored (see the generator's module docstring).
CASE_ARGS = BASE_ARGS + ("--gross-klein",)

_ROOT_RE = re.compile(r"^(- (?:Ordner|Folder): ).*$", re.MULTILINE)
_DATE_RE = re.compile(r"^(- (?:Erstellt|Created): ).*$", re.MULTILINE)


def normalize_export_text(text: str) -> str:
    """Replace the machine and run dependent values with fixed placeholders."""
    text = _ROOT_RE.sub(r"\1<ROOT>", text)
    return _DATE_RE.sub(r"\1<DATE>", text)
