"""URL validation and timeout utilities."""
import logging
import urllib.error
from urllib.parse import urlparse

from funcs_url_extraction import is_valid_domain_url
from project_defs import (SUBPROCESS_TIMEOUT_FACEBOOK,
                          SUBPROCESS_TIMEOUT_OTHER_SITES,
                          SUBPROCESS_TIMEOUT_YOUTUBE, VALID_FACEBOOK_DOMAINS,
                          VALID_OTHER_DOMAINS, VALID_YOUTUBE_DOMAINS)

logger = logging.getLogger(__name__)


def get_timeout_for_url(url: str, video_download_timeout: int | None = None) -> int:
    """
    Determine the appropriate subprocess timeout based on the URL domain.

    Args:
        url: The URL to check
        video_download_timeout: Optional timeout in seconds for video downloads.
                               If specified, this timeout is used for all sites.
                               If None, uses domain-specific defaults (300s for YouTube/Facebook, 3600s for others).

    Returns:
        int: Timeout in seconds
    """
    # If user specified a timeout, use it for all sites
    if video_download_timeout is not None:
        return video_download_timeout

    try:
        parsed = urlparse(url)

        # Check if it's a YouTube or Facebook domain
        if any(domain in parsed.netloc for domain in VALID_YOUTUBE_DOMAINS):
            return SUBPROCESS_TIMEOUT_YOUTUBE

        if any(domain in parsed.netloc for domain in VALID_FACEBOOK_DOMAINS):
            return SUBPROCESS_TIMEOUT_FACEBOOK

        # Check if it's another valid domain
        if any(domain in parsed.netloc for domain in VALID_OTHER_DOMAINS):
            return SUBPROCESS_TIMEOUT_OTHER_SITES

        # Default to YouTube timeout for unknown domains
        return SUBPROCESS_TIMEOUT_YOUTUBE

    except urllib.error.URLError:
        # If parsing fails, abort
        raise ValueError(f"URL '{url}' cannot be parsed, aborting")
    # abort on any other exception


def validate_video_url(url: str) -> tuple[bool, str]:
    """
    Validate that the URL is a valid video streaming URL (YouTube or other supported sites).

    Args:
        url: The URL string to validate

    Returns:
        tuple[bool, str]: (is_valid, error_message)
            - is_valid: True if URL is valid, False otherwise
            - error_message: Empty string if valid, error description if invalid
    """
    if not url or not url.strip():
        return False, 'URL cannot be empty'

    try:
        parsed = urlparse(url=url)

        # Check scheme
        if parsed.scheme not in ('http', 'https'):
            return False, f"Invalid URL scheme '{parsed.scheme}'. Must be http or https"

        # Check domain using the centralized validation function
        if not is_valid_domain_url(url=url):
            return (False,
                    f"Invalid domain '{parsed.netloc}'. Must be a YouTube, Facebook or other supported video site URL")
        return True, ''

    except Exception as e:
        return False, f'Invalid URL format: {e}'
