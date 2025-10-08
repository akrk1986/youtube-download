#!/usr/bin/env python3
"""
Test to extract and display all tags from a real MP3 file.
Downloads a short YouTube video, converts to MP3, and shows all tags.
"""
import sys
import subprocess
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3


def download_test_video():
    """Download a very short test video and convert to MP3."""
    # Use a very short YouTube video (e.g., YouTube's test video)
    test_url = 'https://www.youtube.com/watch?v=jNQXAC9IVRw'  # "Me at the zoo" - first YouTube video (18 seconds)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / 'test_video.mp3'

        print(f'Downloading test video from YouTube...')
        print(f'URL: {test_url}')
        print(f'Output: {output_path}\n')

        # Download using yt-dlp with MP3 conversion
        cmd = [
            'yt-dlp',
            '-x',  # Extract audio
            '--audio-format', 'mp3',
            '--audio-quality', '0',
            '--embed-thumbnail',
            '--add-metadata',
            '-o', str(output_path.with_suffix('')),  # yt-dlp will add .mp3
            test_url
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            print(f'Download failed: {result.stderr}')
            return None

        # Find the actual output file (yt-dlp adds extension)
        mp3_files = list(Path(tmpdir).glob('*.mp3'))
        if not mp3_files:
            print('No MP3 file found after download')
            return None

        mp3_file = mp3_files[0]
        print(f'✓ Downloaded: {mp3_file.name}\n')

        # Display all tags
        display_all_tags(mp3_file)

        return mp3_file


def display_all_tags(mp3_file: Path):
    """Display all tags in the MP3 file."""
    print('=' * 80)
    print('ALL TAGS IN MP3 FILE')
    print('=' * 80)

    # EasyID3 tags (common/simple tags)
    print('\n1. EasyID3 Tags (common tags):')
    print('-' * 80)
    try:
        easy_audio = EasyID3(mp3_file)
        if easy_audio:
            for key in sorted(easy_audio.keys()):
                print(f'  {key:20s} = {easy_audio[key]}')
        else:
            print('  (no EasyID3 tags)')
    except Exception as e:
        print(f'  Error reading EasyID3 tags: {e}')

    # Full ID3 tags (all frames)
    print('\n2. Full ID3 Tags (all frames):')
    print('-' * 80)
    try:
        id3_audio = ID3(mp3_file)
        if id3_audio:
            for frame_id in sorted(id3_audio.keys()):
                frame = id3_audio[frame_id]
                print(f'  {frame_id:15s} = {frame}')
        else:
            print('  (no ID3 tags)')
    except Exception as e:
        print(f'  Error reading ID3 tags: {e}')

    # TXXX frames specifically
    print('\n3. TXXX Frames (user-defined text):')
    print('-' * 80)
    try:
        id3_audio = ID3(mp3_file)
        txxx_frames = id3_audio.getall('TXXX')
        if txxx_frames:
            for frame in txxx_frames:
                print(f'  Key: {frame.desc}')
                print(f'  Value: {frame.text}')
                print()
        else:
            print('  (no TXXX frames)')
    except Exception as e:
        print(f'  Error reading TXXX frames: {e}')

    print('=' * 80)


if __name__ == '__main__':
    print('Testing real MP3 tag extraction...\n')

    try:
        download_test_video()
    except Exception as e:
        print(f'\n❌ Error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
