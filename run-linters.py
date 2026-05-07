"""Linting orchestration script.

Run a single linter tool by name. Designed to be called by Claude sub-agents in parallel.

Usage:
    python run-linters.py --tool <name>                  Run a single tool (raw output)
    python run-linters.py --tool <name> --group-by-files Run one tool, group output by file
    python run-linters.py --group-by-files               Run all tools, group output by file
    python run-linters.py --list                         Print all tool names (one per line)
    python run-linters.py                                Run all tools (raw output, radon excluded)
"""

import argparse
import hashlib
import re
import subprocess  # nosec B404
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from project_defs import EXCLUDED_DIRS

TOOLS = [
    'ruff', 'mypy', 'ty', 'bandit', 'pip-audit', 'deptry', 'pydoclint', 'pylint',
    'vulture', 'skylos', 'pyupgrade', 'eslint', 'jshint',
]

# radon is informational only; excluded from default runs, opt-in via --tool radon or --with-radon
ALL_TOOLS = TOOLS + ['radon']

# Pre-run file hashes for pyupgrade change detection (populated by run_pyupgrade)
_PYUPGRADE_PRE_HASHES: dict[str, str] = {}


@dataclass
class Issue:
    """A single linting issue attributed to a source file."""

    filename: str   # relative path, e.g. "funcs_utils/foo.py"; "(no file)" if unattributable
    tool: str       # e.g. "ruff"
    text: str       # full issue block (may be multi-line, stripped)


def _collect_py_files(root: Path, excluded: list[str]) -> list[str]:
    """Collect all .py files outside excluded directories."""
    files = []
    for f in root.rglob('*.py'):
        parts = f.parts
        if any(ex in parts for ex in excluded):
            continue
        files.append(str(f))
    return sorted(files)


def _has_js_files(root: Path) -> bool:
    """Return True if any .js files exist outside excluded directories."""
    for f in root.rglob('*.js'):
        if not any(ex in f.parts for ex in EXCLUDED_DIRS):
            return True
    return False


def _build_cmd(name: str, root: Path) -> tuple[list[str], bool]:  # pylint: disable=too-many-branches,too-many-return-statements
    """Return (command_args, always_pass) for the given tool name."""
    if name == 'ruff':
        return ['ruff', 'check', '.'], False
    if name == 'mypy':
        return ['mypy', '.'], False
    if name == 'ty':
        cmd = ['ty', 'check', '--output-format=concise']
        for ex in EXCLUDED_DIRS + ['Tests-Standalone']:
            cmd.extend(['--exclude', ex])
        return cmd, False
    if name == 'bandit':
        return ['bandit', '-r', '.', '-c', 'pyproject.toml'], False
    if name == 'pip-audit':
        return ['pip-audit', '--strict'], False
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
        cmd = ['skylos', '.', '--category', 'dead_code', '--format', 'concise']
        for folder in EXCLUDED_DIRS:
            cmd.extend(['--exclude-folder', folder])
        return cmd, False
    if name == 'radon':
        return ['radon', 'cc', '.', '-n', 'C', '--exclude', '*.venv*,Beta/*'], True
    if name == 'pyupgrade':
        py_files = _collect_py_files(root, EXCLUDED_DIRS)
        return ['pyupgrade', '--py311-plus'] + py_files, False
    if name == 'eslint':
        return ['node', str(root / 'node_modules' / 'eslint' / 'bin' / 'eslint.js'), 'JS-files/'], False
    if name == 'jshint':
        return ['node', str(root / 'node_modules' / 'jshint' / 'bin' / 'jshint'), 'JS-files/'], False
    raise ValueError(f'Unknown tool: {name}')


