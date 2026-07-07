#!/usr/bin/env python3
"""Clipboard probe: show exactly what the OS clipboard contains and how the watcher judges it.

Diagnostic for the webapp clipboard watcher. Run it (on Windows, from PyCharm or a terminal with
the shared venv active), then copy things — e.g. right-click a link in a Gmail message and choose
'Copy link address'. Every new clipboard value is printed as repr() together with the watcher's
verdict (_extract_media_url result), so mismatches between the real clipboard content and the
matcher are visible immediately. Stop with Ctrl+C.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pyperclip  # noqa: E402

from webapp.services.clipboard_watcher import _extract_media_url  # noqa: E402

_POLL_SECONDS = 0.5
_MAX_SHOWN = 500


def _force_utf8_console() -> None:
    """Reconfigure stdout/stderr to UTF-8 so any clipboard content prints safely on Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if reconfigure is not None:
            reconfigure(encoding='utf-8', errors='replace')


def main() -> None:
    """Poll the clipboard and report each new value with the watcher's verdict."""
    _force_utf8_console()
    print(f'Polling the clipboard every {_POLL_SECONDS}s - copy something (Ctrl+C to stop)...',
          flush=True)
    last_seen: str | None = None
    while True:
        try:
            value = pyperclip.paste()
        except Exception as exc:  # noqa: BLE001 - show the failure instead of dying
            print(f'[clipboard read failed: {type(exc).__name__}: {exc}]', flush=True)
            time.sleep(_POLL_SECONDS)
            continue
        if value != last_seen:
            last_seen = value
            shown = value if len(value) <= _MAX_SHOWN else value[:_MAX_SHOWN] + '...<truncated>'
            print(f'\nNEW clipboard value ({len(value)} chars):', flush=True)
            print(f'  repr: {shown!r}', flush=True)
            media_url = _extract_media_url(value)
            if media_url is None:
                print('  verdict: NOT matched (watcher would ignore this)', flush=True)
            else:
                print(f"  verdict: matched -> would deliver '{media_url}'", flush=True)
        time.sleep(_POLL_SECONDS)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nStopped.', flush=True)
