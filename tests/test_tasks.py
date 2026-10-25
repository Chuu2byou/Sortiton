"""Die klassischen Aufgaben: tags, rename, sort, all und Sicherungen.

Alle Tests arbeiten über ``cmd_*`` mit gepatchten Lesern/Schreibern, damit sie
ohne Audio-Werkzeuge laufen und nur das Verhalten prüfen: welche Datei wohin
geht, welcher Rückgabecode kommt und was in den Zählern landet.
"""

from __future__ import annotations

import unittest.mock as mock

import pytest

from _support import Path, SimpleNamespace, check, config, output, tempfile


def test_all_pipeline() -> None:
    """cmd_all läuft eine optionale fetch-Stufe vor tags/rename/sort.

    Die Stufen sind ersetzt, der Test ruft also weder yt-dlp noch eine Datei -
    er prüft nur die Reihenfolge, die ``cmd_all`` aus den Argumenten baut, mit
    und ohne ``fetch_url`` und mit fehlender Bestätigung.
    """
    from sortiton import tasks

    order: list[str] = []

    def recorder(name: str):
        def run(_args) -> int:
            order.append(name)
            return 0
        return run

    def all_args(**extra):
        data = dict(source="/src", target="/dst", pattern="%artist% - %title%",
                    move=False, apply=True, backup=False)
        data.update(extra)
        return SimpleNamespace(**data)

    with mock.patch.object(tasks, "cmd_tags", recorder("tags")), \
            mock.patch.object(tasks, "cmd_rename", recorder("rename")), \
            mock.patch.object(tasks, "cmd_sort", recorder("sort")), \
            mock.patch.object(tasks, "cmd_fetch", recorder("fetch")):
        # Ohne URL bleibt die Pipeline bei den drei klassischen Stufen.
        order.clear()
        rc = tasks.cmd_all(all_args())
        check("all without fetch_url returns 0", rc == 0, str(rc))
        check("all without fetch_url is tags -> rename -> sort",
              order == ["tags", "rename", "sort"], str(order))
        keys = [step.title_key for step in tasks._pipeline_steps(all_args())]
        check("pipeline has no fetch stage without fetch_url",
              keys == ["task.step.tags", "task.step.rename", "task.step.sort"], str(keys))

        # Eine bestätigte URL stellt die fetch-Stufe voran.
        order.clear()
        rc = tasks.cmd_all(all_args(fetch_url="https://example.org/x",
                                    fetch_confirmed=True))
        check("all with fetch_url returns 0", rc == 0, str(rc))
        check("fetch runs before the classic stages",
              order == ["fetch", "tags", "rename", "sort"], str(order))
        keys = [step.title_key for step in tasks._pipeline_steps(
            all_args(fetch_url="https://example.org/x", fetch_confirmed=True))]
        check("pipeline puts the fetch stage first",
              keys == ["task.step.fetch", "task.step.tags", "task.step.rename",
                       "task.step.sort"], str(keys))

        # Eine URL ohne ausdrückliche Bestätigung darf nichts herunterladen.
        order.clear()
        messages: list[str] = []
        with mock.patch.object(tasks, "message",
                               side_effect=lambda text="": messages.append(str(text))):
            rc = tasks.cmd_all(all_args(fetch_url="https://example.org/x"))
        check("all refuses an unconfirmed fetch", rc == 2, str(rc))
        check("an unconfirmed fetch downloads nothing", order == [], str(order))
        check("the refusal names the confirmation",
              any("confirm" in text.lower() for text in messages), str(messages[:3]))


def test_all_preview_never_downloads() -> None:
    """Eine Vorschau der "all"-Pipeline muss apply=False an fetch geben.

    Vor dem Fix setzte ``_run_fetch_step`` hart ``apply=True``: ein
    Vorschau-Lauf mit ``--fetch-url`` und ``--fetch-confirmed`` lud Dateien,
    obwohl das Banner "Vorschau" sagte und kein Journal offen war.
    """
    from sortiton import tasks

    seen: list[dict] = []

    def fake_fetch(args) -> int:
        seen.append(vars(args))
        return 0

    args = SimpleNamespace(source="/src", target="/dst", pattern="%artist% - %title%",
                           move=False, apply=False, backup=False,
                           fetch_url="https://example.org/x", fetch_confirmed=True)
    with mock.patch.object(tasks, "cmd_fetch", fake_fetch), \
            mock.patch.object(tasks, "cmd_tags", lambda _args: 0), \
            mock.patch.object(tasks, "cmd_rename", lambda _args: 0), \
            mock.patch.object(tasks, "cmd_sort", lambda _args: 0):
        rc = tasks.cmd_all(args)

    check("preview of all returns 0", rc == 0, str(rc))
    check("the preview reaches the fetch stage", len(seen) == 1, str(seen))
    check("the fetch stage stays a preview", seen[0]["apply"] is False, str(seen[0]))
    check("the preview needs no confirmation", seen[0]["confirm"] is False, str(seen[0]))


