#!/usr/bin/env python3
"""Take the README screenshot on a throw-away demo library.

    tools/screenshot.sh
    SORTITON_SHOT_DIR=/tmp/… python3 tools/make_screenshots.py

Starts the real window on a synthetic folder, runs a preview and stores it as
``assets/screenshot.png``. Everything is synthetic - the image is committed, so
it must never show a real collection or a home directory. Only the Sortiton
window itself is captured and the result is checked against its size, so no
other program can end up in the picture. Needs ffmpeg and ImageMagick
``import`` (or spectacle).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 6 albums x 20 tracks = 120 files. Placeholder names, deliberately messy tags
# so the preview has something to show.
ALBUMS: tuple[tuple[str, str], ...] = (
    ("Greatest  Demo", "Sample Band"),
    ("First Album", "DEMO ORCHESTRA"),
    ("Second Album", "Example Crew"),
    ("Third Album", "Sample Band"),
    ("Fourth Album", "DEMO ORCHESTRA"),
    ("Fifth Album", "Example Crew"),
)
TRACKS_PER_ALBUM = 20
DOUBLE_SPACED_TRACKS = (3, 11, 17)     # titles that need whitespace cleanup
GENRES = ("jpop", "rock; pop", "kpop", "vtuber", "J Pop", "j-rock", "jrock",
          "k-pop", "cpop", "vocaloid")

DEMO_RULES = """\
# Demo rules for the screenshot (synthetic names only).
[Artist]
DEMO ORCHESTRA = Demo Orchestra

[Artist Regex]
(?i)\\bexample\\s+crew\\b = Example Crew

[Genre]
rock = Rock
pop = Pop

