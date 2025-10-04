"""Using yt-dlp, download videos from YouTube URL, and extract the MP3 files."""
import argparse
import glob
import os
import platform
import subprocess
from pathlib import Path

from funcs_process_mp3_tags import set_artists_in_mp3_files, set_tags_in_chapter_mp3_files
from funcs_process_mp4_tags import set_artists_in_m4a_files, set_tags_in_chapter_m4a_files
from funcs_utils import (organize_media_files, get_video_info, is_playlist, get_chapter_count,
                         sanitize_filenames_in_folder)

greek_to_dl_playlist_url = 'https://www.youtube.com/playlist?list=PLRXnwzqAlx1NehOIsFdwtVbsZ0Orf71cE'
yt_dlp_write_json_flag = '--write-info-json'
yt_dlp_split_chapters_flag = '--split-chapters'
yt_dlp_is_playlist_flag = '--yes-playlist'


def run_yt_dlp(ytdlp_exe: Path, playlist_url: str, video_folder: str, get_subs: bool,
               write_json: bool, has_chapters: bool, split_chapters: bool, is_it_playlist: bool) -> None:
    """Extract videos from YouTube playlist/video with yt-dlp. Include subtitles if requested."""
    yt_dlp_cmd = [
        ytdlp_exe,
        '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        '--merge-output-format', 'mp4',
        '-o', os.path.join(video_folder, '%(title)s.%(ext)s'),
        playlist_url
    ]
    if is_it_playlist:
        yt_dlp_cmd[1:1] = [yt_dlp_is_playlist_flag]
    if write_json:
        yt_dlp_cmd[1:1] = [yt_dlp_write_json_flag]
    if split_chapters and has_chapters:
        yt_dlp_cmd[1:1] = [yt_dlp_split_chapters_flag]
    if get_subs:
        # Extract subtitles in Greek, English, Hebrew
        yt_dlp_cmd[1:1] = [
            '--write-subs',
            '--sub-lang', 'el,en,he',
            '--convert-subs', 'srt'
        ]
    print('Downloading videos with yt-dlp...')
    print(f'========\n{yt_dlp_cmd}\n========')
    # Ignore errors (most common error is when playlist contains unavailable videos)
    subprocess.run(yt_dlp_cmd, check=False)


def _extract_single_format(ytdlp_exe: Path, playlist_url: str, audio_folder: str,
                          has_chapters: bool, split_chapters: bool, is_it_playlist: bool,
                          format_type: str, artist_pat: str = None, album_artist_pat: str = None) -> None:
    """Extract audio in a single format using yt-dlp."""
    # Create format-specific subfolder
    format_folder = os.path.join(audio_folder, format_type)
    os.makedirs(format_folder, exist_ok=True)

    yt_dlp_cmd = [
        ytdlp_exe,
        '-f', 'bestaudio/best',
        '--extract-audio',
        '--audio-format', format_type,
        '--audio-quality', '192k',
        '--embed-metadata',
        '--add-metadata',
        '--embed-thumbnail',
        #'--parse-metadata', 'track:',        # Clear the track #, as per Claude AI
        #'--parse-metadata', 'tracknumber:',  # Clear the track #, as per Claude AI
        '-o', os.path.join(format_folder, '%(title)s.%(ext)s'),
        playlist_url
    ]

    if is_it_playlist:
        yt_dlp_cmd[1:1] = [yt_dlp_is_playlist_flag]
    if artist_pat and album_artist_pat:
        yt_dlp_cmd[1:1] = ['--parse-metadata', artist_pat,
                           '--parse-metadata', album_artist_pat,
                           ]
    if split_chapters and has_chapters:
        yt_dlp_cmd[1:1] = [yt_dlp_split_chapters_flag]

    print(f'==== Downloading and extracting {format_type.upper()} audio with yt-dlp ====')
    print(f"CMD: '{yt_dlp_cmd}'")
    print('='*54)
    # Ignore errors (most common error is when playlist contains unavailable videos)
    subprocess.run(yt_dlp_cmd, check=False)



