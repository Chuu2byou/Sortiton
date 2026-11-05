"""Running tasks: plans, previews, workers, progress and closing."""

from __future__ import annotations

from pathlib import Path
import functools
import queue
import threading
import time
import tkinter as tk
import traceback
from types import SimpleNamespace

from ... import config, journal, output, rules, settings
from .. import translations as i18n
from ...cancel import CancelToken, Cancelled
from ...core_features import CORE_FEATURES, PATTERN_DEFAULT, core_feature
from ...paths import PathProblem, check_core_paths
from ...features import get as feature_by_key
from ...files import target_inside_source
from ...tasks import cmd_all, cmd_rename, cmd_restore, cmd_scan, cmd_sort, cmd_tags
from .. import preview
from ..common import _fmt_number, _pretty_path
from ..confirm import ask_confirm
from ..design import GREEN, RED, TEXT_FAINT, TEXT_MUTED, YELLOW
from ..dialogs import _ask_yes_no, _show_error, _show_warning
from ..tools import tool_value
from .base import GuiBase


def _single_operation(method):
    """Run one action at a time, also while its confirmation window is open.

    A focused button keeps its keyboard binding while a modal confirmation is
    shown. Without this guard, repeated Enter/Return presses could stack
    confirmations and start the same write several times.
    """
    @functools.wraps(method)
    def guarded(self, *args, **kwargs):
        if self.running or self._operation_pending:
            return None
        self._operation_pending = True
        try:
            return method(self, *args, **kwargs)
        finally:
            self._operation_pending = False

    return guarded


