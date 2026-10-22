"""Run journal, log files and undo/restore."""

from __future__ import annotations

import json
import os
import threading
import time
import unittest.mock as mock

import pytest

from _support import (
    Path,
    _FrozenClock,
    _make_flac,
    _open_journal,
    _restore_args,
    check,
    cmd_restore,
    config,
    journal,
    output,
    probe_tags,
    shutil,
    skip,
    tempfile,
    write_tags,
)


@pytest.mark.parametrize("legacy", [False, True])
def test_download_undo_preserves_modified_or_unverified_files(legacy: bool) -> None:
      """Undo entfernt weder geänderte Downloads noch Dateien ohne Inhaltsnachweis."""
      from unittest import mock
      from sortiton import tasks

      with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            downloaded = work / "download.mp3"
            downloaded.write_bytes(b"before")
            opened = _open_journal(work, 11)
            try:
                  if legacy:
                        journal.record("download", path=str(downloaded), archive_id="youtube track")
                  else:
                        journal.record_download(downloaded, "https://example.org/track", "youtube track")
            finally:
                  journal.close()

            if not legacy:
                  downloaded.write_bytes(b"edited")
            with mock.patch.object(tasks, "_drop_archive_id") as drop:
                  rc = cmd_restore(_restore_args(opened, apply=True))

            check("unverified download undo succeeds without deleting", rc == 0, str(rc))
            check("the download contents survive",
                    downloaded.read_bytes() == (b"before" if legacy else b"edited"))
            check("the archive is left untouched", not drop.called)
            check("the download is counted as skipped",
                    output.last_stats("restore").get("skipped") == 1,
                    str(output.last_stats("restore")))


def test_journal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        log = work / "sortiton_2026-01-01_00-00-00.log"
        log.write_text("", encoding="utf-8")

        journal.close()
        target = work / "a.mp3"
        target.write_bytes(b"x")

        opened = journal.open_for(log)
        check("journal is created next to the log",
              opened is not None and opened.suffix == ".jsonl", str(opened))
        check("journal knows it is open", journal.is_open())
        check("its path is remembered", journal.latest_path() == opened)
        if opened is None:
            return          # the checks above already failed - nothing to read

        journal.record_tags(target, {"artist": "Old"}, {"artist": "New"})
        journal.record_move("rename", target, work / "b.mp3")
        journal.close()

        events = list(journal.read_journal(opened))
        check("a header is written", bool(events) and events[0]["op"] == "run",
              str(events[:1]))
        check("events are readable",
              [event["op"] for event in events] == ["run", "tags", "rename"],
              str([event["op"] for event in events]))
        check("the header carries argv and cwd",
              "argv" in events[0] and "cwd" in events[0])
        check("schema version is stored",
              journal.schema_version(opened) == journal.SCHEMA)

        planned = journal.plan_restore(opened)
        check("undo runs newest first",
              [event["op"] for event in planned] == ["rename", "tags"],
              str([event["op"] for event in planned]))
        check("summary counts per operation",
              journal.summarize(planned) == {"rename": 1, "tags": 1},
              str(journal.summarize(planned)))

        # A preview must not leave a journal behind: record() on a closed
        # journal does nothing, so no file appears next to the log path.
        preview_log = work / "sortiton_2026-01-01_01-00-00.log"
        check("no journal while closed", not journal.is_open())
        journal.record("tags")      # must simply do nothing
        check("a closed journal writes nothing",
              not journal.journal_path_for(preview_log).exists())

        broken = work / "broken.jsonl"
        broken.write_text('{"v": 1, "op": "run"}\nnot json\n\n'
                          '{"v": 1, "op": "tags"}\n', encoding="utf-8")
        check("broken lines are skipped",
              len(list(journal.read_journal(broken))) == 2)
        check("a missing journal reads as empty",
              list(journal.read_journal(work / "nope.jsonl")) == [])
        check("unknown operations are named",
              journal.summarize([{"op": "rmfile"}]) == {"rmfile": 1})

        # Der Download ist rückgängig zu machen und trägt die Archiv-ID, ist
        # aber additiv und darf die Schema-Version nicht erhöhen.
        dl_log = work / "sortiton_2026-01-01_00-30-00.log"
        dl_log.write_text("", encoding="utf-8")
        dl_journal = journal.open_for(dl_log)
        journal.record_download(work / "down.mp3", "https://example.org/watch?v=x",
                                "youtube abc123")
        journal.close()
        dl_events = journal.plan_restore(dl_journal)
        check("download is an undoable operation",
              "download" in journal.UNDOABLE, str(journal.UNDOABLE))
        check("a download record is planned for undo",
              [event["op"] for event in dl_events] == ["download"],
              str([event["op"] for event in dl_events]))
        check("a download record keeps path, url and archive id",
              bool(dl_events) and str(dl_events[0].get("path", "")).endswith("down.mp3")
              and dl_events[0].get("url") == "https://example.org/watch?v=x"
              and dl_events[0].get("archive_id") == "youtube abc123",
              str(dl_events[0] if dl_events else dl_events))
        check("summarize counts a download",
              journal.summarize(dl_events) == {"download": 1},
              str(journal.summarize(dl_events)))
        check("a new operation does not bump the schema",
              journal.schema_version(dl_journal) == journal.SCHEMA,
              str(journal.schema_version(dl_journal)))

        # A run must never be offered its own journal as "the last one to undo".
        older = journal.open_for(config.LOG_DIR / "sortiton_2026-01-01_02-00-00.log")
        journal.record_move("rename", target, work / "c.mp3")
        journal.close()
        newer = journal.open_for(config.LOG_DIR / "sortiton_2026-01-01_03-00-00.log")
        check("the journal of the running run is skipped",
              journal.latest_journal() == older, str(journal.latest_journal()))
        journal.close()
        check("afterwards the newest journal is the last run",
              journal.latest_journal() == newer, str(journal.latest_journal()))


