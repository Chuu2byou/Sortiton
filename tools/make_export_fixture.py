#!/usr/bin/env python3
"""Build - or check - the synthetic fixture library for the export feature.

    python3 tools/make_export_fixture.py            # build tests/fixtures/export_library
    python3 tools/make_export_fixture.py --check    # verify the committed library
    python3 tools/make_export_fixture.py --out DIR  # build somewhere else

The library must trigger every branch of the old ``musik_export.py`` analysis
(step 0.2 of ``PLAN_export_integration.md``).  It is generated once with ffmpeg
and then committed (decision A3), so the reference reports in ``tests/golden``
stay reproducible and the CI does not need ffmpeg for them.

The files are built deterministically: a fixed sine tone per file, fixed
bitrate/quality per format, all metadata set explicitly and ``+bitexact`` on
every stream.  Regenerating on a different ffmpeg build can still produce other
audio bytes, so ``--check`` compares existence, tags and total size - not the
raw bytes.

Only the source ``ffmpeg`` and the Python package ``mutagen`` are needed, and
only while building.  ``--check`` needs ``mutagen`` alone.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "tests" / "fixtures" / "export_library"

# The whole committed library must stay below this - the plan asks for < 300 kB.
SIZE_LIMIT = 300_000

# A lower sample rate keeps the lossless files small; the tone only has to be a
# valid, deterministic signal.
SAMPLE_RATE = 22050
DURATION = 0.5

# The fingerprint files need a signal chromaprint can tell apart and enough
# frames: it only starts emitting sub-fingerprints after ~2.7 s of context, and
# the comparison in musik_export.py wants at least 20 of them.  A 5.5 s
# frequency chirp gives ~24 frames and is not degenerate like a pure sine (whose
# chroma is constant).  Lossy formats are used here because such a chirp is about
# 90 kB in FLAC and the whole library must stay below the size budget.
FP_DURATION = 5.5
FP_SWEEP = (300, 900)
FP_OTHER_SWEEP = (1500, 5000)

# Encoder and a fixed bitrate/quality per file format.
ENCODERS: dict[str, list[str]] = {
    "flac": ["-c:a", "flac", "-compression_level", "12"],
    "mp3": ["-c:a", "libmp3lame", "-b:a", "128k"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "3"],
    "opus": ["-c:a", "libopus", "-b:a", "64k"],
    "m4a": ["-c:a", "aac", "-b:a", "128k"],
}

# ffmpeg metadata names on the left, the names mutagen's easy interface uses on
# the right.  Everything else keeps its name.
EASY_KEYS: dict[str, str] = {
    "album_artist": "albumartist",
    "track": "tracknumber",
    "disc": "discnumber",
}

TagValue = Union[str, tuple[str, ...]]


@dataclass(frozen=True)
class Track:
    """One planned file: relative path, tags and how the audio is produced."""

    path: str
    tags: dict[str, TagValue] = field(default_factory=dict)
    freq: int = 440
    seconds: float = DURATION
    rate: int = SAMPLE_RATE
    sweep: tuple[int, int] | None = None      # (start, end) Hz -> a chirp
    encoder: tuple[str, ...] | None = None    # overrides ENCODERS for this file
    cover: bool = False
    raw: bytes | None = None          # written verbatim (the broken file)


def meta(**tags: TagValue) -> dict[str, TagValue]:
    """Tags without the empty ones (an empty value means "tag is missing")."""
    return {key: value for key, value in tags.items() if value not in ("", None)}


def library() -> list[Track]:
    """The full manifest - one entry for every branch the analysis must hit."""
    tracks: list[Track] = []

    def add(path: str, tags: dict[str, TagValue], **kwargs: object) -> None:
        tracks.append(Track(path, tags, **kwargs))    # type: ignore[arg-type]

    # 1. Full tags with an explicit total; track 3 is missing -> gap.
    #    The third file carries the spelling variant "artist a" (norm-equal).
    add("Artist A/Album One/01 - Song One.flac",
        meta(artist="Artist A", album_artist="Artist A", album="Album One",
             title="Song One", track="1/3", disc="1", date="2001",
             genre="Rock", mood="calm"))
    add("Artist A/Album One/02 - Song Two.flac",
        meta(artist="Artist A", album_artist="Artist A", album="Album One",
             title="Song Two", track="2/3", disc="1", date="2001", genre="Rock"))
    add("Artist A/Album One/03b - Other.flac",
        meta(artist="artist a", album_artist="Artist A", album="Album One",
             title="Other", genre="Rock"))

    # 2. Sampler: five artists, no album artist, two files share track 1.
    for index, artist in enumerate(("Alpha", "Beta", "Gamma", "Delta", "Epsilon"),
                                   start=1):
        track = "1" if index <= 2 else str(index - 1)
        add(f"Sampler/{index:02d}.mp3",
            meta(artist=artist, album="Sampler", title=f"{artist} One",
                 track=track, genre="Pop"))

    # 3. Junk in the title, a double space and the track number inside the tag.
    add("Artist B/Album Two/01 Song (Official Video).ogg",
        meta(artist="Artist B", album_artist="Artist B", album="Album Two",
             title="01 -  Song (Official Video)", track="1", genre="Pop"))
    #    Underscores instead of spaces.
    add("Artist B/Album Two/02 - snake_case_title.opus",
        meta(artist="Artist B", album_artist="Artist B", album="Album Two",
             title="snake_case_title", track="2", genre="Pop"))
    #    A "(2)" duplicate marker and the same artist+title as the single below.
    add("Artist B/Album Two/03 - Same Song (2).m4a",
        meta(artist="Artist B", album_artist="Artist B", album="Album Two",
             title="Same Song", track="3", genre="Pop"))
    add("Artist B/Singles/Same Song.m4a",
        meta(artist="Artist B", title="Same Song", genre="Pop"))

    # 4. Top folder and album folder both disagree with the tags.
    add("Wrong Folder/Album Three/01.flac",
        meta(artist="Artist C", album_artist="Artist C", album="Different Album",
             title="Wrong One", track="1", genre="Rock"))

    # 5. Two discs; the "CD1"/"CD2" folders must be skipped in folder_vs_tags.
    for disc, label in ((1, "One"), (2, "Two")):
        for number, suffix in ((1, "A"), (2, "B")):
            add(f"Artist D/Album Four/CD{disc}/{number:02d} - Disc {label} {suffix}.flac",
                meta(artist="Artist D", album_artist="Artist D", album="Album Four",
                     title=f"Disc {label} {suffix}", track=str(number),
                     disc=f"{disc}/2", genre="Rock"))

    # 6. Two genres on one file (joined with " | "), plus every date branch.
    add("Artist E/Album Five/01 - Cherry.flac",
        meta(artist="Artist E", album_artist="Artist E", album="Album Five",
             title="Cherry", track="1", date="2001-05-04",
             genre=("J-Pop", "Rock")))
    add("Artist E/Album Five/02 - Sakura.flac",
        meta(artist="Artist E", album_artist="Artist E", album="Album Five",
             title="Sakura", track="2", date="04.05.2001", genre="J-Pop"))
    add("Artist E/Album Five/03 - Hana.flac",
        meta(artist="Artist E", album_artist="Artist E", album="Album Five",
             title="Hana", track="3", date="Spring 2001", genre="Rock"))
    add("Artist E/Album Five/04 - Yuki.flac",
        meta(artist="Artist E", album_artist="Artist E", album="Album Five",
             title="Yuki", track="4", date="2001-2003", genre="J-Pop"))
    add("Artist E/Album Five/05 - Sora.flac",
        meta(artist="Artist E", album_artist="Artist E", album="Album Five",
             title="Sora", track="5", genre="J-Pop"))

    # 7. Dense sequence with a gap (no total) - tracks 1, 2, 4, 5.
    for number in (1, 2, 4, 5):
        add(f"Artist G/Album Six/{number:02d} - Six {number}.flac",
            meta(artist="Artist G", album_artist="Artist G", album="Album Six",
                 title=f"Six {number}", track=str(number), genre="Rock"))
    # 8. Sparse sequence - tracks 1, 7, 40.
    for number in (1, 7, 40):
        add(f"Artist G/Album Seven/{number:02d} - Seven {number}.flac",
            meta(artist="Artist G", album_artist="Artist G", album="Album Seven",
                 title=f"Seven {number}", track=str(number), genre="Rock"))

    # 9. No track tag at all -> "all track tags missing".
    for number in (1, 2, 3):
        add(f"Artist H/Album Eight/{number:02d} - Eight {number}.flac",
            meta(artist="Artist H", album_artist="Artist H", album="Album Eight",
                 title=f"Eight {number}", genre="Rock"))

    # 10. Only the --gross-klein run may flag this one.
    add("ALLCAPS ARTIST/ALLCAPS ALBUM/LOUD SONG.flac",
        meta(artist="ALLCAPS ARTIST", album_artist="ALLCAPS ARTIST",
             album="ALLCAPS ALBUM", title="LOUD SONG", track="1", genre="Rock"))

    # 11. Accents and kana: "Ünïcode" vs "Unicode" are one variant, but the
    #     dakuten titles ほ and ぼ must stay different.
    add("Ünïcode/ほ.flac",
        meta(artist="Ünïcode", album_artist="Ünïcode", album="Ünïcode Album",
             title="ほ", track="1", genre="J-Pop"))
    add("Ünïcode/ぼ.flac",
        meta(artist="Unicode", album_artist="Unicode", album="Ünïcode Album",
             title="ぼ", track="2", genre="J-Pop"))

    # 12. A loose file directly in the root folder.
    add("loose.mp3", meta(artist="Loose Artist", title="Loose Track", genre="Rock"))

    # 13. A read error (64 null bytes).
    add("broken.mp3", {}, raw=b"\x00" * 64)

    # 14. A hidden folder - the old script reads it, and that must stay visible.
    add(".hidden/secret.flac",
        meta(artist="Hidden Artist", album_artist="Hidden Artist",
             album="Hidden Album", title="Secret", track="1", genre="Rock"))

    # 15. Fingerprint group: two identical chirps (opus and mp3) and one
    #     clearly different chirp.  Both share artist+title so they may be
    #     classified as a very likely duplicate.
    fp_tags = meta(artist="Fp Artist", album_artist="Fp Artist", album="Fp Album",
                   genre="Electronic")
    add("Fp/same_a.opus",
        {**fp_tags, "title": "Same Song", "track": "1"},
        seconds=FP_DURATION, sweep=FP_SWEEP,
        encoder=("-c:a", "libopus", "-b:a", "32k"))
    add("Fp/same_b.mp3",
        {**fp_tags, "title": "Same Song", "track": "1"},
        seconds=FP_DURATION, sweep=FP_SWEEP,
        encoder=("-c:a", "libmp3lame", "-b:a", "48k"))
    add("Fp/other.opus",
        {**fp_tags, "title": "Other Song", "track": "2"},
        seconds=FP_DURATION, sweep=FP_OTHER_SWEEP,
        encoder=("-c:a", "libopus", "-b:a", "32k"))

    # 16. A FLAC with an embedded cover -> cover = "j".
    add("Cover Artist/Cover Album/Art.flac",
        meta(artist="Cover Artist", album_artist="Cover Artist",
             album="Cover Album", title="Art", track="1", genre="Rock"),
        cover=True)

    return tracks


# --------------------------------------------------------------------------
# Building
# --------------------------------------------------------------------------
def signal_input(track: Track) -> str:
    """The lavfi source for one file: a plain tone or a frequency chirp."""
    if track.sweep is None:
        return (f"sine=frequency={track.freq}:sample_rate={track.rate}"
                f":duration={track.seconds}")
    start, end = track.sweep
    expr = f"sin(2*PI*({start}*t+({end}-{start})*t*t/(2*{track.seconds})))"
    return f"aevalsrc={expr}:s={track.rate}:d={track.seconds}"


def ffmpeg_command(track: Track, out_path: Path, cover_png: Path | None) -> list[str]:
    """The deterministic ffmpeg call that writes one file."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", signal_input(track)]
    if cover_png is not None:
        cmd += ["-i", str(cover_png)]
    cmd += ["-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact"]
    if cover_png is not None:
        cmd += ["-map", "0:a", "-map", "1:v", "-disposition:v", "attached_pic",
                "-c:v", "png"]
    encoder = track.encoder if track.encoder is not None \
        else ENCODERS[out_path.suffix.lstrip(".")]
    cmd += list(encoder)
    for key, value in track.tags.items():
        first = value[0] if isinstance(value, tuple) else value
        cmd += ["-metadata", f"{key}={first}"]
    cmd.append(str(out_path))
    return cmd


