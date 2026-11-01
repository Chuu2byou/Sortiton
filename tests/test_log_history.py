"""Protokollverlauf ohne GUI testen."""

from sortiton.gui.log_history import LogHistory, line_marker


def test_log_history_retention_and_clear():
    history = LogHistory()
    for index in range(2000):
        history.append(str(index))
    assert len(history.lines()) == 2000
    history.append("2000")
    assert history.lines() == [str(index) for index in range(1000, 2001)]
    snapshot = history.lines()
    snapshot.clear()
    assert len(history.lines()) == 1001
    history.clear()
    assert history.lines() == []


def test_log_marker_precedence():
    assert line_marker("ERROR OK: PREVIEW") == "err"
    assert line_marker("Fertig. ->") == "ok"
    assert line_marker("VORSCHAU") == "info"
    assert line_marker("normal") is None