[Protected]
Example & Co
"""


def build_library(music: Path) -> int:
    """Create the demo files (kept when the folder is already filled)."""
    if music.is_dir() and any(music.glob("*.mp3")):
        return len(list(music.glob("*.mp3")))

    music.mkdir(parents=True, exist_ok=True)
    number = 0
    for album, artist in ALBUMS:
        for index in range(1, TRACKS_PER_ALBUM + 1):
            number += 1
            title = f"Track {index:02d}"
            if index in DOUBLE_SPACED_TRACKS:
                title = f"Track  {index:02d}"
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                 "-i", "anullsrc=r=44100:cl=mono", "-t", "0.3",
                 "-metadata", f"artist={artist}",
                 "-metadata", f"title={title}",
                 "-metadata", f"album={album}",
                 "-metadata", f"genre={GENRES[number % len(GENRES)]}",
                 str(music / f"{number:03d} {title}.mp3")],
                check=True)
    return number


def png_size(path: Path) -> tuple[int, int] | None:
    """Width and height of a PNG, read from its header (no tool needed)."""
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
    except OSError:
        return None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return (int.from_bytes(header[16:20], "big"),
            int.from_bytes(header[20:24], "big"))


def looks_like_window(path: Path, window: tuple[int, int],
                      screen: tuple[int, int]) -> bool:
    """Whether the stored image really shows the Sortiton window.

    The images are committed, so the run must never leave a picture of
    something else behind. The size has to match the window - decorations
    added - and must not be the whole screen.
    """
    size = png_size(path)
    if size is None or size == screen:
        return False
    return abs(size[0] - window[0]) <= 40 and abs(size[1] - window[1]) <= 60


def capture(path: Path, window_id: str, window: tuple[int, int],
            screen: tuple[int, int]) -> bool:
    """Store the Sortiton window - never another window, never the screen.

    ImageMagick gets the window id from Tk and can therefore only photograph
    that one window. Spectacle has no such option, so its active-window shot
    is only kept when the size check confirms it. The whole screen is never
    captured: the user may have anything on it.

    Every attempt lands in a scratch file next to the target and only replaces
    it once the check passed - a failed run must not delete the picture that is
    committed in the repository.
    """
    attempts: list[tuple[str, list[str]]] = []
    if shutil.which("import") is not None:
        attempts.append(("import", ["-window", window_id]))
    if shutil.which("spectacle") is not None:
        attempts.append(("spectacle", ["-b", "-n", "-a"]))

    # The scratch file keeps the .png suffix on purpose: ImageMagick picks the
    # output format from the extension and would write rubbish without it.
    shot = path.with_name(path.stem + ".new" + path.suffix)
    for tool, options in attempts:
        shot.unlink(missing_ok=True)
        if tool == "import":
            argv = [tool, *options, str(shot)]
        else:
            argv = [tool, *options, "-o", str(shot)]
        result = subprocess.run(argv, check=False, capture_output=True)
        if result.returncode != 0 or not shot.is_file():
            continue
        if looks_like_window(shot, window, screen):
            shot.replace(path)
            return True
        print(f"  rejected {tool}: {png_size(shot)} is not the window "
              f"{window[0]}x{window[1]}", file=sys.stderr)
        shot.unlink(missing_ok=True)
    shot.unlink(missing_ok=True)
    return False


def shoot(work: Path) -> bool:
    """Build the window on the demo library, run a preview and capture it.

    True only when the picture was really taken: the picture on disk says
    nothing, because a failed run leaves the previous one in place.
    """
    music = work / "Music"
    os.environ.update({
        "SORTITON_FOLDER": str(music),
        "SORTITON_TARGET": str(work / "target"),
        "SORTITON_RULES": str(work / "my_rules.ini"),
        "SORTITON_LOG_DIR": str(work / "logs"),
        "SORTITON_BACKUP_DIR": str(work / "backups"),
        "SORTITON_SETTINGS": str(work / "settings.ini"),
        # The screenshot is English; a SORTITON_LANG of the caller must not
        # leak into the picture.
        "SORTITON_LANG": "en",
    })
    (work / "target").mkdir(parents=True, exist_ok=True)
    (work / "my_rules.ini").write_text(DEMO_RULES, encoding="utf-8")
    (work / "settings.ini").write_text("[general]\nbackup = true\n",
                                       encoding="utf-8")

    sys.path.insert(0, str(ROOT))
    import tkinter as tk                       # noqa: PLC0415 (env is set now)
    from sortiton import settings              # noqa: PLC0415
    from sortiton.gui.app import SortitonGUI   # noqa: PLC0415

    settings.apply_language()

    target = ROOT / "assets" / "screenshot.png"
    deadline = time.monotonic() + 120
    taken = False

    root = tk.Tk()
    gui = SortitonGUI(root)

    def start_preview() -> None:
        # The same call the "Create preview" button makes - the window is driven
        # from the outside on purpose, so the shot shows a reachable state.
        gui._run_tags(False)                 # noqa: SLF001
        root.after(400, wait_for_run)

    def wait_for_run() -> None:
        if time.monotonic() > deadline:
            root.quit()
            return
        if gui.running:
            root.after(200, wait_for_run)
            return
        root.after(900, take)

    def take() -> None:
        nonlocal taken
        root.lift()
        root.update()
        time.sleep(1.2)                      # give the compositor a moment
        window = (root.winfo_width(), root.winfo_height())
        screen = (root.winfo_screenwidth(), root.winfo_screenheight())
        window_id = hex(root.winfo_id())
        print(f"  window {window[0]}x{window[1]} ({window_id}), "
              f"screen {screen[0]}x{screen[1]}")
        taken = capture(target, window_id, window, screen)
        print(f"  {'ok ' if taken else 'FAIL'} {target.relative_to(ROOT)}")
        root.quit()

    root.after(900, start_preview)
    try:
        root.mainloop()
    finally:
        root.destroy()
    return taken


def main() -> int:
    work = Path(os.environ.get("SORTITON_SHOT_DIR", "")
                or tempfile.mkdtemp(prefix="sortiton-shot-"))
    work.mkdir(parents=True, exist_ok=True)
    count = build_library(work / "Music")
    print(f"demo library: {work / 'Music'} ({count} files)")
    if not shoot(work):
        print("  no screenshot taken - needs a display and ImageMagick ''import'' "
              "(or spectacle) and it must be the Sortiton window that gets "
              "captured; the stored picture was left untouched", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
