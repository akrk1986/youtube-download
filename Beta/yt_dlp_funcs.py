#!/usr/bin/env python3
"""
YouTube downloader functions using yt-dlp
"""
import yt_dlp
from yt_dlp.postprocessor.common import PostProcessor
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import platform
import re
import unicodedata

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FFmpeg location - customize this path based on your setup
FFMPEG_LOCATION = Path("/usr/local/bin") if platform.system() != "Windows" else Path("C:/Users/user/Apps/ffmpeg_bin")


def _sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing emojis, special characters, and leading whitespace
    while preserving Unicode characters for English, Greek, French, and Hebrew
    """
    # Remove leading and trailing whitespace
    filename = filename.strip()

    # Remove emojis - covers most emoji ranges
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002500-\U00002BEF"  # chinese char
        "\U00002702-\U000027B0"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"  # dingbats
        "\u3030"
        "]+",
        re.UNICODE
    )
    filename = emoji_pattern.sub('', filename)

    # Define allowed characters: letters, digits, spaces, and some safe punctuation
    # This preserves Unicode letters from all languages including Greek, Hebrew, French, etc.
    allowed_chars = []
    for char in filename:
        if (
                char.isalnum() or  # Letters and numbers (includes Unicode letters)
                char.isspace() or  # Spaces
                char in ".-_()[]{}'" or  # Safe punctuation
                unicodedata.category(char).startswith('L')  # Unicode letter categories
        ):
            allowed_chars.append(char)
        else:
            # Replace forbidden characters with space
            allowed_chars.append(' ')

    # Join and clean up multiple spaces
    filename = ''.join(allowed_chars)
    filename = re.sub(r'\s+', ' ', filename)  # Replace multiple spaces with single space
    filename = filename.strip()  # Remove leading/trailing spaces again

    # Remove/replace problematic characters for file systems
    problematic_chars = {
        '<': '', '>': '', ':': '', '"': '', '|': '', '?': '', '*': '',
        '/': '-', '\\': '-', '\n': ' ', '\r': ' ', '\t': ' '
    }
    for bad_char, replacement in problematic_chars.items():
        filename = filename.replace(bad_char, replacement)

    # Ensure filename is not empty
    if not filename or filename.isspace():
        filename = "untitled"

    # Limit filename length (keeping some buffer for extension)
    max_length = 200
    if len(filename) > max_length:
        filename = filename[:max_length].strip()

    return filename


def _get_base_options(output_dir: Path) -> Dict[str, Any]:
    """Get base yt-dlp options with FFmpeg configuration"""
    base_options = {
        'writethumbnail': False,
        'writeinfojson': False,
        'ignoreerrors': True,
        'no_warnings': False,
        'extractflat': False,
        'ffmpeg_location': '',
        'ffprobe_location': '',
    }

    # return options

    # Set FFmpeg location if it exists
    if FFMPEG_LOCATION.exists():
        ffmpeg_exe = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
        ffprobe_exe = "ffprobe.exe" if platform.system() == "Windows" else "ffprobe"

        ffmpeg_path = FFMPEG_LOCATION / ffmpeg_exe
        ffprobe_path = FFMPEG_LOCATION / ffprobe_exe

        if ffmpeg_path.exists():
            base_options['ffmpeg_location'] = str(ffmpeg_path)
        if ffprobe_path.exists():
            base_options['ffprobe_location'] = str(ffprobe_path)

    return base_options


def _get_audio_options(output_dir: Path, extract_metadata: bool = True) -> Dict[str, Any]:
    """Get yt-dlp options for audio-only download"""
    audio_dir = output_dir / "yt-audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    options = _get_base_options(output_dir)
    options.update({
        'format': 'bestaudio/best',
        'outtmpl': str(audio_dir / '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'restrictfilenames': False,  # Allow Unicode characters
        'windowsfilenames': False,  # Don't use Windows filename restrictions on other platforms
    })

    if extract_metadata:
        options['postprocessors'].append({
            'key': 'FFmpegMetadata',
            'add_metadata': True,
        })

    return options


def _get_video_options(output_dir: Path) -> Dict[str, Any]:
    """Get yt-dlp options for video download"""
    video_dir = output_dir / "yt-videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    options = _get_base_options(output_dir)
    options.update({
        'format': 'best[ext=mp4]/best',
        'outtmpl': str(video_dir / '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        'restrictfilenames': False,  # Allow Unicode characters
        'windowsfilenames': False,  # Don't use Windows filename restrictions on other platforms
    })
    return options


def _get_both_options(output_dir: Path) -> Dict[str, Any]:
    """Get yt-dlp options for both video and audio download"""
    video_dir = output_dir / "yt-videos"
    audio_dir = output_dir / "yt-audio"
    video_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    return {
        'format': 'best[ext=mp4]/best',
        'outtmpl': {
            'default': str(video_dir / '%(title)s.%(ext)s'),
        },
        'postprocessors': [
            {
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            },
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            },
            {
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }
        ],
        'keepvideo': True,
        'writethumbnail': False,
        'writeinfojson': False,
    }


def _add_metadata_postprocessor(options: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
    """Add metadata postprocessor for ID3 tags"""
    audio_dir = output_dir / "yt-audio"

    # Custom postprocessor for ID3 tags
    class CustomMetadataPostProcessor:
        def __init__(self):
            self.key = 'CustomMetadata'

        def run(self, info):
            # Extract artist information
            artist = info.get('artist') or info.get('uploader', '')
            track_number = info.get('playlist_index', '')

            # Add to postprocessor chain
            if 'postprocessors' not in options:
                options['postprocessors'] = []

            options['postprocessors'].append({
                'key': 'FFmpegMetadata',
                'add_metadata': True,
                'add_chapters': True,
            })

            return [], info

    return options

class MyCustomPP(PostProcessor):
    def run(self, info_dict):
        """Hook to sanitize filenames"""
        if 'title' in info_dict:
            info_dict['title'] = _sanitize_filename(info_dict['title'])
        return [], info_dict

def download_youtube_content(url: str, output_dir: Path,
                             only_audio: bool = False,
                             with_audio: bool = False) -> bool:
    """
    Download YouTube video(s) and/or audio(s) from URL

    Args:
        url: YouTube URL (single video or playlist)
        output_dir: Directory to save downloads
        only_audio: Download only audio files
        with_audio: Download both video and audio files

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)

        # Determine download options based on flags
        if only_audio:
            ydl_opts = _get_audio_options(output_dir)
            logger.info("Downloading audio only...")
        elif with_audio:
            ydl_opts = _get_both_options(output_dir)
            logger.info("Downloading both video and audio...")
        else:
            ydl_opts = _get_video_options(output_dir)
            logger.info("Downloading video only...")

        # Add common options
        ydl_opts.update(_get_base_options(output_dir))

        # Download with yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Add the hook to sanitize filenames
            # ydl.add_post_processor(lambda info: sanitize_filename_hook(info), when='pre_process')
            ydl.add_post_processor(MyCustomPP(), when='pre_process')
            # Get video info first to check if it's a playlist
            info = ydl.extract_info(url, download=False)

            # Sanitize titles in the info
            if 'entries' in info:
                for entry in info['entries']:
                    if entry and 'title' in entry:
                        entry['title'] = _sanitize_filename(entry['title'])
            elif 'title' in info:
                info['title'] = _sanitize_filename(info['title'])

            if 'entries' in info:
                logger.info(f"Found playlist with {len(info['entries'])} videos")

                # For playlist, we need to handle metadata differently
                if only_audio or with_audio:
                    ydl_opts = _update_options_for_playlist(ydl_opts, output_dir)
            else:
                logger.info("Found single video")

            # Perform the actual download
            ydl.download([url])

        logger.info("Download completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Error downloading content: {str(e)}")
        return False


