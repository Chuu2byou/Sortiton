"""Running tasks: plans, previews, workers, progress and closing."""

from __future__ import annotations

import time

from ..common import (
    CancelToken,
    GREEN,
    PATTERN_DEFAULT,
    PLAN_FIELDS,
    Path,
    RED,
    SimpleNamespace,
    TEXT_FAINT,
    TEXT_MUTED,
    YELLOW,
    _ask_yes_no,
    _fmt_duration,
    _fmt_number,
    _pretty_path,
    _show_error,
    _show_warning,
    ask_confirm,
    cmd_all,
    cmd_rename,
    cmd_restore,
    cmd_scan,
    cmd_sort,
    cmd_tags,
    config,
    feature_by_key,
    i18n,
    journal,
    output,
    queue,
    rules,
    settings,
    threading,
    tk,
    tool_value,
    traceback,
)


class RunMixin:
    """Running tasks: plans, previews, workers, progress and closing."""

    #: A second close attempt may force the window away after this many seconds
    #: of waiting for a worker that ignores cancellation.
    _FORCE_CLOSE_AFTER = 10.0

    def _run_restore(self, path: Path, keep_copies: bool) -> bool:
        """Undo the given journal - the dialog has confirmed everything."""
        settings.save_backup(self.var_backup.get())
        return self._start("restore", self._job_name("gui.job.restore", True),
                           cmd_restore,
                           SimpleNamespace(journal=str(path), apply=True,
                                           backup=self.var_backup.get(),
                                           keep_copies=keep_copies),
                           Path(path).parent, source=str(path))

    def _run_tags(self, write: bool) -> None:
        folder = self.var_tags_folder.get().strip()
        if not self._path_ok(folder):
            return
        if write and not self._preview_allowed("tags"):
            return
        if write and not self._confirm_write("tags", folder=folder):
            return
        self._start("tags", self._job_name("gui.job.tags", write), cmd_tags,
                    SimpleNamespace(folder=folder, apply=write,
                                    backup=self._backup_for_run),
                    folder, source=folder)

    def _run_rename(self, execute: bool) -> None:
        folder = self.var_ren_folder.get().strip()
        if not self._path_ok(folder):
            return
        pattern = self.var_ren_pattern.get().strip() or PATTERN_DEFAULT
        if execute and not self._preview_allowed("rename"):
            return
        if execute and not self._confirm_write("rename", folder=folder,
                                               pattern=pattern,
                                               allow_backup=False):
            return
        self._start("rename", self._job_name("gui.job.rename", execute), cmd_rename,
                    SimpleNamespace(folder=folder, pattern=pattern, apply=execute),
                    folder, source=folder)

    def _run_sort(self, execute: bool) -> None:
        source = self.var_source.get().strip()
        target = self.var_target.get().strip()
        if not self._path_ok(source) or not self._target_ok(target):
            return
        pattern = self.var_sort_pattern.get().strip() or PATTERN_DEFAULT
        move = self.var_sort_mode.get() == "move"
        if execute and not self._preview_allowed("sort"):
            return
        if execute and not self._confirm_write("sort", folder=source, target=target,
                                               allow_backup=False):
            return
        self._start("sort", self._job_name("gui.job.sort", execute), cmd_sort,
                    SimpleNamespace(source=source, target=target, pattern=pattern,
                                    move=move, apply=execute), target,
                    source=source, target_root=target)

    def _run_all(self, execute: bool) -> None:
        source = self.var_all_source.get().strip()
        target = self.var_all_target.get().strip()
        if not self._path_ok(source) or not self._target_ok(target):
            return
        pattern = self.var_all_pattern.get().strip() or PATTERN_DEFAULT
        move = self.var_all_mode.get() == "move"
        if execute and not self._preview_allowed("all"):
            return
        if execute and not self._confirm_write("all", folder=source, target=target):
            return
        # TODO: unlike the sort page this hands the source folder to "Open
        # folder", although the files end up in the target as well.
        self._start("all", self._job_name("gui.job.all", execute), cmd_all,
                    SimpleNamespace(source=source, target=target, pattern=pattern,
                                    move=move, apply=execute,
                                    backup=self._backup_for_run), source,
                    source=source, target_root=target)

    def _preview_allowed(self, page: str) -> bool:
        """A write needs a preview of exactly the inputs the form has now."""
        if self._preview_ready(page):
            return True
        _show_warning(i18n.t("gui.dialog.preview_stale.title"),
                      i18n.t("gui.dialog.preview_stale.text"))
        return False

    def _tool_args(self, feature, execute: bool = False) -> SimpleNamespace:
        """Read the tools form back into the namespace the feature expects.

        ``apply``, ``backup`` and ``confirm`` come from the action bar and the
        confirm dialog, not from the form (the form does not draw those).
        ``confirm`` follows ``apply``: the GUI shows its own dialog before a
        run, so reaching this point with ``execute`` means the user confirmed.
        """
        values = {option.name: tool_value(option, self.var_tool[feature.key][option.name])
                  for option in feature.options}
        if any(option.name == "apply" for option in feature.options):
            values["apply"] = execute
        if any(option.name == "backup" for option in feature.options):
            values["backup"] = self.var_backup.get()
        if any(option.name == "confirm" for option in feature.options):
            values["confirm"] = execute
        return SimpleNamespace(**values)

    def _run_tools(self, execute: bool = False) -> None:
        """Start the selected tool: read-only runs directly, writing runs ask."""
        feature = feature_by_key(self.var_tool_choice.get())
        if feature is None:
            return
        args = self._tool_args(feature, execute)

        folder = str(getattr(args, "folder", "") or "").strip()
        root = str(getattr(args, "root", "") or "").strip()
        csv_path = str(getattr(args, "file", "") or "").strip()
        target = str(getattr(args, "target", "") or "").strip()
        if folder:
            if not self._path_ok(folder):
                return
            location = folder
        elif root:
            if not self._path_ok(root):
                return
            location = root
        elif csv_path:
            csv_file = Path(csv_path).expanduser()
            if not csv_file.is_file():
                _show_error(i18n.t("gui.dialog.file_not_found.title"),
                            i18n.t("gui.dialog.file_not_found.text", path=csv_file))
                return
            location = str(csv_file.parent)
        elif target:
            # fetch names its output folder "target"; without this branch every
            # GUI fetch stopped at "choose a folder first".
            if not self._path_ok(target):
                return
            location = target
        else:
            _show_warning(i18n.t("gui.dialog.folder_missing.title"),
                          i18n.t("gui.dialog.folder_missing.text"))
            return

        if feature.writes and execute and not self._confirm_tool_write(feature):
            return
        if any(option.name == "backup" for option in feature.options):
            # The dialog may have changed the backup switch after args was built.
            args.backup = self._backup_for_run
        last = config.EXPORT_DIR if folder else location
        description = (self._job_name(f"gui.job.{feature.key}", execute)
                       if feature.writes else
                       i18n.t("gui.job.run", name=i18n.t(f"gui.job.{feature.key}")))
        self._start("tools", description, feature.run, args, last, source=location)

    def _job_name(self, key: str, execute: bool) -> str:
        name = i18n.t(key)
        return i18n.t("gui.job.run", name=name) if execute else i18n.t("gui.job.preview",
                                                                       name=name)

    def _mode_text(self, page: str) -> str:
        variable = self.var_all_mode if page == "all" else self.var_sort_mode
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
        """Confirmation before a writing tool runs.

        The fetch feature asks on its own: a download must be confirmed every
        single time, and its dialog must not reuse the CSV wording of the fixes
        feature.
        """
        if feature.key == "fetch":
            return self._confirm_fetch()
        has_backup = any(option.name == "backup" for option in feature.options)
        return self._confirm_write("tools", allow_backup=has_backup)

    def _confirm_fetch(self) -> bool:
        """Dedicated download confirmation, including the rights note."""
        confirmed, _options = ask_confirm(
            self.root,
            title=i18n.t("gui.confirm.fetch.title"),
            heading=i18n.t("gui.confirm.fetch.title"),
            text=i18n.t("gui.confirm.fetch.text"),
            note=i18n.t("gui.confirm.fetch.note"),
            ok_text=i18n.t("gui.confirm.ok"),
            cancel_text=i18n.t("gui.button.cancel"))
        return confirmed

    def _confirm_text(self, page: str, *, files: str, changes: str, **fields) -> str:
        if page == "tags":
            return i18n.t("gui.confirm.tags.text", changes=changes, files=files)
        if page == "rename":
            return i18n.t("gui.confirm.rename.text", files=files,
                          pattern=fields.get("pattern", ""))
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
        """Reset the aggregated plan of ``page`` before a run starts."""
        self._plans[page] = {"kind": page, "files": 0, "changes_total": 0, "fields": {},
                             "examples": [], "source": source, "target": target_root,
                             "signature": None}

    def _absorb_plan(self, kind: str, data: dict) -> None:
        """Aggregate one planned change - counters plus a few examples only.

        The full list stays in the log, so the card stays readable.
        """
        plan = self._plans.get(self._job_page)
        if plan is None:
            return

        if kind == "tags":
            # The fixes feature (tools tab) also reports tag changes; render them
            # like the tags page instead of the generic file summary.
            plan["kind"] = "tags"
            changes = data.get("changes") or {}
            plan["files"] += 1
            plan["changes_total"] += len(changes)
            for field, pair in changes.items():
                entry = plan["fields"].setdefault(field, {"count": 0, "examples": []})
                entry["count"] += 1
                example = (pair[0], pair[1])
                if example not in entry["examples"]:
                    entry["examples"].append(example)
            return

        if kind == "fetch":
            # The fetch feature reports what yt-dlp would load, not files on
            # disk; keep the entries so the preview card can name them.
            plan["kind"] = "fetch"
            plan["files"] += 1
            entries = plan.setdefault("entries", [])
            if len(entries) < 3:
                entries.append((str(data.get("title") or data.get("url") or ""),
                                _fmt_duration(data.get("duration"))))
            return

        source = data.get("source")
        target = data.get("target")
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

    def _watch_inputs(self) -> None:
        """Invalidate a preview as soon as one of its inputs changes."""
        for variable in (self.var_tags_folder, self.var_ren_folder, self.var_ren_pattern,
                         self.var_source, self.var_target, self.var_sort_pattern,
                         self.var_sort_mode, self.var_all_source, self.var_all_target,
                         self.var_all_pattern, self.var_all_mode):
            self._traces.append((variable,
                                 variable.trace_add("write", self._inputs_changed)))
        # The tools form is generated per feature; watch every option field too.
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
        """Everything a preview depends on - detects outdated previews."""
        rules_id = (self._rules_fingerprint(), rules.rules_status()["custom_total"])
        if page == "tags":
            return ("tags", self.var_tags_folder.get().strip(), rules_id)
        if page == "rename":
            return ("rename", self.var_ren_folder.get().strip(),
                    self.var_ren_pattern.get().strip(), rules_id)
        if page == "sort":
            return ("sort", self.var_source.get().strip(), self.var_target.get().strip(),
                    self.var_sort_pattern.get().strip(), self.var_sort_mode.get())
        if page == "tools":
            feature = feature_by_key(self.var_tool_choice.get())
            if feature is None:
                return ("tools",)
            values = tuple((option.name, self.var_tool[feature.key][option.name].get())
                           for option in feature.options)
            return ("tools", feature.key, values)
        if page == "restore":
            # An undo has no inputs of its own: the journal is fixed when the run
            # starts, so the signature only has to stay stable while it runs.
            return ("restore", str((self._plans.get("restore") or {}).get("source", "")))
        return ("all", self.var_all_source.get().strip(), self.var_all_target.get().strip(),
                self.var_all_pattern.get().strip(), self.var_all_mode.get(), rules_id)

    def _preview_ready(self, page: str) -> bool:
        plan = self._plans.get(page)
        return bool(plan and plan.get("signature") == self._signature(page))

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
        """Draw the aggregated plan of ``page`` and gate its action button."""
        card = self._previews.get(page)
        if card is None:
            return
        button = self._execute_buttons.get(page)
        note = self._preview_notes.get(page)
        plan = self._plans.get(page)

        if button is not None:
            button.set_enabled(self._preview_ready(page) and not self.running)

        if plan is None:
            card.hint(i18n.t("gui.preview.none"))
            if note is not None:
                note.configure(text=i18n.t("gui.preview.run_first"), fg=TEXT_FAINT)
            return

        if plan.get("signature") is None and self.running and page == self._job_page:
            card.hint(i18n.t("gui.preview.running"))
            return

        card.show(self._plan_summary(plan), self._plan_rows(plan),
                  i18n.t("gui.preview.unchanged"))
        if note is not None:
            if self._preview_ready(page):
                note.configure(text="", fg=TEXT_MUTED)
            else:
                note.configure(text=i18n.t("gui.preview.stale"), fg=YELLOW)

    def _plan_summary(self, plan: dict) -> str:
        files = _fmt_number(plan.get("files", 0))
        if plan.get("kind") == "tags":
            return i18n.t("gui.preview.summary_tags",
                          changes=_fmt_number(plan.get("changes_total", 0)), files=files)
        if plan.get("kind") == "fetch":
            return i18n.t("gui.preview.summary_fetch", count=files)
        return i18n.t("gui.preview.summary_files", files=files)

    def _plan_rows(self, plan: dict) -> list[tuple[str, str, str, str]]:
        rows: list[tuple[str, str, str, str]] = []
        if plan.get("kind") == "fetch":
            return [(i18n.t("gui.field.title"), "", title, duration)
                    for title, duration in (plan.get("entries") or [])]
        if plan.get("kind") == "tags":
            for field in PLAN_FIELDS:
                entry = (plan.get("fields") or {}).get(field)
                if not entry or not entry["examples"]:
                    continue
                old, new = entry["examples"][0]
                extra = (i18n.t("gui.preview.more", count=entry["count"] - 1)
                         if entry["count"] > 1 else "")
                rows.append((i18n.t("gui.field." + field), old, new, extra))
            return rows

        examples = plan.get("examples") or []
        if examples:
            old, new = examples[0]
            extra = (i18n.t("gui.preview.more", count=plan["files"] - 1)
                     if plan["files"] > 1 else "")
            rows.append((i18n.t("gui.field.file"), old, new, extra))
        if plan.get("target"):
            rows.append((i18n.t("gui.field.folder"), _pretty_path(plan.get("source", "")),
                         _pretty_path(plan.get("target", "")), ""))
        return rows

    def _folder_var(self, page: str) -> tk.StringVar:
        return {"tags": self.var_tags_folder, "rename": self.var_ren_folder,
                "sort": self.var_source, "all": self.var_all_source}.get(
                    page, self.var_tags_folder)

    def _refresh_folder_stats(self, page: str, manual: bool = True) -> None:
        """Count files/albums/artists in the background and show the result.

        Without mutagen it falls back to ffprobe and can take a minute, so the
        automatic start is skipped in that case.
        """
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
        label.configure(text=i18n.t("gui.stats.scanning"))
        self.status_var.set(i18n.t("gui.status.scanning"))
        self._set_state(YELLOW)

        def worker() -> None:
            rc = 99
            try:
                rc = cmd_scan(SimpleNamespace(folder=folder))
            except Exception:
                output.message(i18n.t("gui.log.error", text=traceback.format_exc()))
            self.queue.put(("scan_done", rc))

        threading.Thread(target=worker, daemon=True).start()

    def _show_folder_stats(self, page: str | None, values: dict) -> None:
        label = self._stats_labels.get(page or "")
        if label is None:
            return
        label.configure(text=i18n.t("gui.stats.summary",
                                    files=_fmt_number(values.get("files", 0)),
                                    albums=_fmt_number(values.get("albums", 0)),
                                    artists=_fmt_number(values.get("artists", 0))))

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
            # "Open folder" should point at the reports, not at the music folder.
            self.last_path = Path(values["outdir"])
        self._render_stats(kind, values)

    def _render_stats(self, kind: str, values: dict) -> None:
        number = _fmt_number
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
            # The export has no "changed/skipped": it only reads (see step 3.2).
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
        self.running = True
        self._job_page = page
        self._cancel = CancelToken()
        args.cancel = self._cancel
        if self._cancel_button is not None:
            self._cancel_button.set_enabled(True)
            self._cancel_button.grid()
        self.last_path = Path(last_path).expanduser()
        self._begin_plan(page, source=source, target_root=target_root)
        # Snapshot the inputs of this run. _finish() must not recompute them:
        # the user may have changed the form while the worker was running, and
        # stamping the new values would enable a write against other inputs.
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

        def worker() -> None:
            rc = 99
            try:
                log_file = output.open_log_file(f"{description} · {self.last_path}")
                if log_file:
                    output.message(i18n.t("gui.log.log_file", path=log_file))
                    if getattr(args, "apply", False):
                        # Only a run that writes gets a journal. Without one the
                        # run could not be undone, so it must not start.
                        if journal.enabled() and journal.open_for(log_file) is None:
                            output.message(i18n.t("journal.error.open"))
                            rc = 2
                            return
                rc = function(args)
            except Exception:
                output.message(i18n.t("gui.log.error", text=traceback.format_exc()))
                rc = 99
            finally:
                journal.close()
                output.close_log_file(rc)
                self.queue.put(("done", rc))

        threading.Thread(target=worker, daemon=True).start()
        return True

    def _finish(self, rc: int) -> None:
        """A run is over: release the buttons and stamp the preview.

        Only a successful preview keeps a signature, and it is the one captured
        when the run started. An applied run (or a failed one) has no valid
        preview any more: the files or tags on disk may have changed.
        """
        self.progress.stop()
        self.progress_label.configure(text="")
        self.running = False
        self._cancel = None
        if self._cancel_button is not None:
            self._cancel_button.grid_remove()
        plan = self._plans.get(self._job_page)
        applied = getattr(self, "_job_applied", False)
        signature = getattr(self, "_job_signature", None)
        if plan is not None:
            plan["signature"] = signature if rc == 0 and not applied else None
        if rc == 0 and applied:
            # A write changes tags or names behind the other pages, so their
            # previews are stale now and have to be created again.
            for page, other in self._plans.items():
                if page != self._job_page:
                    other["signature"] = None
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
            # The worker is done, so it is safe to destroy the window now.
            # after_idle: this runs from the queue pump, which must be able to
            # finish its current tick first.
            self.root.after_idle(self.root.destroy)

    def _on_window_close(self) -> None:
        """Close the window - but let a running task stop first.

        The worker threads are daemons: destroying the window mid-write would
        kill them inside ``shutil.move`` or ``write_tags``. A running task is
        therefore cancelled and the window closes when it has finished.
        """
        if self._closing:
            # A second close attempt is the escape hatch for a worker that
            # ignores cancellation (a stuck yt-dlp, a huge move) - but only
            # after a grace period, so a double click cannot kill a write.
            since = getattr(self, "_closing_since", time.monotonic())
            if (time.monotonic() - since >= self._FORCE_CLOSE_AFTER
                    and _ask_yes_no(i18n.t("gui.dialog.force_close.title"),
                                    i18n.t("gui.dialog.force_close.text"))):
                self.root.destroy()
            return
        if not self.running:
            self.root.destroy()
            return
        if not _ask_yes_no(i18n.t("gui.dialog.close.title"),
                           i18n.t("gui.dialog.close.text")):
            return
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
                # A folder scan must not paint over the progress bar of a run.
                if self._scan_page is None or not self.running:
                    self._set_progress(*value)
            elif kind == "plan":
                self._absorb_plan(*value)
            elif kind == "stats":
                self._absorb_stats(*value)
            elif kind == "scan_done":
                self._scan_finished()
            elif kind == "done":
                self._finish(value)
        except Exception:
            # One broken handler must not stop the queue pump for the rest of
            # the session (the window would freeze on its last status).
            output.message(i18n.t("gui.log.error", text=traceback.format_exc()))

    def _scan_finished(self) -> None:
        """A folder scan is over (also when it failed and sent no counters)."""
        page, self._scan_page = self._scan_page, None
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
        """Sorting and the all-in-one run need a target folder."""
        if target:
            return True
        _show_warning(i18n.t("gui.dialog.target_missing.title"),
                      i18n.t("gui.dialog.target_missing.text"))
        return False

    def _set_buttons(self, enabled: bool) -> None:
        for button in self.action_buttons:
            button.set_enabled(enabled)