def _run_tool(name: str, cmd: list[str], cwd: Path, always_pass: bool = False) -> int:
    """Run a tool command and print its output. Return exit code."""
    print(f'=== {name} ===')
    print(f'Command: {" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, check=False)  # nosec B603
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


def _run_tool_capture(_name: str, cmd: list[str], cwd: Path, always_pass: bool = False) -> tuple[int, str]:
    """Run a tool command and return (exit_code, combined_output). stdout + stderr combined."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, check=False)  # nosec B603
    output = result.stdout
    if result.stderr:
        output = output + result.stderr
    if always_pass:
        return 0, output
    return result.returncode, output


def _parse_line_colon(output: str, tool: str, _root: Path) -> list[Issue]:
    """Parse output where issues start with 'path/to/file.ext:line' (mypy, pylint, vulture, pydoclint, jshint)."""
    issues = []
    pattern = re.compile(r'^([\w./\-]+\.(py|js)):')
    for line in output.splitlines():
        m = pattern.match(line)
        if m:
            issues.append(Issue(filename=m.group(1), tool=tool, text=line.strip()))
        elif line.strip():
            issues.append(Issue(filename='(no file)', tool=tool, text=line.strip()))
    return issues


def _parse_ruff(output: str, tool: str, _root: Path) -> list[Issue]:
    """Parse ruff output, handling both 'file:line:col: code' and '  --> file:line' formats."""
    issues = []
    arrow_pattern = re.compile(r'^\s+-->\s+([\w./\-]+\.py):(\d+)')
    line_pattern = re.compile(r'^([\w./\-]+\.(py|js)):')
    lines = output.splitlines()
    for i, line in enumerate(lines):
        m_arrow = arrow_pattern.match(line)
        if m_arrow:
            filename = m_arrow.group(1)
            rule_line = lines[i - 1].strip() if i > 0 else ''
            text = f'{rule_line}\n  {line.strip()}' if rule_line else line.strip()
            issues.append(Issue(filename=filename, tool=tool, text=text))
        elif line_pattern.match(line):
            m = line_pattern.match(line)
            assert m is not None
            issues.append(Issue(filename=m.group(1), tool=tool, text=line.strip()))
        elif line.strip():
            issues.append(Issue(filename='(no file)', tool=tool, text=line.strip()))
    return issues


def _parse_pip_audit(output: str, tool: str, _root: Path) -> list[Issue]:
    """Parse pip-audit tabular output. Each vuln row becomes an Issue with no file attribution."""
    issues = []
    in_table = False
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('---'):
            in_table = True
            continue
        if in_table:
            issues.append(Issue(filename='(no file)', tool=tool, text=stripped))
        elif stripped.startswith('Found ') or stripped.startswith('No known'):
            issues.append(Issue(filename='(no file)', tool=tool, text=stripped))
    return issues


def _parse_deptry(output: str, tool: str, _root: Path) -> list[Issue]:
    """Parse deptry output. Issues are file:line:col: DEP00x format; success message forwarded."""
    issues = []
    file_pattern = re.compile(r'^([\w./\-]+\.py):')
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('Scanning '):
            continue
        m = file_pattern.match(line)
        if m:
            issues.append(Issue(filename=m.group(1), tool=tool, text=stripped))
        else:
            issues.append(Issue(filename='(no file)', tool=tool, text=stripped))
    return issues


def _parse_bandit(output: str, tool: str, _root: Path) -> list[Issue]:
    """Parse bandit output. Issues start with '>> Issue:' and end with a 'Location:' line."""
    issues = []
    location_pattern = re.compile(r'^\s+Location:\s+\.?/?([\w./\-]+\.py):\d+')
    block: list[str] = []
    for line in output.splitlines():
        if '>> Issue:' in line:
            block = [line.strip()]
        elif block:
            block.append(line.strip())
            m = location_pattern.match(line)
            if m:
                issues.append(Issue(filename=m.group(1), tool=tool, text='\n'.join(block)))
                block = []
    return issues


def _parse_radon(output: str, tool: str, _root: Path) -> list[Issue]:
    """Parse radon output. Bare filename lines followed by indented complexity lines."""
    issues = []
    file_pattern = re.compile(r'^([\w./\-]+\.py)\s*$')
    current_file = '(no file)'
    for line in output.splitlines():
        if not line[:1].isspace() and file_pattern.match(line):
            current_file = line.strip()
        elif line[:1].isspace() and line.strip():
            issues.append(Issue(filename=current_file, tool=tool, text=line.strip()))
        elif line.strip():
            issues.append(Issue(filename='(no file)', tool=tool, text=line.strip()))
    return issues


def _parse_eslint(output: str, tool: str, root: Path) -> list[Issue]:
    """Parse eslint output. Filename lines (absolute or relative .js) followed by indented issues."""
    issues = []
    # Match absolute paths or relative paths ending in .js, not indented
    file_pattern = re.compile(r'^(/[\w./\- ]+\.js|[\w./\-]+\.js)\s*$')
    current_file = '(no file)'
    for line in output.splitlines():
        if not line[:1].isspace() and file_pattern.match(line.strip()):
            filepath = Path(line.strip())
            try:
                current_file = str(filepath.relative_to(root))
            except ValueError:
                current_file = line.strip()
        elif line[:1].isspace() and line.strip():
            issues.append(Issue(filename=current_file, tool=tool, text=line.strip()))
        elif line.strip():
            issues.append(Issue(filename='(no file)', tool=tool, text=line.strip()))
    return issues


def _hash_files(files: list[str]) -> dict[str, str]:
    """Return a mapping of filepath -> MD5 hash for the given files."""
    hashes = {}
    for path in files:
        try:
            hashes[path] = hashlib.md5(Path(path).read_bytes()).hexdigest()  # nosec B324
        except OSError:
            pass
    return hashes


def _parse_pyupgrade(_output: str, tool: str, root: Path) -> list[Issue]:
    """Parse pyupgrade result using pre/post file hashes to detect modifications."""
    # Hashes were captured before pyupgrade ran; compare to current state
    py_files = _collect_py_files(root, EXCLUDED_DIRS)
    issues = []
    for path in py_files:
        try:
            current_hash = hashlib.md5(Path(path).read_bytes()).hexdigest()  # nosec B324
            rel = str(Path(path).relative_to(root))
            if _PYUPGRADE_PRE_HASHES.get(path) != current_hash:
                issues.append(Issue(filename=rel, tool=tool, text='modified by pyupgrade (review and commit)'))
        except OSError:
            pass
    return issues


_PARSERS: dict[str, Callable[[str, str, Path], list[Issue]]] = {
    'ruff': _parse_ruff,
    'mypy': _parse_line_colon,
    'ty': _parse_line_colon,
    'bandit': _parse_bandit,
    'pip-audit': _parse_pip_audit,
    'deptry': _parse_deptry,
    'pydoclint': _parse_radon,   # bare filename line, then indented issues (same format as radon)
    'pylint': _parse_line_colon,
    'vulture': _parse_line_colon,
    'skylos': _parse_line_colon,
    'radon': _parse_radon,
    'pyupgrade': _parse_pyupgrade,
    'eslint': _parse_eslint,
    'jshint': _parse_line_colon,
}


def _run_tool_grouped(name: str, root: Path) -> tuple[int, list[Issue]]:
    """Run one tool, parse its output, return (exit_code, issues)."""
    if name in ('eslint', 'jshint') and not _has_js_files(root):
        return 0, []
    cmd, always_pass = _build_cmd(name, root)
    rc, output = _run_tool_capture(name, cmd, root, always_pass)
    parser = _PARSERS[name]
    issues = parser(output, name, root)
    return rc, issues


def _print_grouped_by_files(issues: list[Issue], rc_map: dict[str, int]) -> None:
    """Print issues grouped by source filename, then show a summary."""
    file_issues: dict[str, list[Issue]] = {}
    no_file_issues: list[Issue] = []

    for issue in issues:
        if issue.filename == '(no file)':
            no_file_issues.append(issue)
        else:
            file_issues.setdefault(issue.filename, []).append(issue)

    # Per-file sections
    for filename in sorted(file_issues):
        print(f'\n=== {filename} ===')
        for issue in file_issues[filename]:
            for line in issue.text.splitlines():
                print(f'  [{issue.tool}] {line}')

    # No-file section: unattributable issues + status for tools with no issues at all
    print('\n--- No file-specific issues ---')
    for issue in no_file_issues:
        print(f'  [{issue.tool}] {issue.text}')

    tools_with_any_issue = {i.tool for i in issues}
    for tool in rc_map:
        if tool not in tools_with_any_issue:
            rc = rc_map[tool]
            if tool == 'radon':
                print(f'  [{tool}] exit 0 (informational)')
            elif rc == 0:
                print(f'  [{tool}] PASS')
            else:
                print(f'  [{tool}] FAIL (exit {rc})')

    # Summary
    print('\n--- Summary ---')
    tools_failed = sorted(t for t, rc in rc_map.items() if rc != 0)
    if file_issues:
        problems = ', '.join(tools_failed) if tools_failed else 'none'
        print(f'Files with issues: {len(file_issues)} | Tools that reported problems: {problems}')
    else:
        print('No file-specific issues found.')
        if tools_failed:
            print(f'Tools that reported problems: {", ".join(tools_failed)}')


def run_ruff(root: Path) -> int:
    """Run ruff check."""
    cmd, always_pass = _build_cmd('ruff', root)
    return _run_tool('ruff', cmd, cwd=root, always_pass=always_pass)


def run_mypy(root: Path) -> int:
    """Run mypy."""
    cmd, always_pass = _build_cmd('mypy', root)
    return _run_tool('mypy', cmd, cwd=root, always_pass=always_pass)


def run_ty(root: Path) -> int:
    """Run ty type checker."""
    cmd, always_pass = _build_cmd('ty', root)
    return _run_tool('ty', cmd, cwd=root, always_pass=always_pass)


def run_bandit(root: Path) -> int:
    """Run bandit security scanner."""
    cmd, always_pass = _build_cmd('bandit', root)
    return _run_tool('bandit', cmd, cwd=root, always_pass=always_pass)


def run_pip_audit(root: Path) -> int:
    """Run pip-audit dependency vulnerability scanner."""
    cmd, always_pass = _build_cmd('pip-audit', root)
    return _run_tool('pip-audit', cmd, cwd=root, always_pass=always_pass)


def run_deptry(root: Path) -> int:
    """Run deptry dependency consistency checker."""
    cmd, always_pass = _build_cmd('deptry', root)
    return _run_tool('deptry', cmd, cwd=root, always_pass=always_pass)


def run_pydoclint(root: Path) -> int:
    """Run pydoclint docstring linter."""
    cmd, always_pass = _build_cmd('pydoclint', root)
    return _run_tool('pydoclint', cmd, cwd=root, always_pass=always_pass)


def run_pylint(root: Path) -> int:
    """Run pylint."""
    cmd, always_pass = _build_cmd('pylint', root)
    return _run_tool('pylint', cmd, cwd=root, always_pass=always_pass)


def run_vulture(root: Path) -> int:
    """Run vulture dead code finder."""
    cmd, always_pass = _build_cmd('vulture', root)
    return _run_tool('vulture', cmd, cwd=root, always_pass=always_pass)


def run_skylos(root: Path) -> int:
    """Run skylos dead code scanner."""
    cmd, always_pass = _build_cmd('skylos', root)
    return _run_tool('skylos', cmd, cwd=root, always_pass=always_pass)


def run_radon(root: Path) -> int:
    """Run radon complexity checker (informational only, always exits 0)."""
    cmd, always_pass = _build_cmd('radon', root)
    return _run_tool('radon', cmd, cwd=root, always_pass=always_pass)


def run_pyupgrade(root: Path) -> int:
    """Run pyupgrade and detect modifications by comparing file hashes before and after."""
    global _PYUPGRADE_PRE_HASHES  # pylint: disable=global-statement
    print('=== pyupgrade ===')
    py_files = _collect_py_files(root, EXCLUDED_DIRS)
    if not py_files:
        print('[pyupgrade] No .py files found')
        return 0
    print(f'Command: pyupgrade --py311-plus <{len(py_files)} files>')
    _PYUPGRADE_PRE_HASHES = _hash_files(py_files)
    result = subprocess.run(  # nosec B603
        ['pyupgrade', '--py311-plus'] + py_files, capture_output=True, text=True, cwd=root, check=False,
    )
    if result.stdout:
        print(result.stdout, end='')
    if result.stderr:
        print(result.stderr, end='', file=sys.stderr)

    modified = [
        str(Path(f).relative_to(root))
        for f in py_files
        if _hash_files([f]).get(f) != _PYUPGRADE_PRE_HASHES.get(f)
    ]
    if modified:
        print('pyupgrade modified the following files (review and commit):')
        for f in modified:
            print(f'  {f}')
        print('[pyupgrade] FAIL (files were modified)')
        return 1
    print('[pyupgrade] PASS')
    return 0


def run_eslint(root: Path) -> int:
    """Run eslint on JS-files/ directory."""
    if not _has_js_files(root):
        print('[eslint] skipped (no JS files found)')
        return 0
    cmd, always_pass = _build_cmd('eslint', root)
    return _run_tool('eslint', cmd, cwd=root, always_pass=always_pass)


def run_jshint(root: Path) -> int:
    """Run jshint on JS-files/ directory."""
    if not _has_js_files(root):
        print('[jshint] skipped (no JS files found)')
        return 0
    cmd, always_pass = _build_cmd('jshint', root)
    return _run_tool('jshint', cmd, cwd=root, always_pass=always_pass)


_TOOL_RUNNERS = {
    'ruff': run_ruff,
    'mypy': run_mypy,
    'ty': run_ty,
    'bandit': run_bandit,
    'pip-audit': run_pip_audit,
    'deptry': run_deptry,
    'pydoclint': run_pydoclint,
    'pylint': run_pylint,
    'vulture': run_vulture,
    'skylos': run_skylos,
    'radon': run_radon,
    'pyupgrade': run_pyupgrade,
    'eslint': run_eslint,
    'jshint': run_jshint,
}


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description='Run linter tools, optionally grouping output by source file.')
    parser.add_argument('--tool', choices=ALL_TOOLS, metavar='TOOL',
                        help='Tool to run (use --list to see available tools)')
    parser.add_argument('--list', action='store_true', help='Print all available tool names')
    parser.add_argument('--group-by-files', action='store_true',
                        help='Group findings by source file instead of by tool')
    parser.add_argument('--with-radon', action='store_true',
                        help='Include radon in the run (informational only, excluded by default)')
    args = parser.parse_args()

    if args.list:
        for tool in ALL_TOOLS:
            print(tool)
        sys.exit(0)

    root = Path(__file__).parent.resolve()

    if not args.tool and not args.group_by_files:
        overall_rc = 0
        for name in TOOLS:
            runner = _TOOL_RUNNERS[name]
            rc = runner(root)
            if rc != 0:
                overall_rc = 1
        sys.exit(overall_rc)

    if args.group_by_files:
        if args.tool:
            tools_to_run = [args.tool]
        else:
            tools_to_run = TOOLS + (['radon'] if args.with_radon else [])
        all_issues: list[Issue] = []
        rc_map: dict[str, int] = {}
        for name in tools_to_run:
            rc, issues = _run_tool_grouped(name, root)
            rc_map[name] = rc
            all_issues.extend(issues)
        _print_grouped_by_files(all_issues, rc_map)
        overall_rc = 0 if all(rc == 0 for rc in rc_map.values()) else 1
        sys.exit(overall_rc)

    # --tool without --group-by-files: existing raw-output behaviour
    runner = _TOOL_RUNNERS[args.tool]
    rc = runner(root)
    sys.exit(rc)


if __name__ == '__main__':
    main()
