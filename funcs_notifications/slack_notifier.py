"""Slack notification handler."""
import logging

import requests

from funcs_notifications.base import NotificationHandler
from funcs_notifications.message_builder import NotificationData, SlackMessageBuilder

logger = logging.getLogger(__name__)


class SlackNotifier(NotificationHandler):
    """Send notifications via Slack webhook.

    SECURITY NOTE: The webhook_url must NEVER be logged or printed
    to avoid exposing the secret webhook URL in logs.
    """

    def __init__(self, webhook_url: str | None) -> None:
        self._webhook_url = webhook_url
        self._builder = SlackMessageBuilder()

    def is_configured(self) -> bool:
        """Return True if webhook URL is set and not the placeholder."""
        return bool(
            self._webhook_url
            and self._webhook_url != 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        )

    def send(self, data: NotificationData) -> bool:
        """Send a Slack notification about download status.

        Args:
            data: NotificationData object containing all notification information

        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not self.is_configured():
            logger.debug('Slack webhook not configured, skipping notification')
            return False

        # Type guard: is_configured() ensures _webhook_url is str
        assert self._webhook_url is not None

        message_text = self._builder.build_message(data)

        payload = {
            'text': message_text,
            'username': 'yt-dlp Bot',
            'icon_emoji': ':movie_camera:'
        }

        try:
            response = requests.post(self._webhook_url, json=payload, timeout=10)

            if response.ok:
                logger.debug(f'Slack notification sent: {data.status} (HTTP {response.status_code})')
                return True

            logger.warning(f'Slack notification failed with HTTP status {response.status_code}')
            return False

        except requests.Timeout:
            logger.warning('Failed to send Slack notification: Request timed out')
            return False
        except requests.ConnectionError:
            logger.warning('Failed to send Slack notification: Connection error')
            return False
        except requests.RequestException:
            logger.warning('Failed to send Slack notification: Request failed')
            return False
        except Exception as e:
            logger.warning(f'Unexpected error sending Slack notification: {type(e).__name__}')
            return False
