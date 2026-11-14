"""The export feature: read-only reports for an LLM."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ... import config, external, i18n, output
from ...cancel import NO_CANCEL, Cancelled
from ...config import READ_WORKERS
from ...files import canonical_path, free_path
from ...paths import PathProblem
from ..base import (CmdArgs, Feature, Option, Requirement, resolve_args,
                    validate_feature_paths)
from . import fingerprint, reader, report


MANIFEST_NAME = ".sortiton-export.json"
"""Name of the manifest listing files created by a Sortiton run."""


def _valid_name(name: object) -> str | None:
    """A plain file name in the output folder, or ``None`` otherwise."""
    if not isinstance(name, str) or not name or name in (".", "..", MANIFEST_NAME):
        return None
    if "\0" in name or Path(name).name != name:
        return None
    return name


def _read_manifest(outdir: Path) -> list[str]:
    """Names listed in the old manifest; empty if it is missing or invalid.

    Only a fully readable manifest containing a list of names proves ownership;
    otherwise, nothing is deleted.
    """
    try:
        data = json.loads((outdir / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    listed = data.get("files")
    if not isinstance(listed, list):
        return []
    names: list[str] = []
    for item in listed:
        name = _valid_name(item)
        if name is not None and name not in names:
            names.append(name)
    return names


def _write_manifest(outdir: Path, names: list[str]) -> None:
    """Write the manifest for files created so far in this run."""
    try:
        (outdir / MANIFEST_NAME).write_text(
            json.dumps({"version": 1, "files": names}, ensure_ascii=False) + "\n",
            encoding="utf-8")
    except OSError:
        pass


def _clear_reports(outdir: Path) -> list[str]:
    """Remove only reports listed in the old manifest.

    If the manifest is missing or unreadable, leave every file untouched,
    including a user TSV that happens to have a report-like name. Return the
    (still empty) list of files created in this run.
    """
    old = _read_manifest(outdir)
    for name in old:
        try:
            (outdir / name).unlink(missing_ok=True)
        except OSError:
            pass
    _write_manifest(outdir, [])
    return []


class _Output:
    """Write reports without ever replacing a file we do not own.

    ``names`` are this run's files; only they may be overwritten. If a target
    name already exists and is not ours, choose a free name (`` (2)``) so the
    promise that nothing is overwritten also holds for a user-selected folder.

    Record the name in the manifest *before* writing: if the run stops midway,
    the partial file is treated as ours and cleaned up next time instead of
    being left behind as an unknown file.
    """

    def __init__(self, outdir: Path) -> None:
        self.outdir = outdir
        self.names: list[str] = []

    def _claim(self, name: str) -> Path:
        """Return the target path for ``name``, choosing `` (2)`` if needed."""
        if name in self.names:
            return self.outdir / name
        path = free_path(self.outdir / name)
        self.names.append(path.name)
        _write_manifest(self.outdir, self.names)
        return path

    def write(self, name: str, text: str) -> str:
        """Write ``text`` and return the name actually used."""
        path = self._claim(name)
        path.write_text(text, encoding="utf-8")
        return path.name

    def open(self, name: str):
        """Open ``name`` for writing (for line-by-line output)."""
        return self._claim(name).open("w", encoding="utf-8")


def cmd_export(args: CmdArgs) -> int:
    """Read a music folder and write the LLM reports (nothing is changed)."""
    output.require_run_context()
    args = resolve_args(FEATURE, args)
    cancel = getattr(args, "cancel", NO_CANCEL)

    for option in FEATURE.options:
        if option.kind not in ("int", "float") or option.minimum is None:
            continue
        value = getattr(args, option.name, None)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number < option.minimum:
            output.message(i18n.t("export.error.minimum", option=option.name,
                                  minimum=option.minimum))
            return 2

    if not 0.0 <= args.fp_threshold <= 1.0:
        output.message(i18n.t("export.error.threshold"))
        return 2

    lacking = external.missing(FEATURE, args)
    if lacking:
        output.message(external.format_missing(lacking))
        return 2

    try:
        root = canonical_path(args.folder)
        if not root.is_dir():
            output.message(i18n.t("task.error.folder", path=root))
            return 2
    except (OSError, RuntimeError, ValueError):
        output.message(i18n.t("task.error.folder", path=args.folder))
        return 2

    outdir = args.output or config.current_paths().export_dir
    try:
        if args.output:
            outdir = Path(args.output).expanduser()
        else:
            outdir = free_path(config.current_paths().export_dir /
                               f"export_{datetime.now():%Y%m%d_%H%M%S}")
        problem = validate_feature_paths(FEATURE, args, output_path=outdir)
        if problem is not None:
            if problem == PathProblem.TARGET_IN_SOURCE:
                output.message(i18n.t("task.error.target_in_source", target=outdir))
            else:
                output.message(i18n.t("task.error.target_invalid", path=outdir))
            return 2
        created_here = not outdir.exists()
        outdir.mkdir(parents=True, exist_ok=True)
    except (OSError, RuntimeError, ValueError) as error:
        output.message(i18n.t("export.error.outdir", path=outdir, error=error))
        return 2

    try:
        recs = reader.scan(root, args.threads, cancel)
        if not recs:
            output.message(i18n.t("export.error.no_files"))
            if created_here:
                # Remove an empty directory created by this run.
                try:
                    outdir.rmdir()
                except OSError:
                    pass
            return 1
        # Clear owned reports and continue the output manifest.
        _clear_reports(outdir)
        out = _Output(outdir)

        lang = args.report_lang or i18n.get_language()
        opts = report.ReportOptions(max_examples=args.examples, check_case=args.check_case)
        sections = report.build_report(recs, root, opts, lang)
        cancel.check()

        duplicate_groups: int | None = None
        if args.fingerprint:
            fps = fingerprint.compute_fingerprints(recs, root, args.fp_seconds,
                                                   args.threads, outdir, cancel,
                                                   write=out.write)
            groups, _pairs = fingerprint.fingerprint_groups(recs, fps, args.fp_threshold)
            duplicate_groups = len(groups)
            sections.append(report.Section(
                "duplicates",
                fingerprint.fp_section(recs, groups, len(fps), len(recs),
                                       args.fp_threshold, args.examples, lang)))

        report.write_report(sections, out.write)
        parts = report.write_chunks(recs, out.write, args.chunk_chars)
        out.write("00_prompt.md", report.prompt_text(lang, len(recs), len(parts)))
        if args.jsonl:
            for rec in recs:
                cancel.check()
                rec["extra"] = reader.read_extra(root / rec["path"])
            with out.open("alle_tags.jsonl") as handle:
                for rec in recs:
                    handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Cancelled:
        output.message(i18n.t("task.cancelled"))
        output.message(i18n.t("export.cancelled", outdir=str(outdir.resolve())))
        return 130
    except OSError as error:
        output.message(i18n.t("export.error.write", path=outdir, error=error))
        return 2

    errors = sum(1 for rec in recs if rec["error"])
    output.message(i18n.t("export.done", files=len(recs), outdir=str(outdir.resolve())))
    output.report_stats("export", files=len(recs), errors=errors, parts=len(parts),
                        outdir=str(outdir.resolve()), duplicate_groups=duplicate_groups,
                        applied=False)
    return 1 if errors == len(recs) else 0


FEATURE = Feature(
    key="export",
    title_key="export.title",
    help_key="cli.export.help",
    run=cmd_export,
    options=(
        Option("folder", "folder", positional=True, help_key="cli.export.folder",
               path_role="source_folder"),
        Option("output", "folder", None, "cli.export.output",
               flags=("-o", "--output", "--ausgabe"), path_role="output_folder"),
        Option("chunk_chars", "int", 60000, "cli.export.chunk",
               flags=("--chunk-chars", "--chunk-zeichen"), minimum=1000),
        Option("examples", "int", 40, "cli.export.examples",
               flags=("--examples", "--beispiele"), minimum=1),
        Option("jsonl", "bool", False, "cli.export.jsonl", flags=("--jsonl",)),
        Option("check_case", "bool", False, "cli.export.check_case",
               flags=("--check-case", "--gross-klein")),
        Option("fingerprint", "bool", False, "cli.export.fingerprint",
               flags=("--fingerprint",)),
        Option("fp_seconds", "int", 120, "cli.export.fp_seconds",
               flags=("--fp-seconds", "--fp-sekunden"), minimum=1),
        Option("fp_threshold", "float", 0.70, "cli.export.fp_threshold",
               flags=("--fp-threshold", "--fp-schwelle"), minimum=0.0, maximum=1.0),
        Option("threads", "int", READ_WORKERS, "cli.export.threads",
               flags=("--threads",), minimum=1),
        Option("report_lang", "choice", "", "cli.export.report_lang",
               flags=("--report-language",), choices=("", "en", "de")),
    ),
    output_outside_source=True,
    requires=(
        Requirement(any_of=(external.MUTAGEN, external.FFPROBE)),
        Requirement(any_of=(external.FPCALC,), when="fingerprint"),
    ),
)
