#!/usr/bin/env python3
"""
Test that original filenames are stored correctly in audio tags.
MP3: USLT tag (unsynchronized lyrics)
M4A: ©lyr tag (lyrics)
"""
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, TENC
from mutagen.mp4 import MP4

from funcs_audio_tag_handlers import MP3TagHandler, M4ATagHandler


def test_mp3_original_filename():
    """Test that MP3 handler stores original filename in TENC tag."""
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
        tmp_path = Path(tmp.name)

        try:
            # Create a minimal MP3 file with ID3 tags
            audio = EasyID3()
            audio['title'] = ['Test Song']
            audio.save(tmp_path)

            # Rename the temp file to a meaningful name for testing
            test_filename = 'Original Song Name - Artist [video_id].mp3'
            test_path = tmp_path.parent / test_filename
            tmp_path.rename(test_path)

            # Create handler and set original filename
            handler = MP3TagHandler()
            audio = handler.open_audio_file(test_path)

            handler.set_original_filename(audio, test_path)

            # Read back the TENC tag using ID3
            id3 = ID3(test_path)
            tenc_frames = id3.getall('TENC')

            assert len(tenc_frames) > 0, 'No TENC frames found'

            tenc = tenc_frames[0]
            assert tenc.text == [test_filename], f"Expected '{test_filename}', got '{tenc.text}'"

            print(f'✓ MP3: Original filename stored in TENC tag: {tenc.text[0]}')

        finally:
            # Clean up both possible paths
            if tmp_path.exists():
                tmp_path.unlink()
            if test_path.exists():
                test_path.unlink()


def test_m4a_original_filename():
    """Test that M4A handler stores original filename in ©lyr tag."""
    # Creating a valid M4A file from scratch is complex
    # Instead, test that the handler has the method and it sets the tag correctly
    # using a mock MP4 object

    class MockMP4(dict):
        """Mock MP4 object for testing."""
        def __init__(self):
            super().__init__()

    handler = M4ATagHandler()
    mock_audio = MockMP4()
    test_filename = 'Original Song Name - Artist [video_id].m4a'

    # Create a fake Path object
    from unittest.mock import MagicMock
    fake_path = MagicMock()
    fake_path.name = test_filename

    # Set the original filename
    handler.set_original_filename(mock_audio, fake_path)

    # Verify the ©lyr tag was set
    assert handler.TAG_LYRICS in mock_audio, 'No ©lyr tag found'
    assert mock_audio[handler.TAG_LYRICS] == [test_filename], f"Expected '{test_filename}', got '{mock_audio[handler.TAG_LYRICS]}'"

    print(f'✓ M4A: Original filename stored in ©lyr tag: {mock_audio[handler.TAG_LYRICS][0]}')


if __name__ == '__main__':
    print('Testing original filename storage...\n')

    try:
        test_mp3_original_filename()
        test_m4a_original_filename()

        print('\n✅ All original filename storage tests passed!')
        sys.exit(0)
    except AssertionError as e:
        print(f'\n❌ Test failed: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'\n❌ Unexpected error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
