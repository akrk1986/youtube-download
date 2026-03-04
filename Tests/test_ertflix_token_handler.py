"""Unit tests for ERTFlix token handler functions."""
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

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
    """Tests for resolve_ertflix_token_url function.

    Note: ERTFlix token URL resolution no longer calls yt-dlp as a subprocess.
    The playback URL is extracted directly from the 'content_URL' query parameter
    in the token URL.
    """

    _BASE_TOKEN_URL = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token'

    def _make_token_url(self, content_url: str | None = None, content_id: str = 'TEST') -> str:
        """Build a token URL, optionally embedding a content_URL parameter."""
        url = f'{self._BASE_TOKEN_URL}?content_id={content_id}'
        if content_url is not None:
            url += f'&content_URL={quote(content_url, safe="")}'
        return url

    def test_successful_resolution(self):
        """Test successful resolution: content_URL param is decoded and returned."""
        playback_url = 'https://ert-ucdn.broadpeak-aas.com/bpk-vod/vod-nodrm/default/test/index.mpd'
        token_url = self._make_token_url(content_url=playback_url)

        result = resolve_ertflix_token_url(token_url=token_url, ytdlp_path=Path('/usr/bin/yt-dlp'))

        assert result == playback_url

    def test_missing_content_url_param(self):
        """Test sys.exit when token URL has no content_URL parameter."""
        token_url = f'{self._BASE_TOKEN_URL}?content_id=TEST'

        with pytest.raises(SystemExit):
            resolve_ertflix_token_url(token_url=token_url, ytdlp_path=Path('/usr/bin/yt-dlp'))

    def test_invalid_playback_url_format(self):
        """Test sys.exit when content_URL is not a valid http URL."""
        token_url = self._make_token_url(content_url='not-a-valid-url')

        with pytest.raises(SystemExit):
            resolve_ertflix_token_url(token_url=token_url, ytdlp_path=Path('/usr/bin/yt-dlp'))

    @patch('funcs_for_main_yt_dlp.ertflix_token_handler.sanitize_url_for_subprocess')
    def test_url_sanitization_error(self, mock_sanitize):
        """Test sys.exit when URL sanitization rejects the extracted playback URL."""
        mock_sanitize.side_effect = ValueError('URL contains suspicious characters')
        token_url = self._make_token_url(content_url='https://ert-ucdn.example.com/video.mpd')

        with pytest.raises(SystemExit):
            resolve_ertflix_token_url(token_url=token_url, ytdlp_path=Path('/usr/bin/yt-dlp'))
