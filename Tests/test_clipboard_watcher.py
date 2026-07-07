"""Unit tests for the UI-free clipboard watcher (no NiceGUI runtime, no real clipboard)."""

import asyncio
from unittest.mock import Mock

import pyperclip
import pytest

from webapp.services.clipboard_watcher import ClipboardWatcher, _extract_media_url, _is_media_url


def _watcher(captured: list[str]) -> ClipboardWatcher:
    """Build a watcher that records delivered URLs.

    Args:
        captured: List that each delivered media URL is appended to.

    Returns:
        ClipboardWatcher: A watcher wired to the recording list.
    """
    return ClipboardWatcher(on_media_url=captured.append)


def test_is_media_url_accepts_youtube() -> None:
    """Recognises the supported YouTube URL shapes (with/without scheme, www/m, surrounding space)."""
    assert _is_media_url('https://www.youtube.com/watch?v=abc123')
    assert _is_media_url('http://youtube.com/watch?v=abc')
    assert _is_media_url('https://youtu.be/abc123')
    assert _is_media_url('youtu.be/abc')
    assert _is_media_url('https://m.youtube.com/watch?v=abc')
    assert _is_media_url('  https://youtu.be/abc  ')
    # Playlists, shorts, YouTube Music, and watch+list combos are all valid yt-dlp inputs.
    assert _is_media_url('https://www.youtube.com/playlist?list=PLabc123')
    assert _is_media_url('https://youtube.com/playlist?list=PLabc')
    assert _is_media_url('https://music.youtube.com/playlist?list=PLabc')
    assert _is_media_url('https://www.youtube.com/shorts/abc123')
    assert _is_media_url('https://www.youtube.com/watch?v=abc&list=PLabc')


def test_is_media_url_accepts_facebook() -> None:
    """Recognises the supported Facebook video URL shapes (watch, permalink, reel, share, fb.watch)."""
    assert _is_media_url('https://www.facebook.com/watch?v=1234567890')
    assert _is_media_url('https://www.facebook.com/watch/?v=1234567890')
    assert _is_media_url('facebook.com/watch?v=1234567890')
    assert _is_media_url('https://m.facebook.com/watch?v=1234567890')
    assert _is_media_url('https://web.facebook.com/watch?v=1234567890')
    assert _is_media_url('https://www.facebook.com/somepage/videos/1234567890')
    assert _is_media_url('https://www.facebook.com/video.php?v=1234567890')
    assert _is_media_url('https://www.facebook.com/reel/1234567890')
    assert _is_media_url('https://www.facebook.com/share/v/AbCdEf123/')
    assert _is_media_url('https://www.facebook.com/share/r/AbCdEf123/')
    assert _is_media_url('https://fb.watch/AbCdEf123/')
    assert _is_media_url('fb.watch/AbCdEf123')
    assert _is_media_url('  https://fb.watch/AbCdEf123  ')


def test_is_media_url_rejects() -> None:
    """Rejects non-media and non-URL strings, and URLs not at the start of the value."""
    assert not _is_media_url('')
    assert not _is_media_url('just some text')
    assert not _is_media_url('https://vimeo.com/12345')
    assert not _is_media_url('see https://youtu.be/abc here')
    # Facebook non-video pages: a profile/page URL, the bare domain, and a photo link.
    assert not _is_media_url('https://www.facebook.com/somepage')
    assert not _is_media_url('https://www.facebook.com')
    assert not _is_media_url('https://www.facebook.com/photo/?fbid=123')
    assert not _is_media_url('see https://fb.watch/abc here')


def test_extract_media_url_unwraps_gmail_redirect() -> None:
    """A link copied from a Gmail message (Google redirect wrapper) yields the clean target URL."""
    wrapped = ('https://www.google.com/url?q=https://www.youtube.com/watch%3Fv%3Dabc123'
               '&source=gmail&ust=1751900000000000&usg=AOvVaw0abcDEF')
    assert _extract_media_url(wrapped) == 'https://www.youtube.com/watch?v=abc123'
    # Country TLD and a Facebook target work too.
    wrapped_il = 'https://www.google.co.il/url?q=https://fb.watch/AbCdEf123/&source=gmail'
    assert _extract_media_url(wrapped_il) == 'https://fb.watch/AbCdEf123/'
    # A wrapper whose target is not a media URL is not delivered.
    assert _extract_media_url('https://www.google.com/url?q=https://vimeo.com/123&source=gmail') is None
    # An unwrapped media URL passes through (stripped); a non-URL does not.
    assert _extract_media_url('  https://youtu.be/abc  ') == 'https://youtu.be/abc'
    assert _extract_media_url('just some text') is None


