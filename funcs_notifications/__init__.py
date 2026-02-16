"""
Notification handlers for download status updates.
Implements strategy pattern with Slack and Gmail notifiers.

This package is organized into:
- base: Abstract base class for notification handlers
- message_builder: Message builder classes and data structures
- slack_notifier: Slack webhook notifications
- gmail_notifier: Gmail SMTP notifications
- helpers: Helper functions for sending notifications
"""

from funcs_notifications.base import NotificationHandler
from funcs_notifications.gmail_notifier import GmailNotifier
from funcs_notifications.helpers import send_all_notifications
from funcs_notifications.message_builder import NotificationData
from funcs_notifications.slack_notifier import SlackNotifier

__all__ = [
    'NotificationHandler',
    'SlackNotifier',
    'GmailNotifier',
    'NotificationData',
    'send_all_notifications',
]
