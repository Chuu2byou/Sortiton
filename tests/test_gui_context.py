"""Weiterleitung gleichzeitiger Scan- und Laufmeldungen."""

import gc
from queue import Queue
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from sortiton import journal, output
from sortiton.cancel import CancelToken
from sortiton.gui.mixins import run as gui_run
from sortiton.gui.mixins.run import RunMixin


def test_stale_and_cancelled_scan_events_do_not_affect_current_run():
    old = CancelToken()
    current = CancelToken()
    app = SimpleNamespace(_scan_cancel=current, _log_line=Mock(), _set_progress=Mock(),
                          _absorb_stats=Mock(), _scan_finished=Mock(), _finish=Mock(),
                          _absorb_plan=Mock())
    dispatch = lambda kind, value: RunMixin._dispatch(app, kind, value)
    dispatch("scan_stats", (old, ("scan", {"files": 5})))
    dispatch("scan_done", (old, 0))
    dispatch("scan_prog", (current, (1, 2, "scan")))
    app._set_progress.assert_called_once_with(1, 2, "scan")
    current.cancel()
    dispatch("scan_stats", (current, ("scan", {"files": 5})))
    dispatch("scan_prog", (current, (2, 2, "scan")))
    dispatch("scan_log", (current, "veraltet"))
    dispatch("prog", (1, 3, "run"))
    app._absorb_stats.assert_not_called()
    app._log_line.assert_not_called()
    assert app._set_progress.call_count == 2
    app._set_progress.assert_called_with(1, 3, "run")
    dispatch("scan_done", (current, 130))
    app._scan_finished.assert_called_once_with()


def test_run_worker_emits_live_events_before_completion(monkeypatch):
    class ImmediateThread:
        def __init__(self, target, daemon):
            self.target = target
            assert daemon

        def start(self):
            self.target()

    monkeypatch.setattr(gui_run.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(output, "open_log_file", lambda _title: None)
    monkeypatch.setattr(output, "close_log_file", lambda _rc: None)
    monkeypatch.setattr(journal, "close", lambda: None)
    app = SimpleNamespace(
        running=False, _cancel_scan=Mock(), _cancel_button=None,
        _begin_plan=Mock(), _signature=Mock(return_value=("signature",)),
        _set_buttons=Mock(), _render_preview=Mock(), progress=Mock(),
        progress_label=Mock(), _set_state=Mock(), status_var=Mock(),
        _log_line=Mock(), _log_rules=Mock(), queue=Queue())

    def action(_args):
        output.message("Lauf")
        output.progress(1, 1, "fertig")
        output.report_plan("sort", source="a", target="b")
        output.report_stats("sort", files=1, changed=1)
        return 0

    saved_context = output.current_run_context()
    assert RunMixin._start(app, "sort", "Sortieren", action,
                           SimpleNamespace(apply=False), ".")
    events = [app.queue.get_nowait() for _ in range(app.queue.qsize())]
    assert [kind for kind, _value in events] == ["log", "prog", "plan", "stats", "done"]
    assert isinstance(events[2][1], output.FilePlanEvent)
    assert (events[2][1].source, events[2][1].target) == ("a", "b")
    assert events[-1] == ("done", 0)
    assert output.current_run_context() is saved_context


def test_gui_worker_receives_explicit_paths(monkeypatch, tmp_path):
    """Der GUI-Arbeitsthread übernimmt den Pfadwert des aufrufenden Kontexts."""
    from sortiton import config

    paths = config.production_paths(environ={"SORTITON_DATA_DIR": str(tmp_path)},
                                    home=tmp_path)
    monkeypatch.setattr(output, "open_log_file", lambda _title: None)
    monkeypatch.setattr(output, "close_log_file", lambda _rc: None)
    monkeypatch.setattr(journal, "close", lambda: None)
    app = SimpleNamespace(
        running=False, _cancel_scan=Mock(), _cancel_button=None,
        _begin_plan=Mock(), _signature=Mock(return_value=("signature",)),
        _set_buttons=Mock(), _render_preview=Mock(), progress=Mock(),
        progress_label=Mock(), _set_state=Mock(), status_var=Mock(),
        _log_line=Mock(), _log_rules=Mock(), queue=Queue())
    seen = Queue()

    def action(_args):
        seen.put(config.current_paths())
        return 0

    with config.use_paths(paths):
        assert RunMixin._start(app, "sort", "Sortieren", action,
                               SimpleNamespace(apply=False), ".")
    assert seen.get(timeout=5) == paths
    assert app.queue.get(timeout=5) == ("done", 0)


def test_run_stops_when_journal_cannot_be_opened(monkeypatch):
    class ImmediateThread:
        def __init__(self, target, daemon):
            self.target = target
            assert daemon

        def start(self):
            self.target()

    monkeypatch.setattr(gui_run.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(output, "open_log_file", lambda _title: None)
    monkeypatch.setattr(output, "close_log_file", lambda _rc: None)
    monkeypatch.setattr(journal, "enabled", lambda: True)
    monkeypatch.setattr(journal, "close", lambda: None)
    action = Mock()
    app = SimpleNamespace(
        running=False, _cancel_scan=Mock(), _cancel_button=None,
        _begin_plan=Mock(), _signature=Mock(return_value=("signature",)),
        _set_buttons=Mock(), _render_preview=Mock(), progress=Mock(),
        progress_label=Mock(), _set_state=Mock(), status_var=Mock(),
        _log_line=Mock(), _log_rules=Mock(), queue=Queue())
    assert RunMixin._start(app, "sort", "Sortieren", action,
                           SimpleNamespace(apply=True), ".")
    events = [app.queue.get_nowait() for _ in range(app.queue.qsize())]
    assert [kind for kind, _value in events] == ["log", "done"]
    assert events[-1] == ("done", 2)
    action.assert_not_called()


@pytest.mark.gui
def test_real_gui_receives_run_report(monkeypatch, tmp_path):
    import tkinter as tk

    from sortiton.gui.app import SortitonGUI

    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"gui/no display: {error}")
    monkeypatch.setattr(SortitonGUI, "_refresh_folder_stats", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(output, "open_log_file", lambda _title: None)
    monkeypatch.setattr(output, "close_log_file", lambda _rc: None)
    monkeypatch.setattr(journal, "close", lambda: None)
    gui = None
    try:
        gui = SortitonGUI(root)
        root.update_idletasks()

        def action(_args):
            output.message("Vorschau")
            output.report_plan("sort", source=str(tmp_path / "a.mp3"),
                               target=str(tmp_path / "b.mp3"))
            output.report_stats("sort", files=1, changed=1, errors=0, applied=False)
            return 0

        assert gui._start("sort", "Sortieren", action, SimpleNamespace(apply=False),
                          str(tmp_path), source=str(tmp_path), target_root=str(tmp_path))
        for _ in range(4):
            kind, value = gui.queue.get(timeout=5)
            gui._dispatch(kind, value)
        assert not gui.running
        assert gui._plans["sort"]["files"] == 1
        assert gui._preview_ready("sort")
        assert gui._last_result_values["changed"] == 1
    finally:
        root.destroy()
        del gui, root
        gc.collect()
