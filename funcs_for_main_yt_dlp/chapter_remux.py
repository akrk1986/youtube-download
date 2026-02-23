"""Chapter remux functions for fixing MP4 chapter file duration metadata."""
import logging
import re
import subprocess
from pathlib import Path

from funcs_audio_processing.common import sanitize_album_name
from project_defs import FFMPEG_TIMEOUT_SECONDS, GLOB_MP4_FILES

logger = logging.getLogger(__name__)

# Matches yt-dlp chapter filenames: '<title> - NNN <chapter_title>'
_VIDEO_CHAPTER_PATTERN = re.compile(r'^.*?\s*-\s*(\d{3})\s+.+')


def remux_video_chapters(ffmpeg_path: str, video_folder: Path,
                         chapters: list[dict] | None = None,
                         video_title: str | None = None) -> None:
    """Remux split video chapter files to fix duration metadata and set chapter tags.

    yt-dlp's --split-chapters creates MP4 files whose container duration
    still reflects the original (full) video. A stream-copy remux via ffmpeg
    rewrites the container with the correct duration. If chapters metadata is
    provided, also sets title, track number, and album tags.
    """
    sanitized_album = sanitize_album_name(title=video_title) if video_title else ''

    # Chapter files may land in CWD or in video_folder depending on yt-dlp version
    candidates = list(Path.cwd().glob(GLOB_MP4_FILES)) + list(video_folder.glob(GLOB_MP4_FILES))
    # Deduplicate resolved paths (handles CWD == video_folder)
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in candidates:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(f)

    # Filter to chapter files only (stem matches ' - NNN ' pattern)
    chapter_files = [f for f in unique if _VIDEO_CHAPTER_PATTERN.match(f.stem)]

    if not chapter_files:
        logger.debug('No video chapter files to remux')
        return

    logger.info(f'Remuxing {len(chapter_files)} video chapter file(s) to fix duration metadata')

    for mp4_file in chapter_files:
        temp_file = mp4_file.with_name(mp4_file.stem + '.remux.mp4')

        # Set title and trim to chapter duration if chapters info is available
        metadata_args: list[str] = []
        duration_args: list[str] = []
        match = _VIDEO_CHAPTER_PATTERN.match(mp4_file.stem)
        if match and chapters:
            chapter_num = int(match.group(1))
            if 1 <= chapter_num <= len(chapters):
                chapter = chapters[chapter_num - 1]
                chapter_title = chapter.get('title', '')
                if chapter_title:
                    metadata_args = ['-metadata', f'title={chapter_title}']
                metadata_args.extend(['-metadata', f'track={chapter_num}'])
                if sanitized_album:
                    metadata_args.extend(['-metadata', f'album={sanitized_album}'])
                start_time = chapter.get('start_time', 0)
                end_time = chapter.get('end_time', 0)
                if end_time > start_time:
                    duration_args = ['-t', str(end_time - start_time)]

        try:
            cmd = [ffmpeg_path, '-y', '-i', str(mp4_file), '-c', 'copy'] + duration_args + metadata_args + [str(temp_file)]
            subprocess.run(cmd, capture_output=True, check=True, timeout=FFMPEG_TIMEOUT_SECONDS,
                           encoding='utf-8', errors='replace')
            temp_file.replace(mp4_file)
            logger.info(f"Remuxed '{mp4_file.name}'")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to remux '{mp4_file.name}': {e.stderr}")
            if temp_file.exists():
                temp_file.unlink()
        except subprocess.TimeoutExpired:
            logger.error(f"Remux timed out for '{mp4_file.name}'")
            if temp_file.exists():
                temp_file.unlink()
