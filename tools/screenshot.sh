#!/usr/bin/env bash
# Take the README screenshot.
#
#   tools/screenshot.sh
#
# Builds a synthetic demo library in a temp folder, opens the real window on it
# and stores assets/screenshot.png. Only the Sortiton window ends up in the
# image, never the screen. Needs ffmpeg, a display and ImageMagick `import`
# (spectacle works as a fallback).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# The project venv has tkinter and mutagen; the system python may not.
if [ -x "$ROOT/.venv/bin/python3" ]; then
    PATH="$ROOT/.venv/bin:$PATH"
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/sortiton-shot-XXXXXX")"
export SORTITON_SHOT_DIR="$WORK"
trap 'rm -rf "$WORK"' EXIT

python3 "$ROOT/tools/make_screenshots.py"
