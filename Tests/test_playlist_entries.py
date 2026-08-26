"""Tests for the flat yt-dlp probes: get_playlist_entries, the empty-playlist early-exit
signal, and the cookie-less retry behind is_playlist."""
import logging
from unittest.mock import MagicMock, patch

import pytest

from funcs_video_info import EmptyPlaylistError, get_playlist_entries, is_playlist


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


def _failing_ydl(error: Exception) -> MagicMock:
    """Build a mock YoutubeDL context manager whose extract_info raises.

    Args:
        error: The exception extract_info should raise.

    Returns:
        MagicMock: A context-manager mock suitable as YoutubeDL's return value.
    """
    ctx = MagicMock()
    ctx.__enter__.return_value.extract_info.side_effect = error
    ctx.__exit__.return_value = False
    return ctx


@patch('funcs_video_info.metadata.yt_dlp.YoutubeDL')
def test_is_playlist_retries_without_cookies(mock_ydl_cls: MagicMock,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    """A cookie-bearing probe that YouTube rejects is retried without the cookies."""
    monkeypatch.setenv('YTDLP_USE_COOKIES', 'firefox')
    rejected = Exception('ERROR: [youtube] P_qjW1txyY8: The page needs to be reloaded.')
    mock_ydl_cls.side_effect = [_failing_ydl(error=rejected),
                                _mock_ydl(info={'webpage_url_basename': 'playlist'})]

    assert is_playlist(url='https://youtube.com/playlist?list=ABC') is True

    first_opts, second_opts = (call.kwargs['params'] for call in mock_ydl_cls.call_args_list)
    assert first_opts['cookiesfrombrowser'] == ('firefox',)
    assert 'cookiesfrombrowser' not in second_opts


@patch('funcs_video_info.metadata.yt_dlp.YoutubeDL')
def test_is_playlist_probes_once_when_no_cookies_configured(mock_ydl_cls: MagicMock,
                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """With no cookies to drop there is nothing to retry, so the probe runs exactly once."""
    monkeypatch.delenv('YTDLP_USE_COOKIES', raising=False)
    mock_ydl_cls.return_value = _mock_ydl(info={'webpage_url_basename': 'watch'})

    assert is_playlist(url='https://youtu.be/abc') is False
    assert mock_ydl_cls.call_count == 1


@patch('funcs_video_info.metadata.yt_dlp.YoutubeDL')
def test_is_playlist_logs_error_only_after_both_attempts_fail(mock_ydl_cls: MagicMock,
                                                              monkeypatch: pytest.MonkeyPatch,
                                                              caplog: pytest.LogCaptureFixture) -> None:
    """The failed cookie attempt stays at debug; only the final failure is logged as an error."""
    monkeypatch.setenv('YTDLP_USE_COOKIES', 'firefox')
    mock_ydl_cls.side_effect = [_failing_ydl(error=Exception('rejected')),
                                _failing_ydl(error=Exception('still rejected'))]

    with caplog.at_level(logging.ERROR, logger='funcs_video_info.metadata'):
        assert is_playlist(url='https://youtu.be/abc') is False

    assert len(caplog.records) == 1
    assert 'still rejected' in caplog.records[0].message


@patch('funcs_video_info.metadata.yt_dlp.YoutubeDL')
def test_playlist_entries_retries_without_cookies(mock_ydl_cls: MagicMock,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """Enumeration survives a rejected cookie probe instead of failing the run."""
    monkeypatch.setenv('YTDLP_USE_COOKIES', 'firefox')
    rejected = Exception('ERROR: [youtube] LIST: The page needs to be reloaded.')
    mock_ydl_cls.side_effect = [_failing_ydl(error=rejected),
                                _mock_ydl(info={'entries': [{'title': 'A', 'id': 'aaa'}]})]

    assert get_playlist_entries(url='https://youtube.com/playlist?list=ABC') == [
        ('A', 'https://www.youtube.com/watch?v=aaa')]
    assert mock_ydl_cls.call_count == 2
