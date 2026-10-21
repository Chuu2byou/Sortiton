"""Regression checks for the findings of the code review.

One test per defect, written against the public behaviour (not the internals
that were changed), so a later rewrite may keep them.
"""

from __future__ import annotations

import os
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
        saved: list[object] = []

        def fake_stream(_argv, _cancel, handle):
            handle("SORTITON_FILE\t" + str(target))
            return 1, "boom"

        with mock.patch.object(download, "_stream", fake_stream):
            files, error = download.download("https://example.org/x", Path(tmp),
                                             audio_format="mp3", playlist=True,
                                             on_saved=saved.append)

    check("the error is reported", error == "boom", error)
    check("the finished file is returned", [item.path for item in files] == [target],
          str(files))
    check("the callback saw the finished file", [item.path for item in saved] == [target],
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

    secret = "https://user:pass@example.org/watch/session-token?token=abc#frag"
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
        check("the file was copied", (first / source.name).read_bytes() == b"tag data")


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

    with tempfile.TemporaryDirectory() as tmp:
        downloaded = Path(tmp) / "track.mp3"
        downloaded.write_bytes(b"x")
        with mock.patch.object(tasks, "_drop_archive_id", return_value=False):
            outcome = tasks._undo_step(
                {"op": "download", "path": downloaded, "archive_id": "youtube x"})
        check("the step reports an error", outcome == "error", outcome)
        check("the download is kept", downloaded.exists())