def test_all_apply_needs_confirmation() -> None:
    """Ein angewandter "all"-Lauf lädt ohne --fetch-confirmed nichts."""
    from sortiton import tasks

    called: list[dict] = []
    args = SimpleNamespace(source="/src", target="/dst", pattern="%artist% - %title%",
                           move=False, apply=True, backup=False,
                           fetch_url="https://example.org/x", fetch_confirmed=False)
    with mock.patch.object(tasks, "cmd_fetch", lambda value: called.append(vars(value))):
        rc = tasks.cmd_all(args)

    check("an unconfirmed fetch stops the run", rc == 2, str(rc))
    check("nothing was downloaded", not called, str(called))


def test_all_counts_fetch_errors() -> None:
    """Das Gesamtergebnis von ``all`` enthält die optionale fetch-Stufe."""
    from sortiton import tasks

    def fake_fetch(_args) -> int:
        output.report_stats("fetch", files=0, errors=3, applied=True)
        return 1

    def zero(kind: str):
        def run(_args) -> int:
            output.report_stats(kind, files=0, errors=0, applied=True)
            return 0
        return run

    args = SimpleNamespace(source="/src", target="/dst", pattern="%artist% - %title%",
                           move=False, apply=True, backup=False,
                           fetch_url="https://example.org/watch?v=secret",
                           fetch_confirmed=True)
    with mock.patch.object(tasks, "cmd_fetch", fake_fetch), \
            mock.patch.object(tasks, "cmd_tags", zero("tags")), \
            mock.patch.object(tasks, "cmd_rename", zero("rename")), \
            mock.patch.object(tasks, "cmd_sort", zero("sort")):
        rc = tasks.cmd_all(args)

    check("the aggregate exit code is nonzero", rc == 1, str(rc))
    check("fetch errors are counted",
          output.last_stats("all").get("errors") == 3,
          str(output.last_stats("all")))


def test_all_preview_passes_cleaned_tags_and_renamed_paths_forward() -> None:
    """Rename- und Sort-Vorschau nutzen das geplante Ergebnis der Vorstufen."""
    from sortiton import output as out, tasks

    with tempfile.TemporaryDirectory() as source_dir, \
            tempfile.TemporaryDirectory() as target_dir:
        source = Path(source_dir)
        (source / "old.mp3").write_bytes(b"audio")
        tags = {"artist": "OldArtist", "album_artist": "", "album": "Album",
                "title": "Song", "genre": "", "track": "", "disc": "", "year": ""}
        plans = []
        args = SimpleNamespace(source=source_dir, target=target_dir,
                               pattern="%artist% - %title%", move=False,
                               apply=False, backup=False)
        out.set_plan_sink(lambda kind, data: plans.append((kind, data)))
        try:
            with mock.patch.object(tasks, "probe_many", return_value=[dict(tags)]), \
                    mock.patch.object(tasks, "clean_artist",
                                      side_effect=lambda value, _rules:
                                      "NewArtist" if value == "OldArtist" else value):
                rc = tasks.cmd_all(args)
        finally:
            out.set_plan_sink(None)

        rename_plan = next(data for kind, data in plans if kind == "rename")
        sort_plan = next(data for kind, data in plans if kind == "sort")
        check("pipeline preview succeeds", rc == 0, str(rc))
        check("rename preview uses cleaned tags",
              Path(rename_plan["target"]).name == "NewArtist - Song.mp3",
              str(rename_plan))
        check("sort preview uses the planned renamed source",
              Path(sort_plan["source"]).name == "NewArtist - Song.mp3",
              str(sort_plan))
        check("sort preview uses the cleaned artist folder",
              Path(sort_plan["target"]).parent.name == "Album"
              and Path(sort_plan["target"]).parent.parent.name == "NewArtist",
              str(sort_plan))


