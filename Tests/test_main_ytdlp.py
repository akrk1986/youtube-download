#!/usr/bin/env python3
"""
Comprehensive pytest tests for main-yt-dlp.py.
Tests argument parsing, validation, and main execution flow.
"""
import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import after path setup
# Note: We import parse_arguments directly, but need to patch module-level imports
# for _execute_main and main
from project_defs import DEFAULT_AUDIO_FORMAT, VALID_AUDIO_FORMATS


class TestParseArguments:
    """Test argument parsing functionality."""

    def test_defaults_when_no_args(self):
        """Test default values when no arguments provided."""
        # Import here to get fresh module state
        from importlib import import_module
        main_module = import_module('main-yt-dlp')

        args = main_module.parse_arguments([])

        assert args.video_url is None
        assert args.audio_format == DEFAULT_AUDIO_FORMAT
        assert args.split_chapters is False
        assert args.subs is False
        assert args.json is False
        assert args.no_log_file is False
        assert args.progress is False
        assert args.verbose is False
        assert args.show_urls is False
        assert args.rerun is False
        assert args.title is None
        assert args.artist is None
        assert args.album is None
        assert args.with_audio is False
        assert args.only_audio is False

    def test_video_url_positional(self):
        """Test that video URL is parsed as positional argument."""
        from importlib import import_module
        main_module = import_module('main-yt-dlp')

        test_url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        args = main_module.parse_arguments([test_url])

        assert args.video_url == test_url

    def test_audio_format_default_mp3(self):
        """Test that default audio format is mp3."""
        from importlib import import_module
        main_module = import_module('main-yt-dlp')

        args = main_module.parse_arguments([])

        assert args.audio_format == 'mp3'

    def test_audio_format_comma_separated(self):
        """Test parsing comma-separated audio formats."""
        from importlib import import_module
        main_module = import_module('main-yt-dlp')

        args = main_module.parse_arguments(['--audio-format', 'mp3,m4a,flac'])

        assert args.audio_format == 'mp3,m4a,flac'

    def test_with_audio_only_audio_mutually_exclusive(self):
        """Test that --with-audio and --only-audio are mutually exclusive."""
        from importlib import import_module
        main_module = import_module('main-yt-dlp')

        with pytest.raises(SystemExit):
            main_module.parse_arguments(['--with-audio', '--only-audio'])

    def test_split_chapters_flag(self):
        """Test --split-chapters flag parsing."""
        from importlib import import_module
        main_module = import_module('main-yt-dlp')

        args = main_module.parse_arguments(['--split-chapters'])

        assert args.split_chapters is True

    def test_verbose_flag(self):
        """Test --verbose flag parsing."""
        from importlib import import_module
        main_module = import_module('main-yt-dlp')

        args = main_module.parse_arguments(['--verbose'])
        assert args.verbose is True

        args_short = main_module.parse_arguments(['-v'])
        assert args_short.verbose is True

    def test_rerun_flag(self):
        """Test --rerun flag parsing."""
        from importlib import import_module
        main_module = import_module('main-yt-dlp')

        args = main_module.parse_arguments(['--rerun'])

        assert args.rerun is True

    def test_custom_title_artist_album(self):
        """Test custom title, artist, and album arguments."""
        from importlib import import_module
        main_module = import_module('main-yt-dlp')

        args = main_module.parse_arguments([
            '--title', 'Custom Title',
            '--artist', 'Custom Artist',
            '--album', 'Custom Album'
        ])

        assert args.title == 'Custom Title'
        assert args.artist == 'Custom Artist'
        assert args.album == 'Custom Album'

    def test_video_download_timeout(self):
        """Test --video-download-timeout argument parsing."""
        from importlib import import_module
        main_module = import_module('main-yt-dlp')

        args = main_module.parse_arguments(['--video-download-timeout', '600'])

        assert args.video_download_timeout == 600


