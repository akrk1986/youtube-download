"""
Notification handlers for download status updates.
Implements strategy pattern with Slack and Gmail notifiers.

This package is organized into:
- base: Abstract base class for notification handlers
- message_builder: Shared message formatting functions
- slack_notifier: Slack webhook notifications
- gmail_notifier: Gmail SMTP notifications
"""
import logging
from typing import Optional

from funcs_notifications.base import NotificationHandler
from funcs_notifications.gmail_notifier import GmailNotifier
from funcs_notifications.slack_notifier import SlackNotifier

logger = logging.getLogger(__name__)

__all__ = [
    'NotificationHandler',
    'SlackNotifier',
    'GmailNotifier',
    'send_all_notifications',
]


def send_all_notifications(notifiers: list[NotificationHandler],
                           status: str, url: str, args_dict: dict,
                           session_id: str,
                           elapsed_time: Optional[str] = None,
                           video_count: int = 0, audio_count: int = 0,
                           failure_reason: Optional[str] = None,
                           script_version: Optional[str] = None,
                           ytdlp_version: Optional[str] = None) -> None:
    """Send notifications via all configured notifiers.

    Each notifier is called independently — one failure does not block others.
    """
    for notifier in notifiers:
        try:
            notifier.send(
                status=status, url=url, args_dict=args_dict,
                session_id=session_id, elapsed_time=elapsed_time,
                video_count=video_count, audio_count=audio_count,
                failure_reason=failure_reason,
                script_version=script_version, ytdlp_version=ytdlp_version
            )
        except Exception as e:
            logger.warning(f'Notifier {type(notifier).__name__} failed: {type(e).__name__}')
