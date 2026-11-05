"""Variables, fine-tuning and the settings window."""

from __future__ import annotations

from pathlib import Path
import os
import tkinter as tk

from ... import config, settings
from .. import translations as i18n
from ...core_features import CORE_FEATURES, PATTERN_DEFAULT
from ...features import FEATURES
from ...paths import check_core_paths
from .. import design
from ..dialogs import _show_warning
from ..preferences import PreferencesWindow
from ..tools import apply_stored, fine_tuning_items, make_tool_vars, stored_values
from .base import GuiBase


class SettingsMixin(GuiBase):
    """Variables, fine-tuning and the settings window."""

    def _make_vars(self) -> None:
        """Create every StringVar once - they survive a language switch."""
        folders = settings.restore_folder_values(config.current_paths())
        self.var_tags_folder = tk.StringVar(value=folders["tags_source"])
        self.var_tags_target = tk.StringVar(value=folders["tags_target"])
        self.var_tags_mode = tk.StringVar(value="copy")
        self.var_ren_folder = tk.StringVar(value=folders["rename_source"])
        self.var_ren_target = tk.StringVar(value=folders["rename_target"])
        self.var_ren_pattern = tk.StringVar(value=PATTERN_DEFAULT)
        self.var_ren_mode = tk.StringVar(value="copy")
        self.var_source = tk.StringVar(value=folders["sort_source"])
        self.var_target = tk.StringVar(value=folders["sort_target"])
        self.var_sort_pattern = tk.StringVar(value=PATTERN_DEFAULT)
        self.var_sort_mode = tk.StringVar(value="copy")
        self.var_all_source = tk.StringVar(value=folders["all_source"])
        self.var_all_target = tk.StringVar(value=folders["all_target"])
        self.var_all_pattern = tk.StringVar(value=PATTERN_DEFAULT)
        self.var_all_mode = tk.StringVar(value="copy")
        self.var_page = tk.StringVar(value="tags")
        self.var_language = tk.StringVar(value=i18n.get_language())
        self.var_backup = tk.BooleanVar(value=settings.resolve_backup())
        self.var_track_format = tk.StringVar(value=settings.resolve_track_format())
        self.var_tool = make_tool_vars()
        self.var_tool_choice = tk.StringVar(value=FEATURES[0].key if FEATURES else "")
        self.status_var = i18n.StringVar(master=self.root, value="")
        self._seed_tool_folders()
        self._restore_tool_folders()
        apply_stored(self.var_tool)
        self._watch_fine_tuning()
        self._folder_save_job = None
        for feature in CORE_FEATURES:
            for name in (feature.source_var, feature.target_var):
                getattr(self, name).trace_add("write", self._folders_changed)
        for feature in FEATURES:
            for option in feature.options:
                if option.kind == "folder":
                    self.var_tool[feature.key][option.name].trace_add("write", self._folders_changed)

    def _folders_changed(self, *_args) -> None:
        """Texteingaben gebündelt speichern statt bei jedem Tastendruck."""
        if self._folder_save_job is not None:
            self.root.after_cancel(self._folder_save_job)
        self._folder_save_job = self.root.after(400, self._save_folders)

    def _save_folders(self) -> None:
        """Alle Seitenpfade dauerhaft sichern."""
        if self._folder_save_job is not None:
            self.root.after_cancel(self._folder_save_job)
            self._folder_save_job = None
        values = {}
        for feature in CORE_FEATURES:
            for kind, name in (("source", feature.source_var), ("target", feature.target_var)):
                values[f"{feature.key}_{kind}"] = getattr(self, name).get().strip()
        for feature in FEATURES:
            for option in feature.options:
                if option.kind == "folder":
                    values[f"tool_{feature.key}_{option.name}"] = str(
                        self.var_tool[feature.key][option.name].get()).strip()
        for key, value in values.items():
            try:
                values[key] = str(Path(value).expanduser().absolute()) if value else ""
            except (OSError, RuntimeError, ValueError):
                pass
        settings.save_folder_values(values)

    def _restore_tool_folders(self) -> None:
        """Werkzeugordner aus den Einstellungen anhand ihrer Rollen laden."""
        stored = settings.read_folder_values()
        for feature in FEATURES:
            for option in feature.options:
                if option.path_role != "source_folder":
                    continue
                key = f"tool_{feature.key}_{option.name}"
                if key not in stored or (option.positional and os.environ.get("SORTITON_FOLDER", "").strip()):
                    continue
                value = stored[key].strip()
                try:
                    valid = not value or Path(value).expanduser().is_dir()
                except (OSError, RuntimeError, ValueError):
                    valid = False
                if valid:
                    self.var_tool[feature.key][option.name].set(value)
            sources = [self.var_tool[feature.key][option.name].get()
                       for option in feature.options if option.path_role == "source_folder"]
            for option in feature.options:
                if option.path_role != "output_folder":
                    continue
                key = f"tool_{feature.key}_{option.name}"
                if key not in stored:
                    continue
                value = stored[key].strip()
                if value and feature.output_outside_source:
                    if not sources or check_core_paths(sources[0], value).problem is not None:
                        value = ""
                self.var_tool[feature.key][option.name].set(value)

    def _seed_tool_folders(self) -> None:
        """Prefill empty tool folders with the music folder - that is the usual case."""
        for feature in FEATURES:
            for option in feature.options:
                if option.path_role != "source_folder" or not option.positional:
                    continue
                variable = self.var_tool[feature.key][option.name]
                if not str(variable.get()).strip():
                    variable.set(str(config.current_paths().music_source_dir))

    def _watch_fine_tuning(self) -> None:
        """Store fine-tuning changes in settings.ini (debounced to one write)."""
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

        self._prefs_window = PreferencesWindow(self)
        self._prefs_window.window.bind("<Destroy>", self._prefs_closed, add="+")

    def _prefs_closed(self, event) -> None:
        """Forget the window once it is closed (so it can be reopened)."""
        if self._prefs_window is not None and event.widget is self._prefs_window.window:
            self._prefs_window = None

    def _language_changed(self, code: str) -> None:
        """Sprache speichern und bestehende Oberflächen benachrichtigen."""
        if self.running:
            _show_warning(i18n.t("gui.dialog.busy.title"), i18n.t("gui.dialog.busy.text"))
            self.var_language.set(i18n.get_language())
            return
        i18n.set_language(code)
        settings.save_language(code)
        i18n.notify(self.root)
        for page in self.pages:
            self._render_preview(page)

    def _theme_changed(self, mode: str) -> None:
        """Apply the selected appearance immediately by rebuilding the GUI."""
        if self.running:
            _show_warning(i18n.t("gui.dialog.busy.title"), i18n.t("gui.dialog.busy.text"))
            if self._prefs_window is not None:
                self._prefs_window._theme_variable.set(settings.resolve_theme())
            return
        reopen = self._prefs_window is not None
        settings.save_theme(mode)
        design.apply_theme(mode)
        self._build_all()
        if reopen:
            self._open_preferences()

    def _track_format_changed(self, code: str) -> None:
        """Remember the track/disc format and invalidate an old preview."""
        settings.save_track_format(code)
        self._inputs_changed()
