"""Regression checks for journal, tags, comparison and dialogs."""

from __future__ import annotations

from _support import (
    Path,
    check,
    files,
    journal,
    subprocess,
    tempfile,
    threading,
    time,
)


def test_regressions() -> None:
    """Checks for the concurrency and writer fixes (no display needed)."""
    print("regressions: journal, tags, comparison, dialogs")

    # record() must check _file under the lock: close() clears it under the
    # same lock. Before the fix a record() that passed the check first wrote
    # to None and raised AttributeError.
    import unittest.mock as mock
    from sortiton import tags
    from sortiton.gui import dialogs

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
        except BaseException as error:      # noqa: BLE001 - the test collects it
            errors.append(error)

    try:
        journal._lock.acquire()
        journal._file = _NeverUsed()
        worker = threading.Thread(target=record_worker)
        worker.start()
        time.sleep(0.1)                     # let it pass the (old) check
        journal._file = None                # what close() does under the lock
        journal._lock.release()
        worker.join(timeout=2)
    finally:
        journal._lock = original_lock
        journal._file = original_file
    check("record() never writes after close()", not errors, repr(errors))

    # Same size, different first byte: the early compare must say "different".
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

    # Every writer mapping must know every tag field the fixes feature writes.
    fields = set(tags.TAG_FIELDS)
    check("ID3 mapping is complete", fields <= set(tags._ID3_FRAMES))
    check("ASF mapping is complete", fields <= set(tags._ASF_KEYS))
    check("Vorbis mapping is complete", fields <= set(tags._VORBIS_KEYS))
    check("MP4 mapping is complete",
          fields <= set(tags._MP4_TEXT_KEYS) | set(tags._MP4_PAIR_KEYS))

    # A hung native dialog falls back to Tkinter instead of blocking forever.
    timeout = subprocess.TimeoutExpired(cmd="kdialog", timeout=1)
    with mock.patch.object(dialogs, "_command_available", return_value=True), \
            mock.patch.object(dialogs.subprocess, "run", side_effect=timeout) as run, \
            mock.patch.object(dialogs.messagebox, "askyesno", return_value=True) as fallback:
        answer = dialogs._ask_yes_no("Title", "Text")
    check("dialog timeout falls back", answer is True and fallback.called,
          f"answer={answer}, calls={run.call_count}")
    check("dialog timeout is passed to subprocess",
          run.call_count == 2 and all(call.kwargs.get("timeout") for call in run.call_args_list),
          str(run.call_args_list))
