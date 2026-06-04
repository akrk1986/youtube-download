"""Pair audio files with sibling video files by shared basename."""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

AUDIO_SUFFIXES = frozenset({'.m4a', '.mp3'})
VIDEO_SUFFIX = '.mp4'


def pair_audio_with_video(
        audio_dir: Path,
        video_dir: Path) -> tuple[list[tuple[Path, Path]], list[Path], list[Path]]:
    """Match each audio file to a same-basename .mp4 in the video folder.

    Extensions are matched case-insensitively. When two audio files share a stem
    (e.g. song-01.m4a and song-01.mp3) both pair to the one video; a warning is logged.

    Args:
        audio_dir: Folder containing .m4a/.mp3 source files.
        video_dir: Sibling folder containing .mp4 video files.

    Returns:
        tuple[list[tuple[Path, Path]], list[Path], list[Path]]: (pairs, audio_without_video,
            video_without_audio) where pairs is a list of (audio_path, video_path),
            audio_without_video lists audio files with no matching video, and
            video_without_audio lists videos with no matching audio.
    """
    videos = {path.stem.lower(): path
              for path in sorted(video_dir.iterdir())
              if path.is_file() and path.suffix.lower() == VIDEO_SUFFIX}

    audio_files = sorted(path for path in audio_dir.iterdir()
                         if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES)

    pairs: list[tuple[Path, Path]] = []
    audio_without_video: list[Path] = []
    matched_stems: set[str] = set()
    seen_stems: set[str] = set()
    for audio in audio_files:
        stem = audio.stem.lower()
        if stem in seen_stems:
            logger.warning('Multiple audio files share basename %s; %s also targets the same video',
                           stem, audio.name)
        seen_stems.add(stem)

        video = videos.get(stem)
        if video is None:
            audio_without_video.append(audio)
        else:
            pairs.append((audio, video))
            matched_stems.add(stem)

    video_without_audio = [video for stem, video in videos.items() if stem not in matched_stems]
    return pairs, audio_without_video, video_without_audio
