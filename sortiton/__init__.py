"""Sortiton package: the logic behind the CLI and the GUI."""

from __future__ import annotations

from pathlib import Path

__version__ = "1.0.0"

BACKUP_DIR: Path
LOG_DIR: Path
PROJECT_DIR: Path
RULES_FILE: Path

from . import config
from .config import AUDIO_EXTENSIONS, FALLBACK_ARTIST, MAX_NAME_LENGTH, MUTAGEN_AVAILABLE
from .files import build_name, free_path, free_target, iter_audio, safe_name, same_content
from .journal import (find_journals, latest_journal, read_journal, resolve_journal,
                      summarize as summarize_journal)
from .output import (FilePlanEvent, PlanEvent, RunContext, RunReport, TagPlanEvent,
                     banner, close_log_file, current_run_context, latest_log_file,
                     message, open_log_file, progress, report_plan, report_stats,
                     require_run_context, submit_with_context, use_run_context)
from .rules import (builtin_rules_text, clean_artist, clean_genre, clean_text_field,
                    load_custom_rules, rules_status, rules_summary, rules_template)
from .tags import probe_many, probe_tags, write_tags
from .tasks import (CmdArgs, cmd_all, cmd_rename, cmd_restore, cmd_rules, cmd_scan,
                    cmd_sort, cmd_tags)
from .features.export import cmd_export
from .features.fixes import cmd_fixes

def __getattr__(name: str):
    """Frühere Pfadexporte dynamisch aus der aktiven Konfiguration beziehen."""
    if name in {"BACKUP_DIR", "LOG_DIR", "PROJECT_DIR", "RULES_FILE"}:
        return getattr(config, name)
    raise AttributeError(name)


__all__ = [
    "__version__",
    "AUDIO_EXTENSIONS",
    "BACKUP_DIR",
    "CmdArgs",
    "FALLBACK_ARTIST",
    "FilePlanEvent",
    "LOG_DIR",
    "MAX_NAME_LENGTH",
    "MUTAGEN_AVAILABLE",
    "PROJECT_DIR",
    "PlanEvent",
    "RULES_FILE",
    "RunContext",
    "RunReport",
    "TagPlanEvent",
    "banner",
    "build_name",
    "builtin_rules_text",
    "clean_artist",
    "clean_genre",
    "clean_text_field",
    "close_log_file",
    "cmd_all",
    "cmd_export",
    "cmd_fixes",
    "cmd_rename",
    "cmd_restore",
    "cmd_rules",
    "cmd_scan",
    "cmd_sort",
    "cmd_tags",
    "current_run_context",
    "find_journals",
    "free_path",
    "free_target",
    "iter_audio",
    "latest_journal",
    "latest_log_file",
    "load_custom_rules",
    "message",
    "open_log_file",
    "probe_many",
    "probe_tags",
    "progress",
    "read_journal",
    "report_plan",
    "report_stats",
    "require_run_context",
    "resolve_journal",
    "rules_status",
    "rules_summary",
    "rules_template",
    "safe_name",
    "same_content",
    "submit_with_context",
    "summarize_journal",
    "use_run_context",
    "write_tags",
]
