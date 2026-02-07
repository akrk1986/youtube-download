"""Test the video_download_timeout parameter functionality."""

import sys
from pathlib import Path

# Add parent directory to path to import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from funcs_utils import get_timeout_for_url
from project_defs import SUBPROCESS_TIMEOUT_YOUTUBE, SUBPROCESS_TIMEOUT_FACEBOOK, SUBPROCESS_TIMEOUT_OTHER_SITES


def test_youtube_default_timeout():
    """Test YouTube URL with default timeout."""
    url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    timeout = get_timeout_for_url(url=url)
    print(f'YouTube default timeout: {timeout}s (expected: {SUBPROCESS_TIMEOUT_YOUTUBE}s)')
    assert timeout == SUBPROCESS_TIMEOUT_YOUTUBE, f'Expected {SUBPROCESS_TIMEOUT_YOUTUBE}, got {timeout}'


def test_youtube_custom_timeout():
    """Test YouTube URL with custom timeout."""
    url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    custom_timeout = 600
    timeout = get_timeout_for_url(url=url, video_download_timeout=custom_timeout)
    print(f'YouTube custom timeout: {timeout}s (expected: {custom_timeout}s)')
    assert timeout == custom_timeout, f'Expected {custom_timeout}, got {timeout}'


def test_facebook_default_timeout():
    """Test Facebook URL with default timeout."""
    url = 'https://www.facebook.com/watch/?v=123456789'
    timeout = get_timeout_for_url(url=url)
    print(f'Facebook default timeout: {timeout}s (expected: {SUBPROCESS_TIMEOUT_FACEBOOK}s)')
    assert timeout == SUBPROCESS_TIMEOUT_FACEBOOK, f'Expected {SUBPROCESS_TIMEOUT_FACEBOOK}, got {timeout}'


def test_facebook_custom_timeout():
    """Test Facebook URL with custom timeout."""
    url = 'https://www.facebook.com/watch/?v=123456789'
    custom_timeout = 600
    timeout = get_timeout_for_url(url=url, video_download_timeout=custom_timeout)
    print(f'Facebook custom timeout: {timeout}s (expected: {custom_timeout}s)')
    assert timeout == custom_timeout, f'Expected {custom_timeout}, got {timeout}'


def test_other_site_default_timeout():
    """Test other site URL with default timeout."""
    url = 'https://www.ertflix.gr/video/123456789'
    timeout = get_timeout_for_url(url=url)
    print(f'Other site default timeout: {timeout}s (expected: {SUBPROCESS_TIMEOUT_OTHER_SITES}s)')
    assert timeout == SUBPROCESS_TIMEOUT_OTHER_SITES, f'Expected {SUBPROCESS_TIMEOUT_OTHER_SITES}, got {timeout}'


def test_other_site_custom_timeout():
    """Test other site URL with custom timeout."""
    url = 'https://www.ertflix.gr/video/123456789'
    custom_timeout = 1200
    timeout = get_timeout_for_url(url=url, video_download_timeout=custom_timeout)
    print(f'Other site custom timeout: {timeout}s (expected: {custom_timeout}s)')
    assert timeout == custom_timeout, f'Expected {custom_timeout}, got {timeout}'


def test_all_sites_with_same_custom_timeout():
    """Test that custom timeout applies to all sites."""
    custom_timeout = 900
    urls = [
        ('YouTube', 'https://www.youtube.com/watch?v=test'),
        ('Facebook', 'https://www.facebook.com/watch/?v=test'),
        ('ERTFlix', 'https://www.ertflix.gr/video/test'),
    ]

    print(f'\nTesting custom timeout ({custom_timeout}s) applies to all sites:')
    for site_name, url in urls:
        timeout = get_timeout_for_url(url=url, video_download_timeout=custom_timeout)
        print(f'  {site_name}: {timeout}s')
        assert timeout == custom_timeout, f'{site_name} expected {custom_timeout}, got {timeout}'


if __name__ == '__main__':
    print('='*80)
    print('Testing video_download_timeout Parameter')
    print('='*80)

    try:
        test_youtube_default_timeout()
        print('✓ YouTube default timeout test passed')

        test_youtube_custom_timeout()
        print('✓ YouTube custom timeout test passed')

        test_facebook_default_timeout()
        print('✓ Facebook default timeout test passed')

        test_facebook_custom_timeout()
        print('✓ Facebook custom timeout test passed')

        test_other_site_default_timeout()
        print('✓ Other site default timeout test passed')

        test_other_site_custom_timeout()
        print('✓ Other site custom timeout test passed')

        test_all_sites_with_same_custom_timeout()
        print('✓ All sites with custom timeout test passed')

        print('\n' + '='*80)
        print('All tests passed!')
        print('='*80)

    except AssertionError as e:
        print(f'\n✗ Test failed: {e}')
        sys.exit(1)
