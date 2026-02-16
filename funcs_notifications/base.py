"""Abstract base class for notification handlers."""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from funcs_notifications.message_builder import NotificationData


class NotificationHandler(ABC):
    """Base class for all notification handlers (Slack, Gmail, etc.)."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if this notifier has valid credentials configured."""

    @abstractmethod
    def send(self, data: 'NotificationData') -> bool:
        """Send a notification about download status.

        Args:
            data: NotificationData object containing all notification information

        Returns:
            True if notification was sent successfully, False otherwise
        """
