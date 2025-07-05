#!/usr/bin/env python3
"""
YouTube Audio Extractor with ID3 Tag Management
Extracts MP3 audio from YouTube videos and sets artist/albumartist tags
"""

import os
import sys
import yt_dlp
from mutagen.id3 import ID3, TPE1, TPE2, TIT2, TALB
from mutagen.mp3 import MP3
import argparse

# FFmpeg binary location - modify this path as needed
FFMPEG_BIN = "C:/Users/User/Apps/ffmpeg_bin/ffmpeg.exe"  # Default path, change as needed


def extract_video_info(url):
    """Extract video information without downloading"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', ''),
                'artist': info.get('artist', ''),
                'uploader': info.get('uploader', ''),
                'album': info.get('album', ''),
                'id': info.get('id', '')
            }
        except Exception as e:
            print(f"Error extracting video info: {e}")
            return None


def download_audio(url, output_path='.'):
    """Download audio as MP3 using yt-dlp"""
    # Create yt-audio subfolder
    yt_audio_path = os.path.join(output_path, 'yt-audio')
    os.makedirs(yt_audio_path, exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(yt_audio_path, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }

    # Add ffmpeg location if specified
    if FFMPEG_BIN and os.path.exists(FFMPEG_BIN):
        ffprobe_bin = FFMPEG_BIN.replace('ffmpeg', 'ffprobe')
        ydl_opts['ffmpeg_location'] = os.path.dirname(FFMPEG_BIN)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            # Construct the expected filename
            title = info.get('title', 'Unknown')
            filename = f"{title}.mp3"
            filepath = os.path.join(yt_audio_path, filename)
            return filepath, info
        except Exception as e:
            print(f"Error downloading audio: {e}")
            return None, None


def set_id3_tags(filepath, info):
    """Set ID3 tags for the MP3 file"""
    try:
        # Load the MP3 file
        audio = MP3(filepath)

        # Create ID3 tags if they don't exist
        if audio.tags is None:
            audio.add_tags()

        # Extract information
        title = info.get('title', '')
        artist = info.get('artist', '')
        uploader = info.get('uploader', '')
        album = info.get('album', '')

        # Determine which value to use for artist/albumartist
        tag_artist = ''
        if artist and artist.strip() and artist.upper() != 'NA':
            tag_artist = artist.strip()
        elif uploader and uploader.strip() and uploader.upper() != 'NA':
            tag_artist = uploader.strip()

        # Set tags
        if title:
            audio.tags.add(TIT2(encoding=3, text=title))

        if tag_artist:
            audio.tags.add(TPE1(encoding=3, text=tag_artist))  # Artist
            audio.tags.add(TPE2(encoding=3, text=tag_artist))  # Album Artist

        if album:
            audio.tags.add(TALB(encoding=3, text=album))

        # Save the tags
        audio.save()

        print(f"Tags set successfully:")
        print(f"  Title: {title}")
        print(f"  Artist/Album Artist: {tag_artist}")
        if album:
            print(f"  Album: {album}")

        return True

    except Exception as e:
        print(f"Error setting ID3 tags: {e}")
        return False


def process_youtube_video(url, output_path='.'):
    """Main function to process a YouTube video"""
    print(f"Processing: {url}")

    # Extract video info first
    info = extract_video_info(url)
    if not info:
        print("Failed to extract video information")
        return False

    print(f"Video: {info['title']}")
    print(f"Artist: {info['artist'] or 'Not specified'}")
    print(f"Uploader: {info['uploader'] or 'Not specified'}")

    # Download audio
    print("Downloading audio...")
    filepath, download_info = download_audio(url, output_path)
    if not filepath:
        print("Failed to download audio")
        return False

    # Check if file exists
    if not os.path.exists(filepath):
        print(f"Downloaded file not found: {filepath}")
        return False

    print(f"Audio saved to: {filepath}")

    # Set ID3 tags
    print("Setting ID3 tags...")
    if set_id3_tags(filepath, info):
        print("Process completed successfully!")
        return True
    else:
        print("Failed to set ID3 tags")
        return False


def main():
    parser = argparse.ArgumentParser(description='Extract audio from YouTube videos with ID3 tags')
    parser.add_argument('url', nargs='?', help='YouTube video URL')
    parser.add_argument('-o', '--output', default='.', help='Output directory (default: current directory)')

    args = parser.parse_args()

    # Check if required packages are available
    try:
        import yt_dlp
        import mutagen
    except ImportError as e:
        print(f"Missing required package: {e}")
        print("Install with: pip install yt-dlp mutagen")
        sys.exit(1)

    # Get URL from user if not provided
    url = args.url
    if not url:
        url = input("Enter YouTube video URL: ").strip()
        if not url:
            print("No URL provided. Exiting.")
            sys.exit(1)

    # Check if output directory exists
    if not os.path.exists(args.output):
        os.makedirs(args.output)

    # Process the video
    success = process_youtube_video(url, args.output)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()