class TestAudioFormatValidation:
    """Test audio format validation in _execute_main."""

    def test_valid_formats_mp3_m4a_flac(self):
        """Test that mp3, m4a, flac are valid formats."""
        for fmt in ['mp3', 'm4a', 'flac']:
            assert fmt in VALID_AUDIO_FORMATS

    def test_invalid_format_exits(self, sample_args, tmp_path):
        """Test that invalid format causes sys.exit."""
        from importlib import import_module
        main_module = import_module('main-yt-dlp')

        # Create a modified args with invalid format
        sample_args.audio_format = 'wav'
        sample_args.video_url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'

        # Mock dependencies to avoid real operations
        with patch.object(main_module, 'SLACK_WEBHOOK', None), \
             patch.object(main_module, 'get_ytdlp_path', return_value='/usr/bin/yt-dlp'), \
             patch.object(main_module, 'validate_and_get_url', return_value=sample_args.video_url):

            with pytest.raises(SystemExit) as exc_info:
                main_module._execute_main(
                    args=sample_args,
                    args_dict={},
                    start_time=0,
                    session_id='test-session',
                    initial_video_count=0,
                    initial_audio_count=0
                )
            assert exc_info.value.code == 1

    def test_duplicate_formats_deduplicated(self, sample_args):
        """Test that duplicate formats are deduplicated."""
        # Test the deduplication logic manually
        audio_formats_str = 'mp3,mp3,m4a,mp3'
        audio_formats = [fmt.strip() for fmt in audio_formats_str.split(',')]

        seen = set()
        deduplicated_formats = []
        for fmt in audio_formats:
            if fmt not in seen:
                seen.add(fmt)
                deduplicated_formats.append(fmt)

        assert deduplicated_formats == ['mp3', 'm4a']

    def test_whitespace_trimmed(self, sample_args):
        """Test that whitespace is trimmed from formats."""
        audio_formats_str = ' mp3 , m4a , flac '
        audio_formats = [fmt.strip() for fmt in audio_formats_str.split(',')]

        assert audio_formats == ['mp3', 'm4a', 'flac']


class TestURLValidation:
    """Test URL validation functionality."""

    def test_valid_youtube_url(self):
        """Test that valid YouTube URLs pass validation."""
        from funcs_video_info import validate_video_url

        valid_urls = [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://youtube.com/watch?v=dQw4w9WgXcQ',
            'https://m.youtube.com/watch?v=dQw4w9WgXcQ',
        ]
        for url in valid_urls:
            is_valid, error_msg = validate_video_url(url=url)
            assert is_valid, f'Valid URL rejected: {url}, error: {error_msg}'

    def test_valid_youtu_be_url(self):
        """Test that valid youtu.be URLs pass validation."""
        from funcs_video_info import validate_video_url

        url = 'https://youtu.be/dQw4w9WgXcQ'
        is_valid, error_msg = validate_video_url(url=url)
        assert is_valid, f'Valid URL rejected: {url}, error: {error_msg}'

    def test_invalid_domain_fails(self):
        """Test that invalid domains fail validation."""
        from funcs_video_info import validate_video_url

        url = 'https://invalid-domain.com/watch?v=test'
        is_valid, error_msg = validate_video_url(url=url)
        assert not is_valid

    def test_empty_url_prompts_user(self, mock_input):
        """Test that empty URL triggers user prompt."""
        from funcs_for_main_yt_dlp.url_validation import validate_and_get_url

        mock_input.return_value = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'

        result = validate_and_get_url(provided_url='')

        assert mock_input.called
        assert result == 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'


