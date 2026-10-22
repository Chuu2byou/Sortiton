"""Regression checks for the findings of the code review.

One test per defect, written against the public behaviour (not the internals
that were changed), so a later rewrite may keep them.
"""

from __future__ import annotations

import os
import json
import subprocess
import sys
import unittest.mock as mock

from _support import BASE, Path, SimpleNamespace, check, tempfile


def test_all_preview_never_downloads() -> None:
    """A preview of the "all" pipeline must pass apply=False to fetch.

    Before the fix ``_run_fetch_step`` hardcoded ``apply=True``: a preview run
    with ``--fetch-url`` and ``--fetch-confirmed`` downloaded files even though
    the banner said "preview" and no journal was open.
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
    """An applied "all" run refuses to download without --fetch-confirmed."""
    from sortiton import tasks

    called: list[dict] = []
    args = SimpleNamespace(source="/src", target="/dst", pattern="%artist% - %title%",
                           move=False, apply=True, backup=False,
                           fetch_url="https://example.org/x", fetch_confirmed=False)
    with mock.patch.object(tasks, "cmd_fetch", lambda value: called.append(vars(value))):
        rc = tasks.cmd_all(args)

    check("an unconfirmed fetch stops the run", rc == 2, str(rc))
    check("nothing was downloaded", not called, str(called))


def test_settings_keep_percent_values() -> None:
    """settings.ini must round-trip a value containing "%".

    With configparser's default interpolation the write of "50%" raised
    ValueError and a hand-edited file made ``read_tool_values`` crash.
    """
    from sortiton import settings

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "settings.ini"
        with mock.patch.object(settings, "SETTINGS_FILE", path):
            check("a percent value is written", settings.write_value("language", "50%"))
            check("a percent value is read", settings.read_value("language") == "50%")
            check("tool values are saved",
                  settings.save_tool_values({"ratio": "50%"}))
            check("tool values are read",
                  settings.read_tool_values() == {"ratio": "50%"})


def test_build_name_is_literal_once() -> None:
    """A tag value that looks like a placeholder must not be substituted."""
    from sortiton import files

    tags = {"artist": "A", "album_artist": "A", "album": "ALBUM",
            "title": "100% %track%"}
    name = files.build_name(tags, "fallback", "%artist% - %title%")
    check("placeholders inside a tag stay literal",
          name == "A - 100% %track%", name)

    # The cut at MAX_NAME_LENGTH must not leave a trailing dot behind.
    chopped = files.safe_name("x" * (files.MAX_NAME_LENGTH - 1) + "." + "y" * 10)
    check("a truncated name does not end in a dot",
          not chopped.endswith("."), repr(chopped[-5:]))


def test_fetch_rejects_option_like_url() -> None:
    """A "URL" starting with "-" would be read by yt-dlp as an option."""
    from sortiton.features.fetch import cmd_fetch

    with tempfile.TemporaryDirectory() as tmp, \
            mock.patch("sortiton.features.fetch.download.preview",
                       side_effect=AssertionError("yt-dlp must not be called")):
        rc = cmd_fetch(SimpleNamespace(url="--exec=touch x", target=tmp))
    check("an option-like URL is rejected", rc == 2, str(rc))


def test_download_keeps_partial_results() -> None:
    """A playlist that fails midway must still report its finished files.

    Otherwise those files exist on disk and in the yt-dlp archive but have no
    journal entry, so ``restore`` cannot undo them.
    """
    from sortiton.features.fetch import download

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "partial.mp3"
        saved: list[Path] = []

        def fake_stream(_argv, _cancel, handle):
            # The file has to exist: only provably new files reach the journal.
            target.write_bytes(b"audio")
            handle("SORTITON_FILE\t" + str(target))
            return 1, "boom"

        with mock.patch.object(download, "_stream", fake_stream):
            files, error = download.download("https://example.org/x", Path(tmp),
                                             audio_format="mp3", playlist=True,
                                             on_saved=lambda item: saved.append(item.path))

    check("the error is reported", error == "boom", error)
    check("the finished file is returned", [item.path for item in files] == [target],
          str(files))
    check("the callback saw the finished file", saved == [target],
          str(saved))


def test_stats_count_only_written_files() -> None:
    """A failed write is an error, not a change in the run counters."""
    from sortiton import output, tasks

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

        # A trailing space makes the cleaned artist differ from the raw one, so
        # both files are in the plan (the clean-up is what a run writes).
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


def test_fetch_url_is_redacted_in_logs() -> None:
    """A token in the URL path or query must not end up in the log."""
    from sortiton import redact

    # Fixture, not a credential: the password part is what the check removes.
    auth = "user:pass"  # pragma: allowlist secret
    secret = f"https://{auth}@example.org/watch/session-token?token=abc#frag"
    hidden = redact.url(secret)
    check("the host stays readable", hidden.startswith("https://example.org/"), hidden)
    check("the path is gone", "session-token" not in hidden, hidden)
    check("the query is gone", "token" not in hidden, hidden)
    check("the password is gone", "pass" not in hidden, hidden)
    check("inline URLs in an error are redacted",
          "abc" not in redact.text(f"failed for {secret}"), redact.text(secret))
    check("a plain path is unchanged", redact.url("/music/track.mp3") == "/music/track.mp3")


def test_data_dir_environment_wins_in_checkout() -> None:
    """SORTITON_DATA_DIR also moves the data folder of a source checkout."""
    with tempfile.TemporaryDirectory() as data:
        env = dict(os.environ)
        env["SORTITON_DATA_DIR"] = data
        result = subprocess.run(
            [sys.executable, "-c",
             "from sortiton.config import PROJECT_DIR; print(PROJECT_DIR)"],
            cwd=str(BASE), env=env, capture_output=True, text=True, check=False)
    check("the import succeeds", result.returncode == 0, result.stderr[-300:])
    check("SORTITON_DATA_DIR is honoured", result.stdout.strip() == data, result.stdout)


def test_file_names_cannot_escape_the_folder() -> None:
    """A pattern is user input: it must not build a path outside the folder."""
    from sortiton import files

    for pattern in ("../../outside", "/etc/passwd", "..\\..\\windows"):
        name = files.build_name({"artist": "A", "title": "T"}, "base", pattern)
        check(f"no separator in {pattern!r}",
              "/" not in name and "\\" not in name, name)
        check(f"not an absolute path in {pattern!r}", not Path(name).is_absolute(), name)


def test_free_target_keeps_case_variants_apart() -> None:
    """On a case-sensitive disk "Song" and "song" are two different files."""
    from sortiton import files

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


def test_open_new_never_truncates() -> None:
    """Two runs in the same second get two files, not one cut short."""
    from sortiton import files

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


def test_journals_in_the_same_second_are_ordered() -> None:
    """The " (2)" journal of the same second is newer than the base one."""
    from sortiton import config, journal

    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    base = config.LOG_DIR / "sortiton_2026-01-01_00-00-00.jsonl"
    later = config.LOG_DIR / "sortiton_2026-01-01_00-00-00 (2).jsonl"
    base.write_text("{}\n", encoding="utf-8")
    later.write_text("{}\n", encoding="utf-8")
    os.utime(base, ns=(1_000_000_000, 1_000_000_000))
    os.utime(later, ns=(2_000_000_000, 2_000_000_000))
    try:
        order = journal.find_journals(limit=None)
        check("the newer journal comes first",
              order.index(later) < order.index(base), str(order))
    finally:
        base.unlink(missing_ok=True)
        later.unlink(missing_ok=True)


def test_journal_paths_are_absolute_and_legacy_paths_use_recorded_cwd() -> None:
    """Restore binds old relative entries to the journal's original folder."""
    from sortiton import journal

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        original = root / "original"
        original.mkdir()
        target = original / "song.mp3"
        legacy = root / "legacy.jsonl"
        legacy.write_text(
            json.dumps({"op": "run", "cwd": str(original)}) + "\n"
            + json.dumps({"op": "tags", "path": "song.mp3",
                          "before": {"artist": "Old"},
                          "after": {"artist": "New"}}) + "\n",
            encoding="utf-8")

        check("legacy relative paths use the recorded cwd",
              journal.plan_restore(legacy)[0]["path"] == str(target),
              str(journal.plan_restore(legacy)))

        log = root / "run.log"
        journal.close()
        opened = journal.open_for(log)
        journal.record_tags(Path("relative-song.mp3"), {"artist": "A"},
                            {"artist": "B"})
        journal.close()
        events = list(journal.read_journal(opened)) if opened else []
        check("newly recorded paths are absolute",
              len(events) == 2 and Path(events[1]["path"]).is_absolute(),
              str(events))


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


