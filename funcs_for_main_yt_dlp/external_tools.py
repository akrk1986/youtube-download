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


def _verify_tool_path(tool_path: str, version_flag: str, install_hint: str) -> str:
    """Verify an external tool exists and return its path, or exit with error."""
    if platform.system() == 'Windows':
        if Path(tool_path).exists():
            return tool_path
        logger.error(f"Executable not found at path '{tool_path}'")
        sys.exit(1)

    try:
        subprocess.run([tool_path, version_flag], capture_output=True, check=True)
        return tool_path
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f'{tool_path} not found in PATH: {e}')
        logger.error(install_hint)
        sys.exit(1)


def get_ffmpeg_path() -> str:
    """
    Determine ffmpeg path based on the operating system.

    Returns:
        str: Path to ffmpeg executable.
    """
    ffmpeg_path, _, _ = _get_external_paths()
    return _verify_tool_path(ffmpeg_path, '-version', "Install with: 'sudo apt install ffmpeg'")


def get_ytdlp_path() -> str:
    """
    Determine yt-dlp path based on the operating system.

    Returns:
        str: Path to yt-dlp executable.
    """
    _, _, yt_dlp_path = _get_external_paths()
    return _verify_tool_path(yt_dlp_path, '--version', 'Install with: pip install yt-dlp')


def get_ytdlp_version(ytdlp_path: str) -> str:
    """
    Get the version string of yt-dlp executable.

    Args:
        ytdlp_path: Path to yt-dlp executable

    Returns:
        str: Version string (e.g., '2024.12.23') or 'unknown' if version cannot be determined
    """
    try:
        result = subprocess.run(
            [ytdlp_path, '--version'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        return result.stdout.strip()
    except Exception as e:
        logger.warning(f'Failed to get yt-dlp version: {e}')
        return 'unknown'


def quote_if_needed(value: str) -> str:
    """Quote a string with double quotes if it contains whitespace and isn't already quoted."""
    if ' ' in value or '\t' in value:
        # Check if already quoted
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value
        return f'"{value}"'
    return value
