"""ERTFlix token API URL resolution for authenticated content access."""
import json
import logging
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse, unquote

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

    ERTFlix token URLs contain the playback URL as a 'content_URL' parameter.
    This function extracts and decodes that parameter.

    Example token URL:
    https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?
        content_id=DRM_PS027282_DASH&
        type=account&
        content_URL=https%3A%2F%2Fert-ucdn.broadpeak-aas.com%2F...%2Findex.mpd

    Args:
        token_url: ERTFlix token API URL
        ytdlp_path: Path to yt-dlp executable (unused, kept for compatibility)

    Returns:
        Resolved playback URL (the decoded content_URL parameter)

    Raises:
        SystemExit: If token URL is invalid or missing content_URL parameter
    """
    logger.info('ERTFlix token API URL detected, extracting playback URL...')

    # Parse the token URL and extract content_URL parameter
    try:
        parsed = urlparse(token_url)
        params = parse_qs(parsed.query)

        # Get content_URL parameter
        content_urls = params.get('content_URL', [])
        if not content_urls:
            logger.error('Token URL missing "content_URL" parameter')
            logger.error(f'Available parameters: {list(params.keys())}')
            sys.exit(1)

        # Decode the URL-encoded playback URL
        playback_url = unquote(content_urls[0])

    except Exception as e:
        logger.error(f'Failed to parse token URL: {e}')
        sys.exit(1)

    # Validate the extracted playback URL
    if not playback_url.startswith('http'):
        logger.error(f'Invalid playback URL format: {playback_url}')
        logger.error('Expected URL starting with http:// or https://')
        sys.exit(1)

    # Security: Validate playback URL before returning
    try:
        sanitize_url_for_subprocess(url=playback_url)
    except ValueError as e:
        logger.error(f'Invalid playback URL: {e}')
        sys.exit(1)

    logger.info(f'Resolved to playback URL: {playback_url[:80]}...')
    return playback_url
