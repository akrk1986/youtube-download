#!/usr/bin/env python3
"""Send a Slack notification when a torrent completes downloading."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import requests

from git_excluded import SLACK_WEBHOOK


@dataclass
class TorrentInfo:
    """Information about a completed torrent."""
    name: str
    path: Path


def _parse_arguments() -> TorrentInfo:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Send Slack notification for completed torrent"
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Name of the completed torrent"
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Full path to the downloaded content"
    )

    args = parser.parse_args()
    return TorrentInfo(name=args.name, path=Path(args.path))


def _send_slack_message(webhook_url: str, message: str) -> bool:
    """Send a message to Slack via webhook.

    Args:
        webhook_url: The Slack incoming webhook URL.
        message: The message text to send.

    Returns:
        True if successful, False otherwise.
    """
    payload = {"text": message}

    try:
        response = requests.post(
            url=webhook_url,
            json=payload,
            timeout=10
        )
        return response.status_code == requests.codes.ok
    except requests.RequestException as e:
        print(f"Failed to send Slack message: {e}")
        return False


def _build_notification_message(torrent: TorrentInfo) -> str:
    """Build the Slack notification message.

    Args:
        torrent: Information about the completed torrent.

    Returns:
        Formatted message string.
    """
    return (
        f":white_check_mark: *Torrent Complete*\n"
        f"*Name:* {torrent.name}\n"
        f"*Location:* `{torrent.path}`"
    )


def main() -> None:
    """Main entry point."""
    torrent = _parse_arguments()
    message = _build_notification_message(torrent=torrent)
    success = _send_slack_message(webhook_url=SLACK_WEBHOOK, message=message)

    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
