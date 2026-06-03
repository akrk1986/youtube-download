"""Shared qBittorrent post-download hook logic.

Both the Gmail and Slack hook drivers reuse this: run the DoVi profile-5 check on
the downloaded path, then invoke the chosen notifier script with the resulting
good/bad status. Keeping the logic here guarantees both drivers send identical
information and differ only in which notifier they call.
"""
import argparse
import subprocess  # nosec B404
import sys
from pathlib import Path

from funcs_for_qb_notify.dovi import path_is_bad

_UTILS_DIR = Path(__file__).resolve().parent.parent / 'Utils'


def parse_hook_args(version: str, argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the shared --name/--path hook arguments.

    Args:
        version: Driver version string for --version.
        argv: Optional argument list (for testing).

    Returns:
        argparse.Namespace: Parsed arguments with 'name' and 'path'.
    """
    parser = argparse.ArgumentParser(description='qBittorrent post-download hook (DoVi check + notify).')
    parser.add_argument('--version', action='version', version=f'%(prog)s {version}')
    parser.add_argument('--name', required=True, help='Name of the completed torrent')
    parser.add_argument('--path', required=True, type=Path, help='Full path to the downloaded content')
    return parser.parse_args(argv)


def run_hook(name: str, path: Path, notifier_script: str) -> int:
    """Detect DoVi profile 5, then invoke the notifier with the good/bad status.

    Args:
        name: Torrent name forwarded to the notifier.
        path: Downloaded content (file or directory) to check.
        notifier_script: Notifier filename in Utils/ (e.g. 'main-qb-notify-gmail.py').

    Returns:
        int: The notifier's exit code.
    """
    status = 'bad' if path_is_bad(path=path) else 'good'
    print(f'DoVi check: {path} -> {status}')

    result = subprocess.run(  # nosec B603
        [sys.executable, str(_UTILS_DIR / notifier_script),
         '--name', name, '--path', str(path), '--status', status],
        check=False,
    )
    return result.returncode
