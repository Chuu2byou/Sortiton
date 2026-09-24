# Contributing

There is no formal process. If you plan something bigger than a bug fix, an
issue first saves us both a rewrite; small patches can go straight in.

## Getting started

```bash
git clone https://github.com/Chuu2byou/Sortiton.git
cd Sortiton
pip install -r requirements-dev.txt     # lint, freeze, security tools
python3 sortiton.py scan ~/Music        # command line
python3 sortiton_gui.py                 # window
```

The runtime dependency stays `mutagen` (optional, `requirements.txt`); the
development tools live in `requirements-dev.txt`.

## Checks

```bash
tools/checks.sh                # every check, summary at the end
tools/screenshot.sh            # regenerate the README screenshot
tools/build_app.sh             # freeze the program (tar.gz, --appimage)
```

`tools/checks.sh` runs all steps on its own and ends with a line like
`checks: 12 passed, 0 failed, 0 skipped`. The steps are:

```bash
python3 -m compileall -q $(git ls-files '*.py')   # syntax
python3 -c "import sortiton, sortiton.cli, sortiton.gui.app"
python3 tests/smoke.py
xvfb-run -a python3 tests/smoke.py                # with a display: GUI too
python3 sortiton.py --help
python3 sortiton.py rules --builtin
pylint sortiton sortiton_gui.py tests tools
pylint sortiton.py
bandit -r sortiton sortiton.py sortiton_gui.py tests tools -ll
pip-audit -r requirements.txt -r requirements-dev.txt --strict
detect-secrets scan  # exit is always 0; checks.sh inspects the report instead
npx markdownlint-cli2 README.md CONTRIBUTING.md
```

Without a display the GUI part of the smoke test is skipped, and the closing
line says so.

Notes:

- Lint the package and the entry script in **two** calls
  (`pylint sortiton sortiton_gui.py tests tools` and `pylint sortiton.py`).
  Otherwise astroid resolves the name `sortiton` to the script `sortiton.py`
  and complains about a missing `__all__` in every `from . import …` line.
- `.pylintrc` disables warnings, conventions and refactorings (errors only), so
  naming and dead code are not checked.
- Markdown prose stays at 80 columns; tables and code blocks are exempt.
- CI: `.github/workflows/pylint.yml` on Python 3.8 / 3.9 / 3.10.
- Security: `.github/workflows/security.yml` runs bandit at medium severity and
  above, pip-audit over both requirement files and detect-secrets. No CodeQL -
  code scanning is not available for private repositories, so the tools report
  into the job log. Both workflows ask for `contents: read`; only the release
  job writes.

## Layout

The scripts in the main folder are entry points; the logic lives in the
`sortiton/` package.

