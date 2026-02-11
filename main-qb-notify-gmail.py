#!/usr/bin/env python3
"""Send a Gmail notification when a torrent completes downloading."""

import argparse
import smtplib
from dataclasses import dataclass
from email.mime.text import MIMEText
from pathlib import Path

from git_excluded import GMAIL_PARAMS


@dataclass
class TorrentInfo:
    """Information about a completed torrent."""
    name: str
    path: Path


def _parse_arguments() -> TorrentInfo:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Send Gmail notification for completed torrent'
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

    args = parser.parse_args()
    return TorrentInfo(name=args.name, path=Path(args.path))


def _send_gmail_message(gmail_params: dict[str, str], subject: str, html_body: str) -> bool:
    """Send a message via Gmail SMTP.

    Args:
        gmail_params: Dictionary with sender_email, sender_app_password, recipient_email.
        subject: Email subject line.
        html_body: Email body in HTML format.

    Returns:
        True if successful, False otherwise.
    """
    msg = MIMEText(html_body, 'html')
    msg['Subject'] = subject
    msg['From'] = gmail_params['sender_email']
    msg['To'] = gmail_params['recipient_email']

    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as server:
            server.starttls()
            server.login(gmail_params['sender_email'], gmail_params['sender_app_password'])
            server.send_message(msg)
        return True
    except smtplib.SMTPException as e:
        print(f'Failed to send Gmail message: {e}')
        return False
    except Exception as e:
        print(f'Unexpected error: {e}')
        return False


def _build_notification_message(torrent: TorrentInfo) -> tuple[str, str]:
    """Build the Gmail notification message.

    Args:
        torrent: Information about the completed torrent.

    Returns:
        Tuple of (subject, html_body).
    """
    subject = '✅ Torrent Complete'

    html_body = (
        '<h3>✅ Torrent Complete</h3>\n'
        f'<p><b>Name:</b> {torrent.name}</p>\n'
        f'<p><b>Location:</b> <code>{torrent.path}</code></p>'
    )

    return subject, html_body


def main() -> None:
    """Main entry point."""
    torrent = _parse_arguments()
    subject, html_body = _build_notification_message(torrent=torrent)
    success = _send_gmail_message(gmail_params=GMAIL_PARAMS, subject=subject, html_body=html_body)

    if not success:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
