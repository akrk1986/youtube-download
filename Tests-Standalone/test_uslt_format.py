#!/usr/bin/env python3
"""
Test to verify how TENC tags are stored and retrieved in MP3 files.
"""
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, TENC


def test_tenc_storage_format():
    """Test how TENC tags are actually stored and what different tools see."""
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
        tmp_path = Path(tmp.name)

        try:
            # Create a minimal MP3 file with ID3 tags
            audio = EasyID3()
            audio['title'] = ['Test Song']
            audio.save(tmp_path)

            # Add TENC tag
            id3 = ID3(tmp_path)
            original_filename = 'My Song - Artist [video_id].mp3'
            id3.add(TENC(encoding=3, text=original_filename))
            id3.save(tmp_path)

            # Read it back
            id3_verify = ID3(tmp_path)
            tenc_frames = id3_verify.getall('TENC')

            print('TENC Frame Details:')
            for i, tenc in enumerate(tenc_frames):
                print(f'\nFrame {i}:')
                print(f'  Text (value): {tenc.text}')
                print(f'  Full string repr: {str(tenc)}')
                print(f'  Text as list: {tenc.text}')
                print(f'  Text[0]: "{tenc.text[0]}"')

        finally:
            # Clean up
            if tmp_path.exists():
                tmp_path.unlink()


if __name__ == '__main__':
    test_tenc_storage_format()
