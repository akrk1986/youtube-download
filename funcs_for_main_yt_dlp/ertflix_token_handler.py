"""ERTFlix token API URL resolution for authenticated content access."""
import json
import logging
import subprocess
import sys
from pathlib import Path

from funcs_utils import get_cookie_args, sanitize_url_for_subprocess
from project_defs import SUBPROCESS_TIMEOUT_OTHER_SITES

logger = logging.getLogger(__name__)


def is_ertflix_token_url(url: str) -> bool:
    """
    Check if URL is an ERTFlix token API URL.

    Token API URLs have this format:
    https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?content_id=...

    Args:
        url: The URL to check

    Returns:
        True if URL is an ERTFlix token API URL, False otherwise
    """
    return 'api.ertflix.opentv.com/urlbuilder/v1/playout/content/token' in url


def resolve_ertflix_token_url(token_url: str, ytdlp_path: Path) -> str:
    """
    Resolve ERTFlix token API URL to actual playback URL.

    Calls the token API using yt-dlp (which handles browser cookies automatically)
    and extracts the playbackUrl field from the JSON response.

    Args:
        token_url: ERTFlix token API URL
        ytdlp_path: Path to yt-dlp executable

    Returns:
        Resolved playback URL (typically a .mpd manifest URL)

    Raises:
        SystemExit: If token resolution fails (with clear error message)
    """
    logger.info('ERTFlix token API URL detected, resolving to playback URL...')

    # Security: Validate URL before passing to subprocess
    try:
        sanitized_url = sanitize_url_for_subprocess(url=token_url)
    except ValueError as e:
        logger.error(f'Invalid token API URL: {e}')
        sys.exit(1)

    # Build yt-dlp command to fetch JSON without downloading
    cmd = [
        str(ytdlp_path),
        '--dump-json',
        '--no-warnings',
        '--ignore-config',
        sanitized_url,
    ]

    # Add cookie arguments if YTDLP_USE_COOKIES is set
    cookie_args = get_cookie_args()
    if cookie_args:
        cmd.extend(cookie_args)
    else:
        logger.warning('YTDLP_USE_COOKIES not set - token API may fail without browser cookies')
        logger.warning('Set: export YTDLP_USE_COOKIES=firefox  (or chrome)')

    # Call yt-dlp to fetch token API response
    try:
        logger.debug(f'Running yt-dlp to resolve token URL: {" ".join(cmd)}')
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_OTHER_SITES,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.error(f'Token API call timed out after {SUBPROCESS_TIMEOUT_OTHER_SITES}s')
        logger.error('The ERTFlix API may be slow or unreachable')
        sys.exit(1)
    except Exception as e:
        logger.error(f'Failed to call token API: {e}')
        sys.exit(1)

    # Check for subprocess errors
    if result.returncode != 0:
        logger.error(f'yt-dlp failed to resolve token URL (exit code {result.returncode})')
        if result.stderr:
            logger.error(f'Error output: {result.stderr.strip()}')
        # Check for authentication errors
        if '403' in result.stderr or '401' in result.stderr or 'Forbidden' in result.stderr:
            logger.error('Authentication failed - ERTFlix requires login')
            logger.error('Make sure you are logged in to ERTFlix in your browser')
            logger.error('Then set: export YTDLP_USE_COOKIES=firefox  (or chrome)')
        sys.exit(1)

    # Parse JSON response
    try:
        response_data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error(f'Failed to parse token API response as JSON: {e}')
        logger.error('API response may be malformed or not JSON')
        if result.stdout:
            logger.error(f'Response: {result.stdout[:200]}')
        sys.exit(1)

    # Extract playbackUrl field
    playback_url = response_data.get('playbackUrl')
    if not playback_url:
        logger.error('Token API response missing "playbackUrl" field')
        logger.error(f'Available fields: {list(response_data.keys())}')
        sys.exit(1)

    # Validate resolved URL
    if not isinstance(playback_url, str) or not playback_url.startswith('http'):
        logger.error(f'Invalid playbackUrl format: {playback_url}')
        sys.exit(1)

    logger.info(f'Resolved to playback URL: {playback_url[:80]}...')
    return playback_url
