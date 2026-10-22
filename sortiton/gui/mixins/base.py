"""Shared members of the GUI mixins.

The window is assembled from five mixins (see :mod:`sortiton.gui.app`): each of
them reads state another one creates - variables, widgets, caches. A type
checker cannot see that, so the borrowed members are declared once here.
Nothing of this class exists at runtime; it only carries annotations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..common import (
    Path,
    PreviewCard,
    ProgressBar,
    ResultPanel,
    RoundButton,
    queue,
    tk,
)


class GuiBase:
    """Contract between the mixins that make up the main window."""

    if TYPE_CHECKING:
        # Window and worker plumbing, set up in SortitonGUI.__init__.
        root: tk.Tk
        queue: queue.Queue[Any]
        running: bool
        last_path: Path | None
        has_ffprobe: bool
        has_mutagen: bool

        # Variables, created once in SettingsMixin._make_vars so that they
        # survive a language switch.
        var_page: tk.StringVar
        var_language: tk.StringVar
        var_backup: tk.BooleanVar
        var_tool: dict[str, dict[str, tk.Variable]]
        var_tool_choice: tk.StringVar
        var_tags_folder: tk.StringVar
        var_tags_target: tk.StringVar
        var_tags_mode: tk.StringVar
        var_ren_folder: tk.StringVar
        var_ren_target: tk.StringVar
        var_ren_mode: tk.StringVar
        var_ren_pattern: tk.StringVar
        var_source: tk.StringVar
        var_target: tk.StringVar
        var_sort_mode: tk.StringVar
        var_sort_pattern: tk.StringVar
        var_all_source: tk.StringVar
        var_all_target: tk.StringVar
        var_all_mode: tk.StringVar
        var_all_pattern: tk.StringVar
        status_var: tk.StringVar

        # Widgets and caches built by LayoutMixin and LogMixin.
        pages: dict[str, tk.Frame]
        action_buttons: list[RoundButton]
        result_panel: ResultPanel
        progress: ProgressBar
        progress_label: tk.Label
        _result_area: tk.Frame
        _footer: tk.Frame
        _result_height: int
        _log_height: int
        _cancel_button: RoundButton | None
        _execute_buttons: dict[str, RoundButton]
        _stats_labels: dict[str, tk.Label]
        _preview_notes: dict[str, tk.Label]
        _previews: dict[str, PreviewCard]
        _plans: dict[str, dict]
        _traces: list[tuple[tk.Variable, str]]

        # Methods one mixin calls on another - the signatures have to match
        # the implementations, otherwise the override is reported as broken.
        def _build_all(self) -> None: ...
        def _build_footer(self) -> None: ...
        def _build_result_area(self) -> None: ...
        def _cancel_run(self) -> None: ...
        def _inputs_changed(self, *_args) -> None: ...
        def _llm_rules_import(self) -> None: ...
        def _log_line(self, line: str = "") -> None: ...
        def _log_rules(self, prefix: str) -> None: ...
        def _open_preferences(self) -> None: ...
        def _open_restore(self, preselect: Path | None = None) -> None: ...
        def _rebuild_result_header(self, backup: str = "",
                                   export_dir: str = "") -> None: ...
        def _refresh_folder_stats(self, page: str, manual: bool = True) -> None: ...
        def _refresh_recent(self) -> None: ...
        def _refresh_rules_card(self, warnings: int = 0) -> None: ...
        def _render_preview(self, page: str) -> None: ...
        def _render_stats(self, kind: str, values: dict) -> None: ...
        def _replay_log(self) -> None: ...
        def _rules_editor(self, prefill: str | None = None,
                          restored: bool = False) -> None: ...
        def _run_all(self, execute: bool) -> None: ...
        def _run_rename(self, execute: bool) -> None: ...
        def _run_restore(self, path: Path, keep_copies: bool) -> bool: ...
        def _run_sort(self, execute: bool) -> None: ...
        def _run_tags(self, write: bool) -> None: ...
        def _run_tools(self, execute: bool = False) -> None: ...
        def _set_state(self, colour: str) -> None: ...
        def _show_result_view(self) -> None: ...
        def _watch_inputs(self) -> None: ...
        def _xdg_open(self, path: Path) -> None: ...
