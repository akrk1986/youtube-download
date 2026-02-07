"""
Test script for URL validation using the new is_valid_domain_url function.
"""

import sys
from pathlib import Path

# Add parent directory to path to import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from funcs_utils import validate_video_url
from funcs_url_extraction import is_valid_domain_url


def test_url_validation():
    """Test URL validation with various valid and invalid URLs."""

    test_cases = [
        # Valid YouTube URLs
        ('https://www.youtube.com/watch?v=dQw4w9WgXcQ', True, 'Valid YouTube URL'),
        ('https://youtube.com/watch?v=abc123', True, 'Valid YouTube URL without www'),
        ('https://youtu.be/xyz789', True, 'Valid YouTube short URL'),
        ('https://m.youtube.com/watch?v=mobile123', True, 'Valid mobile YouTube URL'),
        ('https://YouTube.COM/watch?v=test', True, 'Valid YouTube URL with mixed case'),

        # Valid Facebook URLs
        ('https://www.facebook.com/video/12345', True, 'Valid Facebook URL'),
        ('https://facebook.com/video/67890', True, 'Valid Facebook URL without www'),
        ('https://fb.me/shortlink', True, 'Valid fb.me short URL'),
        ('https://fb.com/test', True, 'Valid fb.com URL'),

        # Valid ERTFlix URLs
        ('https://www.ertflix.gr/video/12345', True, 'Valid ERTFlix URL'),
        ('https://ertflix.gr/series/greek-music', True, 'Valid ERTFlix URL without www'),

        # Invalid URLs
        ('https://github.com/yt-dlp/yt-dlp', False, 'Invalid - GitHub URL'),
        ('https://www.google.com/search?q=test', False, 'Invalid - Google URL'),
        ('https://example.com/video', False, 'Invalid - example.com'),
        ('https://fake-youtube.com/watch?v=test', False, 'Invalid - fake YouTube domain'),
        ('https://youtube.com.fake.com/test', False, 'Invalid - subdomain attack'),
        ('http://notfacebook.com/video', False, 'Invalid - similar domain name'),
        ('ftp://youtube.com/test', False, 'Invalid - wrong scheme'),
        ('', False, 'Invalid - empty URL'),
        ('not a url', False, 'Invalid - malformed URL'),
    ]

    print('Testing URL validation with validate_video_url()...')
    print('=' * 80)

    passed = 0
    failed = 0

    for url, should_be_valid, description in test_cases:
        is_valid, error_msg = validate_video_url(url=url)

        # Check if result matches expectation
        if is_valid == should_be_valid:
            status = '✓ PASS'
            passed += 1
        else:
            status = '✗ FAIL'
            failed += 1

        # Display result
        print(f'\n{status}: {description}')
        print(f'  URL: {url if url else "(empty)"}')
        print(f'  Expected: {"Valid" if should_be_valid else "Invalid"}')
        print(f'  Got: {"Valid" if is_valid else "Invalid"}')
        if error_msg:
            print(f'  Error: {error_msg}')

    # Summary
    print('\n' + '=' * 80)
    print(f'Results: {passed} passed, {failed} failed out of {len(test_cases)} tests')

    if failed == 0:
        print('✓ All tests passed!')
        return 0

    print(f'✗ {failed} test(s) failed')
    return 1


def test_is_valid_domain_url():
    """Test the is_valid_domain_url function directly."""

    print('\n\nTesting is_valid_domain_url() function directly...')
    print('=' * 80)

    valid_urls = [
        'https://www.youtube.com/watch?v=test',
        'https://youtu.be/test',
        'https://m.youtube.com/test',
        'https://www.facebook.com/test',
        'https://fb.me/test',
        'https://ertflix.gr/test',
    ]

    invalid_urls = [
        'https://github.com/test',
        'https://google.com/test',
        'https://fake-youtube.com/test',
    ]

    print('\nValid URLs (should return True):')
    for url in valid_urls:
        result = is_valid_domain_url(url=url)
        status = '✓' if result else '✗'
        print(f'  {status} {url}: {result}')

    print('\nInvalid URLs (should return False):')
    for url in invalid_urls:
        result = is_valid_domain_url(url=url)
        status = '✓' if not result else '✗'
        print(f'  {status} {url}: {result}')


if __name__ == '__main__':
    exit_code = test_url_validation()
    test_is_valid_domain_url()
    sys.exit(exit_code)
