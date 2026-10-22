"""Dateinamen und die Kopier-/Verschiebe-Helfer.

Geprüft wird ``sortiton/files.py`` (Namen, freie Ziele, Inhaltsvergleich) und
``sortiton/fileops.py`` (kopieren/verschieben ohne Überschreiben) - jeweils
über das nach außen sichtbare Verhalten auf der Platte.
"""

from __future__ import annotations

import errno
import unittest.mock as mock

from _support import Path, check, files, tempfile


def test_build_name_keeps_placeholders_in_tag_values_literal() -> None:
    """Ein Tag-Wert, der wie ein Platzhalter aussieht, wird nicht ersetzt."""
    tags = {"artist": "A", "album_artist": "A", "album": "ALBUM",
            "title": "100% %track%"}
    name = files.build_name(tags, "fallback", "%artist% - %title%")
    check("placeholders inside a tag stay literal",
          name == "A - 100% %track%", name)

    # Der Schnitt bei MAX_NAME_LENGTH darf keinen Punkt am Ende hinterlassen.
    chopped = files.safe_name("x" * (files.MAX_NAME_LENGTH - 1) + "." + "y" * 10)
    check("a truncated name does not end in a dot",
          not chopped.endswith("."), repr(chopped[-5:]))


def test_file_names_cannot_escape_the_folder() -> None:
    """A pattern is user input: it must not build a path outside the folder."""
    for pattern in ("../../outside", "/etc/passwd", "..\\..\\windows"):
        name = files.build_name({"artist": "A", "title": "T"}, "base", pattern)
        check(f"no separator in {pattern!r}",
              "/" not in name and "\\" not in name, name)
        check(f"not an absolute path in {pattern!r}", not Path(name).is_absolute(), name)


def test_free_target_never_blocks_its_own_name() -> None:
    """free_target on a case-insensitive file system (FAT32/exFAT/NTFS)."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        own = folder / "Artist - Track.mp3"
        own.write_bytes(b"x")
        check("a file never blocks its own name",
              files.free_target(own, set(), ignore=own) == own)

        # Auf einem Dateisystem ohne Groß-/Kleinschreibung existiert der Pfad
        # auch dann, wenn nur die Schreibweise abweicht: das darf nicht zu
        # "Artist - Track (2)" führen.
        upper = folder / "ARTIST - TRACK.mp3"
        with mock.patch.object(Path, "exists", return_value=True):
            got = files.free_target(upper, set(), ignore=own)
        check("a case-only difference is not a collision", got == upper, str(got))

        other = folder / "other.mp3"
        other.write_bytes(b"y")
        check("a real collision still gets (2)",
              files.free_target(other, set()) == folder / "other (2).mp3")


def test_free_target_keeps_case_variants_apart() -> None:
    """On a case-sensitive disk "Song" and "song" are two different files."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = root / "Song.mp3"
        second = root / "song.mp3"
        first.write_bytes(b"a")
        second.write_bytes(b"b")
        if first.samefile(second):       # case-insensitive file system
            check("the same file is reused",
                  files.free_target(second, set(), ignore=first) == second)
            return
        got = files.free_target(second, set(), ignore=first)
        check("the other spelling is not overwritten", got != second, str(got))
        check("a free name is chosen", not got.exists(), str(got))


def test_free_path_moves_to_a_numbered_name() -> None:
    """Ein belegter Name bekommt " (2)" statt überschrieben zu werden."""
    with tempfile.TemporaryDirectory() as tmp:
        taken = Path(tmp) / "sortiton_2026-01-01_12-00-00.log"
        check("a free name is left alone", files.free_path(taken) == taken)
        taken.write_text("first\n", encoding="utf-8")
        moved = files.free_path(taken)
        check("a taken name moves to ' (2)'",
              moved.name == "sortiton_2026-01-01_12-00-00 (2).log", moved.name)


