#!/usr/bin/env python3
# pylint: disable=invalid-name
"""qBittorrent post-download hook (Gmail): flag DoVi profile 5, then send a mail.

Wire this as the qBittorrent "Run on torrent finished" command:
    python /path/to/Utils/main-qb-postdownload-gmail.py --name "%N" --path "%F"

It runs the DoVi profile-5 detection on the downloaded content, then invokes
main-qb-notify-gmail.py with the resulting good/bad status. The detection +
notifier-invocation logic is shared with the Slack driver via
funcs_for_qb_notify.hook, so both send identical information.
"""
import sys
from pathlib import Path

# This Utils script imports from packages at the project root; ensure that
# root is importable when the file is invoked as 'python Utils/...'.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# pylint: disable=wrong-import-position
from funcs_for_qb_notify.hook import parse_hook_args, run_hook  # noqa: E402
# pylint: enable=wrong-import-position

VERSION = '2026-06-03-1700'

_NOTIFIER_SCRIPT = 'main-qb-notify-gmail.py'


def main(argv: list[str] | None = None) -> None:
    """Run the hook and exit with the Gmail notifier's return code.

    Args:
        argv: Optional argument list (for testing).

    Raises:
        SystemExit: The notifier's exit code.
    """
    args = parse_hook_args(version=VERSION, argv=argv)
    raise SystemExit(run_hook(name=args.name, path=args.path, notifier_script=_NOTIFIER_SCRIPT))


if __name__ == '__main__':
    main()
