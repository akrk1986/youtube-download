"""Tests for get_playlist_entries and the empty-playlist early-exit signal."""
from unittest.mock import MagicMock, patch

import pytest

from funcs_video_info import EmptyPlaylistError, get_playlist_entries


def _mock_ydl(info: dict) -> MagicMock:
    """Build a mock yt_dlp.YoutubeDL context manager whose extract_info returns info.

    Args:
        info: The dict that extract_info should return.

    Returns:
        MagicMock: A context-manager mock suitable as YoutubeDL's return value.
    """
    ctx = MagicMock()
    ctx.__enter__.return_value.extract_info.return_value = info
    ctx.__exit__.return_value = False
    return ctx


def test_empty_playlist_error_is_runtimeerror_subclass() -> None:
    """EmptyPlaylistError subclasses RuntimeError so existing handlers keep working."""
    assert issubclass(EmptyPlaylistError, RuntimeError)


@patch('funcs_video_info.metadata.yt_dlp.YoutubeDL')
def test_empty_playlist_raises_empty_error(mock_ydl_cls: MagicMock) -> None:
    """A playlist with no entries raises EmptyPlaylistError (distinct from a generic failure)."""
    mock_ydl_cls.return_value = _mock_ydl(info={'entries': []})
    with pytest.raises(EmptyPlaylistError):
        get_playlist_entries(url='https://youtube.com/playlist?list=EMPTY')


@patch('funcs_video_info.metadata.yt_dlp.YoutubeDL')
def test_populated_playlist_returns_entries(mock_ydl_cls: MagicMock) -> None:
    """A populated playlist returns (title, watch_url) tuples, building the URL from id when absent."""
    info = {'entries': [{'title': 'A', 'id': 'aaa'}, {'title': 'B', 'url': 'https://x/b'}]}
    mock_ydl_cls.return_value = _mock_ydl(info=info)
    result = get_playlist_entries(url='https://youtube.com/playlist?list=FULL')
    assert result == [('A', 'https://www.youtube.com/watch?v=aaa'), ('B', 'https://x/b')]


@patch('funcs_video_info.metadata.yt_dlp.YoutubeDL')
def test_extraction_failure_raises_plain_runtimeerror(mock_ydl_cls: MagicMock) -> None:
    """An extraction failure raises RuntimeError but not the empty-playlist subclass."""
    ctx = MagicMock()
    ctx.__enter__.return_value.extract_info.side_effect = ValueError('boom')
    ctx.__exit__.return_value = False
    mock_ydl_cls.return_value = ctx
    with pytest.raises(RuntimeError) as exc_info:
        get_playlist_entries(url='https://youtube.com/playlist?list=BAD')
    assert not isinstance(exc_info.value, EmptyPlaylistError)