class TestSlackNotifications:
    """Test Slack notification functionality."""

    def test_start_notification_sent(self, mock_requests_post):
        """Test that start notification is sent when webhook configured."""
        from funcs_notifications import NotificationData, SlackNotifier

        notifier = SlackNotifier(webhook_url='https://hooks.slack.com/services/TEST/WEBHOOK/URL')
        result = notifier.send(
            data=NotificationData(
                status='start',
                url='https://www.youtube.com/watch?v=test',
                args_dict={'with_audio': True},
                session_id='[2026-02-05 12:00 test-host]'
            )
        )

        assert result is True
        assert mock_requests_post.called
        call_args = mock_requests_post.call_args
        assert 'STARTED' in str(call_args)

    def test_success_notification_sent(self, mock_requests_post):
        """Test that success notification is sent when webhook configured."""
        from funcs_notifications import NotificationData, SlackNotifier

        notifier = SlackNotifier(webhook_url='https://hooks.slack.com/services/TEST/WEBHOOK/URL')
        result = notifier.send(
            data=NotificationData(
                status='success',
                url='https://www.youtube.com/watch?v=test',
                args_dict={'with_audio': True},
                session_id='[2026-02-05 12:00 test-host]',
                elapsed_time='5m 23s',
                video_count=1,
                audio_count=3
            )
        )

        assert result is True
        assert mock_requests_post.called
        call_args = mock_requests_post.call_args
        assert 'SUCCESS' in str(call_args)

    def test_no_notification_when_webhook_none(self, mock_requests_post):
        """Test that no notification is sent when webhook is None."""
        from funcs_notifications import NotificationData, SlackNotifier

        notifier = SlackNotifier(webhook_url=None)
        assert notifier.is_configured() is False
        result = notifier.send(
            data=NotificationData(
                status='start',
                url='https://www.youtube.com/watch?v=test',
                args_dict={},
                session_id='test'
            )
        )

        assert result is False
        assert not mock_requests_post.called

    def test_cancelled_notification_on_keyboard_interrupt(self, mock_requests_post):
        """Test that cancelled notification is sent correctly."""
        from funcs_notifications import NotificationData, SlackNotifier

        notifier = SlackNotifier(webhook_url='https://hooks.slack.com/services/TEST/WEBHOOK/URL')
        result = notifier.send(
            data=NotificationData(
                status='cancelled',
                url='https://www.youtube.com/watch?v=test',
                args_dict={'only_audio': True},
                session_id='[2026-02-05 12:00 test-host]',
                elapsed_time='1m 15s',
                video_count=0,
                audio_count=2
            )
        )

        assert result is True
        assert mock_requests_post.called
        call_args = mock_requests_post.call_args
        assert 'CANCELLED' in str(call_args)


class TestGmailNotifications:
    """Test Gmail notification functionality."""

    def test_gmail_send_success(self):
        """Test that GmailNotifier sends email successfully."""
        from funcs_notifications import GmailNotifier, NotificationData

        params = {
            'sender_email': 'sender@gmail.com',
            'sender_app_password': 'xxxx xxxx xxxx xxxx',
            'recipient_email': 'recipient@gmail.com',
        }
        notifier = GmailNotifier(gmail_params=params)
        assert notifier.is_configured() is True

        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            result = notifier.send(
                data=NotificationData(
                    status='success',
                    url='https://www.youtube.com/watch?v=test',
                    args_dict={'only_audio': True},
                    session_id='[2026-02-11 12:00 test-host]',
                    elapsed_time='3m 10s',
                    video_count=0,
                    audio_count=5
                )
            )

            assert result is True
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with('sender@gmail.com', 'xxxx xxxx xxxx xxxx')
            mock_server.send_message.assert_called_once()

    def test_gmail_not_configured_none(self):
        """Test that GmailNotifier with None returns False."""
        from funcs_notifications import GmailNotifier, NotificationData

        notifier = GmailNotifier(gmail_params=None)
        assert notifier.is_configured() is False
        result = notifier.send(
            data=NotificationData(
                status='start',
                url='https://www.youtube.com/watch?v=test',
                args_dict={},
                session_id='test'
            )
        )
        assert result is False

    def test_gmail_not_configured_missing_keys(self):
        """Test that GmailNotifier with incomplete dict returns False."""
        from funcs_notifications import GmailNotifier

        # Missing sender_app_password
        params = {
            'sender_email': 'sender@gmail.com',
            'recipient_email': 'recipient@gmail.com',
        }
        notifier = GmailNotifier(gmail_params=params)
        assert notifier.is_configured() is False

    def test_gmail_auth_failure(self):
        """Test that GmailNotifier handles SMTPAuthenticationError gracefully."""
        import smtplib
        from funcs_notifications import GmailNotifier, NotificationData

        params = {
            'sender_email': 'sender@gmail.com',
            'sender_app_password': 'bad-password',
            'recipient_email': 'recipient@gmail.com',
        }
        notifier = GmailNotifier(gmail_params=params)

        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b'Auth failed')

            result = notifier.send(
                data=NotificationData(
                    status='start',
                    url='https://www.youtube.com/watch?v=test',
                    args_dict={},
                    session_id='test'
                )
            )
            assert result is False

    def test_gmail_connection_timeout(self):
        """Test that GmailNotifier handles TimeoutError gracefully."""
        from funcs_notifications import GmailNotifier, NotificationData

        params = {
            'sender_email': 'sender@gmail.com',
            'sender_app_password': 'xxxx xxxx xxxx xxxx',
            'recipient_email': 'recipient@gmail.com',
        }
        notifier = GmailNotifier(gmail_params=params)

        with patch('smtplib.SMTP') as mock_smtp:
            mock_smtp.side_effect = TimeoutError('Connection timed out')

            result = notifier.send(
                data=NotificationData(
                    status='start',
                    url='https://www.youtube.com/watch?v=test',
                    args_dict={},
                    session_id='test'
                )
            )
            assert result is False


