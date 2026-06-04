"""Pair audio files with sibling video files by shared basename.

A video matches an audio file when the video's stem equals the audio stem (exact) or ends
with '-<audio-stem>'. The trailing '-<audio-stem>' form covers videos named
'<prefix>-<song-name>.mp4' against a '<song-name>.m4a/.mp3' audio file, where the last '-'
is the generated delimiter between the prefix and the song name. Matching the audio's full
stem as the suffix keeps it correct even when the song name itself contains hyphens.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

AUDIO_SUFFIXES = frozenset({'.m4a', '.mp3'})
VIDEO_SUFFIX = '.mp4'


def pair_audio_with_video(
        audio_dir: Path,
        video_dir: Path) -> tuple[list[tuple[Path, Path]], list[Path], list[Path]]:
    """Match each audio file to its .mp4 in the video folder (exact or '<prefix>-' stem).

    Extensions and stems are compared case-insensitively. Exact stem matches are assigned
    first; remaining audio files are then matched to a video whose stem ends with
    '-<audio-stem>'. Each video pairs at most once. When two audio files share a stem, a
    warning is logged.

    Args:
        audio_dir: Folder containing .m4a/.mp3 source files.
        video_dir: Sibling folder containing .mp4 video files.

    Returns:
        tuple[list[tuple[Path, Path]], list[Path], list[Path]]: (pairs, audio_without_video,
            video_without_audio) where pairs is a list of (audio_path, video_path),
            audio_without_video lists audio files with no matching video, and
            video_without_audio lists videos with no matching audio.
    """
    videos = [path for path in sorted(video_dir.iterdir())
              if path.is_file() and path.suffix.lower() == VIDEO_SUFFIX]
    audio_files = sorted(path for path in audio_dir.iterdir()
                         if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES)

    seen_stems: set[str] = set()
    for audio in audio_files:
        stem = audio.stem.lower()
        if stem in seen_stems:
            logger.warning('Multiple audio files share basename %s; %s also targets the same video',
                           stem, audio.name)
        seen_stems.add(stem)

    matched_videos: set[Path] = set()
    audio_to_video: dict[Path, Path] = {}

    # Pass 1: exact stem match (takes priority so it is never claimed by a prefixed match).
    for audio in audio_files:
        stem = audio.stem.lower()
        for video in videos:
            if video not in matched_videos and video.stem.lower() == stem:
                audio_to_video[audio] = video
                matched_videos.add(video)
                break

    # Pass 2: prefixed match — video stem ends with '-<audio-stem>'.
    for audio in audio_files:
        if audio in audio_to_video:
            continue
        suffix = f'-{audio.stem.lower()}'
        for video in videos:
            if video not in matched_videos and video.stem.lower().endswith(suffix):
                audio_to_video[audio] = video
                matched_videos.add(video)
                break

    pairs = [(audio, audio_to_video[audio]) for audio in audio_files if audio in audio_to_video]
    audio_without_video = [audio for audio in audio_files if audio not in audio_to_video]
    video_without_audio = [video for video in videos if video not in matched_videos]
    return pairs, audio_without_video, video_without_audio
