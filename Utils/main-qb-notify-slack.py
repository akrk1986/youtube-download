#!/usr/bin/env python3
# pylint: disable=invalid-name
"""Send a Slack notification when a torrent completes downloading.

The --status flag marks the content good (green ✅) or bad (orange ⚠️, DoVi
profile 5). The good/bad message logic is shared with the Gmail notifier via
funcs_notifications.torrent_message; only the webhook transport lives here.
"""
import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import requests

# This Utils script imports from packages at the project root; ensure that
# root is importable when the file is invoked as 'python Utils/...'.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# pylint: disable=wrong-import-position
from funcs_notifications.torrent_message import build_torrent_slack_message  # noqa: E402
from git_excluded import SLACK_WEBHOOK  # noqa: E402
# pylint: enable=wrong-import-position


@dataclass
class TorrentInfo:
    """Information about a completed torrent."""
    name: str
    path: Path
    is_bad: bool


def _parse_arguments() -> TorrentInfo:
    """Parse command line arguments.

    Returns:
        TorrentInfo: Parsed torrent name, path, and good/bad flag.
    """
    parser = argparse.ArgumentParser(
        description='Send Slack notification for completed torrent'
    )
    parser.add_argument(
        '--name',
        required=True,
        help='Name of the completed torrent'
    )
    parser.add_argument(
        '--path',
        required=True,
        help='Full path to the downloaded content'
    )
    parser.add_argument(
        '--status',
        choices=['good', 'bad'],
        default='good',
        help='Content status: bad flags DoVi profile 5 (default: %(default)s)'
    )

    args = parser.parse_args()
    return TorrentInfo(name=args.name, path=Path(args.path), is_bad=args.status == 'bad')


def _send_slack_message(webhook_url: str, message: str) -> bool:
    """Send a message to Slack via webhook.

    Args:
        webhook_url: The Slack incoming webhook URL.
        message: The message text to send.

    Returns:
        bool: True if successful, False otherwise.
    """
    payload = {'text': message}

    try:
        response = requests.post(
            url=webhook_url,
            json=payload,
            timeout=10
        )
        return response.status_code == requests.codes.ok
    except requests.RequestException as e:
        print(f'Failed to send Slack message: {e}')
        return False


def main() -> None:
    """Main entry point."""
    torrent = _parse_arguments()
    message = build_torrent_slack_message(name=torrent.name, path=str(torrent.path), is_bad=torrent.is_bad)
    success = _send_slack_message(webhook_url=SLACK_WEBHOOK, message=message)

    if not success:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
