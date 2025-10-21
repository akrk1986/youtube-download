"""Test the cookie argument handling functionality."""

import os
import sys
from pathlib import Path

# Add parent directory to path to import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from funcs_utils import get_cookie_args


def test_no_env_variable():
    """Test when YTDLP_USE_COOKIES is not set."""
    # Clear the environment variable if it exists
    if 'YTDLP_USE_COOKIES' in os.environ:
        del os.environ['YTDLP_USE_COOKIES']

    result = get_cookie_args()
    print(f'No env variable: {result}')
    assert result == [], f'Expected empty list, got {result}'


def test_chrome_browser():
    """Test when YTDLP_USE_COOKIES=chrome."""
    os.environ['YTDLP_USE_COOKIES'] = 'chrome'
    result = get_cookie_args()
    print(f"YTDLP_USE_COOKIES='chrome': {result}")
    assert result == ['--cookies-from-browser', 'chrome', '--no-cache-dir'], f'Expected chrome args with no-cache, got {result}'


def test_chrome_uppercase():
    """Test when YTDLP_USE_COOKIES=CHROME (uppercase)."""
    os.environ['YTDLP_USE_COOKIES'] = 'CHROME'
    result = get_cookie_args()
    print(f"YTDLP_USE_COOKIES='CHROME': {result}")
    assert result == ['--cookies-from-browser', 'chrome', '--no-cache-dir'], f'Expected chrome args with no-cache, got {result}'


def test_firefox_browser():
    """Test when YTDLP_USE_COOKIES=firefox."""
    os.environ['YTDLP_USE_COOKIES'] = 'firefox'
    result = get_cookie_args()
    print(f"YTDLP_USE_COOKIES='firefox': {result}")
    assert result == ['--cookies-from-browser', 'firefox', '--no-cache-dir'], f'Expected firefox args with no-cache, got {result}'


def test_any_other_value():
    """Test when YTDLP_USE_COOKIES has any other non-empty value."""
    os.environ['YTDLP_USE_COOKIES'] = 'yes'
    result = get_cookie_args()
    print(f"YTDLP_USE_COOKIES='yes': {result}")
    assert result == ['--cookies-from-browser', 'firefox', '--no-cache-dir'], f'Expected firefox args with no-cache (default), got {result}'


def test_empty_string():
    """Test when YTDLP_USE_COOKIES is set to empty string."""
    os.environ['YTDLP_USE_COOKIES'] = ''
    result = get_cookie_args()
    print(f"YTDLP_USE_COOKIES='': {result}")
    assert result == [], f'Expected empty list, got {result}'


def test_whitespace_only():
    """Test when YTDLP_USE_COOKIES is set to whitespace."""
    os.environ['YTDLP_USE_COOKIES'] = '   '
    result = get_cookie_args()
    print(f"YTDLP_USE_COOKIES='   ': {result}")
    assert result == [], f'Expected empty list, got {result}'


if __name__ == '__main__':
    print('='*80)
    print('Testing Cookie Arguments Handling')
    print('='*80)

    try:
        test_no_env_variable()
        print('✓ No env variable test passed')

        test_chrome_browser()
        print('✓ Chrome browser test passed')

        test_chrome_uppercase()
        print('✓ Chrome uppercase test passed')

        test_firefox_browser()
        print('✓ Firefox browser test passed')

        test_any_other_value()
        print('✓ Any other value defaults to Firefox test passed')

        test_empty_string()
        print('✓ Empty string test passed')

        test_whitespace_only()
        print('✓ Whitespace only test passed')

        # Clean up
        if 'YTDLP_USE_COOKIES' in os.environ:
            del os.environ['YTDLP_USE_COOKIES']

        print('\n' + '='*80)
        print('All tests passed!')
        print('='*80)

    except AssertionError as e:
        print(f'\n✗ Test failed: {e}')
        sys.exit(1)