def test_all_preview_accounts_for_tag_changes_before_identical_check() -> None:
    """Vorschau und Ausführung wählen nach Tagänderungen dieselbe freie Zieldatei."""
    from sortiton import output as out, tasks

    for dirty in (False, True):
        with tempfile.TemporaryDirectory() as source_dir, \
                tempfile.TemporaryDirectory() as target_dir:
            source = Path(source_dir) / "old.mp3"
            source.write_bytes(b"original")
            existing = Path(target_dir) / "Artist" / "Song.mp3"
            existing.parent.mkdir()
            existing.write_bytes(b"original")
            plans = []

            def probe(paths, **_kwargs):
                return [{"artist": "Artist " if dirty and path.read_bytes() == b"original"
                         else "Artist", "album_artist": "", "album": "", "title": "Song",
                         "genre": "", "track": "", "disc": "", "year": ""}
                        for path in paths]

            def write(path, _diff):
                path.write_bytes(b"cleaned")
                return True

            args = SimpleNamespace(source=source_dir, target=target_dir,
                                   pattern="%title%", move=False, apply=False, backup=False)
            out.set_plan_sink(lambda kind, data: plans.append((kind, data)))
            try:
                with mock.patch.object(tasks, "probe_many", side_effect=probe), \
                        mock.patch.object(tasks, "write_tags", side_effect=write):
                    preview_rc = tasks.cmd_all(args)
                    preview_targets = [data["target"] for kind, data in plans if kind == "sort"]
                    plans.clear()
                    args.apply = True
                    apply_rc = tasks.cmd_all(args)
                    applied_targets = [data["target"] for kind, data in plans if kind == "sort"]
            finally:
                out.set_plan_sink(None)

            expected = [existing.with_name("Song (2).mp3")] if dirty else []
            check("both pipeline runs succeed", preview_rc == apply_rc == 0)
            check("preview and apply agree about identical files",
                  preview_targets == applied_targets == expected,
                  str((preview_targets, applied_targets, dirty)))
            check("the identical old target survives", existing.read_bytes() == b"original")
            if dirty:
                check("the cleaned copy is placed", expected[0].read_bytes() == b"cleaned")


def test_stats_count_only_written_files() -> None:
    """Ein fehlgeschlagener Schreibvorgang ist ein Fehler, keine Änderung."""
    from sortiton import tasks

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = root / "one.mp3"
        second = root / "two.mp3"
        first.write_bytes(b"x")
        second.write_bytes(b"y")

        def fake_write(path, _updates):
            if path == second:
                raise OSError("disk full")
            return True

        # Ein Leerzeichen am Ende lässt den bereinigten Artist vom rohen
        # abweichen, also sind beide Dateien im Plan.
        tags = {"artist": "Old ", "album_artist": "", "album": "", "title": "T",
                "genre": ""}
        args = SimpleNamespace(folder=str(root), apply=True, backup=False)
        with mock.patch.object(tasks, "probe_many", return_value=[dict(tags), dict(tags)]), \
                mock.patch.object(tasks, "write_tags", fake_write):
            rc = tasks.cmd_tags(args)

    stats = output.last_stats("tags")
    check("the run reports the failed write", rc == 1, str(rc))
    check("only the written file counts as changed", stats.get("changed") == 1, str(stats))
    check("the failed file counts as an error", stats.get("errors") == 1, str(stats))


def test_tags_diff_and_diff_csv() -> None:
    """--diff groups changes; --diff-csv writes rows the fixes tool can read."""
    from sortiton import tasks
    from sortiton.features.fixes import parse

    with tempfile.TemporaryDirectory() as src:
        root = Path(src)
        first = root / "one.mp3"
        second = root / "two.mp3"
        first.write_bytes(b"one")
        second.write_bytes(b"two")
        csv_path = root / "changes.csv"
        tags = {"artist": "Artist ", "album_artist": "", "album": "", "title": "Title",
                "genre": "", "track": "", "disc": "", "year": ""}
        lines: list[str] = []
        args = SimpleNamespace(folder=src, apply=False, backup=False, diff=True,
                               diff_csv=str(csv_path))
        with mock.patch.object(tasks, "probe_many", return_value=[dict(tags), dict(tags)]), \
                mock.patch.object(tasks, "message",
                                  side_effect=lambda text="": lines.append(str(text))):
            rc = tasks.cmd_tags(args)

        text = "\n".join(lines)
        check("the diff run succeeds", rc == 0, str(rc))
        check("the diff has a heading", "Planned tag changes" in text, text)
        check("the diff groups by field", "  artist" in text, text)
        check("the diff counts both files", "(2)" in text, text)
        check("the diff names the file", "one.mp3" in text and "two.mp3" in text, text)
        check("the diff CSV is announced", "Diff CSV" in text, text)

        rows = parse.read_csv(csv_path.read_text(encoding="utf-8"))
        check("the CSV has two rows", len(rows) == 2, str(rows))
        # The fixes reader trims cells; the stripped current value still matches.
        check("the CSV rows are fixes-compatible",
              all(row.field == "artist" and row.old == "Artist"
                  and row.new == "Artist" for row in rows), str(rows))


