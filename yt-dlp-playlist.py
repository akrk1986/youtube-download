"""Using yt-dlp, download all videos from YT playlist, and extract the MP3 files for them."""
import argparse
import os
import subprocess
import re
from pathlib import Path

greek_to_dl_playlist_url = "https://www.youtube.com/playlist?list=PLRXnwzqAlx1NehOIsFdwtVbsZ0Orf71cE"

# Regex: remove leading non-alphanumeric (English/Greek) characters, including spaces
pattern = re.compile(r'^[^a-zA-Z0-9\u0370-\u03FF]+')

def clean_filename(filename: str) -> str:
    """Remove leading unwanted characters (including spaces) from filename."""
    return pattern.sub('', filename)

def process_folder(folder_path: Path) -> None:
    """Rename files in the folder by removing leading unwanted characters."""
    ctr = 0
    for file_path in folder_path.iterdir():
        if file_path.is_file():
            new_name = clean_filename(file_path.name)
            if new_name and new_name != file_path.name:
                new_path = file_path.with_name(new_name)
                if not new_path.exists():
                    file_path.rename(new_path)
                    ctr += 1
                    print(f"Renamed: '{file_path.name}' -> '{new_name}'")
                else:
                    print(f"Skipped (target exists): '{new_name}'")
    print(f"Rename {ctr} files in folder '{folder_path}'")

def run_yt_dlp(ytdlp_exe: Path, playlist_url: str, video_folder: str, subs: bool) -> None:
    yt_dlp_cmd = [
        ytdlp_exe,
        '--yes-playlist',
        '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        '--merge-output-format', 'mp4',
        '-o', os.path.join(video_folder, '%(title)s.%(ext)s'),
        playlist_url
    ]
    if subs:
        yt_dlp_cmd[1:1] = [
            '--write-subs',
            '--sub-lang', 'el,en,he',
            '--convert-subs', 'srt'
        ]
    print("Downloading videos with yt-dlp...")
    subprocess.run(yt_dlp_cmd, check=True)

def extract_audio_with_ffmpeg(ffmpeg_exe: Path, video_folder: str, audio_folder: str) -> None:
    """Using the MP4 files that were already download, extract the audio with ffmpeg."""
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
            subprocess.run(ffmpeg_cmd, check=True)

def extract_audio_with_ytdlp(ytdlp_exe: Path, playlist_url: str, audio_folder: str) -> None:
    """Use yt-dlp to download and extract MP3 audio with metadata and thumbnail."""
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
        '--parse-metadata', 'playlist_index:%(track_number)s',
        '-o', os.path.join(audio_folder, '%(title)s.%(ext)s'),
        playlist_url
    ]
    print("Downloading and extracting audio with yt-dlp...")
    subprocess.run(yt_dlp_cmd, check=True)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download YouTube playlist as video and/or audio, optionally with subtitles.")
    parser.add_argument('playlist_url', nargs='?',
                        default=greek_to_dl_playlist_url,
                        help='YouTube playlist URL')
    parser.add_argument('--audio', action='store_true', help='Also extract audio as MP3')
    parser.add_argument('--subs', action='store_true',
                        help='Download subtitles (Greek, English, Hebrew) as SRT files')
    args = parser.parse_args()

    home_dir = Path.home()
    yt_dlp_dir = home_dir / "Apps" / "yt-dlp"
    yt_dlp_exe = yt_dlp_dir / "yt-dlp.exe"
    ffmpeg_exe = yt_dlp_dir / "ffmpeg.exe"

    assert Path(yt_dlp_exe).exists(), f"YT-DLP exe not found at '{yt_dlp_exe}'"
    assert Path(ffmpeg_exe).exists(), f"FFMPEG exe not found at '{ffmpeg_exe}'"

    # Prompt for playlist URL if not provided
    if not args.playlist_url:
        args.playlist_url = input("Enter the YouTube playlist/video URL: ").strip()

    video_folder = os.path.abspath('yt-videos')
    audio_folder = os.path.abspath('yt-audio')
    os.makedirs(video_folder, exist_ok=True)
    os.makedirs(audio_folder, exist_ok=True)

    # Always download videos
    run_yt_dlp(ytdlp_exe=yt_dlp_exe, playlist_url=args.playlist_url, video_folder=video_folder, subs=args.subs)

    # If --audio,
    if args.audio:
        # Old way: extract MP3 from downloaded videos
        # extract_audio_with_ffmpeg(ffmpeg_exe=ffmpeg_exe, video_folder=video_folder, audio_folder=audio_folder)

        # New way: run yt-dlp a second time to download audio and add tags
        extract_audio_with_ytdlp(ytdlp_exe=yt_dlp_exe, playlist_url=args.playlist_url, audio_folder=audio_folder)

    # Sanitize downloaded file names
    process_folder(folder_path=Path(video_folder))
    if args.audio:
        process_folder(folder_path=Path(audio_folder))

if __name__ == '__main__':
    main()
