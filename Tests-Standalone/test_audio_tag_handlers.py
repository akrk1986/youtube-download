#!/usr/bin/env python3
"""
Test audio tag handler classes.
Verifies that both MP3 and M4A handlers work correctly.
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from funcs_audio_tag_handlers import MP3TagHandler, M4ATagHandler


def test_mp3_handler():
    """Test MP3TagHandler attributes and constants."""
    handler = MP3TagHandler()

    # Test tag constants
    assert handler.TAG_TITLE == 'title'
    assert handler.TAG_ARTIST == 'artist'
    assert handler.TAG_ALBUMARTIST == 'albumartist'
    assert handler.TAG_ALBUM == 'album'
    assert handler.TAG_TRACKNUMBER == 'tracknumber'

    # Test file glob
    assert handler.get_file_glob() == '*.mp3'

    print('✓ MP3TagHandler constants and attributes correct')


def test_m4a_handler():
    """Test M4ATagHandler attributes and constants."""
    handler = M4ATagHandler()

    # Test tag constants (Apple atom names)
    assert handler.TAG_TITLE == '\xa9nam'
    assert handler.TAG_ARTIST == '\xa9ART'
    assert handler.TAG_ALBUMARTIST == 'aART'
    assert handler.TAG_ALBUM == '\xa9alb'
    assert handler.TAG_DATE == '\xa9day'
    assert handler.TAG_TRACKNUMBER == 'trkn'

    # Test file glob
    assert handler.get_file_glob() == '*.m4a'

    print('✓ M4ATagHandler constants and attributes correct')


def test_handler_interface():
    """Test that both handlers implement the required interface."""
    mp3_handler = MP3TagHandler()
    m4a_handler = M4ATagHandler()

    # Verify all required methods exist
    required_methods = [
        'open_audio_file',
        'get_tag',
        'set_tag',
        'set_track_number',
        'clear_track_number',
        'save_audio_file',
        'get_file_glob',
        'handle_format_specific_tasks',
        'has_track_number',
        'set_original_filename',
    ]

    for method_name in required_methods:
        assert hasattr(mp3_handler, method_name), f'MP3Handler missing {method_name}'
        assert callable(getattr(mp3_handler, method_name)), f'MP3Handler.{method_name} not callable'

        assert hasattr(m4a_handler, method_name), f'M4AHandler missing {method_name}'
        assert callable(getattr(m4a_handler, method_name)), f'M4AHandler.{method_name} not callable'

    print('✓ Both handlers implement complete interface')


def test_handler_tag_constants():
    """Test that handlers have all required tag name constants."""
    mp3_handler = MP3TagHandler()
    m4a_handler = M4ATagHandler()

    required_constants = [
        'TAG_TITLE',
        'TAG_ARTIST',
        'TAG_ALBUMARTIST',
        'TAG_ALBUM',
        'TAG_TRACKNUMBER',
    ]

    for const_name in required_constants:
        assert hasattr(mp3_handler, const_name), f'MP3Handler missing {const_name}'
        assert hasattr(m4a_handler, const_name), f'M4AHandler missing {const_name}'

        # Verify they have different values (format-specific)
        mp3_value = getattr(mp3_handler, const_name)
        m4a_value = getattr(m4a_handler, const_name)
        assert mp3_value != m4a_value, f'{const_name} should differ between formats'

    print('✓ Both handlers have format-specific tag constants')


def test_format_specific_tasks():
    """Test that M4A handler has date fixing and MP3 doesn't."""
    mp3_handler = MP3TagHandler()
    m4a_handler = M4ATagHandler()

    # Create mock audio objects to test (since we don't have real files)
    class MockAudio(dict):
        """Mock audio object for testing."""
        pass

    mock_mp3 = MockAudio()
    mock_m4a = MockAudio()

    # MP3 should not modify anything
    result = mp3_handler.handle_format_specific_tasks(mock_mp3)
    assert result is False, 'MP3 handler should not have format-specific tasks'

    # M4A with no date should not modify
    result = m4a_handler.handle_format_specific_tasks(mock_m4a)
    assert result is False, 'M4A handler with no date should return False'

    # M4A with date in YYYYMMDD format should fix it
    mock_m4a[m4a_handler.TAG_DATE] = ['20231225']
    result = m4a_handler.handle_format_specific_tasks(mock_m4a)
    assert result is True, 'M4A handler should fix YYYYMMDD date format'
    assert mock_m4a[m4a_handler.TAG_DATE] == ['2023'], 'Date should be fixed to YYYY'

    # M4A with date already in YYYY format should not modify
    mock_m4a2 = MockAudio()
    mock_m4a2[m4a_handler.TAG_DATE] = ['2023']
    result = m4a_handler.handle_format_specific_tasks(mock_m4a2)
    assert result is False, 'M4A handler should not modify YYYY date'
    assert mock_m4a2[m4a_handler.TAG_DATE] == ['2023'], 'Date should remain YYYY'

    print('✓ Format-specific tasks work correctly')


if __name__ == '__main__':
    print('Running audio tag handler tests...\n')

    try:
        test_mp3_handler()
        test_m4a_handler()
        test_handler_interface()
        test_handler_tag_constants()
        test_format_specific_tasks()

        print('\n✅ All tests passed!')
        sys.exit(0)
    except AssertionError as e:
        print(f'\n❌ Test failed: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'\n❌ Unexpected error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