def test_copy_and_move_work_without_hardlink_support() -> None:
    """Dateisysteme ohne Hardlinks unterstützen weiterhin Kopieren und Verschieben."""
    import errno
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
    import errno
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
    import errno
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


def test_rename_does_not_replace_a_racing_destination() -> None:
    """A destination created after planning must survive the rename attempt."""
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


def test_cli_aborts_when_log_open_fails_with_journal_enabled() -> None:
    """A write command cannot proceed without opening its required journal."""
    from sortiton import cli

    called = []
    args = SimpleNamespace(command="rename", apply=True, quiet=True,
                           func=lambda _args: called.append(True) or 0)
    parser = mock.Mock()
    parser.parse_args.return_value = args
    with mock.patch.object(cli, "_build_parser", return_value=parser), \
            mock.patch.object(cli.external, "available", return_value=True), \
            mock.patch.object(cli, "open_log_file", return_value=None), \
            mock.patch.object(cli.journal, "enabled", return_value=True), \
            mock.patch.object(cli, "message"), \
            mock.patch.object(cli, "close_log_file"):
        rc = cli.main()

    check("the command exits before applying", rc == 2, str(rc))
    check("the write function is not called", not called, str(called))


def test_sort_worker_stops_before_the_next_file_after_cancel() -> None:
    """A worker checks cancellation immediately before each file operation."""
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