class RunMixin(GuiBase):
    """Running tasks: plans, previews, workers, progress and closing."""

    _FORCE_CLOSE_AFTER = 10.0

    @_single_operation
    def _run_restore(self, path: Path, keep_copies: bool) -> bool:
        """Undo the given journal - the dialog has confirmed everything."""
        settings.save_backup(self.var_backup.get())
        return self._start("restore", self._job_name("gui.job.restore", True),
                           cmd_restore,
                           SimpleNamespace(journal=str(path), apply=True,
                                           backup=self.var_backup.get(),
                                           keep_copies=keep_copies),
                           Path(path).parent, source=str(path))

    def _run_core(self, page: str, execute: bool) -> None:
        """Starte einen Kernauftrag anhand seiner gemeinsamen Beschreibung."""
        feature = core_feature(page)
        source = getattr(self, feature.source_var).get().strip()
        target = getattr(self, feature.target_var).get().strip()
        move = getattr(self, feature.mode_var).get() == "move"
        if not self._core_paths_ok(page, source, target, move):
            return
        pattern = (getattr(self, feature.pattern_var).get().strip() or PATTERN_DEFAULT
                   if feature.pattern_var else "")
        if execute and not self._preview_allowed(page):
            return
        confirmation = {"folder": source, "target": target}
        if page == "rename":
            confirmation["pattern"] = pattern
        if page in ("rename", "sort"):
            confirmation["allow_backup"] = False
        if execute and not self._confirm_write(page, **confirmation):
            return
        source_option = next(option.name for option in feature.options
                             if option.path_role == "source_folder")
        values = {source_option: source, "target": target or None,
                  "move": move, "apply": execute}
        if feature.pattern_var:
            values["pattern"] = pattern
        if page in ("tags", "all"):
            values.update(backup=self._backup_for_run,
                          track_format=self.var_track_format.get())
        command = {"tags": cmd_tags, "rename": cmd_rename,
                   "sort": cmd_sort, "all": cmd_all}[page]
        location = target if page == "sort" else source
        self._start(page, self._job_name(f"gui.job.{page}", execute), command,
                    SimpleNamespace(**values), location, source=source, target_root=target)

    @_single_operation
    def _run_tags(self, write: bool) -> None:
        self._run_core("tags", write)

    @_single_operation
    def _run_rename(self, execute: bool) -> None:
        self._run_core("rename", execute)

    @_single_operation
    def _run_sort(self, execute: bool) -> None:
        self._run_core("sort", execute)

    @_single_operation
    def _run_all(self, execute: bool) -> None:
        self._run_core("all", execute)

    def _preview_allowed(self, page: str) -> bool:
        """A write needs a preview of exactly the inputs the form has now."""
        if self._preview_ready(page):
            return True
        _show_warning(i18n.t("gui.dialog.preview_stale.title"),
                      i18n.t("gui.dialog.preview_stale.text"))
        return False

    def _tool_args(self, feature, execute: bool = False) -> SimpleNamespace:
        """Read the tools form back into the namespace the feature expects."""
        values = {option.name: tool_value(option, self.var_tool[feature.key][option.name])
                  for option in feature.options}
        if any(option.name == "apply" for option in feature.options):
            values["apply"] = execute
        if any(option.name == "backup" for option in feature.options):
            values["backup"] = self.var_backup.get()
        if any(option.name == "confirm" for option in feature.options):
            values["confirm"] = execute
        return SimpleNamespace(**values)

    @_single_operation
    def _run_tools(self, execute: bool = False) -> None:
        """Start the selected tool: read-only runs directly, writing runs ask."""
        feature = feature_by_key(self.var_tool_choice.get())
        if feature is None:
            return
        args = self._tool_args(feature, execute)

        location = ""
        source = ""
        target = ""
        for option in feature.options:
            if not option.path_role:
                continue
            value = str(getattr(args, option.name, "") or "").strip()
            if option.path_role == "source_folder":
                if (value or option.positional) and not self._path_ok(value):
                    return
                if value:
                    source = location = value
            elif option.path_role == "input_file":
                if not value or not Path(value).expanduser().is_file():
                    _show_error(i18n.t("gui.dialog.file_not_found.title"),
                                i18n.t("gui.dialog.file_not_found.text", path=value))
                    return
                if not location:
                    location = str(Path(value).expanduser().parent)
            elif option.path_role == "output_folder":
                target = value
        if feature.output_outside_source and target:
            result = check_core_paths(source, target, target_required=True)
            if not self._show_core_path_problem(result, source, target):
                return
        if not location:
            _show_warning(i18n.t("gui.dialog.folder_missing.title"),
                          i18n.t("gui.dialog.folder_missing.text"))
            return

        if feature.writes and execute and not self._confirm_tool_write(feature):
            return
        if any(option.name == "backup" for option in feature.options):
            args.backup = self._backup_for_run
        last = config.EXPORT_DIR if feature.key == "export" else location
        description = (self._job_name(f"gui.job.{feature.key}", execute)
                       if feature.writes else
                       i18n.t("gui.job.run", name=i18n.t(f"gui.job.{feature.key}")))
        self._start("tools", description, feature.run, args, last, source=location)

    def _job_name(self, key: str, execute: bool) -> str:
        name = i18n.t(key)
        return i18n.t("gui.job.run", name=name) if execute else i18n.t("gui.job.preview",
                                                                       name=name)

    def _mode_text(self, page: str) -> str:
        feature = next((item for item in CORE_FEATURES if item.key == page), None)
        variable = getattr(self, feature.mode_var) if feature else self.var_sort_mode
        return (i18n.t("gui.mode.move") if variable.get() == "move"
                else i18n.t("gui.mode.copy"))

    def _confirm_write(self, page: str, *, allow_backup: bool = True,
                       **fields) -> bool:
        """Confirmation with the counts of the preview and the backup switch."""
        plan = self._plans.get(page) or {}
        text = self._confirm_text(page, files=_fmt_number(plan.get("files", 0)),
                                  changes=_fmt_number(plan.get("changes_total", 0)),
                                  **fields)
        options = ([("backup", i18n.t("gui.confirm.backup"), self.var_backup.get())]
                   if allow_backup else None)
        confirmed, options = ask_confirm(
            self.root,
            title=i18n.t("gui.confirm." + page + ".title"),
            heading=i18n.t("gui.confirm." + page + ".title"),
            text=text,
            note=i18n.t("gui.confirm.note"),
            ok_text=i18n.t("gui.confirm.ok"),
            cancel_text=i18n.t("gui.button.cancel"),
            options=options)
        if confirmed and allow_backup:
            self.var_backup.set(options.get("backup", True))
            settings.save_backup(self.var_backup.get())
        self._backup_for_run = self.var_backup.get()
        return confirmed

    def _confirm_tool_write(self, feature) -> bool:
        """Confirmation before a writing tool runs."""
        if feature.key == "dedupe":
            return self._confirm_dedupe()
        has_backup = any(option.name == "backup" for option in feature.options)
        return self._confirm_write("tools", allow_backup=has_backup)

    def _confirm_dedupe(self) -> bool:
        """Confirmation for moving duplicates: no backup switch, never deletes."""
        plan = self._plans.get("tools") or {}
        confirmed, _options = ask_confirm(
            self.root,
            title=i18n.t("gui.confirm.dedupe.title"),
            heading=i18n.t("gui.confirm.dedupe.title"),
            text=i18n.t("gui.confirm.dedupe.text",
                        files=_fmt_number(plan.get("files", 0)),
                        folder=_pretty_path(plan.get("source", ""))),
            note=i18n.t("gui.confirm.note"),
            ok_text=i18n.t("gui.confirm.ok"),
            cancel_text=i18n.t("gui.button.cancel"))
        return confirmed

    def _confirm_text(self, page: str, *, files: str, changes: str, **fields) -> str:
        if page == "tags":
            text = i18n.t("gui.confirm.tags.text", changes=changes, files=files)
            if fields.get("target"):
                text += f"\n\n{_pretty_path(fields.get('target', ''))} ({self._mode_text('tags')})"
            return text
        if page == "rename":
            text = i18n.t("gui.confirm.rename.text", files=files,
                          pattern=fields.get("pattern", ""))
            if fields.get("target"):
                text += f"\n\n{_pretty_path(fields.get('target', ''))} ({self._mode_text('rename')})"
            return text
        if page == "sort":
            return i18n.t("gui.confirm.sort.text", files=files,
                          mode=self._mode_text("sort"),
                          target=_pretty_path(fields.get("target", "")))
        if page == "tools":
            return i18n.t("gui.confirm.tools.text", changes=changes, files=files)
        return i18n.t("gui.confirm.all.text", files=files, mode=self._mode_text("all"),
                      target=_pretty_path(fields.get("target", "")))

    def _begin_plan(self, page: str, source: str = "",
                    target_root: str = "") -> None:
        self._plans[page] = preview.begin_plan(page, source, target_root)

    def _absorb_plan(self, event: output.PlanEvent) -> None:
        preview.absorb_plan(self._plans.get(self._job_page), event)

    def _watch_inputs(self) -> None:
        """Invalidate a preview as soon as one of its inputs changes."""
        for feature in CORE_FEATURES:
            names = (feature.source_var, feature.target_var, feature.mode_var,
                     feature.pattern_var)
            for name in filter(None, names):
                variable = getattr(self, name)
                self._traces.append((variable,
                                     variable.trace_add("write", self._inputs_changed)))
        self._traces.append((self.var_track_format,
                             self.var_track_format.trace_add("write", self._inputs_changed)))
        for option_vars in self.var_tool.values():
            for variable in option_vars.values():
                self._traces.append((variable,
                                     variable.trace_add("write", self._inputs_changed)))

    def _rules_fingerprint(self) -> str:
        """Cheap check whether my_rules.ini changed since the preview."""
        try:
            stat = config.RULES_FILE.stat()
            return f"{stat.st_mtime_ns}:{stat.st_size}"
        except OSError:
            return "-"

    def _signature(self, page: str) -> tuple:
        rules_id = (self._rules_fingerprint(), rules.rules_status()["custom_total"])
        if page in {feature.key for feature in CORE_FEATURES}:
            feature = core_feature(page)
            names = (feature.source_var, feature.target_var, feature.mode_var,
                     feature.pattern_var)
            values = tuple(getattr(self, name).get() for name in names if name)
            if any(option.name == "track_format" for option in feature.options):
                values += (self.var_track_format.get(),)
        elif page == "tools":
            feature = feature_by_key(self.var_tool_choice.get())
            if feature is None:
                values = ()
            else:
                options = tuple((option.name, self.var_tool[feature.key][option.name].get())
                                for option in feature.options)
                values = (feature.key, options)
        elif page == "restore":
            values = ((self._plans.get("restore") or {}).get("source", ""),)
        else:
            values = ()
        return preview.signature(page, values, rules_id)

    def _preview_ready(self, page: str) -> bool:
        plan = self._plans.get(page)
        return bool(plan and preview.ready(plan, self._signature(page)))

    def _inputs_changed(self, *_args) -> None:
        if self._dirty:
            return
        self._dirty = True
        self.root.after(120, self._refresh_preview_states)

    def _refresh_preview_states(self) -> None:
        self._dirty = False
        for page in self.pages:
            self._render_preview(page)

    def _render_preview(self, page: str) -> None:
        """Zeige den Plan und schalte die zugehörige Aktion frei."""
        card = self._previews.get(page)
        if card is None:
            return
        button = self._execute_buttons.get(page)
        note = self._preview_notes.get(page)
        state = preview.view(self._plans.get(page), self._preview_ready(page),
                             self.running, page == self._job_page,
                             i18n.t, _fmt_number, _pretty_path)
        if button is not None:
            button.set_enabled(state.enabled)
        if state.state == "none":
            card.hint(i18n.t("gui.preview.none"))
            if note is not None:
                note.configure(text=i18n.t("gui.preview.run_first"), fg=TEXT_FAINT)
                self.root.after_idle(self._fit_top_bar)
            return
        if state.state == "running":
            card.hint(i18n.t("gui.preview.running"))
            return
        card.show(state.summary, list(state.rows), i18n.t("gui.preview.unchanged"))
        if note is not None:
            if state.state == "ready":
                note.configure(text="", fg=TEXT_MUTED)
            else:
                note.configure(text=i18n.t("gui.preview.stale"), fg=YELLOW)
            self.root.after_idle(self._fit_top_bar)

    def _folder_var(self, page: str) -> tk.StringVar:
        feature = next((item for item in CORE_FEATURES if item.key == page), None)
        return getattr(self, feature.source_var) if feature else self.var_tags_folder

    def _refresh_folder_stats(self, page: str, manual: bool = True) -> None:
        """Count files/albums/artists in the background and show the result."""
        label = self._stats_labels.get(page)
        if label is None or self.running or self._scan_page is not None:
            return
        folder = self._folder_var(page).get().strip()
        if not folder or not Path(folder).expanduser().is_dir():
            label.configure(text=i18n.t("gui.stats.unknown"))
            return
        if not manual and not self.has_mutagen:
            label.configure(text=i18n.t("gui.stats.press_refresh"))
            return

        self._scan_page = page
        self._scan_got_stats = False
        token = CancelToken()
        self._scan_cancel = token
        label.configure(text=i18n.t("gui.stats.scanning"))
        self.status_var.set(i18n.t("gui.status.scanning"))
        self._set_state(YELLOW)

        context = output.RunContext(
            logger=lambda text: self.queue.put(("scan_log", (token, text))),
            progress_sink=lambda i, n, text: self.queue.put(
                ("scan_prog", (token, (i, n, text)))),
            stats_sink=lambda kind, values: self.queue.put(
                ("scan_stats", (token, (kind, values)))),
            log_to_file=False,
            paths=config.current_paths(),
        )

        def worker() -> None:
            def scan() -> int:
                try:
                    return cmd_scan(SimpleNamespace(folder=folder, cancel=token))
                except Cancelled:
                    return 130
                except Exception:  # noqa: BLE001
                    output.message(i18n.t("gui.log.error", text=traceback.format_exc()))
                    return 99

            report = context.execute(scan)
            self.queue.put(("scan_done", (token, report.returncode)))

        threading.Thread(target=worker, daemon=True).start()

    def _show_folder_stats(self, page: str | None, values: dict) -> None:
        label = self._stats_labels.get(page or "")
        if label is None:
            return
        def number(key: str) -> i18n.Text:
            value = values.get(key, 0)
            return i18n.Text(lambda: _fmt_number(value))

        label.configure(text=i18n.t("gui.stats.summary",
                                    files=number("files"), albums=number("albums"),
                                    artists=number("artists")))

    def _absorb_stats(self, kind: str, values: dict) -> None:
        """Route the counters: a folder scan fills the line, a run fills the card."""
        if kind == "scan":
            self._scan_got_stats = True
            self._show_folder_stats(self._scan_page, values)
            self._scan_page = None
            if not self.running:
                self.progress_label.configure(text="")
                self.status_var.set(i18n.t("gui.status.ready"))
                self._set_state(GREEN if self.has_ffprobe else YELLOW)
            return
        if kind == "export" and values.get("outdir"):
            self.last_path = Path(values["outdir"])
        self._render_stats(kind, values)

    def _render_stats(self, kind: str, values: dict) -> None:
        def number(value: object) -> i18n.Text:
            return i18n.Text(lambda: _fmt_number(value))
        self._last_result_kind = kind
        self._last_result_values = dict(values)
        if kind == "all":
            rows = [
                (GREEN, "✓", number(values.get("tags_changed", 0)),
                 i18n.t("gui.result.tags_changed")),
                (GREEN, "✓", number(values.get("renamed", 0)), i18n.t("gui.result.renamed")),
                (GREEN, "✓", number(values.get("sorted_files", 0)),
                 i18n.t("gui.result.sorted")),
                (RED, "✕", number(values.get("errors", 0)), i18n.t("gui.result.errors")),
            ]
        elif kind == "export":
            rows = [
                (GREEN, "✓", number(values.get("files", 0)),
                 i18n.t("gui.result.analysed")),
                (RED, "✕", number(values.get("errors", 0)), i18n.t("gui.result.errors")),
                (TEXT_MUTED, "•", number(values.get("parts", 0)),
                 i18n.t("gui.result.parts")),
            ]
            if values.get("duplicate_groups") is not None:
                rows.append((YELLOW, "⚠", number(values.get("duplicate_groups", 0)),
                             i18n.t("gui.result.duplicates")))
        else:
            changed_key = ("gui.result.changed" if values.get("applied")
                           else "gui.result.planned")
            rows = [
                (GREEN, "✓", number(values.get("changed", 0)), i18n.t(changed_key)),
                (TEXT_MUTED, "•", number(values.get("files", 0)),
                 i18n.t("gui.result.analysed")),
                (YELLOW, "⚠", number(values.get("skipped", 0)),
                 i18n.t("gui.result.skipped")),
                (RED, "✕", number(values.get("errors", 0)), i18n.t("gui.result.errors")),
            ]
        self.result_panel.set_counters(rows)
        self._rebuild_result_header(values.get("backup", ""), values.get("outdir", ""))
        self._refresh_recent()

    def _start(self, page: str, description: str, function, args, last_path: str | Path,
               source: str = "", target_root: str = "") -> bool:
        if self.running:
            return False
        self._cancel_scan()
        self.running = True
        self._job_page = page
        self._cancel = CancelToken()
        args.cancel = self._cancel
        if self._cancel_button is not None:
            self._cancel_button.set_enabled(True)
            self._cancel_button.grid()
        self.last_path = Path(last_path).expanduser()
        self._begin_plan(page, source=source, target_root=target_root)
        self._job_signature = self._signature(page)
        self._job_applied = bool(getattr(args, "apply", False))
        self._set_buttons(False)
        self._render_preview(page)
        self.progress.start()
        self.progress_label.configure(text="")
        self._set_state(YELLOW)
        self.status_var.set(i18n.t("gui.status.running"))
        self._log_line("")
        self._log_line(i18n.t("gui.log.job", description=description))
        self._log_rules(i18n.t("gui.rules.prefix"))

        context = output.RunContext(
            logger=lambda text: self.queue.put(("log", text)),
            progress_sink=lambda i, n, text: self.queue.put(("prog", (i, n, text))),
            plan_sink=lambda event: self.queue.put(("plan", event)),
            stats_sink=lambda kind, values: self.queue.put(("stats", (kind, values))),
            paths=config.current_paths(),
        )

        def worker() -> None:
            def run() -> int:
                rc = 99
                try:
                    log_file = output.open_log_file(f"{description} · {self.last_path}")
                    if log_file:
                        output.message(i18n.t("gui.log.log_file", path=log_file))
                    if getattr(args, "apply", False) and journal.enabled():
                        if log_file is None or journal.open_for(log_file) is None:
                            output.message(i18n.t("journal.error.open"))
                            rc = 2
                            return rc
                    rc = function(args)
                except Exception:
                    output.message(i18n.t("gui.log.error", text=traceback.format_exc()))
                    rc = 99
                finally:
                    journal.close()
                    output.close_log_file(rc)
                return rc

            report = context.execute(run)
            self.queue.put(("done", report.returncode))

        threading.Thread(target=worker, daemon=True).start()
        return True

    def _finish(self, rc: int) -> None:
        """A run is over: release the buttons and stamp the preview."""
        self.progress.stop()
        self.progress_label.configure(text="")
        self.running = False
        self._cancel = None
        if self._cancel_button is not None:
            self._cancel_button.grid_remove()
        preview.finish(self._plans, self._job_page,
                       getattr(self, "_job_signature", None),
                       getattr(self, "_job_applied", False), rc)
        self._set_buttons(True)
        self._refresh_preview_states()
        if rc == 0:
            self._set_state(GREEN)
            self.status_var.set(i18n.t("gui.status.ready"))
        elif rc == 130:
            self._set_state(YELLOW)
            self.status_var.set(i18n.t("gui.status.cancelled"))
        else:
            self._set_state(RED)
            self.status_var.set(i18n.t("gui.status.failed", rc=rc))
        if self._closing:
            self.root.after_idle(self.root.destroy)

    def _on_window_close(self) -> None:
        """Close the window - but let a running task stop first."""
        if self._closing:
            since = getattr(self, "_closing_since", time.monotonic())
            if (time.monotonic() - since >= self._FORCE_CLOSE_AFTER
                    and _ask_yes_no(i18n.t("gui.dialog.force_close.title"),
                                    i18n.t("gui.dialog.force_close.text"))):
                self.root.destroy()
            return
        if not self.running:
            self._cancel_scan()
            if getattr(self, "_folder_save_job", None) is not None:
                self._save_folders()
            self.root.destroy()
            return
        if not _ask_yes_no(i18n.t("gui.dialog.close.title"),
                           i18n.t("gui.dialog.close.text")):
            return
        if getattr(self, "_folder_save_job", None) is not None:
            self._save_folders()
        self._closing = True
        self._closing_since = time.monotonic()
        self._cancel_run()
        self._set_buttons(False)
        self.status_var.set(i18n.t("gui.status.cancelling"))

    def _cancel_run(self) -> None:
        """Ask the running command to stop at its next check point."""
        if self._cancel is not None:
            self._cancel.cancel()
            if self._cancel_button is not None:
                self._cancel_button.set_enabled(False)

    def _cancel_scan(self) -> None:
        """Ask a running folder scan to stop (it has no cancel button of its own)."""
        if self._scan_cancel is not None:
            self._scan_cancel.cancel()

    def _queue_pump(self) -> None:
        try:
            while True:
                kind, value = self.queue.get_nowait()
                self._dispatch(kind, value)
        except queue.Empty:
            pass
        finally:
            if not (self._closing and not self.running):
                try:
                    self.root.after(80, self._queue_pump)
                except tk.TclError:
                    pass

    def _dispatch(self, kind: str, value) -> None:
        """Handle one message from a worker thread (also used by the tests)."""
        try:
            if kind == "log":
                self._log_line(value)
            elif kind == "prog":
                self._set_progress(*value)
            elif kind == "plan":
                self._absorb_plan(value)
            elif kind == "stats":
                self._absorb_stats(*value)
            elif kind in ("scan_log", "scan_prog", "scan_stats", "scan_done"):
                token, payload = value
                if token is not self._scan_cancel:
                    return
                if kind == "scan_done":
                    self._scan_finished()
                elif not token.is_set():
                    if kind == "scan_log":
                        self._log_line(payload)
                    elif kind == "scan_prog":
                        self._set_progress(*payload)
                    else:
                        self._absorb_stats(*payload)
            elif kind == "done":
                self._finish(value)
        except Exception:
            context = output.RunContext(logger=self._log_line)
            with output.use_run_context(context):
                output.message(i18n.t("gui.log.error", text=traceback.format_exc()))

    def _scan_finished(self) -> None:
        """A folder scan is over (also when it failed and sent no counters)."""
        page, self._scan_page = self._scan_page, None
        self._scan_cancel = None
        if page is None:
            return
        if not getattr(self, "_scan_got_stats", False):
            label = self._stats_labels.get(page)
            if label is not None:
                label.configure(text=i18n.t("gui.stats.unknown"))
        if not self.running:
            self.progress_label.configure(text="")
            self.status_var.set(i18n.t("gui.status.ready"))
            self._set_state(GREEN if self.has_ffprobe else YELLOW)

    def _set_progress(self, current: int, total: int, text: str) -> None:
        self.progress.set_value(current, total)
        if total:
            self.progress_label.configure(
                text=i18n.t("gui.status.percent", current=_fmt_number(current),
                            total=_fmt_number(total),
                            percent=int(current * 100 / total)))
        if text:
            self.status_var.set(text)

    def _core_paths_ok(self, page: str, source: str, target: str,
                       move: bool = False) -> bool:
        """Zeige das Ergebnis derselben Pfadprüfung wie bei CLI-Aufträgen."""
        required = core_feature(page).target_required or move
        result = check_core_paths(source, target, target_required=required)
        return self._show_core_path_problem(result, source, target)

    def _show_core_path_problem(self, result, source: str, target: str) -> bool:
        """Übersetze strukturierte Pfadfehler in passende Dialoge."""
        if result.problem is None:
            return True
        if result.problem == PathProblem.SOURCE_MISSING:
            return self._path_ok("")
        if result.problem == PathProblem.SOURCE_INVALID:
            _show_error(i18n.t("gui.dialog.folder_not_found.title"),
                        i18n.t("gui.dialog.folder_not_found.text", path=result.source or source))
            return False
        if result.problem == PathProblem.TARGET_MISSING:
            return self._target_ok("")
        if result.problem == PathProblem.TARGET_IN_SOURCE:
            _show_warning(i18n.t("gui.dialog.target_in_source.title"),
                          i18n.t("gui.dialog.target_in_source.text",
                                 source=_pretty_path(source), target=_pretty_path(target)))
            return False
        _show_error(i18n.t("gui.dialog.target_invalid.title"),
                    i18n.t("gui.dialog.target_invalid.text", path=result.target or target))
        return False

    def _path_ok(self, path: str) -> bool:
        if not path:
            _show_warning(i18n.t("gui.dialog.folder_missing.title"),
                          i18n.t("gui.dialog.folder_missing.text"))
            return False
        target = Path(path).expanduser()
        if not target.is_dir():
            _show_error(i18n.t("gui.dialog.folder_not_found.title"),
                        i18n.t("gui.dialog.folder_not_found.text", path=target))
            return False
        return True

    def _target_ok(self, target: str) -> bool:
        """Validate the target for sorting and the all-in-one run."""
        if target:
            return True
        _show_warning(i18n.t("gui.dialog.target_missing.title"),
                      i18n.t("gui.dialog.target_missing.text"))
        return False

    def _target_outside_source(self, source: str, target: str) -> bool:
        """Refuse a target that is the source folder or lies below it."""
        try:
            inside = target_inside_source(source, target)
        except (OSError, RuntimeError, ValueError):
            _show_error(i18n.t("gui.dialog.target_invalid.title"),
                        i18n.t("gui.dialog.target_invalid.text", path=target))
            return False
        if not inside:
            return True
        _show_warning(
            i18n.t("gui.dialog.target_in_source.title"),
            i18n.t("gui.dialog.target_in_source.text",
                   source=_pretty_path(source), target=_pretty_path(target)))
        return False

    def _set_buttons(self, enabled: bool) -> None:
        for button in self.action_buttons:
            button.set_enabled(enabled)
