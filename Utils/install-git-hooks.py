#!/usr/bin/env python3
# pylint: disable=invalid-name
"""Install or uninstall the project git hooks via core.hooksPath.

Run once per clone. The repo's .git is shared between WSL and Windows, so a
single run covers both. Idempotent.

Usage:
    python Utils/install-git-hooks.py              Install (point core.hooksPath at git-hooks/)
    python Utils/install-git-hooks.py --uninstall  Disable (remove the core.hooksPath setting)
"""
import argparse
import subprocess  # nosec B404
import sys
from pathlib import Path


def _set_hooks_path(repo_root: Path) -> int:
    """Point core.hooksPath at the tracked git-hooks directory; return the exit code."""
    result = subprocess.run(  # nosec B603 B607
        ['git', '-C', str(repo_root), 'config', 'core.hooksPath', 'git-hooks'],
        check=False,
    )
    if result.returncode != 0:
        print('install-git-hooks: failed to set core.hooksPath', file=sys.stderr)
        return result.returncode
    print('install-git-hooks: core.hooksPath set to git-hooks/ (hook enabled)')
    return 0


def _unset_hooks_path(repo_root: Path) -> int:
    """Remove the core.hooksPath setting; return the exit code."""
    result = subprocess.run(  # nosec B603 B607
        ['git', '-C', str(repo_root), 'config', '--unset', 'core.hooksPath'],
        check=False,
    )
    # git exits 5 when the key is already absent; treat that as success (idempotent).
    if result.returncode not in (0, 5):
        print('install-git-hooks: failed to unset core.hooksPath', file=sys.stderr)
        return result.returncode
    print('install-git-hooks: core.hooksPath removed (hook disabled)')
    return 0


def main() -> int:
    """Parse args and install or uninstall the git hooks; return the exit code."""
    parser = argparse.ArgumentParser(description='Install or uninstall the project git pre-commit hook.')
    parser.add_argument('--uninstall', action='store_true',
                        help='remove the core.hooksPath setting (disable the hook)')
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    if args.uninstall:
        return _unset_hooks_path(repo_root=repo_root)
    return _set_hooks_path(repo_root=repo_root)


if __name__ == '__main__':
    sys.exit(main())