def test_all_preview_passes_cleaned_tags_and_renamed_paths_forward() -> None:
    """Rename and sort previews use the planned output of earlier steps."""
    from sortiton import output, tasks

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
        output.set_plan_sink(lambda kind, data: plans.append((kind, data)))
        try:
            with mock.patch.object(tasks, "probe_many", return_value=[dict(tags)]), \
                    mock.patch.object(tasks, "clean_artist",
                                      side_effect=lambda value, _rules:
                                      "NewArtist" if value == "OldArtist" else value):
                rc = tasks.cmd_all(args)
        finally:
            output.set_plan_sink(None)

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


def test_probe_tags_includes_track_disc_and_year() -> None:
    """All supported filename placeholders receive values from tag reads.

    The single-file probe and the parallel batch reader that rename and sort
    really use must both carry the three extra fields.
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


def test_backup_deduplicates_paths_that_resolve_to_the_same_file() -> None:
    """A CSV correction file is copied once even when several rows target it."""
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


def test_fixes_normalises_exported_multivalues_but_preserves_literal_titles() -> None:
    """Export-Separatoren gelten nur für Mehrfachwerte, nicht für wörtliche Titel."""
    import csv
    import io
    from sortiton.features import fixes
    from sortiton.tags import TrackInfo

    cases = [(field, ["Alice", "Bob"], "Alice | Bob", "Alice | Carol", "Alice; Carol")
             for field in ("artist", "album_artist", "genre")]
    cases += [("title", ["Alice | Bob"], "Alice | Bob", "Song | Remix", "Song | Remix"),
              ("title", ["Alice | Bob"], "Alice; Bob", "Song", None),
              ("artist", ["Alice", "Bob"], "Bob | Alice", "Carol", None)]
    with tempfile.TemporaryDirectory() as tmp:
        song = Path(tmp) / "song.mp3"
        song.write_bytes(b"audio")
        for field, current, old, new, expected in cases:
            csv_text = io.StringIO()
            csv.writer(csv_text, delimiter=";").writerow([song.name, field, old, new])
            rows = fixes.parse.read_csv(csv_text.getvalue())
            info = TrackInfo()
            setattr(info, field, current)
            with mock.patch.object(fixes, "read_info", return_value=info):
                actions, skipped, errors = fixes._prepare(rows, Path(tmp))

            check("CSV values remain valid", not errors, str(errors))
            if expected is None:
                check("a mismatching old value is skipped", not actions and len(skipped) == 1)
                continue
            check("the exported old value matches", len(actions) == 1 and not skipped)
            action = actions[0]
            check("the planned new value is normalised", action.new == expected, action.new)
            with mock.patch.object(fixes, "write_tags", return_value=True) as write, \
                    mock.patch.object(fixes.journal, "record_tags") as record:
                fixes._write(action)
            write.assert_called_once_with(song, {field: expected})
            record.assert_called_once_with(song, {field: "; ".join(current)}, {field: expected})


def test_fixes_counts_only_successful_applied_actions() -> None:
    """The applied changed count reflects successful writes, not the plan size."""
    from sortiton import output
    from sortiton.features import fixes

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = root / "first.mp3"
        second = root / "second.mp3"
        first.write_bytes(b"a")
        second.write_bytes(b"b")
        csv_file = root / "fixes.csv"
        csv_file.write_text("path;field;old;new\nfirst.mp3;artist;A;B\n"
                    "second.mp3;title;C;D\n", encoding="utf-8")
        actions = [fixes._Action(2, first, "artist", "A", "B"),
                   fixes._Action(3, second, "title", "C", "D")]

        def write(action):
            if action.path == second:
                raise OSError("write failed")

        args = SimpleNamespace(file=str(csv_file), root=tmp, apply=True,
                               backup=False)
        with mock.patch.object(fixes.external, "missing", return_value=[]), \
                mock.patch.object(fixes, "_prepare", return_value=(actions, [], [])), \
                mock.patch.object(fixes, "_write", side_effect=write):
            rc = fixes.cmd_fixes(args)

    stats = output.last_stats("fixes")
    check("the mixed run reports its failure", rc == 1, str(rc))
    check("only the successful correction is counted",
          stats.get("changed") == 1, str(stats))


def test_incomplete_backup_stops_before_writing() -> None:
    """A backup that could not copy every file is not a usable safety net."""
    from sortiton import tasks

    with tempfile.TemporaryDirectory() as tmp:
        missing = Path(tmp) / "gone.mp3"
        folder = tasks._backup_files(Path(tmp), [missing])
    check("an incomplete backup returns no folder", folder is None, str(folder))


def test_fixes_backup_does_not_mix_two_runs_in_one_second() -> None:
    """Two ``fixes --backup`` runs in the same second get separate folders."""
    from sortiton.features import fixes

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "track.flac"
        source.write_bytes(b"tag data")
        first = fixes._backup_files(root, [source])
        second = fixes._backup_files(root, [source])
        check("the first backup exists", first is not None and first.is_dir(), str(first))
        check("the second backup exists", second is not None and second.is_dir(), str(second))
        check("the two runs do not share a folder", first != second,
              f"{first} == {second}")
        check("the file was copied",
              first is not None and (first / source.name).read_bytes() == b"tag data")


def test_fixes_backup_failure_aborts_before_writing() -> None:
    """``fixes --apply --backup`` must not write when the backup failed."""
    from sortiton.features import fixes

    with tempfile.TemporaryDirectory() as tmp:
        csv_file = Path(tmp) / "fixes.csv"
        csv_file.write_text("path;field;old;new\n", encoding="utf-8")
        action = fixes._Action(2, Path(tmp) / "a.flac", "artist", "A", "B")
        args = SimpleNamespace(file=str(csv_file), root=tmp, apply=True, backup=True)
        with mock.patch.object(fixes.external, "missing", return_value=[]), \
                mock.patch.object(fixes.parse, "read_csv", return_value=[object()]), \
                mock.patch.object(fixes, "_prepare",
                                  return_value=([action], [], [])), \
                mock.patch.object(fixes, "_backup_files", return_value=None), \
                mock.patch.object(fixes, "_report"), \
                mock.patch.object(fixes, "_write") as writer:
            rc = fixes.cmd_fixes(args)

    check("the run reports an input error", rc == 2, str(rc))
    check("no tag was written", not writer.called, str(writer.call_args_list))


def test_undo_keeps_a_modified_copy() -> None:
    """The undo may delete a copy only while it still matches its original."""
    from sortiton import tasks

    with tempfile.TemporaryDirectory() as tmp:
        original = Path(tmp) / "original.mp3"
        copy = Path(tmp) / "copy.mp3"
        original.write_bytes(b"same")
        copy.write_bytes(b"different")
        outcome = tasks._undo_step({"op": "copy", "target": copy, "original": original})
        check("the modified copy is skipped", outcome == "skipped", outcome)
        check("the modified copy is kept", copy.exists())


def test_undo_keeps_a_download_when_the_archive_fails() -> None:
    """Deleting the file but not its archive line would make the undo a lie."""
    from sortiton import tasks
    from sortiton.files import content_digest

    with tempfile.TemporaryDirectory() as tmp:
        downloaded = Path(tmp) / "track.mp3"
        downloaded.write_bytes(b"x")
        with mock.patch.object(tasks, "_drop_archive_id", return_value=False):
            outcome = tasks._undo_step(
                {"op": "download", "path": downloaded, "archive_id": "youtube x",
                 "sha256": content_digest(downloaded)})
        check("the step reports an error", outcome == "error", outcome)
        check("the download is kept", downloaded.exists())


def test_tags_with_target_copy_and_move() -> None:
    """tags with target sorts files into the library (copy or move)."""
    from sortiton import tasks

    tags = {"artist": "Artist ", "album_artist": "", "album": "Album", "title": "Track", "genre": ""}
    # Test copy
    with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
        track = Path(src) / "track.mp3"
        track.write_bytes(b"audio-data")
        args = SimpleNamespace(folder=src, target=dst, move=False, apply=True, backup=False)
        with mock.patch.object(tasks, "probe_many", return_value=[dict(tags)]), \
                mock.patch.object(tasks, "write_tags", lambda path, diff: True):
            rc = tasks.cmd_tags(args)
        check("tags with target returns 0", rc == 0, str(rc))
        expected_dst = Path(dst) / "Artist" / "Album" / "track.mp3"
        check("file copied to library", expected_dst.exists())
        check("original kept on copy", track.exists())

    # Test move
    with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
        track = Path(src) / "track.mp3"
        track.write_bytes(b"audio-data")
        args = SimpleNamespace(folder=src, target=dst, move=True, apply=True, backup=False)
        with mock.patch.object(tasks, "probe_many", return_value=[dict(tags)]), \
                mock.patch.object(tasks, "write_tags", lambda path, diff: True):
            rc = tasks.cmd_tags(args)
        check("tags with target returns 0", rc == 0, str(rc))
        expected_dst = Path(dst) / "Artist" / "Album" / "track.mp3"
        check("file moved to library", expected_dst.exists())
        check("original removed on move", not track.exists())


def test_tags_with_dirty_identical_target_places_cleaned_copy() -> None:
    """A dirty source must not be skipped just because its target is identical."""
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
    """rename with target renames and sorts into the library (copy or move)."""
    from sortiton import tasks

    tags = {"artist": "Artist", "album_artist": "", "album": "Album", "title": "Song", "genre": ""}
    # Test copy
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

    # Test move
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
    """Move mode must not silently degrade to an in-place operation."""
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


def test_placement_cancellation_stops_queued_moves() -> None:
    """After cancellation, queued placements do not start moving files."""
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


def test_all_preview_accounts_for_tag_changes_before_identical_check() -> None:
    """Vorschau und Ausführung wählen nach Tagänderungen dieselbe freie Zieldatei."""
    from sortiton import output, tasks

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
            output.set_plan_sink(lambda kind, data: plans.append((kind, data)))
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
                output.set_plan_sink(None)

            expected = [existing.with_name("Song (2).mp3")] if dirty else []
            check("both pipeline runs succeed", preview_rc == apply_rc == 0)
            check("preview and apply agree about identical files",
                  preview_targets == applied_targets == expected,
                  str((preview_targets, applied_targets, dirty)))
            check("the identical old target survives", existing.read_bytes() == b"original")
            if dirty:
                check("the cleaned copy is placed", expected[0].read_bytes() == b"cleaned")
