"""Unit tests for ERTFlix token handler functions."""
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from funcs_for_main_yt_dlp.ertflix_token_handler import (
    is_ertflix_token_url,
    resolve_ertflix_token_url,
)


class TestIsErtflixTokenUrl:
    """Tests for is_ertflix_token_url function."""

    def test_valid_token_url(self):
        """Test detection of valid ERTFlix token API URL."""
        url = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?content_id=DRM_PS027309_DASH'
        assert is_ertflix_token_url(url=url) is True

    def test_token_url_with_params(self):
        """Test detection with multiple query parameters."""
        url = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?content_id=123&type=account'
        assert is_ertflix_token_url(url=url) is True

    def test_youtube_url(self):
        """Test that YouTube URLs are not detected as token URLs."""
        url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        assert is_ertflix_token_url(url=url) is False

    def test_ertflix_video_page(self):
        """Test that ERTFlix video pages are not detected as token URLs."""
        url = 'https://www.ertflix.gr/#/details/ERT_PS054741_E0'
        assert is_ertflix_token_url(url=url) is False

    def test_direct_mpd_url(self):
        """Test that direct .mpd URLs are not detected as token URLs."""
        url = 'https://ert-ucdn.broadpeak-aas.com/bpk-vod/vod-nodrm/default/parea-ep28/index.mpd'
        assert is_ertflix_token_url(url=url) is False

    def test_empty_string(self):
        """Test that empty string is not detected as token URL."""
        assert is_ertflix_token_url(url='') is False


