"""yt-dlp specific utility functions."""
import logging
import os
import subprocess
import time
from collections.abc import Callable
from typing import TypeVar
from urllib.parse import urlparse

from project_defs import VALID_FACEBOOK_DOMAINS

logger = logging.getLogger(__name__)

# yt-dlp's Facebook extractor fails with 'Cannot parse data' on a page variant that Facebook
# serves at random -- measured at roughly one attempt in three for the same URL, with and
# without browser cookies alike. Repeating the identical command usually lands a parseable
# variant, so every Facebook invocation gets a few attempts before the failure is reported.
FACEBOOK_PARSE_ATTEMPTS = 4
FACEBOOK_PARSE_RETRY_DELAY = 2.0

T = TypeVar('T')


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


def is_facebook_parse_error(url: str, error_text: str | None) -> bool:
    """Check if a Facebook URL failed with yt-dlp's 'Cannot parse data' extractor error.

    Facebook serves an unparseable page variant at random, independently of whether browser
    cookies are used, so the same command often succeeds on the next try. Callers use this to
    decide whether the failure is worth retrying (see retry_on_facebook_parse_error).
    """
    if not error_text or 'cannot parse data' not in error_text.lower():
        return False
    parsed = urlparse(url)
    return any(domain in parsed.netloc for domain in VALID_FACEBOOK_DOMAINS)


def retry_on_facebook_parse_error(attempt: Callable[[int], T], url: str, label: str) -> T:
    """Repeat a yt-dlp attempt while it fails with Facebook's 'Cannot parse data' extractor error.

    The failure is not caused by the browser cookies: Facebook serves the unparseable page
    variant at random, so the same command succeeds on a later try. Any other failure propagates
    at once -- only this one is worth repeating.

    Args:
        attempt: Runs a single attempt, receiving the 1-based attempt number so that the caller
            can vary the command between tries (both callers drop the cookies after the first).
        url: The URL being downloaded or probed, used to recognise a Facebook failure.
        label: Name of the operation, used in the retry warnings.

    Returns:
        T: Whatever the first successful attempt returns.

    Raises:
        subprocess.CalledProcessError: If the final attempt fails, or any attempt fails with
            an error other than Facebook's 'Cannot parse data'.
    """
    attempt_number = 0
    while True:
        attempt_number += 1
        try:
            return attempt(attempt_number)
        except subprocess.CalledProcessError as e:
            last_attempt = attempt_number >= FACEBOOK_PARSE_ATTEMPTS
            if last_attempt or not is_facebook_parse_error(url=url, error_text=e.stderr):
                raise
            logger.warning(f"{label} hit Facebook's 'Cannot parse data' extractor error "
                           f'(attempt {attempt_number} of {FACEBOOK_PARSE_ATTEMPTS}), '
                           f'retrying in {FACEBOOK_PARSE_RETRY_DELAY:g} seconds')
            time.sleep(FACEBOOK_PARSE_RETRY_DELAY)


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
