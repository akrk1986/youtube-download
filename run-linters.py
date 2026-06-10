"""Linting orchestration script.

Run a single linter tool by name. Designed to be called by Claude sub-agents in parallel.
Generic machinery lives in ``common_linters.linters_funcs``; this script only defines the
project-specific tool set and per-tool commands.

Usage:
    python run-linters.py --tool <name>                  Run a single tool (raw output)
    python run-linters.py --tool <name> --group-by-files Run one tool, group output by file
    python run-linters.py --group-by-files               Run all tools, group output by file
    python run-linters.py --list                         Print all tool names (one per line)
    python run-linters.py                                Run all tools (raw output, radon excluded)
"""

import re
import sys
from pathlib import Path

from common_linters.linters_defs import LINTER_TOOLS
from common_linters.linters_funcs import collect_py_files, main
from project_defs import EXCLUDED_DIRS

# Filter the shared superset to the tools this repo runs.
_FULLY_EXCLUDED: frozenset[str] = frozenset({'deadcode'})  # not used in this repo
_DEFAULT_SKIP: frozenset[str] = frozenset({'skylos'})       # slow; opt-in via --tool skylos only

TOOLS = [t for t in LINTER_TOOLS if t not in _FULLY_EXCLUDED and t not in _DEFAULT_SKIP]

# skylos (slow) and radon/freshness (informational) are excluded from default runs; all stay
# opt-in via --tool <name>. freshness: `pip list --outdated` (needs network, never blocks).
ALL_TOOLS = TOOLS + ['skylos', 'radon', 'freshness']


# pylint: disable-next=too-many-branches,too-many-return-statements
def build_cmd(name: str, root: Path) -> tuple[list[str], bool]:
    """Return (command_args, always_pass) for the given tool name."""
    if name == 'ruff':
        return ['ruff', 'check', '.'], False
    if name == 'mypy':
        return ['mypy', '.'], False
    if name == 'ty':
        cmd = ['ty', 'check', '--output-format=concise']
        for ex in EXCLUDED_DIRS + ['Tests', 'Tests-Standalone']:
            cmd.extend(['--exclude', ex])
        return cmd, False
    if name == 'bandit':
        return ['bandit', '-r', '.', '-c', 'pyproject.toml'], False
    if name == 'pip-audit':
        # --skip-editable skips common-av (local editable install not on PyPI) and surfaces
        # the skip in the output. --strict is dropped because it treats --skip-editable
        # skips as failures.
        return ['pip-audit', '--skip-editable'], False
    if name == 'deptry':
        return ['deptry', '.', '--no-ansi'], False
    if name == 'pydoclint':
        # Tests/ and Tests-Standalone/ excluded: pytest fixtures/patterns, split pending
        extra = ['Tests', 'Tests-Standalone']
        exclude_pattern = '|'.join(re.escape(d) for d in EXCLUDED_DIRS + extra)
        return ['pydoclint', '--config=pyproject.toml', f'--exclude={exclude_pattern}', '.'], False
    if name == 'pylint':
        # Tests/ and Tests-Standalone excluded: pytest patterns confuse pylint, split pending
        ignore_str = ','.join(EXCLUDED_DIRS + ['Tests', 'Tests-Standalone'])
        return ['pylint', '.', f'--ignore={ignore_str}'], False
    if name == 'vulture':
        exclude_str = ','.join(EXCLUDED_DIRS)
        return ['vulture', '.', '--exclude', exclude_str, '--min-confidence', '80'], False
    if name == 'skylos':
        cmd = ['skylos', '.', '--category', 'dead_code', '--format', 'concise', '--baseline']
        for folder in EXCLUDED_DIRS + ['JS-files']:
            cmd.extend(['--exclude-folder', folder])
        return cmd, False
    if name == 'radon':
        return ['radon', 'cc', '.', '-n', 'C', '--exclude', '*.venv*,Beta/*'], True
    if name == 'freshness':
        # Informational: list installed packages with a newer (stable) release on PyPI. Mirrors what
        # `pip-compile --upgrade` can actually move (pre-releases excluded). always_pass=True.
        return [sys.executable, '-m', 'pip', 'list', '--outdated'], True
    if name == 'pyupgrade':
        py_files = collect_py_files(root, EXCLUDED_DIRS)
        return ['pyupgrade', '--py311-plus'] + py_files, False
    if name == 'eslint':
        return ['node', str(root / 'node_modules' / 'eslint' / 'bin' / 'eslint.js'), 'JS-files/'], False
    if name == 'jshint':
        return ['node', str(root / 'node_modules' / 'jshint' / 'bin' / 'jshint'), 'JS-files/'], False
    raise ValueError(f'Unknown tool: {name}')


if __name__ == '__main__':
    main(root=Path(__file__).parent.resolve(), tools=TOOLS, all_tools=ALL_TOOLS,
         build_cmd=build_cmd, excluded_dirs=EXCLUDED_DIRS)