def make_cover(path: Path) -> None:
    """A tiny, deterministic image for the embedded cover."""
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "color=c=steelblue:s=120x120", "-frames:v", "1",
         str(path)],
        check=True)


def write_multi_value_tags(path: Path, track: Track) -> None:
    """Add repeated tags (e.g. two genres) that ffmpeg only writes once."""
    multi = {EASY_KEYS.get(key, key): list(value)
             for key, value in track.tags.items() if isinstance(value, tuple)}
    if not multi:
        return
    import mutagen                                    # noqa: PLC0415 (late import)

    audio = mutagen.File(path, easy=True)
    if audio is None:
        raise RuntimeError(f"cannot tag {path}")
    for key, values in multi.items():
        audio[key] = values
    audio.save()


def strip_flac_padding(path: Path) -> None:
    """Drop the 8 KiB PADDING block ffmpeg adds to every FLAC.

    Without this the library would be far over the size budget.  Killing the
    block is safe here: it only reserves room for growing tags.  The operation
    is done by hand so no extra tool (``metaflac``) is needed.
    """
    data = path.read_bytes()
    if data[:4] != b"fLaC":
        return
    pos, blocks = 4, []
    while True:
        header = data[pos]
        is_last = bool(header & 0x80)
        block_type = header & 0x7F
        length = int.from_bytes(data[pos + 1:pos + 4], "big")
        blocks.append((block_type, data[pos + 4:pos + 4 + length]))
        pos += 4 + length
        if is_last:
            break
    kept = [(block_type, body) for block_type, body in blocks if block_type != 1]
    if len(kept) == len(blocks):
        return
    out = bytearray(b"fLaC")
    for index, (block_type, body) in enumerate(kept):
        last = 0x80 if index == len(kept) - 1 else 0
        out.append(last | block_type)
        out += len(body).to_bytes(3, "big")
        out += body
    out += data[pos:]
    path.write_bytes(bytes(out))


