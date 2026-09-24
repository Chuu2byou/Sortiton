#!/usr/bin/env python3
"""Sortiton for Linux - command line entry point.

Commands:
  tags   FOLDER           clean tags (artist, album artist, title, album, genre)
  rename FOLDER           rename from tags (default "%artist% - %title%")
  sort   SOURCE TARGET    sort into artist/album/file (no album -> artist/file)
  all    SOURCE TARGET    all-in-one: clean tags -> rename -> sort
  scan   FOLDER           only count files/albums/artists, change nothing
  rules                   show or create your own rules (my_rules.ini)
  restore                 undo the changes of an earlier run (from its journal)

A preview is always the default - only ``--apply`` writes, and nothing is ever
overwritten (collisions get " (2)", " (3)", ...). ``SORTITON_LANG=de`` switches
the language; the logic lives in the ``sortiton`` package.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Own folder has to be importable, also from another cwd.
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sortiton.cli import main  # noqa: E402  (after the sys.path entry)


if __name__ == "__main__":
    raise SystemExit(main())