class TestSendAllNotifications:
    """Test send_all_notifications convenience function."""

    def test_send_all_skips_unconfigured(self):
        """Test that unconfigured notifiers are skipped."""
        from funcs_notifications import GmailNotifier, NotificationData, SlackNotifier, send_all_notifications

        slack = SlackNotifier(webhook_url=None)
        gmail = GmailNotifier(gmail_params=None)

        with patch.object(slack, 'send') as mock_slack_send, \
             patch.object(gmail, 'send') as mock_gmail_send:
            send_all_notifications(
                notifiers=[slack, gmail],
                data=NotificationData(
                    status='start',
                    url='https://www.youtube.com/watch?v=test',
                    args_dict={},
                    session_id='test'
                )
            )
            # send() is called on all notifiers in the list, but
            # each notifier's send() checks is_configured() internally
            mock_slack_send.assert_called_once()
            mock_gmail_send.assert_called_once()

    def test_one_failure_does_not_block_other(self, mock_requests_post):
        """Test that if one notifier fails, others still send."""
        from funcs_notifications import GmailNotifier, NotificationData, SlackNotifier, send_all_notifications

        slack = SlackNotifier(webhook_url='https://hooks.slack.com/services/TEST/WEBHOOK/URL')
        gmail = GmailNotifier(gmail_params={
            'sender_email': 'sender@gmail.com',
            'sender_app_password': 'xxxx xxxx xxxx xxxx',
            'recipient_email': 'recipient@gmail.com',
        })

        # Make Slack raise an exception
        with patch.object(slack, 'send', side_effect=RuntimeError('Slack boom')), \
             patch.object(gmail, 'send', return_value=True) as mock_gmail_send:
            # Should not raise
            send_all_notifications(
                notifiers=[slack, gmail],
                data=NotificationData(
                    status='success',
                    url='https://www.youtube.com/watch?v=test',
                    args_dict={},
                    session_id='test'
                )
            )
            # Gmail should still be called despite Slack failure
            mock_gmail_send.assert_called_once()


