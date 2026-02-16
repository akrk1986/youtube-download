#!/usr/bin/env python3
"""Manual test script for enhanced notification system.

This script demonstrates the new NOTIFICATIONS and NOTIF_MSG functionality
without actually sending notifications or downloading videos.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from funcs_notifications import GmailNotifier, SlackNotifier, send_all_notifications


def test_notifications_env_var() -> None:
    """Test NOTIFICATIONS env var parsing."""
    print('Testing NOTIFICATIONS environment variable parsing...\n')

    test_cases = [
        ('', 'No notifications (empty)'),
        ('N', 'No notifications (N)'),
        ('NO', 'No notifications (NO)'),
        ('S', 'Slack only'),
        ('G', 'Gmail only'),
        ('ALL', 'Both Slack and Gmail'),
        ('INVALID', 'Invalid value'),
    ]

    for value, description in test_cases:
        os.environ['NOTIFICATIONS'] = value
        notifications_enabled = os.getenv('NOTIFICATIONS', '').strip().upper()
        print(f'NOTIFICATIONS={value!r:10} -> {notifications_enabled!r:10} ({description})')

    print()


def test_notif_msg_suffix() -> None:
    """Test NOTIF_MSG suffix parsing."""
    print('Testing NOTIF_MSG environment variable parsing...\n')

    test_cases = [
        ('PROD', 'Production environment'),
        ('TEST', 'Test environment'),
        ('', 'Empty (no suffix)'),
        ('   ', 'Whitespace only (no suffix)'),
        ('  DEV  ', 'With surrounding whitespace'),
    ]

    for value, description in test_cases:
        os.environ['NOTIF_MSG'] = value
        notif_msg_suffix = os.getenv('NOTIF_MSG', '').strip()
        print(f'NOTIF_MSG={value!r:12} -> {notif_msg_suffix!r:10} ({description})')

    print()


def test_message_building() -> None:
    """Test message building with suffix."""
    from funcs_notifications.message_builder import build_email_message, build_slack_message

    print('Testing message building with suffix...\n')

    # Test Slack message
    slack_msg = build_slack_message(
        status='start',
        url='https://youtube.com/watch?v=test',
        args_dict={'with_audio': True},
        session_id='[2026-02-16 12:00 hostname]',
        notif_msg_suffix='PROD'
    )
    print('Slack message with PROD suffix:')
    print(slack_msg[:100] + '...\n')

    # Test Email message
    subject, html_body = build_email_message(
        status='success',
        url='https://youtube.com/watch?v=test',
        args_dict={},
        session_id='[2026-02-16 12:00 hostname]',
        notif_msg_suffix='TEST'
    )
    print('Email subject with TEST suffix:')
    print(f'{subject}\n')
    print('Email body <h3> tag:')
    print(html_body.split('\n')[0] + '\n')


def test_notifier_configuration() -> None:
    """Test notifier configuration detection."""
    print('Testing notifier configuration...\n')

    # Test with None values
    slack = SlackNotifier(webhook_url=None)
    gmail = GmailNotifier(gmail_params=None)

    print(f'SlackNotifier(None) configured: {slack.is_configured()}')
    print(f'GmailNotifier(None) configured: {gmail.is_configured()}\n')

    # Test with placeholder values
    slack = SlackNotifier(webhook_url='https://hooks.slack.com/services/YOUR/WEBHOOK/URL')
    gmail = GmailNotifier(gmail_params={})

    print(f'SlackNotifier(placeholder) configured: {slack.is_configured()}')
    print(f'GmailNotifier(empty dict) configured: {gmail.is_configured()}\n')


if __name__ == '__main__':
    print('=' * 70)
    print('Enhanced Notification System - Manual Test')
    print('=' * 70)
    print()

    test_notifications_env_var()
    test_notif_msg_suffix()
    test_message_building()
    test_notifier_configuration()

    print('=' * 70)
    print('All manual tests completed successfully!')
    print('=' * 70)
