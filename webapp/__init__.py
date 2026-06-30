"""Local NiceGUI web app wrapping the ``main-yt-dlp.py`` driver.

Renders a curated set of PyCharm-run-configuration presets as a browser form, shells out to the
driver (or ``run-linters.py``) via ``asyncio.create_subprocess_exec``, and streams the live output
into a scrollable log. The driver scripts themselves are never modified.
"""