def test_track_format_normalisation() -> None:
    """keep/number/padded only touch plain track and disc numbers."""
    from sortiton import tasks

    check("keep keeps the total",
          tasks._normalise_number("1/11", "keep") == "1/11")
    check("number drops the total",
          tasks._normalise_number("1/11", "number") == "1",
          tasks._normalise_number("1/11", "number"))
    check("number removes leading zeroes",
          tasks._normalise_number("07", "number") == "7",
          tasks._normalise_number("07", "number"))
    check("padded adds a leading zero",
          tasks._normalise_number("1/11", "padded") == "01",
          tasks._normalise_number("1/11", "padded"))
    check("padded leaves three digits alone",
          tasks._normalise_number("123", "padded") == "123")
    for value in ("", "A1", "1a", "1; 2", "-1"):
        check(f"{value!r} stays untouched",
              tasks._normalise_number(value, "padded") == value,
              tasks._normalise_number(value, "padded"))


def test_tags_apply_track_format() -> None:
    """The chosen mode reaches the tags diff written by cmd_tags."""
    from sortiton import tasks

    for mode, expected in (("number", ("7", "1")), ("padded", ("07", "01"))):
        with tempfile.TemporaryDirectory() as src:
            track = Path(src) / "track.mp3"
            track.write_bytes(b"audio-data")
            tags = {"artist": "Artist", "album_artist": "", "album": "Album",
                    "title": "Track", "genre": "", "track": "7/12", "disc": "1/2",
                    "year": ""}
            written: list[dict] = []
            args = SimpleNamespace(folder=src, apply=True, backup=False,
                                   track_format=mode)
            with mock.patch.object(tasks, "probe_many", return_value=[dict(tags)]), \
                    mock.patch.object(tasks, "write_tags",
                                      side_effect=lambda _path, diff: written.append(dict(diff)) or True):
                rc = tasks.cmd_tags(args)

            check(f"{mode}: the run succeeds", rc == 0, str(rc))
            check(f"{mode}: the file is written", len(written) == 1, str(written))
            check(f"{mode}: the track is normalised",
                  written[0].get("track") == expected[0], str(written))
            check(f"{mode}: the disc is normalised",
                  written[0].get("disc") == expected[1], str(written))


def test_tags_with_target_copy_and_move() -> None:
    """tags mit Ziel sortiert die Dateien in die Bibliothek (kopieren oder verschieben)."""
    from sortiton import tasks

    tags = {"artist": "Artist ", "album_artist": "", "album": "Album",
            "title": "Track", "genre": ""}
    with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
        track = Path(src) / "track.mp3"
        track.write_bytes(b"audio-data")
        args = SimpleNamespace(folder=src, target=dst, move=False, apply=True, backup=False)
        with mock.patch.object(tasks, "probe_many", return_value=[dict(tags)]), \
                mock.patch.object(tasks, "write_tags", lambda _path, _diff: True):
            rc = tasks.cmd_tags(args)
        check("tags with target returns 0", rc == 0, str(rc))
        expected_dst = Path(dst) / "Artist" / "Album" / "track.mp3"
        check("file copied to library", expected_dst.exists())
        check("original kept on copy", track.exists())

    with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
        track = Path(src) / "track.mp3"
        track.write_bytes(b"audio-data")
        args = SimpleNamespace(folder=src, target=dst, move=True, apply=True, backup=False)
        with mock.patch.object(tasks, "probe_many", return_value=[dict(tags)]), \
                mock.patch.object(tasks, "write_tags", lambda _path, _diff: True):
            rc = tasks.cmd_tags(args)
        check("tags with target returns 0", rc == 0, str(rc))
        expected_dst = Path(dst) / "Artist" / "Album" / "track.mp3"
        check("file moved to library", expected_dst.exists())
        check("original removed on move", not track.exists())


