#!/usr/bin/env bash
# Every check of the project in one run.
#
#   tools/checks.sh
#
# Syntax, imports, the smoke test, pylint, a short CLI run and the security
# tools. The optional steps (xvfb-run for the GUI, npx for the Markdown) run
# when their tool is installed; when one is missing the script names the
# package that brings it instead of failing.
#
# Everything happens in the project folder and a temp dir - your own settings,
# rules, logs and backups stay untouched.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# The project venv when it exists - pylint and the rest live there, and this way
# nothing has to be activated first.
if [ -x "$ROOT/.venv/bin/python3" ]; then
    PATH="$ROOT/.venv/bin:$PATH"
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/sortiton-checks-XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# Keep the CLI runs away from the real settings, rules and logs.
export SORTITON_SETTINGS="$WORK/settings.ini"
export SORTITON_RULES="$WORK/my_rules.ini"
export SORTITON_LOG_DIR="$WORK/logs"
export SORTITON_BACKUP_DIR="$WORK/backups"
unset SORTITON_LANG

passed=0
failed=0
skipped=0

have() {
    command -v "$1" >/dev/null 2>&1
}

# Every Python file of the project. --others also picks up files that are not
# committed yet (a new module gets checked right away), --exclude-standard keeps
# .venv out. In a clean checkout this equals `git ls-files`.
py_files() {
    git ls-files --cached --others --exclude-standard '*.py'
}

run() {
    local name="$1"
    shift
    printf '\n== %s ==\n' "$name"
    if "$@"; then
        printf '   ok: %s\n' "$name"
        passed=$((passed + 1))
    else
        printf '   FAILED: %s\n' "$name"
        failed=$((failed + 1))
    fi
}

skip() {
    local name="$1"
    local reason="$2"
    printf '\n== %s ==\n' "$name"
    printf '   SKIPPED: %s\n' "$reason"
    skipped=$((skipped + 1))
}

# detect-secrets itself never fails - hence this wrapper.
secrets_scan() {
    detect-secrets scan > "$WORK/secrets.json" || return 1
    python3 - "$WORK/secrets.json" <<'PY'
import json
import sys

findings = json.load(open(sys.argv[1], encoding="utf-8"))["results"]
for path, items in sorted(findings.items()):
    print("   %s: %s" % (path, ", ".join(item["type"] for item in items)))
print("   %d file(s) with findings" % len(findings))
sys.exit(1 if findings else 0)
PY
}

run "syntax (compileall)" python3 -m compileall -q $(py_files)
run "imports" python3 -c "import sortiton, sortiton.cli, sortiton.gui.app"
run "smoke test (tests/smoke.py)" python3 tests/smoke.py
run "cli: --help" python3 sortiton.py --help
run "cli: rules --builtin" python3 sortiton.py rules --builtin

if have pylint; then
    # Two runs: astroid mixes sortiton.py and sortiton/ up when both are in one
    # invocation (E0611). The long version is in CONTRIBUTING.md.
    run "pylint (package, gui, tests, tools)" pylint sortiton sortiton_gui.py tests tools
    run "pylint (entry script)" pylint sortiton.py
else
    skip "pylint" "not installed - run: pip install -r requirements-dev.txt"
fi

if have bandit; then
    # -ll = medium and above. The low findings are the subprocess calls and
    # try/except-pass blocks the program is built from, so they stay unreported.
    run "bandit (source)" bandit -r sortiton sortiton.py sortiton_gui.py tests tools -ll
else
    skip "bandit" "not installed - run: pip install -r requirements-dev.txt"
fi

if have pip-audit; then
    # Talks to the PyPI advisory database, so it needs the network.
    run "pip-audit (dependencies)" pip-audit -r requirements.txt -r requirements-dev.txt --strict
else
    skip "pip-audit" "not installed - run: pip install -r requirements-dev.txt"
fi

if have detect-secrets; then
    run "detect-secrets (credentials)" secrets_scan
else
    skip "detect-secrets" "not installed - run: pip install -r requirements-dev.txt"
fi

if have xvfb-run; then
    run "gui checks (xvfb-run)" xvfb-run -a python3 tests/smoke.py
else
    skip "gui checks (xvfb-run)" "xvfb-run not installed - Arch: sudo pacman -S xorg-server-xvfb"
fi

if have npx; then
    run "markdownlint" npx --yes markdownlint-cli2 README.md CONTRIBUTING.md
else
    skip "markdownlint" "npx not installed - install nodejs"
fi

printf '\n%s\n' "=============================================================="
printf 'checks: %d passed, %d failed, %d skipped\n' "$passed" "$failed" "$skipped"
if [ "$skipped" -gt 0 ]; then
    printf 'note: skipped checks did not run - see the SKIPPED lines above\n'
fi
if [ "$failed" -gt 0 ]; then
    printf 'RESULT: FAILED\n'
    exit 1
fi
printf 'RESULT: ok\n'
