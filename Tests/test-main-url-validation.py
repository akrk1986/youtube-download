"""
Test that main-yt-dlp.py correctly validates URLs without downloading.
"""

import sys
from pathlib import Path

# Add parent directory to path to import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from funcs_for_main_yt_dlp import validate_and_get_url


def test_url_validation_in_main():
    """Test URL validation as used in main-yt-dlp.py."""

    test_cases = [
        # Valid URLs
        ('https://www.youtube.com/watch?v=dQw4w9WgXcQ', True, 'Valid YouTube URL'),
        ('https://youtu.be/xyz789', True, 'Valid YouTube short URL'),
        ('https://www.facebook.com/video/12345', True, 'Valid Facebook URL'),
        ('https://ertflix.gr/series/test', True, 'Valid ERTFlix URL'),

        # Invalid URLs
        ('https://github.com/test', False, 'Invalid - GitHub URL'),
        ('https://www.google.com/', False, 'Invalid - Google URL'),
        ('https://example.com/video', False, 'Invalid - example.com'),
    ]

    print('Testing URL validation in validate_and_get_url()...')
    print('=' * 80)

    passed = 0
    failed = 0

    for url, should_pass, description in test_cases:
        try:
            result = validate_and_get_url(provided_url=url)
            if should_pass:
                status = '✓ PASS'
                passed += 1
                print(f'\n{status}: {description}')
                print(f'  URL: {url}')
                print(f'  Result: Accepted (returned: {result})')
            else:
                status = '✗ FAIL'
                failed += 1
                print(f'\n{status}: {description}')
                print(f'  URL: {url}')
                print(f'  Expected: Should be rejected')
                print(f'  Got: Was accepted (returned: {result})')
        except SystemExit as e:
            if not should_pass:
                status = '✓ PASS'
                passed += 1
                print(f'\n{status}: {description}')
                print(f'  URL: {url}')
                print(f'  Result: Correctly rejected')
            else:
                status = '✗ FAIL'
                failed += 1
                print(f'\n{status}: {description}')
                print(f'  URL: {url}')
                print(f'  Expected: Should be accepted')
                print(f'  Got: Was rejected')

    # Summary
    print('\n' + '=' * 80)
    print(f'Results: {passed} passed, {failed} failed out of {len(test_cases)} tests')

    if failed == 0:
        print('✓ All tests passed!')
        return 0

    print(f'✗ {failed} test(s) failed')
    return 1


if __name__ == '__main__':
    exit_code = test_url_validation_in_main()
    sys.exit(exit_code)
