"""Subprocess hand-off of a captured token URL to main-yt-dlp.py."""
import logging
import subprocess  # nosec B404
import sys
from pathlib import Path

from funcs_utils import sanitize_url_for_subprocess


logger = logging.getLogger(__name__)


def build_ytdlp_argv(token_url: str, passthrough_args: list[str],
                     python_exe: Path | str | None = None,
                     script_path: Path | str = 'main-yt-dlp.py') -> list[str]:
    """Build the argv list for the `main-yt-dlp.py --ertflix-program` subprocess.

    Args:
        token_url: The ERTFlix token API URL captured from the browser.
        passthrough_args: Extra CLI flags to forward (e.g. --only-audio).
        python_exe: Python interpreter to use. Defaults to sys.executable.
        script_path: Path to main-yt-dlp.py (defaults to the bare name so
            it's resolved relative to the current working directory).

    Returns:
        list[str]: argv suitable for subprocess.run(...).
    """
    safe_url = sanitize_url_for_subprocess(url=token_url)
    interpreter = str(python_exe) if python_exe is not None else sys.executable
    return [interpreter, str(script_path), '--ertflix-program', safe_url, *passthrough_args]


def hand_off_to_ytdlp(token_url: str, passthrough_args: list[str]) -> int:
    """Run `main-yt-dlp.py --ertflix-program <token>` and return its exit code.

    Args:
        token_url: The ERTFlix token API URL captured from the browser.
        passthrough_args: Extra CLI flags to forward to main-yt-dlp.py.

    Returns:
        int: The child process exit code.
    """
    argv = build_ytdlp_argv(token_url=token_url, passthrough_args=passthrough_args)
    logger.info(f'Handing off to main-yt-dlp.py with {len(passthrough_args)} pass-through flag(s)')
    logger.debug(f'Subprocess argv: {argv}')
    completed = subprocess.run(argv, check=False)  # nosec B603
    return completed.returncode