def build_library(out_dir: Path, *, force: bool = False) -> int:
    if shutil.which("ffmpeg") is None:
        print("error: ffmpeg is not on PATH - it is needed to build the library",
              file=sys.stderr)
        return 2
    try:
        import mutagen                                # noqa: PLC0415,F401
    except ImportError:
        print("error: the Python package 'mutagen' is needed (pip install mutagen)",
              file=sys.stderr)
        return 2

    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()) and not force:
        print(f"error: {out_dir} is not empty - pass --force to replace it",
              file=sys.stderr)
        return 2
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    tracks = library()
    with tempfile.TemporaryDirectory(prefix="export-fixture-") as tmp:
        cover = Path(tmp) / "cover.png"
        make_cover(cover)
        for track in tracks:
            target = out_dir / track.path
            target.parent.mkdir(parents=True, exist_ok=True)
            if track.raw is not None:
                target.write_bytes(track.raw)
                continue
            subprocess.run(ffmpeg_command(track, target, cover if track.cover else None),
                           check=True)
            write_multi_value_tags(target, track)
            if target.suffix == ".flac":
                strip_flac_padding(target)

    total = sum(item.stat().st_size for item in out_dir.rglob("*") if item.is_file())
    print(f"built {len(tracks)} files ({total} bytes) in {out_dir}")
    return 0


