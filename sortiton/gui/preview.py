"""Tk-freie Signaturen, Aggregation und Darstellung von Vorschauplänen."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..output import FilePlanEvent, PlanEvent, TagPlanEvent

PLAN_FIELDS = ("artist", "album_artist", "title", "album", "genre",
               "track", "disc", "year")


def signature(page: str, values: tuple, rules_id: tuple = ()) -> tuple:
    """Erzeuge dieselbe Signatur aus konkreten Formwerten wie die GUI."""
    if page == "tools":
        return ("tools", *values) if values else ("tools",)
    if page == "restore":
        return ("restore", str(values[0]))
    if page == "tags":
        return ("tags", values[0].strip(), values[1].strip(), *values[2:], rules_id)
    if page == "rename":
        return ("rename", values[0].strip(), values[1].strip(), values[2],
                values[3].strip(), rules_id)
    if page == "sort":
        return ("sort", values[0].strip(), values[1].strip(), values[2].strip(), values[3])
    return ("all", values[0].strip(), values[1].strip(), values[2].strip(),
            values[3], values[4], rules_id)


def begin_plan(page: str, source: str = "", target_root: str = "") -> dict:
    return {"kind": page, "files": 0, "changes_total": 0, "fields": {},
            "examples": [], "source": source, "target": target_root, "signature": None}


def absorb_plan(plan: dict | None, event: PlanEvent) -> None:
    if plan is None:
        return
    if event.kind == "tags":
        plan["kind"] = "tags"
        changes = (event.changes if isinstance(event, TagPlanEvent)
                   else event.data.get("changes")) or {}
        plan["files"] += 1
        plan["changes_total"] += len(changes)
        for field, pair in changes.items():
            entry = plan["fields"].setdefault(field, {"count": 0, "examples": []})
            entry["count"] += 1
            example = (pair[0], pair[1])
            if example not in entry["examples"]:
                entry["examples"].append(example)
        return
    if isinstance(event, FilePlanEvent):
        source, target = event.source, event.target
    else:
        source, target = event.data.get("source"), event.data.get("target")
    if source is None or target is None:
        return
    plan["files"] += 1
    if len(plan["examples"]) < 3:
        new = Path(target).name
        root = plan.get("target") or ""
        if root:
            try:
                new = str(Path(target).relative_to(root))
            except (ValueError, OSError):
                pass
        plan["examples"].append((Path(source).name, new))


def ready(plan: dict | None, current_signature: tuple) -> bool:
    return bool(plan and plan.get("signature") == current_signature)


def finish(plans: dict, page: str, job_signature: tuple | None,
           applied: bool, rc: int) -> None:
    plan = plans.get(page)
    if plan is not None:
        plan["signature"] = job_signature if rc == 0 and not applied else None
    if applied:
        for other_page, other in plans.items():
            if other_page != page:
                other["signature"] = None


@dataclass(frozen=True)
class PreviewView:
    state: str
    enabled: bool
    summary: str = ""
    rows: tuple = ()


def view(plan: dict | None, is_ready: bool, running: bool, active: bool,
         translate: Callable, format_number: Callable, pretty_path: Callable) -> PreviewView:
    enabled = is_ready and not running
    if plan is None:
        return PreviewView("none", enabled)
    if plan.get("signature") is None and running and active:
        return PreviewView("running", enabled)
    files = format_number(plan.get("files", 0))
    if plan.get("kind") == "tags":
        summary = translate("gui.preview.summary_tags",
                            changes=format_number(plan.get("changes_total", 0)), files=files)
    else:
        summary = translate("gui.preview.summary_files", files=files)
    rows = []
    if plan.get("kind") == "tags":
        for field in PLAN_FIELDS:
            entry = (plan.get("fields") or {}).get(field)
            if not entry or not entry["examples"]:
                continue
            old, new = entry["examples"][0]
            extra = (translate("gui.preview.more", count=entry["count"] - 1)
                     if entry["count"] > 1 else "")
            rows.append((translate("gui.field." + field), old, new, extra))
    else:
        examples = plan.get("examples") or []
        if examples:
            old, new = examples[0]
            extra = (translate("gui.preview.more", count=plan["files"] - 1)
                     if plan["files"] > 1 else "")
            rows.append((translate("gui.field.file"), old, new, extra))
    if plan.get("target"):
        rows.append((translate("gui.field.folder"), pretty_path(plan.get("source", "")),
                     pretty_path(plan.get("target", "")), ""))
    return PreviewView("ready" if is_ready else "stale", enabled, summary, tuple(rows))