| File | Description |
| --- | --- |
| `sortiton.py` | **CLI entry point** (`tags` / `rename` / `sort` / `all` / `scan` / `rules` / `restore`) |
| `sortiton_gui.py` | **GUI entry point** (checks Tkinter, starts the interface) |
| `sortiton/config.py` | Constants and paths (project folder, `logs/`, `my_rules.ini`, `settings.ini`) |
| `sortiton/i18n.py` | Translations - every visible text lives here |
| `sortiton/settings.py` | User settings (`settings.ini`) |
| `sortiton/output.py` | Console/GUI output, progress, log file |
| `sortiton/journal.py` | Run journal: what a run changed, the basis for `restore` |
| `sortiton/rules.py` | Rule tables, `my_rules.ini`, text cleanup |
| `sortiton/files.py` | File names, target paths, content comparison |
| `sortiton/tags.py` | Read/write tags (mutagen or ffprobe/ffmpeg) |
| `sortiton/tasks.py` | The tasks (`cmd_*`) |
| `sortiton/cli.py` | Command line arguments |
| `sortiton/__init__.py` | Public interface (the stable names) |
| `sortiton/gui/design.py` | Colours and fonts |
| `sortiton/gui/widgets.py` | Hand-drawn widgets (buttons, chips, segments, progress bar) |
| `sortiton/gui/panels.py` | Preview card and result panel |
| `sortiton/gui/preferences.py` | Settings window (tag backends, language) |
| `sortiton/gui/confirm.py` | Confirmation with counts and backup switch |
| `sortiton/gui/restore.py` | Undo window (pick a journal, check the plan, undo) |
| `sortiton/gui/dialogs.py` | System dialogs (`kdialog` → `zenity` → Tkinter) |
| `sortiton/gui/app.py` | Window, cards, tasks, language switch |
| `tools/checks.sh` | Runs every check (syntax, imports, smoke test, pylint, security, CLI) |
| `tools/build_app.sh` | Freezes the program for the release (tar.gz, `--appimage`) |
| `packaging/` | AppImage glue: `AppRun` and the `.desktop` entry |
| `tools/screenshot.sh` | Takes the README screenshot on a synthetic demo library |
| `tests/smoke.py` | Smoke test (imports, translations, rules, CLI, GUI) |
| `my_rules.ini` | Your own rules (read automatically) |
| `assets/` | Icons in three colours: `icon*.svg` (source) and `icon*.png`; copy one over `assets/icon.png` to switch, plus the screenshot |
| `requirements.txt` | Optional Python dependency (`mutagen`) |
| `requirements-dev.txt` | Development tools (`pylint`, `pyinstaller`, `bandit`, `pip-audit`, `detect-secrets`) - not needed to run Sortiton |
| `.pylintrc` | Pylint configuration for the CI (errors only) |
| `.markdownlint.jsonc` | markdownlint configuration (allows the `<img>` app icon) |
| `CONTRIBUTING.md` | This file |

### Where to change what

| Goal | File |
| --- | --- |
| Fix your own artist/genre | **`my_rules.ini`** (no code change needed) |
| Extend the built-in rules | `sortiton/rules.py` (`GENRE_ALIASES`, `ARTIST_FIXES`) |
| Change command behaviour | `sortiton/tasks.py` |
| Change a visible text / add a language | `sortiton/i18n.py` |
| Appearance (colours/fonts) | `sortiton/gui/design.py` |
| New command line option | `sortiton/cli.py` |
| New control | `sortiton/gui/widgets.py` |

## Conventions

- Target Python 3.8: no `match`, no `X | Y` at runtime (`Union` instead), no
  `str.removeprefix`, no `Path.is_relative_to`. `from __future__ import
  annotations` is set everywhere.
- Every visible text lives in `sortiton/i18n.py`, in `_EN` **and** `_DE` (keep
  the lines aligned); `tests/smoke.py` enforces both catalogs and every
  `i18n.t("literal")`.
- Never print directly: all output goes through `output.message()`, progress via
  `report_plan()`, `report_stats()` and `_progress()`. The GUI attaches itself
  with `set_logger` / `set_progress` / `set_plan_sink` / `set_stats_sink`.
- The `cmd_*` functions in `sortiton/tasks.py` take an `argparse.Namespace`
  (CLI) or a `SimpleNamespace` (GUI) with the same field names.
- Every user path can be overridden with an environment variable
  (`SORTITON_RULES`, `SORTITON_LOG_DIR`, `SORTITON_SETTINGS`, …).
- A preview is the default and `--apply` writes; existing files stay untouched
  (`sortiton/files.py::free_path()` appends `(2)`, `(3)`, …).
- `sortiton/__init__.py::__all__` is the stable interface; new public names
  belong there (`tests/smoke.py::test_import` checks every name).

## Releasing

The version lives in `sortiton/__init__.py` (`__version__`); the packaging
version in `pyproject.toml` must match (a test keeps the two together). A tag
that matches starts `.github/workflows/release.yml`, which builds the AppImage,
the tar.gz, the wheel and the sdist and hangs them onto the release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

`tools/build_app.sh --appimage` builds the same files on this machine - the way
to see a broken build before pushing the tag. The workflow runs on
ubuntu-22.04: a binary linked against a newer glibc refuses to start on an
older distribution. A manual run (`workflow_dispatch`) only stores the files as
workflow artifacts, without a release.
