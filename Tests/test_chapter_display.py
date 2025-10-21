"""Test the chapter display and confirmation functionality."""

import sys
from pathlib import Path

# Add parent directory to path to import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from funcs_utils import display_chapters_and_confirm, _format_duration


def test_format_duration():
    """Test the duration formatting function."""
    print('Testing duration formatting:')

    # Test cases: (seconds, expected_output)
    test_cases = [
        (0, '00:00'),
        (59, '00:59'),
        (60, '01:00'),
        (90, '01:30'),
        (3599, '59:59'),
        (3600, '01:00:00'),
        (3661, '01:01:01'),
        (7265, '02:01:05'),
    ]

    for seconds, expected in test_cases:
        result = _format_duration(seconds=seconds)
        status = '✓' if result == expected else '✗'
        print(f'  {status} {seconds}s -> {result} (expected: {expected})')


def test_display_chapters():
    """Test the chapter display with mock video info."""
    print('\nTesting chapter display and confirmation:')

    # Mock video info with chapters
    video_info = {
        'title': 'Test Video with Multiple Chapters',
        'duration': 3600,  # 1 hour
        'chapters': [
            {'title': 'Introduction', 'start_time': 0, 'end_time': 300},
            {'title': 'Main Content Part 1', 'start_time': 300, 'end_time': 900},
            {'title': 'Main Content Part 2', 'start_time': 900, 'end_time': 1800},
            {'title': 'Discussion and Q&A Session', 'start_time': 1800, 'end_time': 2700},
            {'title': 'Conclusion and Final Thoughts for This Amazing Video', 'start_time': 2700, 'end_time': 3600},
        ]
    }

    # This will display the chapters and prompt for user input
    result = display_chapters_and_confirm(video_info=video_info)

    if result:
        print('\nUser chose to continue')
    else:
        print('\nUser chose to abort')


def test_no_chapters():
    """Test behavior when video has no chapters."""
    print('\nTesting video without chapters:')

    video_info = {
        'title': 'Video Without Chapters',
        'duration': 600,
        'chapters': []
    }

    result = display_chapters_and_confirm(video_info=video_info)
    print(f'Result (should be True): {result}')


if __name__ == '__main__':
    print('='*80)
    print('Chapter Display and Confirmation Test')
    print('='*80)

    test_format_duration()
    test_no_chapters()
    test_display_chapters()

    print('\n' + '='*80)
    print('Test completed')
    print('='*80)
