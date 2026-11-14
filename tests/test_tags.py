"""Tag reading and writing (``sortiton/tags.py``).

Expected values come from the export golden (``alle_tags.jsonl``), keeping the
tag reader and report in sync. Tests that need real audio files generate them
with ffmpeg and are skipped otherwise.
"""

from __future__ import annotations

import json
import unittest.mock as mock

import pytest

from _support import (
    _INFO_TO_RECORD,
    Path,
    _load_export_helper,
    check,
    importlib,
    shutil,
    tempfile,
)

FIXTURE = _load_export_helper().FIXTURE_DIR
FLAC_SAMPLE = FIXTURE / "Artist A" / "Album One" / "01 - Song One.flac"

#: One fixture for each format the reader must support.
SAMPLES = ("Artist A/Album One/01 - Song One.flac",
           "Sampler/01.mp3",
           "Artist B/Album Two/01 Song (Official Video).ogg",
           "Artist B/Album Two/02 - snake_case_title.opus",
           "Artist B/Album Two/03 - Same Song (2).m4a")


@pytest.mark.external
@pytest.mark.skipif(importlib.util.find_spec("mutagen") is None, reason="mutagen not installed")
def test_tag_reader() -> None:
    """``read_info`` reads all eight fields for every supported format."""
    from sortiton.tags import TAG_FIELDS, TrackInfo, read_info

    helper = _load_export_helper()
    golden_file = helper.GOLDEN_DIR / "base" / "alle_tags.jsonl"
    if not FIXTURE.is_dir() or not golden_file.is_file():
        pytest.skip("fixture or golden missing")

    records = {}
    for line in golden_file.read_text(encoding="utf-8").splitlines():
        if line:
            record = json.loads(line)
            records[record["path"]] = record

    for rel in SAMPLES:
        info = read_info(FIXTURE / rel)
        ext = Path(rel).suffix.lstrip(".")
        check(f"read_info reads {ext}", isinstance(info, TrackInfo) and not info.error,
              info.error)
        if info.error:
            continue
        wrong = {field: (info.joined(field, " | "), records[rel][_INFO_TO_RECORD[field]])
                 for field in TAG_FIELDS
                 if info.joined(field, " | ") != records[rel][_INFO_TO_RECORD[field]]}
        check(f"read_info fills all eight fields ({ext})", not wrong, str(wrong))


@pytest.mark.external
@pytest.mark.skipif(importlib.util.find_spec("mutagen") is None, reason="mutagen not installed")
def test_probe_tags_keeps_its_five_text_fields() -> None:
    """``probe_tags`` keeps the five text fields and the ``"; "`` separator.

    Expected values were recorded before the readers were unified. This test
    protects tags/rename/sort/scan. The additional ``track``, ``disc`` and
    ``year`` fields are allowed; they populate ``%track%``, ``%disc%`` and
    ``%year%``.
    """
    from sortiton.tags import probe_tags

    if not FIXTURE.is_dir():
        pytest.skip("export fixture missing")

    expected = {
        "Artist A/Album One/01 - Song One.flac":
            {"artist": "Artist A", "album_artist": "Artist A", "album": "Album One",
             "title": "Song One", "genre": "Rock"},
        "Sampler/01.mp3":
            {"artist": "Alpha", "album_artist": "", "album": "Sampler",
             "title": "Alpha One", "genre": "Pop"},
        "Artist E/Album Five/01 - Cherry.flac":
            {"artist": "Artist E", "album_artist": "Artist E", "album": "Album Five",
             "title": "Cherry", "genre": "J-Pop; Rock"},
        "Ünïcode/ぼ.flac":
            {"artist": "Unicode", "album_artist": "Unicode", "album": "Ünïcode Album",
             "title": "ぼ", "genre": "J-Pop"},
    }
    for rel, want in expected.items():
        got = probe_tags(FIXTURE / rel)
        core = {name: got.get(name) for name in want}
        check(f"probe_tags keeps the five fields ({Path(rel).name})", core == want,
              f"{core} != {want}")


