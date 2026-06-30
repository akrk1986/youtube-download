#!/usr/bin/env python3
"""Entry point for the yt-dlp download web UI.

Runnable from a PyCharm run configuration or the command line on every OS (Windows PowerShell,
WSL, Linux) after activating the shared venv: ``./webapp-yt-dlp.py``. Optional ``--host`` / ``--port``
override config.json (which defaults to port 8081); ``WEBAPP_HOST`` / ``WEBAPP_PORT`` env vars sit
between them in precedence. ``--native`` launches a standalone desktop window instead of a browser
tab (needs ``pip install pywebview``). All logic lives in the ``webapp`` package.
"""

from webapp.app import run_app

# NiceGUI's reload / native modes re-import this module under multiprocessing as '__mp_main__';
# the guard must accept both names or ui.run() is never reached in the worker (NiceGUI raises).
if __name__ in {'__main__', '__mp_main__'}:
    run_app()
