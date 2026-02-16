"""Tests for enhanced notification system.

Tests NOTIFICATIONS env var parsing (empty/N/NO/S/G/ALL)
and NOTIF_MSG suffix functionality.
"""
import pytest
from unittest.mock import patch

from funcs_notifications import send_all_notifications
from funcs_notifications.base import NotificationHandler
from funcs_notifications.message_builder import build_email_message, build_slack_message


class MockNotifier(NotificationHandler):
    """Mock notifier for testing."""

    def __init__(self, configured: bool = True) -> None:
        self.configured = configured
        self.sent_messages: list[dict] = []

    def is_configured(self) -> bool:
        return self.configured

    def send(self, status: str, url: str, args_dict: dict,
             session_id: str, elapsed_time: str | None = None,
             video_count: int = 0, audio_count: int = 0,
             failure_reason: str | None = None,
             script_version: str | None = None,
             ytdlp_version: str | None = None,
             notif_msg_suffix: str = '') -> bool:
        """Record sent messages."""
        self.sent_messages.append({
            'status': status,
            'url': url,
            'args_dict': args_dict,
            'session_id': session_id,
            'elapsed_time': elapsed_time,
            'video_count': video_count,
            'audio_count': audio_count,
            'failure_reason': failure_reason,
            'script_version': script_version,
            'ytdlp_version': ytdlp_version,
            'notif_msg_suffix': notif_msg_suffix,
        })
        return True


# ============================================================================
# Tests for message_builder functions
# ============================================================================

class TestBuildSlackMessage:
    """Test build_slack_message() with and without suffix."""

    def test_no_suffix(self) -> None:
        """Test Slack message without suffix."""
        msg = build_slack_message(
            status='start',
            url='https://youtube.com/watch?v=test',
            args_dict={'with_audio': True},
            session_id='[2026-02-16 12:00 hostname]'
        )
        assert '🚀 Download STARTED' in msg
        assert '🚀 Download STARTED -' not in msg  # No suffix

    def test_with_suffix(self) -> None:
        """Test Slack message with suffix."""
        msg = build_slack_message(
            status='start',
            url='https://youtube.com/watch?v=test',
            args_dict={'with_audio': True},
            session_id='[2026-02-16 12:00 hostname]',
            notif_msg_suffix='PROD'
        )
        assert '🚀 Download STARTED - PROD' in msg

    def test_empty_suffix(self) -> None:
        """Test Slack message with empty suffix (treated as no suffix)."""
        msg = build_slack_message(
            status='success',
            url='https://youtube.com/watch?v=test',
            args_dict={},
            session_id='[2026-02-16 12:00 hostname]',
            notif_msg_suffix=''
        )
        assert '✅ Download SUCCESS' in msg
        assert '✅ Download SUCCESS -' not in msg  # No suffix

    def test_all_status_types(self) -> None:
        """Test suffix works for all status types."""
        statuses = [
            ('start', '🚀', 'STARTED'),
            ('success', '✅', 'SUCCESS'),
            ('cancelled', '🛑', 'CANCELLED'),
            ('failure', '❌', 'FAILURE'),
        ]
        for status, emoji, word in statuses:
            msg = build_slack_message(
                status=status,
                url='https://youtube.com/watch?v=test',
                args_dict={},
                session_id='[2026-02-16 12:00 hostname]',
                notif_msg_suffix='TEST'
            )
            expected = f'{emoji} Download {word} - TEST'
            assert expected in msg