def test_probe_tags_includes_track_disc_and_year() -> None:
    """All supported name placeholders receive values from tag reading.

    Both the single-file reader and the parallel batch reader used by rename
    and sort must provide the three additional fields.
    """
    from sortiton import tags as tag_reader

    info = tag_reader.TrackInfo(track=["07"], disc=["2"], year=["2024"])
    with mock.patch.object(tag_reader, "read_info", return_value=info):
        single = tag_reader.probe_tags(Path("song.mp3"))
        batch = tag_reader.probe_many([Path("song.mp3")])[0]

    for label, values in (("probe_tags", single), ("probe_many", batch)):
        check(f"{label}: track is available", values.get("track") == "07",
              f"{label}: {values}")
        check(f"{label}: disc is available", values.get("disc") == "2",
              f"{label}: {values}")
        check(f"{label}: year is available", values.get("year") == "2024",
              f"{label}: {values}")


@pytest.mark.skipif(importlib.util.find_spec("mutagen") is None, reason="mutagen not installed")
def test_title_is_not_split_at_semicolons() -> None:
    """Split only multi-value fields on ``;``, never a title."""
    from sortiton.tags import read_info, write_tags

    if not FLAC_SAMPLE.is_file():
        pytest.skip("export fixture missing")

    with tempfile.TemporaryDirectory() as tmp:
        song = Path(tmp) / "song.flac"
        shutil.copy2(FLAC_SAMPLE, song)

        check("a title with a semicolon is written", write_tags(song, {"title": "Intro;Outro"}))
        check("the title stays one value", read_info(song).title == ["Intro;Outro"],
              str(read_info(song).title))

        check("a multi-value artist is written", write_tags(song, {"artist": "A; B"}))
        check("the artist still splits into two values",
              read_info(song).artist == ["A", "B"], str(read_info(song).artist))


def test_writer_mappings_cover_every_tag_field() -> None:
    """Every writer mapping includes every field the fixes feature can write."""
    from sortiton import tags

    fields = set(tags.TAG_FIELDS)
    check("ID3 mapping is complete", fields <= set(tags._ID3_FRAMES))
    check("ASF mapping is complete", fields <= set(tags._ASF_KEYS))
    check("Vorbis mapping is complete", fields <= set(tags._VORBIS_KEYS))
    check("MP4 mapping is complete",
          fields <= set(tags._MP4_TEXT_KEYS) | set(tags._MP4_PAIR_KEYS))


def test_write_tags_reports_a_missing_writer() -> None:
    """``write_tags`` raises RuntimeError without mutagen or ffmpeg."""
    from sortiton import tags

    with tempfile.TemporaryDirectory() as tmp:
        song = Path(tmp) / "song.unknown"
        song.write_bytes(b"\x00" * 16)
        with mock.patch.object(tags, "_write_mutagen",
                               side_effect=RuntimeError("no mutagen")), \
                mock.patch.object(tags.subprocess, "run",
                                  side_effect=FileNotFoundError("ffmpeg")):
            with pytest.raises(RuntimeError):
                tags.write_tags(song, {"artist": "X"})


def test_mutagen_write_is_atomic_on_failure() -> None:
    """A failure while tagging leaves the original bytes untouched."""
    from sortiton import tags

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "song.mp3"
        original = b"original-bytes"
        path.write_bytes(original)

        def broken(temporary: Path, _updates: dict) -> None:
            temporary.write_bytes(b"half-written")
            raise RuntimeError("simulated save failure")

        with mock.patch.object(tags, "_write_mutagen_inplace", side_effect=broken):
            try:
                tags._write_mutagen(path, {"artist": "New"})
            except RuntimeError:
                pass
            else:
                raise AssertionError("the simulated failure was swallowed")

        check("the original is unchanged", path.read_bytes() == original)
        check("the temporary file was removed", not list(Path(tmp).glob(".sortiton-*")))
