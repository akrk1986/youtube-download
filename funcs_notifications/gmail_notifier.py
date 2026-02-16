"""Gmail notification handler."""
import logging
import smtplib
from email.mime.text import MIMEText
from typing import Optional

from funcs_notifications.base import NotificationHandler
from funcs_notifications.message_builder import build_email_message

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

    def is_configured(self) -> bool:
        """Return True if all required Gmail parameters are present and non-empty."""
        if not self._params or not isinstance(self._params, dict):
            return False
        return all(
            self._params.get(key)
            for key in self.REQUIRED_KEYS
        )

    def send(self, status: str, url: str, args_dict: dict,
             session_id: str, elapsed_time: Optional[str] = None,
             video_count: int = 0, audio_count: int = 0,
             failure_reason: Optional[str] = None,
             script_version: Optional[str] = None,
             ytdlp_version: Optional[str] = None,
             notif_msg_suffix: str = '') -> bool:
        """Send a Gmail notification about download status."""
        if not self.is_configured():
            logger.debug('Gmail not configured, skipping notification')
            return False

        # Type guard: is_configured() ensures _params is dict[str, str]
        assert self._params is not None

        subject, html_body = build_email_message(
            status=status, url=url, args_dict=args_dict,
            session_id=session_id, elapsed_time=elapsed_time,
            video_count=video_count, audio_count=audio_count,
            failure_reason=failure_reason,
            script_version=script_version, ytdlp_version=ytdlp_version,
            notif_msg_suffix=notif_msg_suffix
        )

        msg = MIMEText(html_body, 'html')
        msg['Subject'] = subject
        msg['From'] = self._params['sender_email']
        msg['To'] = self._params['recipient_email']

        try:
            with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as server:
                server.starttls()
                server.login(self._params['sender_email'], self._params['sender_app_password'])
                server.send_message(msg)

            logger.debug(f'Gmail notification sent: {status}')
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
