"""Vertrag der Tk-freien Vorschau."""

import pytest

from sortiton.gui import preview
from sortiton.output import FilePlanEvent, TagPlanEvent


@pytest.mark.parametrize(("page", "values", "expected"), [
    ("tags", (" a ", " b ", "copy", "02"), ("tags", "a", "b", "copy", "02", ("rules",))),
    ("rename", (" a ", " b ", "move", " %title% "),
     ("rename", "a", "b", "move", "%title%", ("rules",))),
    ("sort", (" a ", " b ", "  ", "copy"), ("sort", "a", "b", "", "copy")),
    ("all", (" a ", " b ", " %title% ", "copy", "02"),
     ("all", "a", "b", "%title%", "copy", "02", ("rules",))),
    ("tools", ("fixes", (("path", " x "),)), ("tools", "fixes", (("path", " x "),))),
    ("tools", (), ("tools",)),
    ("restore", (" x ",), ("restore", " x ")),
])
def test_signature(page, values, expected):
    assert preview.signature(page, values, ("rules",)) == expected


def test_plan_aggregation_and_rows():
    plan = preview.begin_plan("all", "/source", "/target")
    first = {"title": ("alt", "neu")}
    second = {"title": ("alt", "neu"), "artist": ("a", "b")}
    preview.absorb_plan(plan, TagPlanEvent("tags", {"path": "a", "changes": first}, "a", first))
    preview.absorb_plan(plan, TagPlanEvent("tags", {"path": "b", "changes": second}, "b", second))
    for index in range(4):
        source, target = f"/source/{index}.mp3", f"/target/album/{index}.mp3"
        preview.absorb_plan(plan, FilePlanEvent("sort", {"source": source, "target": target},
                                               source, target))
    assert plan["files"] == 6
    assert plan["changes_total"] == 3
    assert len(plan["examples"]) == 3
    assert plan["examples"][0] == ("0.mp3", "album/0.mp3")
    assert plan["fields"]["title"]["examples"] == [("alt", "neu")]
    result = preview.view(plan, False, False, False,
                          lambda key, **_kwargs: key, str, str)
    assert result.state == "stale"
    assert [row[0] for row in result.rows] == ["gui.field.artist", "gui.field.title",
                                                 "gui.field.folder"]


@pytest.mark.parametrize("rc", [0, 1, 130, 99])
@pytest.mark.parametrize("applied", [False, True])
def test_finish_preserves_preview_invalidation(rc, applied):
    plans = {"tags": preview.begin_plan("tags"), "sort": preview.begin_plan("sort")}
    plans["sort"]["signature"] = ("old",)
    preview.finish(plans, "tags", ("start",), applied, rc)
    assert plans["tags"]["signature"] == (("start",) if rc == 0 and not applied else None)
    assert plans["sort"]["signature"] == (None if applied else ("old",))
    assert preview.ready(plans["tags"], ("changed",)) is False
