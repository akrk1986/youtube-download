"""URL validation and input handling."""
import logging
import sys
from pathlib import Path

from funcs_video_info import validate_video_url
from project_defs import MAX_URL_RETRIES

logger = logging.getLogger(__name__)


def validate_and_get_url(provided_url: str, ytdlp_path: Path | None = None) -> str:
    """
    Validate YouTube URL or prompt user for one if not provided.

    If the URL is an ERTFlix token API URL, resolve it to the actual playback URL.

    Args:
        provided_url: URL from command line, or None for interactive mode
        ytdlp_path: Path to yt-dlp executable (required for ERTFlix token resolution)

    Returns:
        Validated URL (or resolved playback URL for ERTFlix token URLs)

    Raises:
        SystemExit: If URL validation fails after max retries
    """
    # Import here to avoid circular imports
    from funcs_for_main_yt_dlp.ertflix_token_handler import (
        is_ertflix_token_url,
        resolve_ertflix_token_url,
    )

    if not provided_url:
        # Interactive mode: prompt with retry
        for attempt in range(MAX_URL_RETRIES):
            url = input('Enter the YouTube URL: ').strip()
            is_valid, error_msg = validate_video_url(url=url)
            if is_valid:
                # Check if it's an ERTFlix token URL and resolve if needed
                if is_ertflix_token_url(url=url):
                    if not ytdlp_path:
                        logger.error('ytdlp_path required for ERTFlix token resolution')
                        sys.exit(1)
                    return resolve_ertflix_token_url(token_url=url, ytdlp_path=ytdlp_path)
                return url

            logger.error(f'Invalid URL: {error_msg}')
            if attempt < MAX_URL_RETRIES - 1:
                logger.info(f'Please try again ({MAX_URL_RETRIES - attempt - 1} attempts remaining)')
            else:
                logger.error('Maximum retry attempts reached. Exiting.')
                sys.exit(1)
        # Should never reach here, but mypy needs this
        sys.exit(1)
    else:
        # CLI mode: validate provided URL
        is_valid, error_msg = validate_video_url(url=provided_url)
        if not is_valid:
            logger.error(f'Invalid URL: {error_msg}')
            sys.exit(1)

        # Check if it's an ERTFlix token URL and resolve if needed
        if is_ertflix_token_url(url=provided_url):
            if not ytdlp_path:
                logger.error('ytdlp_path required for ERTFlix token resolution')
                sys.exit(1)
            return resolve_ertflix_token_url(token_url=provided_url, ytdlp_path=ytdlp_path)

        return provided_url