class TestResolveErtflixTokenUrl:
    """Tests for resolve_ertflix_token_url function."""

    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.subprocess.run')
    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.get_cookie_args')
    def test_successful_resolution(self, mock_get_cookie_args, mock_subprocess_run):
        """Test successful token URL resolution."""
        # Mock cookie args (simulate YTDLP_USE_COOKIES=firefox)
        mock_get_cookie_args.return_value = [
            '--cookies-from-browser', 'firefox',
            '--no-cache-dir', '--sleep-requests', '1'
        ]

        # Mock successful yt-dlp response
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            'playbackUrl': 'https://ert-ucdn.broadpeak-aas.com/bpk-vod/vod-nodrm/default/test/index.mpd',
            'other_field': 'value'
        })
        mock_result.stderr = ''
        mock_subprocess_run.return_value = mock_result

        token_url = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?content_id=TEST'
        ytdlp_path = Path('/usr/bin/yt-dlp')

        result = resolve_ertflix_token_url(token_url=token_url, ytdlp_path=ytdlp_path)

        assert result == 'https://ert-ucdn.broadpeak-aas.com/bpk-vod/vod-nodrm/default/test/index.mpd'
        mock_subprocess_run.assert_called_once()

        # Verify command structure
        call_args = mock_subprocess_run.call_args
        cmd = call_args[0][0]
        assert str(ytdlp_path) in cmd
        assert '--dump-json' in cmd
        assert '--cookies-from-browser' in cmd
        assert 'firefox' in cmd

    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.subprocess.run')
    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.get_cookie_args')
    def test_no_cookies_warning(self, mock_get_cookie_args, mock_subprocess_run):
        """Test warning when YTDLP_USE_COOKIES not set."""
        # Mock no cookies
        mock_get_cookie_args.return_value = []

        # Mock successful response anyway (API might work without cookies for some content)
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            'playbackUrl': 'https://example.com/video.mpd'
        })
        mock_result.stderr = ''
        mock_subprocess_run.return_value = mock_result

        token_url = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?content_id=TEST'
        ytdlp_path = Path('/usr/bin/yt-dlp')

        # Should still work but log warning
        result = resolve_ertflix_token_url(token_url=token_url, ytdlp_path=ytdlp_path)
        assert result == 'https://example.com/video.mpd'

    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.subprocess.run')
    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.get_cookie_args')
    def test_subprocess_error(self, mock_get_cookie_args, mock_subprocess_run):
        """Test handling of subprocess error (non-zero exit code)."""
        mock_get_cookie_args.return_value = []

        # Mock failed subprocess
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ''
        mock_result.stderr = 'ERROR: Some yt-dlp error'
        mock_subprocess_run.return_value = mock_result

        token_url = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?content_id=TEST'
        ytdlp_path = Path('/usr/bin/yt-dlp')

        with pytest.raises(SystemExit):
            resolve_ertflix_token_url(token_url=token_url, ytdlp_path=ytdlp_path)

    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.subprocess.run')
    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.get_cookie_args')
    def test_authentication_error(self, mock_get_cookie_args, mock_subprocess_run):
        """Test handling of authentication errors (403/401)."""
        mock_get_cookie_args.return_value = []

        # Mock authentication failure
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ''
        mock_result.stderr = 'ERROR: HTTP Error 403: Forbidden'
        mock_subprocess_run.return_value = mock_result

        token_url = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?content_id=TEST'
        ytdlp_path = Path('/usr/bin/yt-dlp')

        with pytest.raises(SystemExit):
            resolve_ertflix_token_url(token_url=token_url, ytdlp_path=ytdlp_path)

    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.subprocess.run')
    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.get_cookie_args')
    def test_timeout_error(self, mock_get_cookie_args, mock_subprocess_run):
        """Test handling of subprocess timeout."""
        mock_get_cookie_args.return_value = []

        # Mock timeout
        mock_subprocess_run.side_effect = subprocess.TimeoutExpired(cmd='yt-dlp', timeout=5400)

        token_url = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?content_id=TEST'
        ytdlp_path = Path('/usr/bin/yt-dlp')

        with pytest.raises(SystemExit):
            resolve_ertflix_token_url(token_url=token_url, ytdlp_path=ytdlp_path)

    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.subprocess.run')
    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.get_cookie_args')
    def test_invalid_json_response(self, mock_get_cookie_args, mock_subprocess_run):
        """Test handling of malformed JSON response."""
        mock_get_cookie_args.return_value = []

        # Mock response with invalid JSON
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = 'This is not valid JSON'
        mock_result.stderr = ''
        mock_subprocess_run.return_value = mock_result

        token_url = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?content_id=TEST'
        ytdlp_path = Path('/usr/bin/yt-dlp')

        with pytest.raises(SystemExit):
            resolve_ertflix_token_url(token_url=token_url, ytdlp_path=ytdlp_path)

    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.subprocess.run')
    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.get_cookie_args')
    def test_missing_playback_url_field(self, mock_get_cookie_args, mock_subprocess_run):
        """Test handling of missing playbackUrl field in response."""
        mock_get_cookie_args.return_value = []

        # Mock response without playbackUrl field
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            'some_other_field': 'value',
            'another_field': 123
        })
        mock_result.stderr = ''
        mock_subprocess_run.return_value = mock_result

        token_url = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?content_id=TEST'
        ytdlp_path = Path('/usr/bin/yt-dlp')

        with pytest.raises(SystemExit):
            resolve_ertflix_token_url(token_url=token_url, ytdlp_path=ytdlp_path)

    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.subprocess.run')
    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.get_cookie_args')
    def test_invalid_playback_url_format(self, mock_get_cookie_args, mock_subprocess_run):
        """Test handling of invalid playbackUrl format."""
        mock_get_cookie_args.return_value = []

        # Mock response with invalid URL
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            'playbackUrl': 'not-a-valid-url'
        })
        mock_result.stderr = ''
        mock_subprocess_run.return_value = mock_result

        token_url = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?content_id=TEST'
        ytdlp_path = Path('/usr/bin/yt-dlp')

        with pytest.raises(SystemExit):
            resolve_ertflix_token_url(token_url=token_url, ytdlp_path=ytdlp_path)

    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.sanitize_url_for_subprocess')
    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.get_cookie_args')
    def test_url_sanitization_error(self, mock_get_cookie_args, mock_sanitize):
        """Test handling of URL sanitization failure."""
        mock_get_cookie_args.return_value = []

        # Mock sanitization raising ValueError
        mock_sanitize.side_effect = ValueError('URL contains suspicious characters')

        token_url = 'https://api.ertflix.opentv.com/token?evil=`rm -rf /`'
        ytdlp_path = Path('/usr/bin/yt-dlp')

        with pytest.raises(SystemExit):
            resolve_ertflix_token_url(token_url=token_url, ytdlp_path=ytdlp_path)