def test_tags_with_dirty_identical_target_places_cleaned_copy() -> None:
    """Eine unsaubere Quelle wird nicht übersprungen, nur weil das Ziel identisch ist."""
    from sortiton import tasks

    tags = {"artist": "Artist ", "album_artist": "", "album": "Album",
            "title": "Track", "genre": ""}
    with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
        track = Path(src) / "track.mp3"
        track.write_bytes(b"audio-data")
        existing = Path(dst) / "Artist" / "Album" / track.name
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"audio-data")
        args = SimpleNamespace(folder=src, target=dst, move=False, apply=True,
                               backup=False)

        def clean_file(path: Path, _diff: dict) -> bool:
            path.write_bytes(b"cleaned-audio-data")
            return True

        with mock.patch.object(tasks, "probe_many", return_value=[dict(tags)]), \
                mock.patch.object(tasks, "write_tags", side_effect=clean_file):
            rc = tasks.cmd_tags(args)

        placed = existing.with_name("track (2).mp3")
        check("tags with an identical old target returns 0", rc == 0, str(rc))
        check("old target is preserved", existing.read_bytes() == b"audio-data")
        check("cleaned copy is placed at a free name",
              placed.exists() and placed.read_bytes() == b"cleaned-audio-data")


def test_rename_with_target_copy_and_move() -> None:
    """rename mit Ziel benennt um und sortiert in die Bibliothek (kopieren oder verschieben)."""
    from sortiton import tasks

    tags = {"artist": "Artist", "album_artist": "", "album": "Album",
            "title": "Song", "genre": ""}
    with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
        track = Path(src) / "old.mp3"
        track.write_bytes(b"audio-data")
        args = SimpleNamespace(folder=src, target=dst, pattern="%artist% - %title%",
                               move=False, apply=True)
        with mock.patch.object(tasks, "probe_many", return_value=[dict(tags)]):
            rc = tasks.cmd_rename(args)
        check("rename with target returns 0", rc == 0, str(rc))
        expected_dst = Path(dst) / "Artist" / "Album" / "Artist - Song.mp3"
        check("renamed file copied to library", expected_dst.exists())
        renamed_src = Path(src) / "Artist - Song.mp3"
        check("source renamed and kept on copy", renamed_src.exists())

    with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
        track = Path(src) / "old.mp3"
        track.write_bytes(b"audio-data")
        args = SimpleNamespace(folder=src, target=dst, pattern="%artist% - %title%",
                               move=True, apply=True)
        with mock.patch.object(tasks, "probe_many", return_value=[dict(tags)]):
            rc = tasks.cmd_rename(args)
        check("rename with target returns 0", rc == 0, str(rc))
        expected_dst = Path(dst) / "Artist" / "Album" / "Artist - Song.mp3"
        check("renamed file moved to library", expected_dst.exists())
        renamed_src = Path(src) / "Artist - Song.mp3"
        check("source removed on move", not renamed_src.exists())


def test_move_without_target_is_rejected() -> None:
    """Verschieben ohne Ziel darf nicht stillschweigend an Ort und Stelle passieren."""
    from sortiton import tasks

    with tempfile.TemporaryDirectory() as folder:
        tags_args = SimpleNamespace(folder=folder, target=None, move=True,
                                    apply=True, backup=False)
        rename_args = SimpleNamespace(folder=folder, target=None, move=True,
                                      pattern="%title%", apply=True)
        with mock.patch.object(tasks, "probe_many") as probe:
            tags_rc = tasks.cmd_tags(tags_args)
            rename_rc = tasks.cmd_rename(rename_args)

    check("tags rejects move without a target", tags_rc == 2, str(tags_rc))
    check("rename rejects move without a target", rename_rc == 2, str(rename_rc))
    check("invalid move does not scan or modify files", not probe.called)


