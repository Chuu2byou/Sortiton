#!/usr/bin/env python3
"""Compatibility wrapper: run the pytest suite.

The checks themselves live in the ``test_*.py`` modules next to this file; this
script keeps ``python3 tests/smoke.py`` working for existing callers.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

if __name__ == "__main__":
    sys.exit(pytest.main(["-q", str(Path(__file__).resolve().parent)]))