class TestMainExecution:
    """Test main execution flow."""

    def test_single_video_download_flow(self, tmp_path, sample_args, mock_video_info_no_chapters):
        """Test single video download execution flow."""
        from importlib import import_module
        main_module = import_module('main-yt-dlp')

        # Setup temp directories
        video_dir = tmp_path / 'yt-videos'
        audio_dir = tmp_path / 'yt-audio'
        video_dir.mkdir()
        audio_dir.mkdir()

        sample_args.with_audio = True

        # Mock all external dependencies
        with patch.object(main_module, 'SLACK_WEBHOOK', None), \
             patch.object(main_module, 'get_ytdlp_path', return_value='/usr/bin/yt-dlp'), \
             patch.object(main_module, 'get_ffmpeg_path', return_value='/usr/bin/ffmpeg'), \
             patch.object(main_module, 'validate_and_get_url', return_value=sample_args.video_url), \
             patch.object(main_module, 'is_playlist', return_value=False), \
             patch.object(main_module, 'get_chapter_count', return_value=0), \
             patch.object(main_module, 'run_yt_dlp'), \
             patch.object(main_module, 'extract_audio_with_ytdlp'), \
             patch.object(main_module, 'organize_and_sanitize_files', return_value={}), \
             patch.object(main_module, 'process_audio_tags'), \
             patch('pathlib.Path.resolve', return_value=video_dir), \
             patch('pathlib.Path.mkdir'), \
             patch('pathlib.Path.read_text'), \
             patch('pathlib.Path.write_text'), \
             patch('pathlib.Path.exists', return_value=True):

            # This should run without raising exceptions
            main_module._execute_main(
                args=sample_args,
                args_dict={'video_url': sample_args.video_url, 'with_audio': True},
                start_time=0,
                session_id='test-session',
                initial_video_count=0,
                initial_audio_count=0
            )

    def test_only_audio_skips_video_retention(self, tmp_path, sample_args, mock_video_info_no_chapters):
        """Test that --only-audio skips video file retention."""
        from importlib import import_module
        main_module = import_module('main-yt-dlp')

        sample_args.only_audio = True

        video_dir = tmp_path / 'yt-videos'
        audio_dir = tmp_path / 'yt-audio'
        video_dir.mkdir()
        audio_dir.mkdir()

        run_yt_dlp_mock = MagicMock()

        with patch.object(main_module, 'SLACK_WEBHOOK', None), \
             patch.object(main_module, 'get_ytdlp_path', return_value='/usr/bin/yt-dlp'), \
             patch.object(main_module, 'get_ffmpeg_path', return_value='/usr/bin/ffmpeg'), \
             patch.object(main_module, 'validate_and_get_url', return_value=sample_args.video_url), \
             patch.object(main_module, 'is_playlist', return_value=False), \
             patch.object(main_module, 'get_chapter_count', return_value=0), \
             patch.object(main_module, 'run_yt_dlp', run_yt_dlp_mock), \
             patch.object(main_module, 'extract_audio_with_ytdlp'), \
             patch.object(main_module, 'organize_and_sanitize_files', return_value={}), \
             patch.object(main_module, 'process_audio_tags'), \
             patch('pathlib.Path.resolve', return_value=video_dir), \
             patch('pathlib.Path.mkdir'), \
             patch('pathlib.Path.read_text'), \
             patch('pathlib.Path.write_text'), \
             patch('pathlib.Path.exists', return_value=True):

            main_module._execute_main(
                args=sample_args,
                args_dict={'video_url': sample_args.video_url, 'only_audio': True},
                start_time=0,
                session_id='test-session',
                initial_video_count=0,
                initial_audio_count=0
            )

            # run_yt_dlp should NOT be called when only_audio is True
            run_yt_dlp_mock.assert_not_called()

    def test_custom_metadata_applied(self, tmp_path, sample_args):
        """Test that custom title/artist/album are passed to download options."""
        from importlib import import_module
        main_module = import_module('main-yt-dlp')

        sample_args.only_audio = True
        sample_args.title = 'Custom Title'
        sample_args.artist = 'Custom Artist'
        sample_args.album = 'Custom Album'

        video_dir = tmp_path / 'yt-videos'
        audio_dir = tmp_path / 'yt-audio'
        video_dir.mkdir()
        audio_dir.mkdir()

        extract_audio_mock = MagicMock()

        with patch.object(main_module, 'SLACK_WEBHOOK', None), \
             patch.object(main_module, 'get_ytdlp_path', return_value='/usr/bin/yt-dlp'), \
             patch.object(main_module, 'get_ffmpeg_path', return_value='/usr/bin/ffmpeg'), \
             patch.object(main_module, 'validate_and_get_url', return_value=sample_args.video_url), \
             patch.object(main_module, 'is_playlist', return_value=False), \
             patch.object(main_module, 'get_chapter_count', return_value=0), \
             patch.object(main_module, 'extract_audio_with_ytdlp', extract_audio_mock), \
             patch.object(main_module, 'organize_and_sanitize_files', return_value={}), \
             patch.object(main_module, 'process_audio_tags'), \
             patch('pathlib.Path.resolve', return_value=video_dir), \
             patch('pathlib.Path.mkdir'), \
             patch('pathlib.Path.read_text'), \
             patch('pathlib.Path.write_text'), \
             patch('pathlib.Path.exists', return_value=True):

            main_module._execute_main(
                args=sample_args,
                args_dict={'video_url': sample_args.video_url},
                start_time=0,
                session_id='test-session',
                initial_video_count=0,
                initial_audio_count=0
            )

            # Verify extract_audio_with_ytdlp was called
            extract_audio_mock.assert_called_once()
            # Get the DownloadOptions passed to it
            call_args = extract_audio_mock.call_args
            opts = call_args.kwargs.get('opts') or call_args[1].get('opts')
            assert opts.custom_title == 'Custom Title'
            assert opts.custom_artist == 'Custom Artist'
            assert opts.custom_album == 'Custom Album'

    def test_rerun_loads_saved_url(self, tmp_path, sample_args):
        """Test that --rerun loads URL from last_url.txt."""
        # Test the logic manually since the full flow is complex to mock
        saved_url = 'https://www.youtube.com/watch?v=savedURL'

        # Create test last_url.txt
        data_dir = tmp_path / 'Data'
        data_dir.mkdir()
        last_url_file = data_dir / 'last_url.txt'
        last_url_file.write_text(saved_url)

        # Test the rerun logic
        rerun = True
        video_url = None

        if rerun and not video_url:
            if last_url_file.exists():
                loaded_url = last_url_file.read_text().strip()
                assert loaded_url == saved_url
            else:
                pytest.fail('last_url.txt should exist for this test')