def _update_options_for_playlist(options: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
    """Update options to handle playlist metadata correctly"""
    audio_dir = output_dir / "yt-audio"

    # Keep original output template without playlist index prefix
    # The metadata will contain playlist information but filename stays clean
    if 'outtmpl' in options:
        if isinstance(options['outtmpl'], dict):
            options['outtmpl']['default'] = str(audio_dir / '%(title)s.%(ext)s')
        else:
            options['outtmpl'] = str(audio_dir / '%(title)s.%(ext)s')

    # Add postprocessor for custom metadata
    metadata_pp = {
        'key': 'FFmpegMetadata',
        'add_metadata': True,
    }

    # Ensure postprocessors list exists
    if 'postprocessors' not in options:
        options['postprocessors'] = []

    # Add or update metadata postprocessor
    found_metadata = False
    for i, pp in enumerate(options['postprocessors']):
        if pp.get('key') == 'FFmpegMetadata':
            options['postprocessors'][i] = metadata_pp
            found_metadata = True
            break

    if not found_metadata:
        options['postprocessors'].append(metadata_pp)

    return options


def get_video_info(url: str) -> Optional[Dict[str, Any]]:
    """
    Extract video information without downloading

    Args:
        url: YouTube URL

    Returns:
        Dict containing video information or None if failed
    """
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info

    except Exception as e:
        logger.error(f"Error extracting video info: {str(e)}")
        return None


def list_available_formats(url: str) -> List[Dict[str, Any]]:
    """
    List available formats for a video

    Args:
        url: YouTube URL

    Returns:
        List of available formats
    """
    try:
        info = get_video_info(url)
        if info and 'formats' in info:
            return info['formats']
        return []

    except Exception as e:
        logger.error(f"Error listing formats: {str(e)}")
        return []
