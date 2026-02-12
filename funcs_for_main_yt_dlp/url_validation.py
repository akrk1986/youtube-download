"""URL validation and input handling."""
import logging
import sys

from funcs_video_info import validate_video_url
from project_defs import MAX_URL_RETRIES

logger = logging.getLogger(__name__)


def validate_and_get_url(provided_url: str) -> str:
    """
    Validate YouTube URL or prompt user for one if not provided.

    Args:
        provided_url: URL from command line, or None for interactive mode

    Returns:
        Validated YouTube URL

    Raises:
        SystemExit: If URL validation fails after max retries
    """
    if not provided_url:
        # Interactive mode: prompt with retry
        for attempt in range(MAX_URL_RETRIES):
            url = input('Enter the YouTube URL: ').strip()
            is_valid, error_msg = validate_video_url(url=url)
            if is_valid:
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
        return provided_url
