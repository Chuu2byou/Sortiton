"""Regression tests for the hardening changes from the code review."""

from __future__ import annotations

import os
import unittest.mock as mock

from _support import Path, SimpleNamespace, check, config, output, tempfile


def test_backup_retention_does_not_let_incomplete_evict_complete() -> None:
    """An incomplete backup must never displace the last usable one."""
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

            # Simulate a crash: a newer folder with an incomplete marker.
            incomplete = backups / "backup_2999-01-01_00-00-00"
            incomplete.mkdir()
            (incomplete / ".incomplete").write_text("incomplete\n", encoding="utf-8")

            tasks._prune_backups(keep=1)
            check("the complete backup survived", complete.is_dir())
            check("the incomplete folder left the backup namespace",
                  not incomplete.exists())
            check("the incomplete folder is kept as evidence",
                  (backups / "failed" / incomplete.name).is_dir())

            # A backup that fails while copying is not counted either.
            failed = tasks._backup_files(root, [root / "missing.mp3"])
            check("a failed backup is not returned", failed is None)
            tasks._prune_backups(keep=1)
            check("the good backup still survived", complete.is_dir())


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


def test_redaction_covers_option_urls_and_scheme_less_queries() -> None:
    """Tokens in ``--fetch-url=…`` and bare URLs never reach the log."""
    from sortiton import redact

    for argument in ("--fetch-url=https://example.org/watch?v=secret",
                     "--fetch-url=youtu.be/watch?v=secret"):
        rendered = redact.command([argument])[0]
        check("the token is redacted", "secret" not in rendered, rendered)
        check("the option is still visible", rendered.startswith("--fetch-url="),
              rendered)

    bare = redact.url("youtu.be/watch?v=secret")
    check("a scheme-less query is redacted", "secret" not in bare, bare)


def test_fixes_write_failure_is_a_nonzero_exit() -> None:
    """A failed correction is not counted as a completed change."""
    from sortiton.features import fixes

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "song.mp3"
        path.write_bytes(b"x")
        second_path = Path(tmp) / "song-2.mp3"
        second_path.write_bytes(b"y")
        csv_file = Path(tmp) / "fixes.csv"
        csv_file.write_text("path;field;old;new\nsong.mp3;track;1;2\n",
                            encoding="utf-8")
        action = fixes._Action(2, path, "track", "1", "2")
        failed_action = fixes._Action(3, second_path, "track", "3", "4")

        args = SimpleNamespace(file=str(csv_file), root=tmp, apply=True,
                               backup=False)
        with mock.patch.object(fixes.external, "missing", return_value=[]), \
               mock.patch.object(fixes, "_prepare",
                             return_value=([action, failed_action], [], [])), \
               mock.patch.object(fixes, "_write",
                             side_effect=[None, RuntimeError("write failed")]):
            rc = fixes.cmd_fixes(args)

        check("a failed write returns 1", rc == 1, str(rc))
        check("the failure is counted",
              output.last_stats("fixes").get("errors") == 1,
              str(output.last_stats("fixes")))


def test_log_prune_uses_the_real_timestamp() -> None:
    """A same-second ``... (2).log`` is newer than the base file."""
    with tempfile.TemporaryDirectory() as tmp:
        logs = Path(tmp)
        base = logs / f"{output.LOG_PREFIX}_2026-01-01_00-00-00.log"
        later = logs / f"{output.LOG_PREFIX}_2026-01-01_00-00-00 (2).log"
        base.write_text("old\n", encoding="utf-8")
        later.write_text("new\n", encoding="utf-8")
        os.utime(base, ns=(1_000_000_000, 1_000_000_000))
        os.utime(later, ns=(2_000_000_000, 2_000_000_000))

        with mock.patch.object(output, "LOG_DIR", logs):
            output._prune_old_logs(keep=1)

        check("the older log was removed", not base.exists())
        check("the newer log survived", later.is_file())


def test_fetch_requires_ffmpeg_only_when_applying() -> None:
    """A preview asks yt-dlp only; ffmpeg is a write-stage requirement."""
    from sortiton import external
    from sortiton.features.fetch import FEATURE

    def available(tool):
        return tool == external.YT_DLP

    with mock.patch.object(external, "available", side_effect=available):
        preview = external.missing(FEATURE, SimpleNamespace(apply=False))
        applied = external.missing(FEATURE, SimpleNamespace(apply=True))

    check("a preview does not need ffmpeg", not preview, str(preview))
    check("an applied fetch needs ffmpeg",
          any(external.FFMPEG in requirement.any_of for requirement in applied),
          str(applied))


def test_all_counts_fetch_errors() -> None:
    """The aggregate result of ``all`` includes the optional fetch stage."""
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


def test_unsafe_regex_rules_are_rejected() -> None:
    """Nested/alternating quantifiers and oversized patterns are skipped."""
    from sortiton import rules

    text = ("[Artist Regex]\n"
            "(a+)+$ = nested\n"
            "(ab|cd)+$ = alternating\n"
            + "a" * 501 + " = too_long\n"
            "safe = done\n")
    parsed, warnings = rules.parse_custom_rules(text)

    check("only the safe rule was loaded",
          len(parsed.regex) == 1, str([pattern.pattern for pattern, _ in parsed.regex]))
    check("all three unsafe rules were reported", len(warnings) == 3, str(warnings))
    check("the safe rule is the expected one",
          parsed.regex[0][0].pattern == "safe", parsed.regex[0][0].pattern)


def test_journal_write_failure_is_reported_once() -> None:
    """A failing journal does not stop the run but warns the user once."""
    from sortiton import journal

    class Broken:
        def write(self, _line: str) -> None:
            raise OSError("disk full")

        def flush(self) -> None:
            pass

    old = (journal._file, journal._path, journal._write_error_reported)
    try:
        journal._file = Broken()
        journal._path = Path("broken.jsonl")
        journal._write_error_reported = False
        with mock.patch.object(journal.output, "message") as warning:
            journal.record("tags", path="song.mp3")
            journal.record("tags", path="other.mp3")
        check("the failure is reported exactly once", warning.call_count == 1,
              str(warning.call_count))
    finally:
        journal._file, journal._path, journal._write_error_reported = old


def test_fingerprint_index_drops_common_values() -> None:
    """A sub-fingerprint in too many files is removed instead of kept forever."""
    from sortiton.features.export import fingerprint

    fps = {0: [7, 8, 9], 1: [7, 8], 2: [7, 8]}
    with mock.patch.object(fingerprint, "FP_MAX_POSTINGS", 2):
        index = fingerprint._build_index(fps)

    check("the common values are gone", 7 not in index and 8 not in index, str(index))
    check("the rare value is kept", list(index.get(9, [])) == [2], str(index))


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
