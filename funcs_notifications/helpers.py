"""Helper functions for sending notifications via multiple notifiers."""
import logging

from funcs_notifications.base import NotificationHandler
from funcs_notifications.message_builder import NotificationData

logger = logging.getLogger(__name__)


def send_all_notifications(notifiers: list[NotificationHandler],
                           data: NotificationData) -> None:
    """Send notifications via all configured notifiers.

    Each notifier is called independently — one failure does not block others.

    Args:
        notifiers: List of notification handlers to use
        data: NotificationData object containing all notification information
    """
    for notifier in notifiers:
        try:
            notifier.send(data=data)
        except Exception as e:
            logger.warning(f'Notifier {type(notifier).__name__} failed: {type(e).__name__}')