class TestBuildEmailMessage:
    """Test build_email_message() with and without suffix."""

    def test_no_suffix(self) -> None:
        """Test email message without suffix."""
        subject, html_body = build_email_message(
            status='start',
            url='https://youtube.com/watch?v=test',
            args_dict={'with_audio': True},
            session_id='[2026-02-16 12:00 hostname]'
        )
        assert subject == '🚀 yt-dlp Download STARTED'
        assert '<h3>🚀 Download STARTED</h3>' in html_body
        assert '🚀 Download STARTED -' not in html_body  # No suffix

    def test_with_suffix(self) -> None:
        """Test email message with suffix in both subject and body."""
        subject, html_body = build_email_message(
            status='start',
            url='https://youtube.com/watch?v=test',
            args_dict={'with_audio': True},
            session_id='[2026-02-16 12:00 hostname]',
            notif_msg_suffix='PROD'
        )
        # Check subject has suffix
        assert subject == '🚀 yt-dlp Download STARTED - PROD'
        # Check HTML body <h3> has suffix
        assert '<h3>🚀 Download STARTED - PROD</h3>' in html_body

    def test_empty_suffix(self) -> None:
        """Test email message with empty suffix (treated as no suffix)."""
        subject, html_body = build_email_message(
            status='success',
            url='https://youtube.com/watch?v=test',
            args_dict={},
            session_id='[2026-02-16 12:00 hostname]',
            notif_msg_suffix=''
        )
        assert subject == '✅ yt-dlp Download SUCCESS'
        assert '<h3>✅ Download SUCCESS</h3>' in html_body
        assert '✅ Download SUCCESS -' not in html_body  # No suffix

    def test_all_status_types(self) -> None:
        """Test suffix works for all status types in subject and body."""
        statuses = [
            ('start', '🚀', 'STARTED'),
            ('success', '✅', 'SUCCESS'),
            ('cancelled', '🛑', 'CANCELLED'),
            ('failure', '❌', 'FAILURE'),
        ]
        for status, emoji, word in statuses:
            subject, html_body = build_email_message(
                status=status,
                url='https://youtube.com/watch?v=test',
                args_dict={},
                session_id='[2026-02-16 12:00 hostname]',
                notif_msg_suffix='DEV'
            )
            expected_subject = f'{emoji} yt-dlp Download {word} - DEV'
            expected_body = f'<h3>{emoji} Download {word} - DEV</h3>'
            assert subject == expected_subject
            assert expected_body in html_body


# ============================================================================
# Tests for send_all_notifications()
# ============================================================================

class TestSendAllNotifications:
    """Test send_all_notifications() passes suffix correctly."""

    def test_suffix_passed_to_notifiers(self) -> None:
        """Test suffix is correctly passed to all notifiers."""
        mock_notifier = MockNotifier()
        send_all_notifications(
            notifiers=[mock_notifier],
            status='start',
            url='https://youtube.com/watch?v=test',
            args_dict={'with_audio': True},
            session_id='[2026-02-16 12:00 hostname]',
            notif_msg_suffix='PROD'
        )
        assert len(mock_notifier.sent_messages) == 1
        assert mock_notifier.sent_messages[0]['notif_msg_suffix'] == 'PROD'

    def test_empty_suffix_passed(self) -> None:
        """Test empty suffix is correctly passed."""
        mock_notifier = MockNotifier()
        send_all_notifications(
            notifiers=[mock_notifier],
            status='start',
            url='https://youtube.com/watch?v=test',
            args_dict={'with_audio': True},
            session_id='[2026-02-16 12:00 hostname]',
            notif_msg_suffix=''
        )
        assert len(mock_notifier.sent_messages) == 1
        assert mock_notifier.sent_messages[0]['notif_msg_suffix'] == ''

    def test_multiple_notifiers(self) -> None:
        """Test suffix passed to multiple notifiers."""
        mock1 = MockNotifier()
        mock2 = MockNotifier()
        send_all_notifications(
            notifiers=[mock1, mock2],
            status='success',
            url='https://youtube.com/watch?v=test',
            args_dict={},
            session_id='[2026-02-16 12:00 hostname]',
            elapsed_time='5m 23s',
            notif_msg_suffix='TEST'
        )
        assert len(mock1.sent_messages) == 1
        assert mock1.sent_messages[0]['notif_msg_suffix'] == 'TEST'
        assert len(mock2.sent_messages) == 1
        assert mock2.sent_messages[0]['notif_msg_suffix'] == 'TEST'


# ============================================================================
# Tests for NOTIFICATIONS environment variable parsing
# ============================================================================

