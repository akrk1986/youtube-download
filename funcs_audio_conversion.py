#!/usr/bin/env python3
"""
Audio conversion functions using ffmpeg.
Handles conversion between MP3 and M4A formats.
"""
import subprocess
import sys
from pathlib import Path
import platform

from project_defs import FFMPEG_TIMEOUT_SECONDS


def _get_ffmpeg_tool_path(tool_name: str) -> str:
    """
    Generic function to get path to ffmpeg tools (ffmpeg or ffprobe).
    On Windows: tries system-installed tool first, then falls back to ~/Apps/ffmpeg_bin
    On other platforms: uses system tool
    Aborts if tool is not found.

    Args:
        tool_name (str): Name of the tool ('ffmpeg' or 'ffprobe')

    Returns:
        str: Path to the tool executable
    """
    if platform.system() == 'Windows':
        # Try system-installed tool first
        try:
            subprocess.run(
                [tool_name, '-version'],
                capture_output=True,
                check=True
            )
            return tool_name
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to local installation
            fallback_path = Path.home() / 'Apps' / 'ffmpeg_bin' / f'{tool_name}.exe'
            if fallback_path.exists():
                return str(fallback_path)

            # Neither system nor local tool found
            print(f'Error: {tool_name} not found. Please install ffmpeg system-wide or place it in ~/Apps/ffmpeg_bin/')
            sys.exit(1)

    # Non-Windows: verify system tool exists
    try:
        subprocess.run(
            [tool_name, '-version'],
            capture_output=True,
            check=True
        )
        return tool_name
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f'Error: {tool_name} not found. Please install ffmpeg.')
        sys.exit(1)


def get_ffmpeg_path() -> str:
    """Get the path to ffmpeg executable."""
    return _get_ffmpeg_tool_path('ffmpeg')


def get_ffprobe_path() -> str:
    """Get the path to ffprobe executable."""
    return _get_ffmpeg_tool_path('ffprobe')

def convert_mp3_to_m4a(mp3_file: Path | str, m4a_file: Path | str | None = None) -> Path | None:
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
            check=True,
            timeout=FFMPEG_TIMEOUT_SECONDS
        )

        print(f'  Converted MP3 to M4A: {m4a_file.name}')
        return m4a_file

    except subprocess.TimeoutExpired:
        print(f'Error: Conversion timed out after {FFMPEG_TIMEOUT_SECONDS} seconds for {mp3_file.name}')
        return None
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode('utf-8', errors='replace') if e.stderr else 'Unknown error'
        print(f'Error converting {mp3_file.name} to M4A: {error_msg}')
        return None

def convert_m4a_to_mp3(m4a_file: Path | str, mp3_file: Path | str | None = None) -> Path | None:
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
            check=True,
            timeout=FFMPEG_TIMEOUT_SECONDS
        )

        print(f'  Converted M4A to MP3: {mp3_file.name}')
        return mp3_file

    except subprocess.TimeoutExpired:
        print(f'Error: Conversion timed out after {FFMPEG_TIMEOUT_SECONDS} seconds for {m4a_file.name}')
        return None
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode('utf-8', errors='replace') if e.stderr else 'Unknown error'
        print(f'Error converting {m4a_file.name} to MP3: {error_msg}')
        return None