def test_open_new_never_truncates() -> None:
    """Two runs in the same second get two files, not one cut short."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sortiton_2026-01-01_00-00-00.log"
        first_path, first = files.open_new(path)
        first.write("first\n")
        first.close()
        second_path, second = files.open_new(path)
        second.write("second\n")
        second.close()
        check("a second name is used", first_path != second_path, str(second_path))
        check("the first file survives", first_path.read_text() == "first\n")
        check("the second file is separate", second_path.read_text() == "second\n")


def test_same_content_rejects_an_early_difference() -> None:
    """Gleiche Größe, anderes erstes Byte: der Vergleich muss "anders" sagen."""
    with tempfile.TemporaryDirectory() as tmp:
        first = Path(tmp) / "a.bin"
        second = Path(tmp) / "b.bin"
        same = Path(tmp) / "c.bin"
        first.write_bytes(b"A" + b"x" * 4095)
        second.write_bytes(b"B" + b"x" * 4095)
        same.write_bytes(first.read_bytes())
        check("same_content rejects an early difference",
              not files.same_content(first, second))
        check("same_content accepts identical files", files.same_content(first, same))


def test_move_no_clobber_never_overwrites() -> None:
    """The move helper refuses an existing target and removes the source only once."""
    from sortiton import fileops

    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "source.mp3"
        target = Path(tmp) / "target.mp3"
        source.write_bytes(b"source")
        fileops.move_no_clobber(source, target)
        check("the source was moved", not source.exists())
        check("the target has the content", target.read_bytes() == b"source")

        source.write_bytes(b"new")
        try:
            fileops.move_no_clobber(source, target)
        except FileExistsError:
            pass
        else:
            raise AssertionError("an existing target was overwritten")
        check("the source remains after the refused move", source.is_file())
        check("the target was not overwritten", target.read_bytes() == b"source")


def test_copy_failure_removes_partial_destination() -> None:
    """An interrupted copy never leaves a name that restore can mistake as complete."""
    from sortiton import fileops

    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "source.mp3"
        target = Path(tmp) / "target.mp3"
        source.write_bytes(b"source")

        def fail_after_partial(_reader, writer):
            writer.write(b"sou")
            raise OSError("disk full")

        with mock.patch.object(fileops.shutil, "copyfileobj",
                               side_effect=fail_after_partial):
            try:
                fileops.copy_new(source, target)
            except OSError:
                pass

        check("the incomplete final target is absent", not target.exists())
        check("the temporary copy is cleaned", not list(Path(tmp).glob(".target.mp3.*.tmp")))


def test_copy_and_move_fall_back_without_hardlinks() -> None:
    """Dateisysteme ohne Hardlinks unterstützen weiterhin Kopieren und Verschieben."""
    from sortiton import fileops

    for move in (False, True):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp3"
            target = Path(tmp) / "target.mp3"
            source.write_bytes(b"source")
            source.chmod(0o640)
            operation = fileops.move_no_clobber if move else fileops.copy_new
            with mock.patch.object(fileops.os, "link",
                                   side_effect=OSError(errno.EOPNOTSUPP, "no hardlinks")):
                operation(source, target)

            check("fallback preserves file contents", target.read_bytes() == b"source")
            check("fallback preserves permissions", target.stat().st_mode & 0o777 == 0o640)
            check("only moves remove their source", source.exists() != move)
            check("fallback leaves no temporary files", not list(Path(tmp).glob(".*.tmp")))


def test_copy_fallback_keeps_a_racing_destination() -> None:
    """Auch ohne Hardlinks darf eine zwischenzeitlich angelegte Zieldatei nicht verschwinden."""
    from sortiton import fileops

    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "source.mp3"
        target = Path(tmp) / "target.mp3"
        source.write_bytes(b"source")

        def unsupported_link(_source, destination):
            destination.write_bytes(b"foreign")
            raise OSError(errno.EOPNOTSUPP, "no hardlinks")

        with mock.patch.object(fileops.os, "link", side_effect=unsupported_link):
            try:
                fileops.copy_new(source, target)
            except FileExistsError:
                collided = True
            else:
                collided = False

        check("fallback refuses a racing destination", collided)
        check("the foreign destination survives", target.read_bytes() == b"foreign")
        check("the source survives", source.read_bytes() == b"source")


def test_copy_fallback_removes_an_incomplete_destination() -> None:
    """Ein Fehler in der exklusiven Fallback-Kopie hinterlässt keine Teilkopie."""
    from sortiton import fileops

    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "source.mp3"
        target = Path(tmp) / "target.mp3"
        source.write_bytes(b"source")
        real_copy = fileops.shutil.copyfileobj

        def fail_only_for_final_target(reader, writer):
            if writer.name == str(target):
                writer.write(b"sou")
                raise OSError("disk full")
            real_copy(reader, writer)

        with mock.patch.object(fileops.os, "link",
                               side_effect=OSError(errno.EOPNOTSUPP, "no hardlinks")), \
                mock.patch.object(fileops.shutil, "copyfileobj",
                                  side_effect=fail_only_for_final_target):
            try:
                fileops.copy_new(source, target)
            except OSError:
                failed = True
            else:
                failed = False

        check("the fallback reports failure", failed)
        check("the partial destination is removed", not target.exists())
        check("the source survives", source.read_bytes() == b"source")
        check("no temporary files remain", not list(Path(tmp).glob(".*.tmp")))
