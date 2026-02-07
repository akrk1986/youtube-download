"""Test script to verify urllib3/requests logging suppression."""
import logging
import sys
from pathlib import Path

# Add parent directory to path to import logger_config
sys.path.insert(0, str(Path(__file__).parent.parent))

from logger_config import setup_logging


def test_without_show_urls():
    """Test that urllib3/requests are suppressed by default."""
    print('=' * 70)
    print('TEST 1: Default behavior (--verbose without --show-urls)')
    print('Expected: urllib3 and requests loggers should be at WARNING level')
    print('=' * 70)

    setup_logging(verbose=True, log_to_file=False, show_urls=False)

    urllib3_level = logging.getLogger('urllib3').level
    requests_level = logging.getLogger('requests').level

    print(f'urllib3 log level: {logging.getLevelName(urllib3_level)} ({urllib3_level})')
    print(f'requests log level: {logging.getLevelName(requests_level)} ({requests_level})')
    print(f'WARNING level value: {logging.WARNING}')

    if urllib3_level == logging.WARNING and requests_level == logging.WARNING:
        print('✓ PASS: Both loggers suppressed at WARNING level')
    else:
        print('✗ FAIL: Loggers not properly suppressed')
    print()


def test_with_show_urls():
    """Test that urllib3/requests are NOT suppressed with --show-urls."""
    print('=' * 70)
    print('TEST 2: With --show-urls flag')
    print('Expected: urllib3 and requests should inherit root logger level (DEBUG)')
    print('=' * 70)

    # Reset loggers to NOTSET before testing
    logging.getLogger('urllib3').setLevel(logging.NOTSET)
    logging.getLogger('requests').setLevel(logging.NOTSET)

    setup_logging(verbose=True, log_to_file=False, show_urls=True)

    urllib3_level = logging.getLogger('urllib3').level
    requests_level = logging.getLogger('requests').level
    root_level = logging.getLogger().level

    print(f'Root logger level: {logging.getLevelName(root_level)} ({root_level})')
    print(f'urllib3 log level: {logging.getLevelName(urllib3_level)} ({urllib3_level})')
    print(f'requests log level: {logging.getLevelName(requests_level)} ({requests_level})')

    # When not explicitly set, they inherit from root (level 0 = NOTSET)
    if urllib3_level == logging.NOTSET and requests_level == logging.NOTSET:
        print('✓ PASS: Both loggers will inherit root level (can log URLs)')
    else:
        print('✗ FAIL: Loggers should inherit from root')
    print()


if __name__ == '__main__':
    test_without_show_urls()
    test_with_show_urls()

    print('=' * 70)
    print('SUMMARY:')
    print('- Without --show-urls: Slack webhook URL is protected')
    print('- With --show-urls: URLs will be logged (use only for debugging)')
    print('=' * 70)
