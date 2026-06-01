#!/usr/bin/env python3
"""Pre-commit linter runner.

Invoked by git-hooks/pre-commit. Runs the canonical linter set (via
run-linters.py) only when the staged changes include Python/JS code that is
neither docs-only nor a VERSION-string-only bump.
"""
import re
import subprocess  # nosec B404
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# pylint: disable=wrong-import-position  # imports below need repo root on sys.path (set above)
from common_av.linters_defs import CANONICAL_LINTER_TOOLS  # noqa: E402
from project_defs import EXCLUDED_DIRS  # noqa: E402

CODE_SUFFIXES = {'.py', '.js'}
_VERSION_LINE = re.compile(r'^[+-]\s*VERSION\s*=')


def _staged_code_files() -> list[str]:
    """Return staged .py/.js files (added/copied/modified/renamed/deleted), excluding EXCLUDED_DIRS."""
    out = subprocess.run(  # nosec B603 B607
        ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMRD'],
        capture_output=True, encoding='utf-8', errors='replace', check=True,
    ).stdout
    files = []
    for raw in out.splitlines():
        name = raw.strip()
        if not name:
            continue
        path = Path(name)
        if path.suffix.lower() not in CODE_SUFFIXES:
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        files.append(name)
    return files


def _only_version_changes(code_files: list[str]) -> bool:
    """Return True if every staged content change in code_files touches only a VERSION= line."""
    out = subprocess.run(  # nosec B603 B607
        ['git', 'diff', '--cached', '-U0', '--', *code_files],
        capture_output=True, encoding='utf-8', errors='replace', check=True,
    ).stdout
    saw_change = False
    for line in out.splitlines():
        if line[:3] in ('+++', '---') or line.startswith('@@'):
            continue
        if line and line[0] in '+-':
            saw_change = True
            if not _VERSION_LINE.match(line):
                return False
    return saw_change


def main() -> int:
    """Lint staged code when warranted; return the process exit code."""
    code_files = _staged_code_files()
    if not code_files:
        print('pre-commit: docs-only change; skipping linters.')
        return 0
    if _only_version_changes(code_files=code_files):
        print('pre-commit: VERSION-only change; skipping linters.')
        return 0

    failed = []
    for tool in CANONICAL_LINTER_TOOLS:
        result = subprocess.run(  # nosec B603
            [sys.executable, 'run-linters.py', '--tool', tool],
            capture_output=True, encoding='utf-8', errors='replace', check=False,
        )
        if result.returncode == 0:
            print(f'[{tool}] PASS')
            continue
        failed.append(tool)
        print(f'[{tool}] FAIL')
        details = ((result.stdout or '') + (result.stderr or '')).rstrip()
        if details:
            print(details)

    if failed:
        sys.stdout.flush()  # ensure per-tool output precedes the stderr summary
        print(f"pre-commit: linters FAILED: {', '.join(failed)}", file=sys.stderr)
        print("pre-commit: fix the issues, or bypass with 'git commit --no-verify'.", file=sys.stderr)
        return 1
    print('pre-commit: all linters passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