def test_rename_does_not_replace_a_racing_destination() -> None:
    """Ein nach der Planung angelegtes Ziel muss den Umbenenn-Versuch überleben."""
    from sortiton import fileops, tasks

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "old.mp3"
        target = root / "new.mp3"
        source.write_bytes(b"original")
        tags = {"artist": "Artist", "album_artist": "", "album": "",
                "title": "new", "genre": "", "track": "", "disc": "",
                "year": ""}

        def race_move(origin: Path, destination: Path) -> None:
            destination.write_bytes(b"foreign")
            fileops.move_no_clobber(origin, destination)

        args = SimpleNamespace(folder=str(root), pattern="%title%", apply=True)
        with mock.patch.object(tasks, "probe_many", return_value=[tags]), \
                mock.patch.object(tasks, "move_no_clobber", side_effect=race_move):
            rc = tasks.cmd_rename(args)

        check("the colliding rename reports failure", rc == 1, str(rc))
        check("the racing destination is preserved",
              target.read_bytes() == b"foreign")
        check("the original file is preserved", source.read_bytes() == b"original")


def test_sort_worker_stops_before_the_next_file_after_cancel() -> None:
    """Ein Worker prüft den Abbruch unmittelbar vor jeder Dateioperation."""
    from sortiton import fileops, tasks
    from sortiton.cancel import CancelToken

    with tempfile.TemporaryDirectory() as source_dir, \
            tempfile.TemporaryDirectory() as target_dir:
        source = Path(source_dir)
        first = source / "a.mp3"
        second = source / "b.mp3"
        first.write_bytes(b"a")
        second.write_bytes(b"b")
        cancel = CancelToken()
        tag_rows = [
            {"artist": "Artist", "album_artist": "", "album": "",
             "title": "a", "genre": "", "track": "", "disc": "", "year": ""},
            {"artist": "Artist", "album_artist": "", "album": "",
             "title": "b", "genre": "", "track": "", "disc": "", "year": ""},
        ]
        moved = []

        def cancel_after_move(origin: Path, destination: Path) -> None:
            fileops.move_no_clobber(origin, destination)
            moved.append(origin)
            cancel.cancel()

        args = SimpleNamespace(source=source_dir, target=target_dir,
                               pattern="%title%", move=True, apply=True,
                               cancel=cancel)
        with mock.patch.object(tasks, "COPY_WORKERS", 1), \
                mock.patch.object(tasks, "probe_many", return_value=tag_rows), \
                mock.patch.object(tasks, "move_no_clobber",
                                  side_effect=cancel_after_move):
            rc = tasks.cmd_sort(args)

        check("sort returns the cancellation code", rc == 130, str(rc))
        check("only one worker operation started", len(moved) == 1, str(moved))
        check("the other source remains", (first.exists() != second.exists()))


def test_tags_workers_stop_even_when_completion_observer_is_delayed() -> None:
    """Tag-Worker prüfen den Abbruch unabhängig von der Hauptthread-Auswertung."""
    from concurrent.futures import as_completed
    from sortiton import tasks
    from sortiton.cancel import CancelToken

    with tempfile.TemporaryDirectory() as folder:
        sources = [Path(folder) / f"{name}.mp3" for name in ("a", "b", "c")]
        for path in sources:
            path.write_bytes(b"audio")
        tags = {"artist": "Artist ", "album_artist": "", "album": "",
                "title": "Song", "genre": ""}
        cancel = CancelToken()
        written = []

        def write_and_cancel(path, _diff):
            written.append(path)
            cancel.cancel()
            return True

        def delayed_observer(futures):
            return iter(list(as_completed(futures)))

        args = SimpleNamespace(folder=folder, apply=True, backup=False, cancel=cancel)
        with mock.patch.object(tasks, "WRITE_WORKERS", 1), \
                mock.patch.object(tasks, "probe_many",
                                  return_value=[dict(tags) for _path in sources]), \
                mock.patch.object(tasks, "write_tags", side_effect=write_and_cancel), \
                mock.patch.object(tasks, "as_completed", side_effect=delayed_observer), \
                mock.patch.object(tasks.journal, "record_failure") as failure:
            rc = tasks.cmd_tags(args)

        check("tag cancellation returns 130", rc == 130, str(rc))
        check("only the in-flight tag write completes", written == sources[:1], str(written))
        check("cancellation is not journaled as a file error", not failure.called)


