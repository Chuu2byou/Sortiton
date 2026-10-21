"""The export feature: read-only reports for an LLM.

Reads a music folder and writes ``00_prompt.md``, ``01_zusammenfassung.md``,
``02_auffaelligkeiten.md``, ``03_duplikate.md`` (with ``--fingerprint``),
``tracks_partNN.tsv`` and - on request - ``alle_tags.jsonl``. The export never
changes the library, so it has no ``--apply``.

The logic lives in the sibling modules (:mod:`reader`, :mod:`analysis`,
:mod:`fingerprint`, :mod:`report`); this module wires it to the Sortiton output
and describes the feature for the CLI and the GUI.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ... import external, i18n, output
from ...cancel import NO_CANCEL, Cancelled
from ...config import EXPORT_DIR, READ_WORKERS
from ...files import free_path
from ..base import CmdArgs, Feature, Option, Requirement, resolve_args
from . import fingerprint, reader, report


def _clear_reports(outdir: Path) -> None:
    """Remove the reports of an earlier run that this run may not rewrite.

    Without this a second export into the same folder keeps a stale
    ``03_duplikate.md`` (run without ``--fingerprint``) or extra
    ``tracks_partNN.tsv`` files, and ``00_prompt.md`` presents them as current.
    Only the names this feature writes are touched.
    """
    for name in ("00_prompt.md", "01_zusammenfassung.md", "02_auffaelligkeiten.md",
                 "03_duplikate.md", "alle_tags.jsonl", "fpcalc_fehler.log"):
        try:
            (outdir / name).unlink(missing_ok=True)
        except OSError:
            pass
    try:
        for old in outdir.glob("tracks_part*.tsv"):
            old.unlink(missing_ok=True)
    except OSError:
        pass


def cmd_export(args: CmdArgs) -> int:
    """Read a music folder and write the LLM reports (nothing is changed).

    Returns 0 on success, 1 when no audio file was found (or none was
    readable), 2 on a bad input or a missing tool, 130 when the run was
    cancelled. The old script always ended with 1; the split is deliberate.
    """
    args = resolve_args(FEATURE, args)
    cancel = getattr(args, "cancel", NO_CANCEL)

    # Option.minimum was only a hint for the GUI spinbox; a typed or scripted
    # value (--threads 0) used to crash deep inside the run.
    for option in FEATURE.options:
        if option.kind not in ("int", "float") or option.minimum is None:
            continue
        value = getattr(args, option.name, None)
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

    # The GUI does not go through cli.main, so the tool check lives here too.
    lacking = external.missing(FEATURE, args)
    if lacking:
        output.message(external.format_missing(lacking))
        return 2

    root = Path(args.folder).expanduser().resolve()
    if not root.is_dir():
        output.message(i18n.t("task.error.folder", path=root))
        return 2

    if args.output:
        outdir = Path(args.output).expanduser()
    else:
        outdir = free_path(EXPORT_DIR / f"export_{datetime.now():%Y%m%d_%H%M%S}")
    try:
        outdir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        output.message(i18n.t("export.error.outdir", path=outdir, error=error))
        return 2

    try:
        recs = reader.scan(root, args.threads, cancel)
        if not recs:
            output.message(i18n.t("export.error.no_files"))
            return 1
        _clear_reports(outdir)

        lang = args.report_lang or i18n.get_language()
        opts = report.ReportOptions(max_examples=args.examples, check_case=args.check_case)
        sections = report.build_report(recs, root, opts, lang)
        cancel.check()

        duplicate_groups: int | None = None
        if args.fingerprint:
            fps = fingerprint.compute_fingerprints(recs, root, args.fp_seconds,
                                                   args.threads, outdir, cancel)
            groups, _pairs = fingerprint.fingerprint_groups(recs, fps, args.fp_threshold)
            duplicate_groups = len(groups)
            sections.append(report.Section(
                "duplicates",
                fingerprint.fp_section(recs, groups, len(fps), len(recs),
                                       args.fp_threshold, args.examples, lang)))

        report.write_report(sections, outdir)
        parts = report.write_chunks(recs, outdir, args.chunk_chars)
        (outdir / "00_prompt.md").write_text(
            report.prompt_text(lang, len(recs), len(parts)), encoding="utf-8")
        if args.jsonl:
            # Own non-core tags are only needed for the JSONL dump (owner decision O4).
            for rec in recs:
                cancel.check()
                rec["extra"] = reader.read_extra(root / rec["path"])
            with open(outdir / "alle_tags.jsonl", "w", encoding="utf-8") as handle:
                for rec in recs:
                    handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Cancelled:
        # A half-finished export is kept, never deleted; the message names it.
        output.message(i18n.t("task.cancelled"))
        output.message(i18n.t("export.cancelled", outdir=str(outdir.resolve())))
        return 130

    errors = sum(1 for rec in recs if rec["error"])
    output.message(i18n.t("export.done", files=len(recs), outdir=str(outdir.resolve())))
    output.report_stats("export", files=len(recs), errors=errors, parts=len(parts),
                        outdir=str(outdir.resolve()), duplicate_groups=duplicate_groups,
                        applied=False)
    # A folder in which not a single file could be read has no usable report.
    return 1 if errors == len(recs) else 0


#: The one description the CLI and the GUI share (steps 1.6 and 1.8).
FEATURE = Feature(
    key="export",
    title_key="export.title",
    help_key="cli.export.help",
    run=cmd_export,
    options=(
        Option("folder", "folder", positional=True, help_key="cli.export.folder"),
        Option("output", "folder", None, "cli.export.output",
               flags=("-o", "--output", "--ausgabe")),
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
    requires=(
        Requirement(any_of=(external.MUTAGEN, external.FFPROBE)),
        Requirement(any_of=(external.FPCALC,), when="fingerprint"),
    ),
)
