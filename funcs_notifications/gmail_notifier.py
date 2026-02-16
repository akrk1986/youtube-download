"""Gmail notification handler."""
import logging
import smtplib
from email.mime.text import MIMEText

from funcs_notifications.base import NotificationHandler
from funcs_notifications.message_builder import EmailMessageBuilder, NotificationData

logger = logging.getLogger(__name__)


class GmailNotifier(NotificationHandler):
    """Send notifications via Gmail SMTP.

    SECURITY NOTE: Credentials must NEVER be logged or printed.

    Requires a Gmail App Password (not the regular Gmail password).
    See: https://support.google.com/accounts/answer/185833
    """

    REQUIRED_KEYS = ['sender_email', 'sender_app_password', 'recipient_email']

    def __init__(self, gmail_params: dict[str, str] | None) -> None:
        self._params = gmail_params
        self._builder = EmailMessageBuilder()

    def is_configured(self) -> bool:
        """Return True if all required Gmail parameters are present and non-empty."""
        if not self._params or not isinstance(self._params, dict):
            return False
        return all(
            self._params.get(key)
            for key in self.REQUIRED_KEYS
        )

    def send(self, data: NotificationData) -> bool:
        """Send a Gmail notification about download status.

        Args:
            data: NotificationData object containing all notification information

        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not self.is_configured():
            logger.debug('Gmail not configured, skipping notification')
            return False

        # Type guard: is_configured() ensures _params is dict[str, str]
        assert self._params is not None

        email_message = self._builder.build_message(data)

        msg = MIMEText(email_message.html_body, 'html')
        msg['Subject'] = email_message.subject
        msg['From'] = self._params['sender_email']
        msg['To'] = self._params['recipient_email']

        try:
            with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as server:
                server.starttls()
                server.login(self._params['sender_email'], self._params['sender_app_password'])
                server.send_message(msg)

            logger.debug(f'Gmail notification sent: {data.status}')
            return True

        except smtplib.SMTPAuthenticationError:
            logger.warning('Failed to send Gmail notification: Authentication failed')
            return False
        except smtplib.SMTPConnectError:
            logger.warning('Failed to send Gmail notification: Connection error')
            return False
        except smtplib.SMTPException:
            logger.warning('Failed to send Gmail notification: SMTP error')
            return False
        except TimeoutError:
            logger.warning('Failed to send Gmail notification: Connection timed out')
            return False
        except Exception as e:
            logger.warning(f'Unexpected error sending Gmail notification: {type(e).__name__}')
            return False
