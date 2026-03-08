"""Linting orchestration script.

Run a single linter tool by name. Designed to be called by Claude sub-agents in parallel.

Usage:
    python run-linters.py --tool <name>   Run a single tool
    python run-linters.py --list          Print all tool names (one per line)
    python run-linters.py                 Print usage
"""

import argparse
import subprocess
import sys
from pathlib import Path


EXCLUDED_DIRS = [
    '.venv-linux', '.venv-3.14', '.venv-windows', '.venv',
    'Beta', 'node_modules', '.git', '.idea', '.pytest_cache', '.mypy_cache',
]

TOOLS = [
    'ruff', 'mypy', 'bandit', 'pydoclint', 'pylint',
    'vulture', 'radon', 'pyupgrade', 'eslint', 'jshint',
]


def _collect_py_files(root: Path, excluded: list[str]) -> list[str]:
    """Collect all .py files outside excluded directories."""
    files = []
    for f in root.rglob('*.py'):
        parts = f.parts
        if any(ex in parts for ex in excluded):
            continue
        files.append(str(f))
    return sorted(files)


def _run_tool(name: str, cmd: list[str], cwd: Path, always_pass: bool = False) -> int:
    """Run a tool command and print its output. Return exit code."""
    print(f'=== {name} ===')
    print(f'Command: {" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.stdout:
        print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, end='', file=sys.stderr)
    if always_pass:
        print(f'[{name}] exit 0 (informational)')
        return 0
    rc = result.returncode
    status = 'PASS' if rc == 0 else f'FAIL (exit {rc})'
    print(f'[{name}] {status}')
    return rc


def run_ruff(root: Path) -> int:
    """Run ruff check."""
    return _run_tool('ruff', ['ruff', 'check', '.'], cwd=root)


def run_mypy(root: Path) -> int:
    """Run mypy."""
    return _run_tool('mypy', ['mypy', '.'], cwd=root)


def run_bandit(root: Path) -> int:
    """Run bandit security scanner."""
    exclude_str = ','.join([
        '.venv-linux', '.venv-3.14', '.venv-windows', '.venv',
        'Beta', 'Tests-Standalone', 'node_modules',
    ])
    cmd = ['bandit', '-r', '.', '-x', exclude_str, '--skip', 'B101']
    return _run_tool('bandit', cmd, cwd=root)


def run_pydoclint(root: Path) -> int:
    """Run pydoclint docstring linter."""
    targets = [
        'funcs_for_main_yt_dlp/', 'funcs_video_info/', 'funcs_utils/',
        'funcs_audio_processing/', 'funcs_audio_tag_handlers/',
        'funcs_for_audio_utils/', 'funcs_notifications/',
        'main-yt-dlp.py', 'main-get-artists-from-trello.py',
    ]
    existing = [t for t in targets if (root / t).exists()]
    cmd = ['pydoclint', '--config=pyproject.toml'] + existing
    return _run_tool('pydoclint', cmd, cwd=root)


def run_pylint(root: Path) -> int:
    """Run pylint."""
    targets = [
        'funcs_for_main_yt_dlp/', 'funcs_video_info/', 'funcs_utils/',
        'funcs_audio_processing/', 'funcs_audio_tag_handlers/',
        'funcs_for_audio_utils/', 'funcs_notifications/',
        'main-yt-dlp.py', 'main-get-artists-from-trello.py',
    ]
    existing = [t for t in targets if (root / t).exists()]
    cmd = ['pylint'] + existing + ['--ignore=Beta']
    return _run_tool('pylint', cmd, cwd=root)


def run_vulture(root: Path) -> int:
    """Run vulture dead code finder."""
    exclude_str = ','.join(['.venv-linux', '.venv-3.14', '.venv-windows', '.venv', 'Beta', 'node_modules'])
    cmd = ['vulture', '.', '--exclude', exclude_str, '--min-confidence', '80']
    return _run_tool('vulture', cmd, cwd=root)


def run_radon(root: Path) -> int:
    """Run radon complexity checker (informational only, always exits 0)."""
    cmd = ['radon', 'cc', '.', '-n', 'C', '--exclude', '*.venv*,Beta/*']
    return _run_tool('radon', cmd, cwd=root, always_pass=True)


def run_pyupgrade(root: Path) -> int:
    """Run pyupgrade and check for modifications via git diff."""
    print('=== pyupgrade ===')
    py_files = _collect_py_files(root, EXCLUDED_DIRS)
    if not py_files:
        print('[pyupgrade] No .py files found')
        return 0
    print(f'Command: pyupgrade --py311-plus <{len(py_files)} files>')
    result = subprocess.run(['pyupgrade', '--py311-plus'] + py_files, capture_output=True, text=True, cwd=root)
    if result.stdout:
        print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, end='', file=sys.stderr)

    # Check if any files were modified
    diff_result = subprocess.run(['git', 'diff', '--exit-code'], capture_output=True, text=True, cwd=root)
    if diff_result.returncode != 0:
        print('pyupgrade modified the following files (review and commit):')
        print(diff_result.stdout, end='')
        print('[pyupgrade] FAIL (files were modified)')
        return 1
    print('[pyupgrade] PASS')
    return 0


def run_eslint(root: Path) -> int:
    """Run eslint on JS-files/ directory."""
    return _run_tool('eslint', ['npx', 'eslint', 'JS-files/'], cwd=root)


def run_jshint(root: Path) -> int:
    """Run jshint on JS-files/ directory."""
    return _run_tool('jshint', ['npx', 'jshint', 'JS-files/'], cwd=root)


_TOOL_RUNNERS = {
    'ruff': run_ruff,
    'mypy': run_mypy,
    'bandit': run_bandit,
    'pydoclint': run_pydoclint,
    'pylint': run_pylint,
    'vulture': run_vulture,
    'radon': run_radon,
    'pyupgrade': run_pyupgrade,
    'eslint': run_eslint,
    'jshint': run_jshint,
}


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description='Run a single linter tool by name.')
    parser.add_argument('--tool', choices=TOOLS, metavar='TOOL', help='Tool to run (use --list to see available tools)')
    parser.add_argument('--list', action='store_true', help='Print all available tool names')
    args = parser.parse_args()

    if args.list:
        for tool in TOOLS:
            print(tool)
        sys.exit(0)

    if not args.tool:
        parser.print_help()
        sys.exit(0)

    root = Path(__file__).parent.resolve()
    runner = _TOOL_RUNNERS[args.tool]
    rc = runner(root)
    sys.exit(rc)


if __name__ == '__main__':
    main()
