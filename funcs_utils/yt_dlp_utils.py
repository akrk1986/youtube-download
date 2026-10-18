"""yt-dlp specific utility functions."""
import logging
import os
import platform
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

# Browser whose cookies a Facebook URL gets on native Windows when YTDLP_USE_COOKIES is unset.
DEFAULT_FACEBOOK_COOKIE_BROWSER = 'firefox'

T = TypeVar('T')


class FacebookLoginRequiredError(RuntimeError):
    """Raised when every attempt on a Facebook URL fails with 'Cannot parse data'.

    The random unparseable page variant clears within a few attempts; a video shown only to
    logged-in users (friends-only, group, age-gated) fails every time, because logged-out
    Facebook serves a generic page with no video data. A known outcome rather than a bug, so
    main() reports it without a traceback. A subclass of RuntimeError so existing
    ``except RuntimeError`` callers keep working.
    """


def _is_facebook_url(url: str) -> bool:
    """Check whether a URL points at a Facebook domain.

    Args:
        url: The URL to check.

    Returns:
        bool: True when the URL's host is one of VALID_FACEBOOK_DOMAINS.
    """
    return any(domain in urlparse(url).netloc for domain in VALID_FACEBOOK_DOMAINS)


def _warn_facebook_login_needed(url: str) -> None:
    """Log that a Facebook video failing every parse attempt likely needs a logged-in session.

    Args:
        url: The Facebook URL that failed every attempt, used to tell which cookies were sent.
    """
    browser = cookie_browser(url=url)
    if browser:
        logger.warning(f'Facebook returned no video data on every attempt, including the first one with '
                       f'the {browser} browser cookies. Check that the video plays in {browser} while '
                       f'logged in; under WSL the Windows browser profile cannot be read, so run on '
                       f'native Windows')
        return
    logger.warning('Facebook returned no video data on every attempt -- the video is probably visible '
                   'only to logged-in users. Run on native Windows (Facebook URLs use Firefox cookies by '
                   'default there) or set YTDLP_USE_COOKIES=firefox (or chrome)')


def cookie_browser(url: str | None = None) -> str:
    """Return the browser whose cookies yt-dlp should use for a URL, or '' for no cookies.

    YTDLP_USE_COOKIES decides when set: 'chrome' or 'firefox', 'none' to turn cookies off, and any
    other value falls back to firefox with a warning. When it is unset, a Facebook URL on native
    Windows gets DEFAULT_FACEBOOK_COOKIE_BROWSER -- Facebook shows some videos only to a logged-in
    session. Other sites stay anonymous, since cookies add --sleep-requests to every call and put
    the YouTube account at risk; so do WSL, Linux, and macOS, where the Windows browser profile is
    unreachable and yt-dlp fails on the missing cookie database.

    Args:
        url: The URL about to be fetched; None when it is unknown, which disables the default.

    Returns:
        str: 'chrome', 'firefox', or '' when no cookies should be used.
    """
    cookie_env = os.getenv('YTDLP_USE_COOKIES', '').strip()
    if not cookie_env:
        if url and platform.system() == 'Windows' and _is_facebook_url(url=url):
            return DEFAULT_FACEBOOK_COOKIE_BROWSER
        return ''
    if cookie_env.lower() == 'none':
        return ''
    if cookie_env.lower() in ('chrome', 'firefox'):
        return cookie_env.lower()
    logger.warning(f"Unrecognized YTDLP_USE_COOKIES value '{cookie_env}', defaulting to firefox")
    return 'firefox'


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


def get_cookie_args(url: str | None = None) -> list[str]:
    """
    Get yt-dlp cookie arguments for a URL, as chosen by cookie_browser().

    Environment variable usage:
    - YTDLP_USE_COOKIES=chrome    -> Use cookies from Chrome browser
    - YTDLP_USE_COOKIES=firefox   -> Use cookies from Firefox browser
    - YTDLP_USE_COOKIES=none      -> No cookies, not even the Facebook default
    - YTDLP_USE_COOKIES=<any>     -> Use cookies from Firefox browser (default)
    - YTDLP_USE_COOKIES not set   -> Firefox cookies for Facebook URLs on native Windows, else none

    Works on Windows, Linux, and WSL.

    Args:
        url: The URL about to be fetched; None skips the Facebook default.

    Returns:
        list[str]: Cookie arguments for yt-dlp command, or empty list if not configured
    """
    browser = cookie_browser(url=url)
    if not browser:
        return []

    logger.debug(f'Using cookies from {browser} browser')
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
    return _is_facebook_url(url=url)


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
        subprocess.CalledProcessError: If any attempt fails with an error other than Facebook's
            'Cannot parse data'.
        FacebookLoginRequiredError: If every attempt fails with Facebook's 'Cannot parse data'.
    """
    attempt_number = 0
    while True:
        attempt_number += 1
        try:
            return attempt(attempt_number)
        except subprocess.CalledProcessError as e:
            if not is_facebook_parse_error(url=url, error_text=e.stderr):
                raise
            if attempt_number >= FACEBOOK_PARSE_ATTEMPTS:
                _warn_facebook_login_needed(url=url)
                raise FacebookLoginRequiredError(
                    f"Facebook returned no video data for '{url}' in {FACEBOOK_PARSE_ATTEMPTS} attempts"
                ) from e
            logger.warning(f"{label} hit Facebook's 'Cannot parse data' extractor error "
                           f'(attempt {attempt_number} of {FACEBOOK_PARSE_ATTEMPTS}), '
                           f'retrying in {FACEBOOK_PARSE_RETRY_DELAY:g} seconds')
            time.sleep(FACEBOOK_PARSE_RETRY_DELAY)


def warn_if_auth_error(error_text: str | None, url: str | None = None) -> None:
    """Log a cookie-related hint when a download failure looks like an auth problem.

    Args:
        error_text: The yt-dlp error output.
        url: The URL that failed, used to tell which cookies were sent (see cookie_browser).
    """
    if not is_auth_error(error_text):
        return

    browser = cookie_browser(url=url)
    if browser:
        logger.warning(f'Download may have failed because the {browser} browser cookies '
                       f'are missing, expired, or for the wrong browser')
    else:
        logger.warning('Download may have failed because no browser cookies are being used. '
                       'Set YTDLP_USE_COOKIES=firefox (or chrome) to use your logged-in session')
