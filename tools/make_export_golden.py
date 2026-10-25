#!/usr/bin/env python3
"""Build the golden reference output of the old ``musik_export.py``.

    python3 tools/make_export_golden.py --reference musik_export.py
    python3 tools/make_export_golden.py            # uses the committed copy

Runs the old, read-only export script on the committed fixture library
(``tests/fixtures/export_library``) and stores its output as the golden
reference for the export feature (step 0.3 of ``PLAN_export_integration.md``).

Two lines differ on every machine and run - the absolute source folder and the
creation timestamp - and are replaced by fixed placeholders through
``normalize_export_text`` before the files are stored.  Everything else stays
byte-exact.

Variant A (plain) lands in ``tests/golden/export/base``; variant B (the same
invocation plus ``--gross-klein``) in ``tests/golden/export/case``, where only
``01_*`` and ``02_*`` are kept.  A fingerprint run gets no byte-golden on
purpose: fpcalc versions produce different fingerprints (steps 0.3 and 1.9).

The reference must be built with ``mutagen`` installed, otherwise the old
script takes the slower ffprobe path.  The run happens in a throwaway
``XDG_CACHE_HOME`` so the real fingerprint cache of the user stays untouched.

**Legacy only:** the committed ``02_*`` goldens now also contain Sortiton's
own cover section (cover files and missing embedded covers), which the old
script does not produce.  Re-running this generator therefore removes that
section; only use it to inspect the historical reference, not to refresh the
current goldens.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]

# Which files of a run are stored per variant; an empty tuple keeps all of them.
KEEP_ALL: tuple[str, ...] = ()
KEEP_CASE = ("01_", "02_")


def _load_helper() -> ModuleType:
    """Load ``tests/export_golden.py`` by path (it is not an installed module)."""
    path = ROOT / "tests" / "export_golden.py"
    spec = importlib.util.spec_from_file_location("export_golden", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"error: cannot load helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def materialize_reference(explicit: str | None) -> tuple[Path, Path | None]:
    """Return the old script to run and, when it had to be written, its temp dir."""
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise SystemExit(f"error: reference script not found: {path}")
        return path, None
    local = ROOT / "musik_export.py"
    if local.is_file():
        return local, None
    # The script may already be gone from the working tree - take the committed
    # copy, so the reference stays rebuildable from a later commit as well.
    tmpdir = Path(tempfile.mkdtemp(prefix="export-golden-ref-"))
    script = tmpdir / "musik_export.py"
    result = subprocess.run(
        ["git", "-C", str(ROOT), "show", "HEAD:musik_export.py"],
        capture_output=True, text=True, encoding="utf-8", check=False)
    if result.returncode != 0 or not result.stdout:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise SystemExit("error: musik_export.py is neither in the working tree "
                         "nor in git history - pass --reference")
    script.write_text(result.stdout, encoding="utf-8")
    return script, tmpdir


def run_variant(python: str, script: Path, fixture: Path, outdir: Path,
                cache: Path, extra: tuple[str, ...]) -> None:
    """Run the old script once; abort with a clear message on a non-zero exit."""
    outdir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["XDG_CACHE_HOME"] = str(cache)      # keep the user's fingerprint cache out
    env["LC_ALL"] = "C.UTF-8"
    command = [python, str(script), str(fixture), "-o", str(outdir), *extra]
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding="utf-8", env=env, timeout=600, check=False)
    if result.returncode != 0:
        lines = (result.stderr or result.stdout or "").strip().splitlines()
        raise SystemExit(f"error: reference run failed (exit {result.returncode}): "
                         f"{lines[-1] if lines else 'no output'}")


def store(source: Path, target: Path, keep: tuple[str, ...], normalize) -> list[str]:
    """Write the normalized files of ``source`` into ``target``; list the names."""
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    names: list[str] = []
    for path in sorted(source.iterdir()):
        if not path.is_file():
            continue
        if keep and not path.name.startswith(keep):
            continue
        text = path.read_text(encoding="utf-8")
        (target / path.name).write_text(normalize(text), encoding="utf-8")
        names.append(path.name)
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the golden reference output of the old musik_export.py.")
    parser.add_argument("--reference",
                        help="path to the old musik_export.py "
                             "(default: the working-tree copy, else HEAD via git show)")
    parser.add_argument("--fixture", type=Path,
                        help="library to analyse (default: tests/fixtures/export_library)")
    parser.add_argument("--out", type=Path,
                        help="where to store the golden trees (default: tests/golden/export)")
    args = parser.parse_args(argv)

    print("warning: legacy reference only; this removes the cover section "
          "from the committed 02_* goldens.", file=sys.stderr)
    golden = _load_helper()
    fixture = (args.fixture or golden.FIXTURE_DIR).expanduser().resolve()
    out = (args.out or golden.GOLDEN_DIR).expanduser().resolve()
    if not fixture.is_dir():
        print(f"error: fixture library not found: {fixture}", file=sys.stderr)
        return 2

    script, script_tmp = materialize_reference(args.reference)
    work = Path(tempfile.mkdtemp(prefix="export-golden-"))
    try:
        cache = work / "cache"
        base_src, case_src = work / "base", work / "case"
        run_variant(sys.executable, script, fixture, base_src, cache,
                    golden.BASE_ARGS)
        run_variant(sys.executable, script, fixture, case_src, cache,
                    golden.CASE_ARGS)
        base_names = store(base_src, out / "base", KEEP_ALL,
                           golden.normalize_export_text)
        case_names = store(case_src, out / "case", KEEP_CASE,
                           golden.normalize_export_text)
    finally:
        shutil.rmtree(work, ignore_errors=True)
        if script_tmp is not None:
            shutil.rmtree(script_tmp, ignore_errors=True)

    print(f"reference: {script}")
    print(f"fixture:   {fixture}")
    for label, names in (("base", base_names), ("case", case_names)):
        print(f"{label}: {len(names)} file(s) -> {out / label}")
        for name in names:
            print(f"  {name}")
    print("RESULT: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