def test_placement_cancellation_stops_queued_moves() -> None:
    """Nach dem Abbruch starten eingeplante Verschiebungen nicht mehr."""
    from sortiton import tasks
    from sortiton.cancel import CancelToken, Cancelled

    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        sources = [root / f"source-{index}.mp3" for index in range(3)]
        destinations = [root / "target" / source.name for source in sources]
        cancel = CancelToken()
        moved: list[Path] = []

        def cancel_after_first(source: Path, _destination: Path) -> None:
            moved.append(source)
            cancel.cancel()

        with mock.patch.object(tasks, "COPY_WORKERS", 1), \
                mock.patch.object(tasks, "_no_clobber_move", cancel_after_first), \
                mock.patch.object(tasks.journal, "record_move"):
            try:
                tasks._place_files(list(zip(sources, destinations)), root / "target",
                                   move=True, apply=True, cancel=cancel)
            except Cancelled:
                was_cancelled = True
            else:
                was_cancelled = False

    check("placement propagates cancellation", was_cancelled)
    check("only the in-flight move completes", moved == sources[:1], str(moved))


def test_scan_counts_files_and_can_be_cancelled() -> None:
    """``scan`` zählt die Dateien, meldet einen fehlenden Ordner und ist abbrechbar."""
    from sortiton.cancel import Cancelled, CancelToken
    from sortiton.tasks import cmd_scan

    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "track.mp3").write_bytes(b"\x00" * 64)
        rc = cmd_scan(SimpleNamespace(folder=tmp))
        check("scan runs", rc == 0)
        check("scan counts files", output.last_stats("scan").get("files") == 1,
              str(output.last_stats("scan")))
        check("scan of a missing folder fails",
              cmd_scan(SimpleNamespace(folder=str(Path(tmp) / "nope"))) == 2)

        token = CancelToken()
        token.cancel()
        with pytest.raises(Cancelled):
            cmd_scan(SimpleNamespace(folder=tmp, cancel=token))


def test_backup_deduplicates_paths_that_resolve_to_the_same_file() -> None:
    """Eine CSV-Datei wird einmal gesichert, auch wenn mehrere Zeilen sie nennen."""
    from sortiton import tasks

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "song.mp3"
        source.write_bytes(b"audio")
        alias = root / "unused" / ".." / "song.mp3"
        folder = tasks._backup_files(root, [source, alias, source])
        copies = list(folder.rglob("song.mp3")) if folder is not None else []

    check("backup succeeds with duplicate inputs", folder is not None, str(folder))
    check("the source is present exactly once", len(copies) == 1, str(copies))


def test_incomplete_backup_stops_before_writing() -> None:
    """Eine Sicherung, die nicht alle Dateien kopieren konnte, ist kein Schutz."""
    from sortiton import tasks

    with tempfile.TemporaryDirectory() as tmp:
        missing = Path(tmp) / "gone.mp3"
        folder = tasks._backup_files(Path(tmp), [missing])
    check("an incomplete backup returns no folder", folder is None, str(folder))


def test_backup_retention_does_not_let_incomplete_evict_complete() -> None:
    """Eine unvollständige Sicherung darf die letzte brauchbare nicht verdrängen."""
    from sortiton import tasks

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "music"
        root.mkdir()
        source = root / "song.mp3"
        source.write_bytes(b"music")
        backups = Path(tmp) / "backups"
        backups.mkdir()

        with mock.patch.object(config, "BACKUP_DIR", backups):
            complete = tasks._backup_files(root, [source])
            check("a complete backup was created", complete is not None)
            assert complete is not None
            check("the complete marker exists", (complete / ".complete").is_file())

            # Absturz simulieren: ein neuerer Ordner mit unvollständiger Marke.
            incomplete = backups / "backup_2999-01-01_00-00-00"
            incomplete.mkdir()
            (incomplete / ".incomplete").write_text("incomplete\n", encoding="utf-8")

            tasks._prune_backups(keep=1)
            check("the complete backup survived", complete.is_dir())
            check("the incomplete folder left the backup namespace",
                  not incomplete.exists())
            check("the incomplete folder is kept as evidence",
                  (backups / "failed" / incomplete.name).is_dir())

            # Eine Sicherung, die beim Kopieren scheitert, zählt ebenfalls nicht.
            failed = tasks._backup_files(root, [root / "missing.mp3"])
            check("a failed backup is not returned", failed is None)
            tasks._prune_backups(keep=1)
            check("the good backup still survived", complete.is_dir())
