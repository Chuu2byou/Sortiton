"""Window and tasks of the graphical interface."""

from __future__ import annotations

from .common import (
    CancelToken,
    Path,
    PreferencesWindow,
    PreviewCard,
    RoundButton,
    _LOG_HEIGHT_BASE,
    _RESULT_HEIGHT_BASE,
    _ask_yes_no,
    _fmt_duration,
    _fmt_number,
    _pretty_path,
    config,
    design,
    i18n,
    output,
    queue,
    settings,
    shutil,
    tk,
)

from .mixins.layout import LayoutMixin
from .mixins.log import LogMixin
from .mixins.run import RunMixin
from .mixins.rules import RulesMixin
from .mixins.settings import SettingsMixin


class SortitonGUI(LayoutMixin, LogMixin, RunMixin, RulesMixin, SettingsMixin):
    """Main window of Sortiton."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.queue: queue.Queue = queue.Queue()
        self.running = False
        self.last_path: Path | None = None
        self.action_buttons: list[RoundButton] = []
        self._tools_buttons: list[RoundButton] = []
        self._cancel: CancelToken | None = None
        self._cancel_button: RoundButton | None = None
        self._icon_large: tk.PhotoImage | None = None
        self._rules_window: tk.Toplevel | None = None
        self._rules_text: tk.Text | None = None
        self._rules_status: tk.StringVar | None = None
        self._rules_status_label: tk.Label | None = None
        self._llm_window: tk.Toplevel | None = None
        self._llm_text: tk.Text | None = None
        self._llm_status: tk.StringVar | None = None
        self._llm_status_label: tk.Label | None = None
        self._restore_window: tk.Toplevel | None = None
        self._log_history: list[str] = []
        self._log_lines = 0
        self.pages: dict[str, tk.Frame] = {}

        self._plans: dict[str, dict] = {}
        self._execute_buttons: dict[str, RoundButton] = {}
        self._preview_notes: dict[str, tk.Label] = {}
        self._previews: dict[str, PreviewCard] = {}
        self._stats_labels: dict[str, tk.Label] = {}
        self._tool_widgets: dict[tuple[str, str], tk.Widget] = {}
        self._traces: list[tuple[tk.Variable, str]] = []
        self._fine_tuning_job: str | None = None
        self._job_page = "tags"
        self._dirty = False
        self._scan_page: str | None = None
        self._log_shown = False
        self._prefs_window: PreferencesWindow | None = None
        self._backup_for_run = True
        self._placed = False
        self._closing = False

        self.has_ffprobe = shutil.which("ffprobe") is not None
        self.has_mutagen = config.MUTAGEN_AVAILABLE

        design.configure(root)
        design.load_fonts(root)
        self._apply_scale()
        self._make_vars()
        self._install_output_hooks()
        self.root.bind("<Configure>", self._align_fixed_rows, add="+")
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        self._build_all()
        self._queue_pump()
        self._log_rules(i18n.t("gui.rules.prefix"))
        if not self.has_ffprobe:
            self._log_line(i18n.t("gui.log.ffprobe_missing"))
        self._refresh_folder_stats("tags", manual=False)

    def _apply_scale(self) -> None:
        """Scale the layout heights once the screen scale is known."""
        self._result_height = design.px(_RESULT_HEIGHT_BASE)
        self._log_height = design.px(_LOG_HEIGHT_BASE)

    def _install_output_hooks(self) -> None:
        """Route everything the tasks report into the queue."""
        output.set_logger(lambda text: self.queue.put(("log", text)))
        output.set_progress(lambda i, n, text: self.queue.put(("prog", (i, n, text))))
        output.set_plan_sink(lambda kind, data: self.queue.put(("plan", (kind, data))))
        output.set_stats_sink(lambda kind, values: self.queue.put(("stats", (kind, values))))


def main() -> int:
    settings.apply_language()
    root = tk.Tk()
    SortitonGUI(root)
    root.mainloop()
    return 0