# --------------------------------------------------------------------------
# Checking
# --------------------------------------------------------------------------
def tag_differences(path: Path, track: Track) -> str:
    """The tags that do not match the manifest, as readable text ("" = ok)."""
    import mutagen                                    # noqa: PLC0415 (late import)

    audio = mutagen.File(path, easy=True)
    if audio is None or audio.tags is None:
        return "file is not readable"
    diffs = []
    for key, value in track.tags.items():
        easy = EASY_KEYS.get(key, key)
        wanted = sorted(value) if isinstance(value, tuple) else [value]
        got = sorted(str(item) for item in audio.tags.get(easy, []))
        if wanted != got:
            diffs.append(f"{key}: expected {wanted}, got {got}")
    return "; ".join(diffs)


def check_library(out_dir: Path, limit_bytes: int) -> int:
    try:
        import mutagen                                # noqa: PLC0415,F401
    except ImportError:
        print("error: the Python package 'mutagen' is needed for --check "
              "(pip install mutagen)", file=sys.stderr)
        return 2

    out_dir = Path(out_dir)
    if not out_dir.is_dir():
        print(f"error: {out_dir} does not exist - build it first (without --check)",
              file=sys.stderr)
        return 2

    tracks = library()
    expected = {track.path for track in tracks}
    problems: list[str] = []
    total = 0
    for track in tracks:
        target = out_dir / track.path
        if not target.is_file():
            problems.append(f"missing: {track.path}")
            continue
        total += target.stat().st_size
        if track.raw is not None:
            if target.read_bytes() != track.raw:
                problems.append(f"content differs: {track.path}")
            continue
        diff = tag_differences(target, track)
        if diff:
            problems.append(f"tags differ: {track.path} ({diff})")
    for item in sorted(out_dir.rglob("*")):
        if item.is_file():
            rel = item.relative_to(out_dir).as_posix()
            if rel not in expected:
                problems.append(f"unexpected: {rel}")

    print(f"library: {out_dir}")
    print(f"files: {len(tracks)}, size: {total} bytes "
          f"({100 * total / limit_bytes:.0f}% of the {limit_bytes} byte limit)")
    print("note: audio bytes depend on the ffmpeg build, so only the files, "
          "their tags and the total size are compared - a rebuild may produce "
          "different bytes.")
    if total > limit_bytes:
        problems.append(f"size {total} exceeds the limit of {limit_bytes} bytes")
    if problems:
        print(f"RESULT: FAILED ({len(problems)} problem(s))")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("RESULT: ok - the library matches the script")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build or check the synthetic export fixture library.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help=f"library folder (default: {DEFAULT_OUT.relative_to(ROOT)})")
    parser.add_argument("--check", action="store_true",
                        help="verify the existing library instead of building it")
    parser.add_argument("--force", action="store_true",
                        help="replace a non-empty output folder while building")
    parser.add_argument("--limit-bytes", type=int, default=SIZE_LIMIT,
                        help=f"size limit used by --check (default: {SIZE_LIMIT})")
    args = parser.parse_args(argv)

    if args.check:
        return check_library(args.out, args.limit_bytes)
    return build_library(args.out, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
