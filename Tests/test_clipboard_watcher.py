"""Unit tests for the UI-free clipboard watcher (no NiceGUI runtime, no real clipboard)."""

import asyncio
from unittest.mock import Mock

import pyperclip
import pytest

from webapp.services.clipboard_watcher import ClipboardWatcher, _is_youtube_url


def _watcher(captured: list[str]) -> ClipboardWatcher:
    """Build a watcher that records delivered URLs.

    Args:
        captured: List that each delivered YouTube URL is appended to.

    Returns:
        ClipboardWatcher: A watcher wired to the recording list.
    """
    return ClipboardWatcher(on_youtube_url=captured.append)


def test_is_youtube_url_accepts() -> None:
    """Recognises the supported YouTube URL shapes (with/without scheme, www/m, surrounding space)."""
    assert _is_youtube_url('https://www.youtube.com/watch?v=abc123')
    assert _is_youtube_url('http://youtube.com/watch?v=abc')
    assert _is_youtube_url('https://youtu.be/abc123')
    assert _is_youtube_url('youtu.be/abc')
    assert _is_youtube_url('https://m.youtube.com/watch?v=abc')
    assert _is_youtube_url('  https://youtu.be/abc  ')


def test_is_youtube_url_rejects() -> None:
    """Rejects non-YouTube and non-URL strings, and URLs not at the start of the value."""
    assert not _is_youtube_url('')
    assert not _is_youtube_url('just some text')
    assert not _is_youtube_url('https://vimeo.com/12345')
    assert not _is_youtube_url('see https://youtu.be/abc here')


def test_start_seeds_last_seen_no_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    """A URL already on the clipboard when watching starts is not delivered."""
    monkeypatch.setattr(pyperclip, 'paste', lambda: 'https://youtu.be/preexisting')
    captured: list[str] = []
    watcher = _watcher(captured=captured)
    watcher.start()
    asyncio.run(watcher.poll())
    assert captured == []


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