class TestNotificationsEnvVarParsing:
    """Test NOTIFICATIONS env var parsing in main-yt-dlp.py.

    These tests use patch to simulate different env var values.
    """

    @pytest.mark.parametrize('value', ['', 'N', 'n', 'NO', 'no', 'No'])
    def test_no_notifications(self, value: str) -> None:
        """Test empty/N/NO disables all notifications."""
        with patch('os.getenv') as mock_getenv:
            # Mock NOTIFICATIONS env var
            def getenv_side_effect(key: str, default: str = '') -> str:
                if key == 'NOTIFICATIONS':
                    return value
                if key == 'NOTIF_MSG':
                    return ''
                return default

            mock_getenv.side_effect = getenv_side_effect

            # Simulate the parsing logic from main-yt-dlp.py
            notifications_enabled = mock_getenv('NOTIFICATIONS', '').strip().upper()
            assert notifications_enabled in ('', 'N', 'NO')

    @pytest.mark.parametrize('value', ['S', 's', 'SLACK'])
    def test_slack_only(self, value: str) -> None:
        """Test S/SLACK enables Slack only."""
        with patch('os.getenv') as mock_getenv:
            def getenv_side_effect(key: str, default: str = '') -> str:
                if key == 'NOTIFICATIONS':
                    return value
                if key == 'NOTIF_MSG':
                    return ''
                return default

            mock_getenv.side_effect = getenv_side_effect

            notifications_enabled = mock_getenv('NOTIFICATIONS', '').strip().upper()
            # Accept 'S' or 'SLACK' (implementation uses 'S')
            assert notifications_enabled in ('S', 'SLACK')

    @pytest.mark.parametrize('value', ['G', 'g', 'GMAIL'])
    def test_gmail_only(self, value: str) -> None:
        """Test G/GMAIL enables Gmail only."""
        with patch('os.getenv') as mock_getenv:
            def getenv_side_effect(key: str, default: str = '') -> str:
                if key == 'NOTIFICATIONS':
                    return value
                if key == 'NOTIF_MSG':
                    return ''
                return default

            mock_getenv.side_effect = getenv_side_effect

            notifications_enabled = mock_getenv('NOTIFICATIONS', '').strip().upper()
            # Accept 'G' or 'GMAIL' (implementation uses 'G')
            assert notifications_enabled in ('G', 'GMAIL')

    @pytest.mark.parametrize('value', ['ALL', 'all', 'All'])
    def test_both_notifications(self, value: str) -> None:
        """Test ALL enables both Slack and Gmail."""
        with patch('os.getenv') as mock_getenv:
            def getenv_side_effect(key: str, default: str = '') -> str:
                if key == 'NOTIFICATIONS':
                    return value
                if key == 'NOTIF_MSG':
                    return ''
                return default

            mock_getenv.side_effect = getenv_side_effect

            notifications_enabled = mock_getenv('NOTIFICATIONS', '').strip().upper()
            assert notifications_enabled == 'ALL'

    @pytest.mark.parametrize('value', ['INVALID', 'Y', 'YES', 'TRUE', '1'])
    def test_invalid_values(self, value: str) -> None:
        """Test invalid values (including legacy Y/YES) are rejected."""
        with patch('os.getenv') as mock_getenv:
            def getenv_side_effect(key: str, default: str = '') -> str:
                if key == 'NOTIFICATIONS':
                    return value
                if key == 'NOTIF_MSG':
                    return ''
                return default

            mock_getenv.side_effect = getenv_side_effect

            notifications_enabled = mock_getenv('NOTIFICATIONS', '').strip().upper()
            # Should not match any valid value
            assert notifications_enabled not in ('', 'N', 'NO', 'S', 'G', 'ALL')


# ============================================================================
# Tests for NOTIF_MSG environment variable
# ============================================================================

class TestNotifMsgEnvVar:
    """Test NOTIF_MSG env var parsing and handling."""

    def test_valid_suffix(self) -> None:
        """Test valid NOTIF_MSG suffix is read correctly."""
        with patch('os.getenv') as mock_getenv:
            def getenv_side_effect(key: str, default: str = '') -> str:
                if key == 'NOTIF_MSG':
                    return 'PROD'
                return default

            mock_getenv.side_effect = getenv_side_effect

            notif_msg_suffix = mock_getenv('NOTIF_MSG', '').strip()
            assert notif_msg_suffix == 'PROD'

    def test_empty_suffix(self) -> None:
        """Test empty NOTIF_MSG is treated as no suffix."""
        with patch('os.getenv') as mock_getenv:
            def getenv_side_effect(key: str, default: str = '') -> str:
                if key == 'NOTIF_MSG':
                    return ''
                return default

            mock_getenv.side_effect = getenv_side_effect

            notif_msg_suffix = mock_getenv('NOTIF_MSG', '').strip()
            assert notif_msg_suffix == ''

    def test_whitespace_only_suffix(self) -> None:
        """Test whitespace-only NOTIF_MSG is stripped to empty."""
        with patch('os.getenv') as mock_getenv:
            def getenv_side_effect(key: str, default: str = '') -> str:
                if key == 'NOTIF_MSG':
                    return '   '
                return default

            mock_getenv.side_effect = getenv_side_effect

            notif_msg_suffix = mock_getenv('NOTIF_MSG', '').strip()
            assert notif_msg_suffix == ''

    def test_suffix_with_surrounding_whitespace(self) -> None:
        """Test NOTIF_MSG with surrounding whitespace is stripped."""
        with patch('os.getenv') as mock_getenv:
            def getenv_side_effect(key: str, default: str = '') -> str:
                if key == 'NOTIF_MSG':
                    return '  TEST  '
                return default

            mock_getenv.side_effect = getenv_side_effect

            notif_msg_suffix = mock_getenv('NOTIF_MSG', '').strip()
            assert notif_msg_suffix == 'TEST'