def extract_audio_with_ytdlp(ytdlp_exe: Path, playlist_url: str, audio_folder: str,
                             has_chapters: bool, split_chapters: bool, is_it_playlist: bool, audio_format: str = 'mp3') -> None:
    """Use yt-dlp to download and extract audio with metadata and thumbnail."""

    # For a single video, check if video has 'artist' or 'uploader' tags.
    # Use either to embed 'artist' and 'albumartist' tags in the audio file.
    artist_pat = album_artist_pat = None

    if is_it_playlist:
        have_artist = have_uploader = False
        print('URL is a playlist, cannot extract artist/uploader')
    else:
        video_info = get_video_info(yt_dlp_path=ytdlp_exe, url=playlist_url)
        artist = video_info.get('artist')
        uploader = video_info.get('uploader')
        have_artist = artist and artist not in ('NA', '')
        have_uploader = uploader and uploader not in ('NA', '')

        if have_artist:
            artist_pat = 'artist:%(artist)s'
            album_artist_pat = 'album_artist:%(artist)s'
            print(f"Video has artist: '{artist}'")
        elif have_uploader:
            artist_pat = 'artist:%(uploader)s'
            album_artist_pat = 'album_artist:%(uploader)s'
            print(f"Video has uploader: '{uploader}'")

    # Handle different audio format options
    if audio_format == 'both':
        # Extract both MP3 and M4A formats directly (will download twice)
        _extract_single_format(ytdlp_exe, playlist_url, audio_folder, has_chapters,
                              split_chapters, is_it_playlist, 'mp3', artist_pat, album_artist_pat)
        _extract_single_format(ytdlp_exe, playlist_url, audio_folder, has_chapters,
                              split_chapters, is_it_playlist, 'm4a', artist_pat, album_artist_pat)
    else:
        # Extract single format
        _extract_single_format(ytdlp_exe, playlist_url, audio_folder, has_chapters,
                              split_chapters, is_it_playlist, audio_format, artist_pat, album_artist_pat)

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Download YouTube playlist/video, optionally with subtitles.')
    parser.add_argument('playlist_url', nargs='?', help='YouTube playlist/video URL')
    parser.add_argument('--with-audio', action='store_true', help='Also extract audio (format specified by --audio-format)')
    parser.add_argument('--audio-format', choices=['mp3', 'm4a', 'both'], default='mp3', help='Audio format for extraction: mp3, m4a, or both (default: mp3)')
    parser.add_argument('--only-audio', action='store_true', help='Delete video files after extraction')
    parser.add_argument('--split-chapters', action='store_true', help='Split to chapters')
    parser.add_argument('--subs', action='store_true', help='Download subtitles')
    parser.add_argument('--json', action='store_true', help='Write JSON file')
    args = parser.parse_args()

    need_audio = args.with_audio or args.only_audio

    # Detect platform and set appropriate executable paths
    system_platform = platform.system().lower()

    if system_platform == 'windows':
        # Windows paths
        home_dir = Path.home()
        yt_dlp_dir = home_dir / 'Apps' / 'yt-dlp'
        yt_dlp_exe = yt_dlp_dir / 'yt-dlp.exe'
    else:
        # Linux/Mac - use system-wide installations
        yt_dlp_exe = 'yt-dlp'  # Should be in PATH

    # Handle artists.json path relative to script location, not current working directory
    script_dir = Path(__file__).parent
    artists_json = script_dir / 'Data' / 'artists.json'

    # Verify executables exist
    if system_platform == 'windows':
        assert Path(yt_dlp_exe).exists(), f"YT-DLP executable not found at '{yt_dlp_exe}'"
    else:
        # For Linux/Mac, check if commands are available in PATH
        try:
            subprocess.run([yt_dlp_exe, '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise AssertionError(f'YT-DLP not found in PATH. Install with: pip install yt-dlp')

    # Prompt for playlist/video URL if not provided
    if not args.playlist_url:
        args.playlist_url = input('Enter the URL: ').strip()

    video_folder = os.path.abspath('yt-videos')
    audio_folder = os.path.abspath('yt-audio')
    if not args.only_audio:
        os.makedirs(video_folder, exist_ok=True)
    if need_audio:
        os.makedirs(audio_folder, exist_ok=True)

    url_is_playlist = is_playlist(url=args.playlist_url)
    uploader_name = None  # Initialize uploader name for chapter processing
    video_title = None  # Initialize video title for chapter processing

    if not url_is_playlist:
        chapters_count = get_chapter_count(ytdlp_exe=yt_dlp_exe, playlist_url=args.playlist_url)
        has_chapters = chapters_count > 0
        print(f'Video has {chapters_count} chapters')

        # Get uploader and title information for chapter processing
        if has_chapters:
            video_info = get_video_info(yt_dlp_path=yt_dlp_exe, url=args.playlist_url)
            uploader_name = video_info.get('uploader')
            video_title = video_info.get('title')
            if uploader_name and uploader_name not in ('NA', ''):
                print(f"Uploader for chapters: '{uploader_name}'")
            if video_title and video_title not in ('NA', ''):
                print(f"Video title for chapters: '{video_title}'")
    else:
        print('URL is a playlist, not extracting chapters')
        has_chapters = False

    # Download videos if requested
    if not args.only_audio:
        run_yt_dlp(ytdlp_exe=yt_dlp_exe, playlist_url=args.playlist_url, video_folder=video_folder, get_subs=args.subs,
                   write_json=args.json, split_chapters=args.split_chapters, has_chapters=has_chapters,
                   is_it_playlist=url_is_playlist)

    # Download audios if requested
    if need_audio:
        # Run yt-dlp to download videos, and let yt-dlp extract audio and add tags
        extract_audio_with_ytdlp(ytdlp_exe=yt_dlp_exe, playlist_url=args.playlist_url, audio_folder=audio_folder,
                                 split_chapters=args.split_chapters, has_chapters=has_chapters,
                                 is_it_playlist=url_is_playlist, audio_format=args.audio_format)

    # If chapters, move chapter files (audio and videos), if any exist, to the corresponding sub-folders.
    # This is because chapter files are extracted to the current directory.
    if has_chapters:
        result = organize_media_files(video_dir=Path(video_folder), audio_dir=Path(audio_folder))

        # Check move results
        if result['mp3'] or result['m4a'] or result['mp4']:
            print('\nFiles organized successfully!')
        else:
            print('\nNo MP3/M4A'
                  ''
                  ' or MP4 files found in current directory.')

        if result['errors']:
            print('\nErrors encountered:')
            for error in result['errors']:
                print(f'- {error}')

    # Sanitize downloaded video file names
    if not args.only_audio:
        sanitize_filenames_in_folder(folder_path=Path(video_folder))
    if need_audio:
        # Sanitize downloaded audio file names in both subfolders
        if args.audio_format == 'mp3':
            mp3_subfolder = Path(audio_folder) / 'mp3'
            if mp3_subfolder.exists():
                sanitize_filenames_in_folder(folder_path=mp3_subfolder)
        elif args.audio_format == 'm4a':
            m4a_subfolder = Path(audio_folder) / 'm4a'
            if m4a_subfolder.exists():
                sanitize_filenames_in_folder(folder_path=m4a_subfolder)
        elif args.audio_format == 'both':
            mp3_subfolder = Path(audio_folder) / 'mp3'
            m4a_subfolder = Path(audio_folder) / 'm4a'
            if mp3_subfolder.exists():
                sanitize_filenames_in_folder(folder_path=mp3_subfolder)
            if m4a_subfolder.exists():
                sanitize_filenames_in_folder(folder_path=m4a_subfolder)


        # Process audio tags based on format
        if args.audio_format == 'mp3':
            # Modify MP3 tags based on the title
            mp3_subfolder = Path(audio_folder) / 'mp3'
            set_artists_in_mp3_files(mp3_folder=mp3_subfolder, artists_json=artists_json)
            # if the audio files are chapters, clean up the 'title' ID3 tag
            if has_chapters:
                _ = set_tags_in_chapter_mp3_files(mp3_folder=mp3_subfolder, uploader=uploader_name, video_title=video_title)
        elif args.audio_format == 'm4a':
            # Modify M4A tags based on the title
            m4a_subfolder = Path(audio_folder) / 'm4a'
            set_artists_in_m4a_files(m4a_folder=m4a_subfolder, artists_json=artists_json)
            # if the audio files are chapters, clean up the 'title' MP4 tag
            if has_chapters:
                _ = set_tags_in_chapter_m4a_files(m4a_folder=m4a_subfolder, uploader=uploader_name, video_title=video_title)
        elif args.audio_format == 'both':
            # Process both MP3 and M4A files
            print('Processing MP3 files...')
            mp3_subfolder = Path(audio_folder) / 'mp3'
            set_artists_in_mp3_files(mp3_folder=mp3_subfolder, artists_json=artists_json)
            if has_chapters:
                _ = set_tags_in_chapter_mp3_files(mp3_folder=mp3_subfolder, uploader=uploader_name, video_title=video_title)

            print('Processing M4A files...')
            m4a_subfolder = Path(audio_folder) / 'm4a'
            set_artists_in_m4a_files(m4a_folder=m4a_subfolder, artists_json=artists_json)
            if has_chapters:
                _ = set_tags_in_chapter_m4a_files(m4a_folder=m4a_subfolder, uploader=uploader_name, video_title=video_title)

if __name__ == '__main__':
    main()
