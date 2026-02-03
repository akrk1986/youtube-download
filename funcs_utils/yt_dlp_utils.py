"""yt-dlp specific utility functions."""
import logging
import os

logger = logging.getLogger(__name__)


def is_format_error(error_text: str | None) -> bool:
    """Check if the error is a format availability error that should be suppressed."""
    if not error_text:
        return False
    format_error_patterns = [
        'Requested format is not available',
        'No video formats found',
        'requested format not available',
    ]
    return any(_pattern.lower() in error_text.lower() for _pattern in format_error_patterns)


def get_cookie_args() -> list[str]:
    """
    Get yt-dlp cookie arguments based on YTDLP_USE_COOKIES environment variable.

    Environment variable usage:
    - YTDLP_USE_COOKIES=chrome    -> Use cookies from Chrome browser
    - YTDLP_USE_COOKIES=firefox   -> Use cookies from Firefox browser
    - YTDLP_USE_COOKIES=<any>     -> Use cookies from Firefox browser (default)
    - YTDLP_USE_COOKIES not set   -> No cookies (empty list)

    Works on Windows, Linux, and WSL.

    Returns:
        list[str]: Cookie arguments for yt-dlp command, or empty list if not configured
    """
    cookie_env = os.getenv('YTDLP_USE_COOKIES', '').strip()

    if not cookie_env:
        return []

    # Determine browser based on environment variable value
    if cookie_env.lower() == 'chrome':
        browser = 'chrome'
    else:
        # Default to Firefox for any other non-empty value
        browser = 'firefox'

    logger.info(f"Using cookies from {browser} browser (YTDLP_USE_COOKIES={cookie_env})")
    # Include --no-cache-dir to force fresh authentication and avoid 403 errors
    # Add --sleep-requests to avoid rate limiting by YouTube
    return ['--cookies-from-browser', browser, '--no-cache-dir', '--sleep-requests', '1']
