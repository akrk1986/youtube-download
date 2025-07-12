#!/usr/bin/env python3
"""
YouTube downloader functions using yt-dlp
"""

import yt_dlp
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_audio_options(output_dir: Path, extract_metadata: bool = True) -> Dict[str, Any]:
    """Get yt-dlp options for audio-only download"""
    audio_dir = output_dir / "yt-audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    options = {
        'format': 'bestaudio/best',
        'outtmpl': str(audio_dir / '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'writethumbnail': False,
        'writeinfojson': False,
    }

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

    return {
        'format': 'best[ext=mp4]/best',
        'outtmpl': str(video_dir / '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        'writethumbnail': False,
        'writeinfojson': False,
    }


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


def download_youtube_content(url: str, output_dir: Path, only_audio: bool = False,
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
        ydl_opts.update({
            'ignoreerrors': True,
            'no_warnings': False,
            'extractflat': False,
        })

        # Download with yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Get video info first to check if it's a playlist
            info = ydl.extract_info(url, download=False)

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

    # Update output template to include playlist information
    if 'outtmpl' in options:
        if isinstance(options['outtmpl'], dict):
            options['outtmpl']['default'] = str(audio_dir / '%(playlist_index)s - %(title)s.%(ext)s')
        else:
            options['outtmpl'] = str(audio_dir / '%(playlist_index)s - %(title)s.%(ext)s')

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