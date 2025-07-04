"""Using yt-dlp, download all videos from YT playlist, and extract the MP3 files for them."""
import argparse
import os
import json
import subprocess
from pathlib import Path
from process_mp3_files_for_tags import set_artists_in_mp3_files, set_tags_in_chapter_mp3_files
from utils import sanitize_string, organize_media_files, get_video_info


greek_to_dl_playlist_url = "https://www.youtube.com/playlist?list=PLRXnwzqAlx1NehOIsFdwtVbsZ0Orf71cE"
yt_dlp_write_json_flag = '--write-info-json'
yt_dlp_split_chapters_flag = '--split-chapters'


def get_chapter_count(ytdlp_exe: Path, playlist_url: str) -> int:
    """
    Get the number of chapters in a YouTube video using yt-dlp.

    Args:
        ytdlp_exe (Path): path to yt-dlp executable
        playlist_url (str): YouTube video URL

    Returns:
        int: Number of chapters (0 if none or error)
    """
    try:
        cmd = [ytdlp_exe, '--dump-json', '--no-download', playlist_url]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)
        chapters = video_info.get('chapters', [])
        return len(chapters)
    except:
        return 0

def sanitize_filenames_in_folder(folder_path: Path) -> None:
    """Sanitize file names in the folder by removing leading unwanted characters."""
    ctr = 0
    for file_path in folder_path.iterdir():
        if file_path.is_file():
            new_name = sanitize_string(dirty_string=file_path.name)
            if new_name and new_name != file_path.name:
                new_path = file_path.with_name(new_name)
                if not new_path.exists():
                    file_path.rename(new_path)
                    ctr += 1
                    print(f"Renamed: '{file_path.name}' -> '{new_name}'")
                else:
                    print(f"Skipped (target exists): '{new_name}'")
    print(f"Renamed {ctr} files in folder '{folder_path}'")

def run_yt_dlp(ytdlp_exe: Path, playlist_url: str, video_folder: str, subs: bool,
               write_json: bool, has_chapters: bool, split_chapters: bool) -> None:
    """Extract videos from YouTube playlist/video with yt-dlp. Include subtitles if requested."""
    yt_dlp_cmd = [
        ytdlp_exe,
        '--yes-playlist',
        '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        '--merge-output-format', 'mp4',
        '-o', os.path.join(video_folder, '%(title)s.%(ext)s'),
        playlist_url
    ]
    if write_json:
        yt_dlp_cmd[1:1] = [yt_dlp_write_json_flag]
    if split_chapters and has_chapters:
        yt_dlp_cmd[1:1] = [yt_dlp_split_chapters_flag]

    if subs:
        # Extract subtitles in Greek, English, Hebrew
        yt_dlp_cmd[1:1] = [
            '--write-subs',
            '--sub-lang', 'el,en,he',
            '--convert-subs', 'srt'
        ]
    print("Downloading videos with yt-dlp...")
    print(f'========\n{yt_dlp_cmd}\n========')
    # Ignore errors (most common error is when playlist contains unavailable videos)
    subprocess.run(yt_dlp_cmd, check=False)

def extract_audio_with_ffmpeg(ffmpeg_exe: Path, video_folder: str, audio_folder: str) -> None:
    """Using the MP4 files that were already downloaded by yt-dlp, extract the audio using ffmpeg.
    Currently not in use.
    """
    video_files = list(Path(video_folder).glob('*.mp4'))
    for video_file in video_files:
        audio_file = Path(audio_folder) / (video_file.stem + '.mp3')
        if not audio_file.exists():
            print(f"Extracting audio from {video_file.name}...")
            ffmpeg_cmd = [
                ffmpeg_exe, '-hide_banner', '-loglevel', 'info',
                '-i', str(video_file),
                '-vn', '-ab', '192k', '-ar', '44100', '-y',
                str(audio_file)
            ]
            subprocess.run(ffmpeg_cmd, check=False)

