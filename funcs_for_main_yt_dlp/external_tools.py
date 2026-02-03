"""External tool path detection and utilities."""
import logging
import platform
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_external_paths() -> tuple[str, str, str]:
    """
    Determine yt-dlp, ffmpeg and ffprobe paths based on the operating system.

    Returns:
        tuple: Tuple of (ffmpeg_path, ffprobe_path, yt_dlp_path).
    """
    system = platform.system()

    if system == 'Windows':
        # Windows: use specific directory
        yt_dlp_dir = Path('C:/Users/user/Apps/yt-dlp')
        return str(yt_dlp_dir / 'ffmpeg.exe'), str(yt_dlp_dir / 'ffprobe.exe'), str(yt_dlp_dir / 'yt-dlp.exe')
    # Linux/WSL/macOS: assume ffmpeg/ffprobe are in PATH
    return 'ffmpeg', 'ffprobe', 'yt-dlp'


def get_ffmpeg_path() -> str:
    """
    Determine ffmpeg path based on the operating system.

    Returns:
        str: Path to ffmpeg executable.
    """
    ffmpeg_path, _, _ = _get_external_paths()

    # Windows
    if platform.system() == 'Windows':
        if Path(ffmpeg_path).exists():
            return ffmpeg_path
        logger.error(f"ffmpeg executable not found at path '{ffmpeg_path}'")
        logger.error(f"Please ensure ffmpeg is installed in '{ffmpeg_path}'")
        sys.exit(1)

    # Linux/WSL
    try:
        subprocess.run([ffmpeg_path, '-version'], capture_output=True, check=True)
        return ffmpeg_path
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f'ffmpeg not found in PATH: {e}')
        logger.error("Install with: 'sudo apt install ffmpeg'")
        sys.exit(1)


def get_ytdlp_path() -> str:
    """
    Determine yt-dlp path based on the operating system.

    Returns:
        str: Path to yt-dlp executable.
    """
    _, _, yt_dlp_path = _get_external_paths()

    # Windows
    if platform.system() == 'Windows':
        if Path(yt_dlp_path).exists():
            return yt_dlp_path
        logger.error(f"yt-dlp executable not found at path '{yt_dlp_path}'")
        logger.error(f"Please ensure yt-dlp is installed in '{yt_dlp_path}'")
        sys.exit(1)

    # Linux/WSL
    try:
        subprocess.run([yt_dlp_path, '--version'], capture_output=True, check=True)
        return yt_dlp_path
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f'yt-dlp not found in PATH: {e}')
        logger.error('Install with: pip install yt-dlp')
        sys.exit(1)


def quote_if_needed(value: str) -> str:
    """Quote a string with double quotes if it contains whitespace and isn't already quoted."""
    if ' ' in value or '\t' in value:
        # Check if already quoted
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value
        return f'"{value}"'
    return value