def test_gmail_wrapped_copy_delivers_unwrapped_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Copying a Gmail-wrapped YouTube link fires the callback with the unwrapped URL."""
    clip = {'value': ''}
    monkeypatch.setattr(pyperclip, 'paste', lambda: clip['value'])
    captured: list[str] = []
    watcher = _watcher(captured=captured)
    watcher.start()
    clip['value'] = 'https://www.google.com/url?q=https://youtu.be/NEW%3Ft%3D42&source=gmail'
    asyncio.run(watcher.poll())
    assert captured == ['https://youtu.be/NEW?t=42']


def test_start_delivers_preexisting_url_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A media URL already on the clipboard is delivered at start, and polls do not re-deliver it."""
    monkeypatch.setattr(pyperclip, 'paste', lambda: 'https://youtu.be/preexisting')
    captured: list[str] = []
    watcher = _watcher(captured=captured)
    watcher.start()
    asyncio.run(watcher.poll())
    asyncio.run(watcher.poll())
    assert captured == ['https://youtu.be/preexisting']


def test_start_with_non_media_clipboard_delivers_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-media clipboard value at start is only recorded as the baseline, not delivered."""
    monkeypatch.setattr(pyperclip, 'paste', lambda: 'just some text')
    captured: list[str] = []
    watcher = _watcher(captured=captured)
    watcher.start()
    asyncio.run(watcher.poll())
    assert captured == []


def test_start_unwraps_preexisting_gmail_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Gmail-wrapped link copied before 'Start watching' is delivered unwrapped at start."""
    wrapped = 'https://www.google.com/url?q=https://www.facebook.com/watch%3Fv%3D123&source=gmail'
    monkeypatch.setattr(pyperclip, 'paste', lambda: wrapped)
    captured: list[str] = []
    watcher = _watcher(captured=captured)
    watcher.start()
    assert captured == ['https://www.facebook.com/watch?v=123']


def test_new_youtube_url_delivered_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A new YouTube copy fires the callback once; re-polling without a change does not refire."""
    clip = {'value': 'nothing-yet'}
    monkeypatch.setattr(pyperclip, 'paste', lambda: clip['value'])
    captured: list[str] = []
    watcher = _watcher(captured=captured)
    watcher.start()
    clip['value'] = 'https://youtu.be/NEW'
    asyncio.run(watcher.poll())
    asyncio.run(watcher.poll())
    assert captured == ['https://youtu.be/NEW']


def test_non_youtube_copy_not_delivered(monkeypatch: pytest.MonkeyPatch) -> None:
    """A new non-YouTube copy updates last-seen but is not delivered to the callback."""
    clip = {'value': ''}
    monkeypatch.setattr(pyperclip, 'paste', lambda: clip['value'])
    captured: list[str] = []
    watcher = _watcher(captured=captured)
    watcher.start()
    clip['value'] = 'https://vimeo.com/123'
    asyncio.run(watcher.poll())
    assert captured == []


def test_disabled_poll_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    """poll() does nothing while the watcher is disabled (never started)."""
    monkeypatch.setattr(pyperclip, 'paste', lambda: 'https://youtu.be/x')
    captured: list[str] = []
    watcher = _watcher(captured=captured)
    asyncio.run(watcher.poll())
    assert captured == []
    assert not watcher.is_enabled()


def test_paste_failure_is_skipped_and_watcher_stays_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pyperclip failure (e.g. WSL empty clipboard) is skipped; the watcher keeps running."""
    monkeypatch.setattr(pyperclip, 'paste',
                        Mock(side_effect=pyperclip.PyperclipException('Array cannot be null')))
    captured: list[str] = []
    watcher = _watcher(captured=captured)
    watcher.start()  # seeding paste fails, but start() must not disable
    assert watcher.is_enabled()
    asyncio.run(watcher.poll())  # must not raise despite the failing paste
    assert captured == []


def test_recovers_after_transient_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """After failing reads (start + first poll), a later successful YouTube copy is delivered."""
    # paste() is called by start(), then by each poll(); fail twice, then return a URL.
    monkeypatch.setattr(pyperclip, 'paste', Mock(side_effect=[
        pyperclip.PyperclipException('empty'),
        pyperclip.PyperclipException('empty'),
        'https://youtu.be/LATER',
    ]))
    captured: list[str] = []
    watcher = _watcher(captured=captured)
    watcher.start()              # fails -> last_seen None, still enabled
    asyncio.run(watcher.poll())  # still failing -> skipped
    asyncio.run(watcher.poll())  # now succeeds with a new YouTube URL
    assert captured == ['https://youtu.be/LATER']
