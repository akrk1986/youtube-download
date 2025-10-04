#!/usr/bin/env python3
"""
Audio conversion functions using ffmpeg.
Handles conversion between MP3 and M4A formats.
"""

import subprocess
from pathlib import Path


def get_ffmpeg_path():
    """Get the path to ffmpeg executable."""
    # Try Windows path first (for WSL environment)
    windows_path = Path.home() / 'Apps' / 'yt-dlp' / 'ffmpeg.exe'
    if windows_path.exists():
        return str(windows_path)

    # Fallback to system ffmpeg
    return 'ffmpeg'


def convert_mp3_to_m4a(mp3_file, m4a_file=None):
    """
    Convert MP3 file to M4A format using ffmpeg.

    Args:
        mp3_file (Path or str): Path to source MP3 file
        m4a_file (Path or str, optional): Path to output M4A file.
                                          If not provided, uses same basename as source.

    Returns:
        Path: Path to created M4A file if successful, None otherwise
    """
    mp3_file = Path(mp3_file)

    if not mp3_file.exists():
        print(f'Error: MP3 file not found: {mp3_file}')
        return None

    # Use same basename if output not specified
    if m4a_file is None:
        m4a_file = mp3_file.parent / (mp3_file.stem + '.m4a')
    else:
        m4a_file = Path(m4a_file)

    ffmpeg_path = get_ffmpeg_path()

    try:
        cmd = [
            ffmpeg_path,
            '-i', str(mp3_file),
            '-c:a', 'aac',
            '-b:a', '192k',
            '-c:v', 'copy',  # Copy album art as-is
            '-disposition:v:0', 'attached_pic',  # Mark as attached picture
            '-y',  # Overwrite output file if exists
            str(m4a_file)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True
        )

        print(f'  Converted MP3 to M4A: {m4a_file.name}')
        return m4a_file

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode('utf-8', errors='replace') if e.stderr else 'Unknown error'
        print(f'Error converting {mp3_file.name} to M4A: {error_msg}')
        return None


def convert_m4a_to_mp3(m4a_file, mp3_file=None):
    """
    Convert M4A file to MP3 format using ffmpeg.

    Args:
        m4a_file (Path or str): Path to source M4A file
        mp3_file (Path or str, optional): Path to output MP3 file.
                                          If not provided, uses same basename as source.

    Returns:
        Path: Path to created MP3 file if successful, None otherwise
    """
    m4a_file = Path(m4a_file)

    if not m4a_file.exists():
        print(f'Error: M4A file not found: {m4a_file}')
        return None

    # Use same basename if output not specified
    if mp3_file is None:
        mp3_file = m4a_file.parent / (m4a_file.stem + '.mp3')
    else:
        mp3_file = Path(mp3_file)

    ffmpeg_path = get_ffmpeg_path()

    try:
        cmd = [
            ffmpeg_path,
            '-i', str(m4a_file),
            '-c:a', 'libmp3lame',
            '-q:a', '2',  # VBR quality 2 (~190 kbps)
            '-c:v', 'copy',  # Copy album art as-is
            '-map', '0:a',  # Map audio stream
            '-map', '0:v?',  # Map video stream (album art) if it exists
            '-id3v2_version', '3',  # Use ID3v2.3 for MP3
            '-y',  # Overwrite output file if exists
            str(mp3_file)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True
        )

        print(f'  Converted M4A to MP3: {mp3_file.name}')
        return mp3_file

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode('utf-8', errors='replace') if e.stderr else 'Unknown error'
        print(f'Error converting {m4a_file.name} to MP3: {error_msg}')
        return None