def test_logs() -> None:
    """Zwei Läufe in derselben Sekunde bekommen zwei eigene, vollständige Protokolle."""
    output.close_log_file()

    # A second run in the same second must not cut the first log short.
    real_clock = output.datetime
    output.datetime = _FrozenClock
    try:
        first = output.open_log_file("first run")
        second = output.open_log_file("second run")
        output.close_log_file()
    finally:
        output.datetime = real_clock

    check("the second run gets a log of its own",
          first is not None and second is not None and first != second,
          f"{first} / {second}")
    first_text = first.read_text(encoding="utf-8") if first else ""
    second_text = second.read_text(encoding="utf-8") if second else ""
    check("the first log survives complete", "first run" in first_text)
    check("both logs name their own run",
          "second run" in second_text and "first run" not in second_text)


@pytest.mark.external
def test_restore() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)

        # moves and copies; no audio file needed for these
        music = work / "music"
        music.mkdir()
        track = music / "track.mp3"
        track.write_bytes(b"\x00" * 64)

        moved_to = work / "library" / "Demo - Song.mp3"
        moved_to.parent.mkdir()
        shutil.move(str(track), str(moved_to))
        copied_to = work / "copies" / "Demo - Song.mp3"
        copied_to.parent.mkdir()
        shutil.copy2(moved_to, copied_to)

        jrn = _open_journal(work, 1)
        journal.record_move("rename", track, moved_to)
        journal.record_move("copy", moved_to, copied_to, mode="copy")
        journal.close()

        check("preview runs", cmd_restore(_restore_args(jrn)) == 0)
        check("preview changes nothing",
              moved_to.exists() and copied_to.exists() and not track.exists())
        check("preview counts both changes",
              output.last_stats("restore").get("changed") == 2,
              str(output.last_stats("restore")))
        check("preview does not write",
              not output.last_stats("restore").get("applied"))

        check("apply runs", cmd_restore(_restore_args(jrn, apply=True)) == 0)
        check("moved file is back", track.exists() and not moved_to.exists())
        check("the copy is gone", not copied_to.exists())
        stats = output.last_stats("restore")
        check("nothing was skipped", stats.get("skipped") == 0, str(stats))
        check("no errors", stats.get("errors") == 0, str(stats))
        check("apply is reported", bool(stats.get("applied")))

        # A combined run (tags -> rename -> sort/move) is undone as one chain.
        # Planning must not drop the steps that only work after an earlier undo
        # step has moved the file back.
        chain = work / "chain"
        chain.mkdir()
        first = chain / "first.mp3"
        second = chain / "second.mp3"
        third = chain / "library" / "third.mp3"
        first.write_bytes(b"\x02" * 64)
        first.rename(second)
        third.parent.mkdir()
        shutil.move(str(second), str(third))
        jrn_chain = _open_journal(work, 11)
        journal.record_move("rename", first, second)
        journal.record_move("sort", second, third, mode="move")
        journal.close()

        check("chain preview plans every step",
              cmd_restore(_restore_args(jrn_chain)) == 0
              and output.last_stats("restore").get("changed") == 2,
              str(output.last_stats("restore")))
        check("chain preview changes nothing", third.exists())
        check("chain undo runs", cmd_restore(_restore_args(jrn_chain, apply=True)) == 0)
        check("chain undo restores the first name",
              first.read_bytes() == b"\x02" * 64
              and not second.exists() and not third.exists(),
              str([path.name for path in chain.rglob("*.mp3")]))
        stats = output.last_stats("restore")
        check("chain undo counts both steps", stats.get("changed") == 2, str(stats))
        check("chain undo skips nothing", stats.get("skipped") == 0, str(stats))

        # --backup in a chain copies the file where it lies before the undo,
        # not at an intermediate name that does not exist yet.
        backup_chain = work / "chain_backup"
        backup_chain.mkdir()
        b_first = backup_chain / "first.mp3"
        b_second = backup_chain / "second.mp3"
        b_third = backup_chain / "library" / "third.mp3"
        b_first.write_bytes(b"\x03" * 64)
        b_first.rename(b_second)
        b_third.parent.mkdir()
        shutil.move(str(b_second), str(b_third))
        jrn_backup = _open_journal(work, 12)
        journal.record_move("rename", b_first, b_second)
        journal.record_move("sort", b_second, b_third, mode="move")
        journal.close()
        cmd_restore(_restore_args(jrn_backup, apply=True, backup=True))
        folder = Path(str(output.last_stats("restore").get("backup") or ""))
        copied = list(folder.rglob("*.mp3")) if folder.is_dir() else []
        check("--backup of a chain copies the file",
              len(copied) == 1 and copied[0].read_bytes() == b"\x03" * 64,
              str(copied))

        # The tags step of the same run is only possible after the renames:
        # its path must be planned virtually, not checked on disk.
        tag_chain = work / "chain_tags"
        tag_chain.mkdir()
        old_name = tag_chain / "01 - Song.flac"
        tag_renamed = tag_chain / "Demo - Song.flac"
        tag_sorted = tag_chain / "library" / "Demo" / "Demo - Song.flac"
        if not _make_flac(old_name):
            skip("undo/tags chain", "ffmpeg is missing - cannot build a test file")
        else:
            write_tags(old_name, {"artist": "Old Name"})
            jrn_chain_tags = _open_journal(work, 13)
            journal.record_tags(old_name, {"artist": "Old Name"},
                                {"artist": "New Name"})
            journal.record_move("rename", old_name, tag_renamed)
            journal.record_move("sort", tag_renamed, tag_sorted, mode="move")
            # The run itself: tags -> rename -> sort/move.
            write_tags(old_name, {"artist": "New Name"})
            old_name.rename(tag_renamed)
            tag_sorted.parent.mkdir(parents=True)
            shutil.move(str(tag_renamed), str(tag_sorted))
            journal.close()

            check("tag chain preview plans all three steps",
                  cmd_restore(_restore_args(jrn_chain_tags)) == 0
                  and output.last_stats("restore").get("changed") == 3,
                  str(output.last_stats("restore")))
            check("tag chain undo runs",
                  cmd_restore(_restore_args(jrn_chain_tags, apply=True)) == 0)
            check("tag chain restores the original name",
                  old_name.exists() and not tag_renamed.exists()
                  and not tag_sorted.exists(),
                  str([path.name for path in tag_chain.rglob("*.flac")]))
            check("tag chain restores the old tag",
                  probe_tags(old_name)["artist"] == "Old Name",
                  probe_tags(old_name)["artist"])
            check("tag chain reports no errors",
                  output.last_stats("restore").get("errors") == 0,
                  str(output.last_stats("restore")))

        # A name taken again between preview and apply is skipped, never
        # overwritten - and the counters show what really happened.
        late = work / "late"
        late.mkdir()
        late_old = late / "old.mp3"
        late_new = late / "new.mp3"
        late_old.write_bytes(b"\x04" * 8)
        shutil.move(str(late_old), str(late_new))
        jrn_late = _open_journal(work, 14)
        journal.record_move("rename", late_old, late_new)
        journal.close()
        cmd_restore(_restore_args(jrn_late))
        late_old.write_bytes(b"\x05" * 8)
        cmd_restore(_restore_args(jrn_late, apply=True))
        stats = output.last_stats("restore")
        check("a name taken after the preview is skipped",
              late_old.read_bytes() == b"\x05" * 8 and late_new.exists()
              and stats.get("skipped") == 1 and stats.get("changed") == 0,
              str(stats))

        # A cancelled undo never starts its first step.
        from sortiton.cancel import CancelToken
        cancel_dir = work / "cancel_restore"
        cancel_dir.mkdir()
        c_old = cancel_dir / "old.mp3"
        c_new = cancel_dir / "new.mp3"
        c_old.write_bytes(b"\x06" * 8)
        shutil.move(str(c_old), str(c_new))
        jrn_cancel = _open_journal(work, 15)
        journal.record_move("rename", c_old, c_new)
        journal.close()
        token = CancelToken()
        token.cancel()
        check("a cancelled undo returns 130",
              cmd_restore(_restore_args(jrn_cancel, apply=True,
                                        cancel=token)) == 130)
        check("a cancelled undo changes nothing", c_new.exists() and not c_old.exists())

        # --keep-copies: a copy run stays where it is
        keep_dir = work / "keep"
        keep_dir.mkdir()
        original = keep_dir / "orig.mp3"
        original.write_bytes(b"\x00" * 64)
        kept = keep_dir / "kept.mp3"
        shutil.copy2(original, kept)
        jrn_keep = _open_journal(work, 2)
        journal.record_move("copy", original, kept, mode="copy")
        journal.close()
        cmd_keep = cmd_restore(_restore_args(jrn_keep, apply=True, keep_copies=True))
        check("--keep-copies run works", cmd_keep == 0)
        check("--keep-copies keeps the copy", kept.exists())

        # the last copy is the only file left - do not delete it
        only = work / "only"
        only.mkdir()
        last_copy = only / "last.mp3"
        last_copy.write_bytes(b"\x00" * 64)
        jrn_only = _open_journal(work, 3)
        journal.record_move("copy", only / "gone.mp3", last_copy, mode="copy")
        journal.close()
        cmd_restore(_restore_args(jrn_only, apply=True))
        check("the only copy survives", last_copy.exists())
        check("that case is counted as skipped",
              output.last_stats("restore").get("skipped") == 1,
              str(output.last_stats("restore")))

        # Ein Download wird rückgängig gemacht, indem die Datei gelöscht und
        # ihre Archiv-Zeile entfernt wird - sonst blockiert das Archiv einen
        # späteren erneuten Download.
        archive = config.FETCH_ARCHIVE
        archive.parent.mkdir(parents=True, exist_ok=True)
        downloads = work / "downloads"
        downloads.mkdir()

        grabbed = downloads / "grabbed.mp3"
        grabbed.write_bytes(b"\x00" * 32)
        archive.write_text("youtube keepme\nyoutube abc123\nyoutube other\n",
                           encoding="utf-8")
        jrn_dl = _open_journal(work, 7)
        journal.record_download(grabbed, "https://example.org/watch?v=abc",
                                "youtube abc123")
        journal.close()

        check("download preview runs", cmd_restore(_restore_args(jrn_dl)) == 0)
        check("download preview keeps the file", grabbed.exists())
        check("download preview counts one change",
              output.last_stats("restore").get("changed") == 1,
              str(output.last_stats("restore")))
        check("download undo runs", cmd_restore(_restore_args(jrn_dl, apply=True)) == 0)
        check("the downloaded file is gone", not grabbed.exists())
        remaining = archive.read_text(encoding="utf-8")
        check("the archive line is dropped",
              "youtube abc123" not in remaining and "youtube keepme" in remaining,
              remaining)
        check("download undo reports no errors",
              output.last_stats("restore").get("errors") == 0,
              str(output.last_stats("restore")))

        # --keep-copies keeps the download (and its archive line) in place
        kept_download = downloads / "kept.mp3"
        kept_download.write_bytes(b"\x00" * 32)
        archive.write_text("youtube keepme\nyoutube keep2\n", encoding="utf-8")
        jrn_dl_keep = _open_journal(work, 8)
        journal.record_download(kept_download, "https://example.org/watch?v=keep",
                                "youtube keep2")
        journal.close()
        cmd_restore(_restore_args(jrn_dl_keep, apply=True, keep_copies=True))
        check("--keep-copies keeps the download", kept_download.exists())
        check("a kept download is counted as skipped",
              output.last_stats("restore").get("skipped") == 1,
              str(output.last_stats("restore")))
        check("--keep-copies keeps the archive line",
              "youtube keep2" in archive.read_text(encoding="utf-8"))

        # a download whose file is already gone is skipped, not an error
        jrn_dl_gone = _open_journal(work, 9)
        journal.record_download(downloads / "gone.mp3", "https://example.org/g",
                                "youtube gone")
        journal.close()
        check("a missing download is skipped",
              cmd_restore(_restore_args(jrn_dl_gone, apply=True)) == 0
              and output.last_stats("restore").get("skipped") == 1,
              str(output.last_stats("restore")))

        # no archive was used (--no-archive): the undo still deletes the file
        no_arch = downloads / "noarch.mp3"
        no_arch.write_bytes(b"\x00" * 32)
        jrn_dl_noarch = _open_journal(work, 10)
        journal.record_download(no_arch, "https://example.org/e", "")
        journal.close()
        check("a download without an archive id still undoes",
              cmd_restore(_restore_args(jrn_dl_noarch, apply=True)) == 0
              and not no_arch.exists(),
              str(output.last_stats("restore")))

        # the old name is taken again: nothing may be overwritten
        clash = work / "clash"
        clash.mkdir()
        old_name = clash / "old.mp3"
        new_name = clash / "new.mp3"
        new_name.write_bytes(b"\x00" * 64)
        old_name.write_bytes(b"\x01" * 64)     # something new took the name
        jrn_clash = _open_journal(work, 4)
        journal.record_move("rename", old_name, new_name)
        journal.close()
        cmd_restore(_restore_args(jrn_clash, apply=True))
        check("a taken name is not overwritten",
              new_name.read_bytes() == b"\x00" * 64 and old_name.exists())

        # for tags we need a real audio file
        tag_dir = work / "tags"
        tag_dir.mkdir()
        song = tag_dir / "song.flac"
        if not _make_flac(song):
            skip("undo/tags", "ffmpeg is missing - cannot build a test file")
        else:
            write_tags(song, {"artist": "Demo Orchestra"})
            jrn_tags = _open_journal(work, 5)
            journal.record_tags(song, {"artist": "Demo Orchestra"},
                                {"artist": "Demo"})
            journal.close()
            write_tags(song, {"artist": "Demo"})
            check("the tag was changed", probe_tags(song)["artist"] == "Demo",
                  probe_tags(song)["artist"])

            check("tag undo runs",
                  cmd_restore(_restore_args(jrn_tags, apply=True)) == 0)
            check("the old tag is back",
                  probe_tags(song)["artist"] == "Demo Orchestra",
                  probe_tags(song)["artist"])

        # a failed event is reported, not hidden
        jrn_missing = _open_journal(work, 6)
        journal.record_failure("tags", "boom", path=str(tag_dir / "x.flac"))
        journal.close()
        check("a failed event is skipped",
              cmd_restore(_restore_args(jrn_missing, apply=True)) == 0
              and output.last_stats("restore").get("skipped") == 1,
              str(output.last_stats("restore")))

        check("a missing journal is an error",
              cmd_restore(_restore_args(work / "nope.jsonl")) == 2)
        check("--list runs", cmd_restore(_restore_args(None, list_journals=True)) == 0)


