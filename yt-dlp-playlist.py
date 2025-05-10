"""Using yt-dlp, download all videos from YT playlist, and extract the MP3 files for them."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

greek_to_dl_playlist_url = "https://www.youtube.com/playlist?list=PLRXnwzqAlx1NehOIsFdwtVbsZ0Orf71cE"

def validate_args(args: argparse.Namespace) -> None:
    allowed = {'audio', 'subs'}
    for arg in vars(args):
        if getattr(args, arg) and arg not in allowed and arg != 'playlist_url':
            print(f"Invalid option: --{arg}. Only --audio and --subs are allowed.")
            sys.exit(1)

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

def extract_audio(ffmpeg_exe: Path, video_folder: str, audio_folder: str) -> None:
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

    # Abort on any unknown arguments
    # args, unknown = parser.parse_known_args()
    # if unknown:
    #     print(f"Invalid options: {' '.join(unknown)}. Only --audio and --subs are allowed.")
    #     sys.exit(1)

    # Validate allowed arguments
    # validate_args(args=args)

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

    # If --audio, extract MP3 from downloaded videos
    if args.audio:
        extract_audio(ffmpeg_exe=ffmpeg_exe, video_folder=video_folder, audio_folder=audio_folder)

if __name__ == '__main__':
    main()
