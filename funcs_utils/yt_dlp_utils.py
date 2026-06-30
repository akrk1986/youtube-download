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
    elif cookie_env.lower() == 'firefox':
        browser = 'firefox'
    else:
        logger.warning(f"Unrecognized YTDLP_USE_COOKIES value '{cookie_env}', defaulting to firefox")
        browser = 'firefox'

    logger.debug(f"Using cookies from {browser} browser (YTDLP_USE_COOKIES={cookie_env})")
    # Include --no-cache-dir to force fresh authentication and avoid 403 errors
    # Add --sleep-requests to avoid rate limiting by YouTube
    return ['--cookies-from-browser', browser, '--no-cache-dir', '--sleep-requests', '1']


def is_auth_error(error_text: str | None) -> bool:
    """Check if the error text looks like an authentication / cookie-related failure."""
    if not error_text:
        return False
    auth_error_patterns = [
        'sign in to confirm',
        "confirm you're not a bot",
        'this video is private',
        'private video',
        'members-only',
        'join this channel',
        'age-restricted',
        'age restricted',
        'login required',
        'log in',
        'use --cookies',
        '--cookies-from-browser',
        'http error 403',
    ]
    return any(_pattern in error_text.lower() for _pattern in auth_error_patterns)


def warn_if_auth_error(error_text: str | None) -> None:
    """Log a cookie-related hint when a download failure looks like an auth problem."""
    if not is_auth_error(error_text):
        return

    cookie_env = os.getenv('YTDLP_USE_COOKIES', '').strip()
    if cookie_env:
        logger.warning(f'Download may have failed because the browser cookies '
                       f'(YTDLP_USE_COOKIES={cookie_env}) are missing, expired, or for the wrong browser')
    else:
        logger.warning('Download may have failed because no browser cookies are being used. '
                       'Set YTDLP_USE_COOKIES=firefox (or chrome) to use your logged-in session')