def test_journals_in_the_same_second_are_ordered() -> None:
    """Das " (2)"-Journal derselben Sekunde ist neuer als das Basis-Journal."""
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
    """Restore bindet alte relative Einträge an den damaligen Ordner des Laufs."""
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


def test_journal_write_failure_is_reported_once() -> None:
    """Ein fehlschlagendes Journal stoppt den Lauf nicht, warnt aber genau einmal."""
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


def test_log_prune_uses_the_real_timestamp() -> None:
    """Ein ``... (2).log`` derselben Sekunde ist neuer als die Basisdatei."""
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


def test_record_never_writes_after_close() -> None:
    """``record`` prüft ``_file`` unter dem Lock, das ``close`` unter demselben räumt.

    Vor dem Fix konnte ein ``record()``, das die Prüfung gerade passiert hatte,
    auf ``None`` schreiben und ``AttributeError`` werfen.
    """
    class _NeverUsed:
        def write(self, _text):
            raise AssertionError("record wrote after close()")

        def flush(self):
            raise AssertionError("record flushed after close()")

    original_lock, original_file = journal._lock, journal._file
    journal._lock = threading.Lock()
    errors: list[BaseException] = []

    def record_worker() -> None:
        try:
            journal.record("regression")
        except BaseException as error:      # noqa: BLE001 - der Test sammelt sie
            errors.append(error)

    try:
        journal._lock.acquire()
        journal._file = _NeverUsed()
        worker = threading.Thread(target=record_worker)
        worker.start()
        time.sleep(0.1)                     # dem Worker die Prüfung passieren lassen
        journal._file = None                # was close() unter dem Lock tut
        journal._lock.release()
        worker.join(timeout=2)
    finally:
        journal._lock = original_lock
        journal._file = original_file
    check("record() never writes after close()", not errors, repr(errors))


def test_undo_keeps_a_modified_copy() -> None:
    """Der Undo darf eine Kopie nur löschen, solange sie ihrem Original gleicht."""
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
    """Die Datei löschen, aber die Archiv-Zeile behalten, wäre ein falsches Undo."""
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
