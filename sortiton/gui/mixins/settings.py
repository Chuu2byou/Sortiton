"""Variables, fine-tuning and the settings window."""

from __future__ import annotations

from ..common import (
    DEFAULT_FOLDER,
    FEATURES,
    PATTERN_DEFAULT,
    PreferencesWindow,
    TARGET_FOLDER,
    _show_warning,
    apply_stored,
    fine_tuning_items,
    i18n,
    make_tool_vars,
    settings,
    stored_values,
    tk,
)


class SettingsMixin:
    """Variables, fine-tuning and the settings window."""

    def _make_vars(self) -> None:
        """Create every StringVar once - they survive a language switch."""
        self.var_tags_folder = tk.StringVar(value=str(DEFAULT_FOLDER))
        self.var_ren_folder = tk.StringVar(value=str(DEFAULT_FOLDER))
        self.var_ren_pattern = tk.StringVar(value=PATTERN_DEFAULT)
        self.var_source = tk.StringVar(value=str(DEFAULT_FOLDER))
        self.var_target = tk.StringVar(value=str(TARGET_FOLDER))
        self.var_sort_pattern = tk.StringVar(value=PATTERN_DEFAULT)
        self.var_sort_mode = tk.StringVar(value="copy")
        self.var_all_source = tk.StringVar(value=str(DEFAULT_FOLDER))
        self.var_all_target = tk.StringVar(value=str(TARGET_FOLDER))
        self.var_all_pattern = tk.StringVar(value=PATTERN_DEFAULT)
        self.var_all_mode = tk.StringVar(value="copy")
        self.var_page = tk.StringVar(value="tags")
        self.var_language = tk.StringVar(value=i18n.get_language())
        self.var_backup = tk.BooleanVar(value=settings.resolve_backup())
        # Tools tab: the feature picker and one variable per feature option.
        # Created here, not in the page builders, so a language switch keeps
        # every value the user typed.
        self.var_tool = make_tool_vars()
        self.var_tool_choice = tk.StringVar(value=FEATURES[0].key if FEATURES else "")
        self.status_var = tk.StringVar(value="")
        self._seed_tool_folders()
        # Fine-tuning lives in the settings window but in these variables: load
        # the stored values once and write them back whenever they change.
        apply_stored(self.var_tool)
        self._watch_fine_tuning()

    def _seed_tool_folders(self) -> None:
        """Prefill empty tool folders with the music folder - that is the usual case."""
        for feature in FEATURES:
            for option in feature.options:
                if option.kind != "folder" or option.name not in ("folder", "target"):
                    continue
                variable = self.var_tool[feature.key][option.name]
                if not str(variable.get()).strip():
                    variable.set(str(DEFAULT_FOLDER))

    def _watch_fine_tuning(self) -> None:
        """Store fine-tuning changes in settings.ini (debounced to one write).

        The traces live outside ``self._traces``: that list is rebuilt for the
        preview invalidation on every language switch, these must survive.
        """
        for feature, option in fine_tuning_items():
            self.var_tool[feature.key][option.name].trace_add("write",
                                                              self._fine_tuning_changed)

    def _fine_tuning_changed(self, *_args) -> None:
        """Wait a moment before writing - a spinbox fires on every digit."""
        if self._fine_tuning_job is not None:
            try:
                self.root.after_cancel(self._fine_tuning_job)
            except tk.TclError:
                pass
        self._fine_tuning_job = self.root.after(400, self._save_fine_tuning)

    def _save_fine_tuning(self) -> None:
        """Write the current fine-tuning values to the [tools] section."""
        if self._fine_tuning_job is not None:
            try:
                self.root.after_cancel(self._fine_tuning_job)
            except tk.TclError:
                pass
        self._fine_tuning_job = None
        settings.save_tool_values(stored_values(self.var_tool))

    def _open_preferences(self) -> None:
        """Open the settings window (or raise it when it is already open)."""
        if self._prefs_window is not None:
            try:
                if self._prefs_window.window.winfo_exists():
                    self._prefs_window.window.lift()
                    self._prefs_window.window.focus_set()
                    return
            except tk.TclError:
                pass
            self._prefs_window = None

        # The window edits the same variables the tools tab reads, so it only
        # needs the app - not a copy of the language handler or the form vars.
        self._prefs_window = PreferencesWindow(self)
        self._prefs_window.window.bind("<Destroy>", self._prefs_closed, add="+")

    def _prefs_closed(self, event) -> None:
        """Forget the window once it is closed (so it can be reopened)."""
        if self._prefs_window is not None and event.widget is self._prefs_window.window:
            self._prefs_window = None

    def _language_changed(self, code: str) -> None:
        """Switch the interface language and rebuild the window."""
        if self.running:
            _show_warning(i18n.t("gui.dialog.busy.title"), i18n.t("gui.dialog.busy.text"))
            self.var_language.set(i18n.get_language())
            return
        reopen = self._prefs_window is not None
        if reopen and self._prefs_window is not None:
            try:
                self._prefs_window.window.destroy()
            except tk.TclError:
                pass
            self._prefs_window = None
        i18n.set_language(code)
        settings.save_language(code)
        self._build_all()
        if reopen:
            self._open_preferences()