def extract_audio_with_ytdlp(ytdlp_exe: Path, playlist_url: str, audio_folder: str,
                             has_chapters: bool, split_chapters: bool) -> None:
    """Use yt-dlp to download and extract MP3 audio with metadata and thumbnail."""

    # Check if video has 'artist' or 'uploader' tags.
    # Use either to embed 'artist' and 'albumartist' tags in the MP3 file.
    video_info = get_video_info(yt_dlp_path=ytdlp_exe, url=playlist_url)
    artist = video_info.get('artist')
    uploader = video_info.get('uploader')
    have_artist = artist is not None and artist not in ('NA', '')
    have_uploader = uploader is not None and uploader not in ('NA', '')
    a = aa = up = None
    if have_artist:
        a = 'artist:%(artist)s'
        aa = 'album_artist:%(artist)s'
        up = 'uploader:%(artist)s'
    elif have_uploader:
        a = 'artist:%(uploader)s'
        aa = 'album_artist:%(uploader)s'
        up = 'uploader:%(uploader)s'

    yt_dlp_cmd = [
        ytdlp_exe,
        '--yes-playlist',
        '-f', 'bestaudio/best',
        '--extract-audio',
        '--audio-format', 'mp3',
        '--audio-quality', '192k',
        '--embed-metadata',
        '--add-metadata',
        '--embed-thumbnail',
        #'--parse-metadata', 'album_artist:%(artist)s',
        #'--parse-metadata', 'artist:%(artist)s',
        '-o', os.path.join(audio_folder, '%(title)s.%(ext)s'),
        playlist_url
    ]
    if have_artist or have_uploader:
        yt_dlp_cmd[1:1] = ['--parse-metadata', a,
                           '--parse-metadata', aa,
                           #'--parse-metadata', up,
                           ]

    if split_chapters and has_chapters:
        yt_dlp_cmd[1:1] = [yt_dlp_split_chapters_flag]

    print("==== Downloading and extracting audio with yt-dlp ====")
    print(f"CMD: '{yt_dlp_cmd}'")
    print('='*54)
    # Ignore errors (most common error is when playlist contains unavailable videos)
    subprocess.run(yt_dlp_cmd, check=False)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download YouTube playlist/video, optionally with subtitles.")
    parser.add_argument('playlist_url', nargs='?', help='YouTube playlist/video URL')
    parser.add_argument('--with-audio', action='store_true', help='Also extract audio as MP3')
    parser.add_argument('--only-audio', action='store_true', help='Delete video files after extraction')
    parser.add_argument('--split-chapters', action='store_true', help='Split to chapters')
    parser.add_argument('--subs', action='store_true', help='Download subtitles')
    parser.add_argument('--json', action='store_true', help='Write JSON file')
    args = parser.parse_args()

    need_audio = args.with_audio or args.only_audio

    home_dir = Path.home()
    yt_dlp_dir = home_dir / "Apps" / "yt-dlp"
    yt_dlp_exe = yt_dlp_dir / "yt-dlp.exe"
    ffmpeg_exe = yt_dlp_dir / "ffmpeg.exe"
    artists_json = Path('Data/artists.json')

    assert Path(yt_dlp_exe).exists(), f"YT-DLP executable not found at '{yt_dlp_exe}'"
    assert Path(ffmpeg_exe).exists(), f"FFMPEG executable not found at '{ffmpeg_exe}'"

    # Prompt for playlist/video URL if not provided
    if not args.playlist_url:
        args.playlist_url = input("Enter the URL: ").strip()

    video_folder = os.path.abspath('yt-videos')
    audio_folder = os.path.abspath('yt-audio')
    if not args.only_audio:
        os.makedirs(video_folder, exist_ok=True)
    if need_audio:
        os.makedirs(audio_folder, exist_ok=True)

    chapters_count = get_chapter_count(ytdlp_exe=yt_dlp_exe, playlist_url=args.playlist_url)
    has_chapters = chapters_count > 0
    print(f'Video has {chapters_count} chapters')

    # Download videos if requested
    if not args.only_audio:
        run_yt_dlp(ytdlp_exe=yt_dlp_exe, playlist_url=args.playlist_url, video_folder=video_folder, subs=args.subs,
                   write_json=args.json, split_chapters=args.split_chapters, has_chapters=has_chapters)

    # Download audios if requested
    if need_audio:
        # Run yt-dlp to download videos, and let yt-dlp extract audio and add tags
        extract_audio_with_ytdlp(ytdlp_exe=yt_dlp_exe, playlist_url=args.playlist_url, audio_folder=audio_folder,
                                 split_chapters=args.split_chapters, has_chapters=has_chapters)

    # Move chapter files (audio and videos), if any exist, to the corresponding sub-folders
    result = organize_media_files(video_dir=Path(video_folder), audio_dir=Path(audio_folder))

    # Check move results
    if result['mp3'] or result['mp4']:
        print("\nFiles organized successfully!")
    else:
        print("\nNo MP3 or MP4 files found in current directory.")

    if result['errors']:
        print("\nErrors encountered:")
        for error in result['errors']:
            print(f"- {error}")

    # Sanitize downloaded video file names
    if not args.only_audio:
        sanitize_filenames_in_folder(folder_path=Path(video_folder))
    if need_audio:
        # Sanitize downloaded audio file names
        sanitize_filenames_in_folder(folder_path=Path(audio_folder))
        # Modify some MP3 tags based on the title
        set_artists_in_mp3_files(mp3_folder=Path(audio_folder), artists_json=artists_json)
        # if the audio files are chapters, clean up the 'title' ID3 tag
        if has_chapters:
            _ = set_tags_in_chapter_mp3_files(mp3_folder=Path(audio_folder))

if __name__ == '__main__':
    main()
