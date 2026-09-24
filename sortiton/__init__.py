"""Sortiton package: the logic behind the CLI and the GUI.

The names re-exported here are the stable public interface.
"""

from __future__ import annotations

# Single source of truth for the version: the release workflow checks it against
# the git tag, tools/build_app.sh puts it into the file names.
__version__ = "1.0.0"

from .config import (AUDIO_EXTENSIONS, BACKUP_DIR, FALLBACK_ARTIST, LOG_DIR, MAX_NAME_LENGTH,
                     MUTAGEN_AVAILABLE, PROJECT_DIR, RULES_FILE)
from .files import build_name, free_path, free_target, iter_audio, safe_name, same_content
from .journal import (find_journals, latest_journal, read_journal, resolve_journal,
                      summarize as summarize_journal)
from .output import (banner, close_log_file, last_stats, latest_log_file, message,
                     open_log_file, report_plan, report_stats, set_logger, set_plan_sink,
                     set_progress, set_stats_sink)
from .rules import (builtin_rules_text, clean_artist, clean_genre, clean_text_field,
                    load_custom_rules, rules_status, rules_summary, rules_template)
from .tags import probe_many, probe_tags, write_tags
from .tasks import (CmdArgs, cmd_all, cmd_rename, cmd_restore, cmd_rules, cmd_scan,
                    cmd_sort, cmd_tags)

__all__ = [
    "__version__",
    "AUDIO_EXTENSIONS",
    "BACKUP_DIR",
    "CmdArgs",
    "FALLBACK_ARTIST",
    "LOG_DIR",
    "MAX_NAME_LENGTH",
    "MUTAGEN_AVAILABLE",
    "PROJECT_DIR",
    "RULES_FILE",
    "banner",
    "build_name",
    "builtin_rules_text",
    "clean_artist",
    "clean_genre",
    "clean_text_field",
    "close_log_file",
    "cmd_all",
    "cmd_rename",
    "cmd_restore",
    "cmd_rules",
    "cmd_scan",
    "cmd_sort",
    "cmd_tags",
    "find_journals",
    "free_path",
    "free_target",
    "iter_audio",
    "last_stats",
    "latest_journal",
    "latest_log_file",
    "load_custom_rules",
    "message",
    "open_log_file",
    "probe_many",
    "probe_tags",
    "read_journal",
    "report_plan",
    "report_stats",
    "resolve_journal",
    "rules_status",
    "rules_summary",
    "rules_template",
    "safe_name",
    "same_content",
    "set_logger",
    "set_plan_sink",
    "set_progress",
    "set_stats_sink",
    "summarize_journal",
    "write_tags",
]