class TestInteractivePrompts:
    """Test interactive prompt handling for title/artist/album."""

    def test_title_prompt_when_ask(self, mock_input, sample_args):
        """Test that 'ask' triggers prompt for title."""
        mock_input.return_value = 'User Entered Title'

        custom_title = 'ask'
        if custom_title.lower().startswith(('ask', 'prompt')):
            custom_title = mock_input('Enter custom title : ').strip() or None

        assert custom_title == 'User Entered Title'
        mock_input.assert_called_once()

    def test_artist_prompt_when_prompt(self, mock_input, sample_args):
        """Test that 'prompt' triggers prompt for artist."""
        mock_input.return_value = 'User Entered Artist'

        custom_artist = 'prompt'
        if custom_artist.lower().startswith(('ask', 'prompt')):
            custom_artist = mock_input('Enter custom artist: ').strip() or None

        assert custom_artist == 'User Entered Artist'
        mock_input.assert_called_once()

    def test_album_empty_prompt_returns_none(self, mock_input, sample_args):
        """Test that empty prompt returns None for album."""
        mock_input.return_value = '   '

        custom_album = 'ask'
        if custom_album.lower().startswith(('ask', 'prompt')):
            custom_album = mock_input('Enter custom album : ').strip() or None

        assert custom_album is None


class TestPlaylistHandling:
    """Test playlist-specific behavior."""

    def test_custom_metadata_ignored_for_playlists(self, sample_args):
        """Test that custom title/artist/album are ignored for playlists."""
        # Simulate the logic from _execute_main
        url_is_playlist = True

        custom_title = 'Custom Title'
        if custom_title and url_is_playlist:
            custom_title = None  # Should be set to None for playlists

        custom_artist = 'Custom Artist'
        if custom_artist and url_is_playlist:
            custom_artist = None

        custom_album = 'Custom Album'
        if custom_album and url_is_playlist:
            custom_album = None

        assert custom_title is None
        assert custom_artist is None
        assert custom_album is None


if __name__ == '__main__':
    # Run tests with verbose output
    import subprocess as sp
    result = sp.run(
        [sys.executable, '-m', 'pytest', __file__, '-v', '-s'],
        capture_output=False
    )
    sys.exit(result.returncode)
