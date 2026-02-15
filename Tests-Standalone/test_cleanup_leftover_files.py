#!/usr/bin/env python3
"""Test the cleanup of leftover *.ytdl and *.part files."""
import sys
from pathlib import Path

# Add parent directory to path to import main module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the cleanup function directly
import importlib.util
spec = importlib.util.spec_from_file_location('main_yt_dlp', Path(__file__).parent.parent / 'main-yt-dlp.py')
main_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_module)
_cleanup_leftover_files = main_module._cleanup_leftover_files


def test_cleanup_leftover_files():
    """Test that cleanup function removes *.ytdl and *.part files."""
    # Create a test directory
    test_dir = Path(__file__).parent / 'test_cleanup_temp'
    test_dir.mkdir(exist_ok=True)

    try:
        # Create some test leftover files
        ytdl_file = test_dir / 'test_video.ytdl'
        part_file = test_dir / 'test_video.part'
        normal_file = test_dir / 'test_video.mp4'

        ytdl_file.write_text('leftover ytdl data')
        part_file.write_text('leftover part data')
        normal_file.write_text('normal video file')

        print(f'Created test files in {test_dir}:')
        for f in test_dir.iterdir():
            print(f'  - {f.name}')

        # Run cleanup
        print('\nRunning cleanup...')
        _cleanup_leftover_files(video_folder=test_dir)

        # Check results
        print('\nFiles after cleanup:')
        remaining_files = list(test_dir.iterdir())
        for f in remaining_files:
            print(f'  - {f.name}')

        # Verify
        assert not ytdl_file.exists(), 'ytdl file should be removed'
        assert not part_file.exists(), 'part file should be removed'
        assert normal_file.exists(), 'normal file should remain'

        print('\n✅ Test passed: Cleanup removed leftover files correctly')

    finally:
        # Cleanup test directory
        for f in test_dir.iterdir():
            f.unlink()
        test_dir.rmdir()
        print(f'\nCleaned up test directory: {test_dir}')


if __name__ == '__main__':
    test_cleanup_leftover_files()
