"""Audio tag processing package."""
from pathlib import Path

from funcs_audio_tag_handlers import (
    AudioTagHandler,
    FLACTagHandler, M4ATagHandler, MP3TagHandler,
)
from funcs_audio_processing.unified import (
    set_artists_in_audio_files,
    set_tags_in_chapter_audio_files
)

# Dispatch map: audio format string -> handler class
_HANDLER_MAP: dict[str, type[AudioTagHandler]] = {
    'mp3': MP3TagHandler,
    'm4a': M4ATagHandler,
    'flac': FLACTagHandler,
}


def set_artists_for_format(
        audio_format: str, audio_folder: Path,
        artists_json: Path,
        original_names: dict[str, str] | None = None
) -> None:
    """
    Set artists in audio files for the given format.

    Args:
        audio_format: Audio format key ('mp3', 'm4a', or 'flac')
        audio_folder: Path to audio files folder
        artists_json: Path to artists database JSON file
        original_names: Optional mapping of
            final_path -> original_ytdlp_filename

    Raises:
        ValueError: If audio_format is not one of the supported formats.
    """
    if audio_format not in _HANDLER_MAP:
        raise ValueError(f'Unknown audio format {audio_format!r}. Expected one of: {list(_HANDLER_MAP)}')
    handler_cls = _HANDLER_MAP[audio_format]
    set_artists_in_audio_files(
        audio_folder=audio_folder,
        artists_json=artists_json,
        handler=handler_cls(),
        original_names=original_names
    )


def set_chapter_tags_for_format(
        audio_format: str, audio_folder: Path,
        uploader: str | None = None,
        video_title: str | None = None,
        original_names: dict[str, str] | None = None
) -> int:
    """
    Set chapter tags in audio files for the given format.

    Args:
        audio_format: Audio format key ('mp3', 'm4a', or 'flac')
        audio_folder: Path to audio files folder
        uploader: Video uploader name
        video_title: Video title (used as album)
        original_names: Optional mapping of
            final_path -> original_ytdlp_filename

    Returns:
        int: Number of files whose title was modified

    Raises:
        ValueError: If audio_format is not one of the supported formats.
    """
    if audio_format not in _HANDLER_MAP:
        raise ValueError(f'Unknown audio format {audio_format!r}. Expected one of: {list(_HANDLER_MAP)}')
    handler_cls = _HANDLER_MAP[audio_format]
    return set_tags_in_chapter_audio_files(
        audio_folder=audio_folder,
        handler=handler_cls(),
        uploader=uploader,
        video_title=video_title,
        original_names=original_names
    )


# Backward-compatible aliases for standalone test scripts

def set_artists_in_mp3_files(
        mp3_folder: Path, artists_json: Path,
        original_names: dict[str, str] | None = None
) -> None:
    """Backward-compatible alias."""
    set_artists_for_format(
        'mp3', audio_folder=mp3_folder,
        artists_json=artists_json,
        original_names=original_names
    )


def set_tags_in_chapter_mp3_files(
        mp3_folder: Path,
        uploader: str | None = None,
        video_title: str | None = None,
        original_names: dict[str, str] | None = None
) -> int:
    """Backward-compatible alias."""
    return set_chapter_tags_for_format(
        'mp3', audio_folder=mp3_folder,
        uploader=uploader,
        video_title=video_title,
        original_names=original_names
    )


def set_artists_in_m4a_files(
        m4a_folder: Path, artists_json: Path,
        original_names: dict[str, str] | None = None
) -> None:
    """Backward-compatible alias."""
    set_artists_for_format(
        'm4a', audio_folder=m4a_folder,
        artists_json=artists_json,
        original_names=original_names
    )


def set_tags_in_chapter_m4a_files(
        m4a_folder: Path,
        uploader: str | None = None,
        video_title: str | None = None,
        original_names: dict[str, str] | None = None
) -> int:
    """Backward-compatible alias."""
    return set_chapter_tags_for_format(
        'm4a', audio_folder=m4a_folder,
        uploader=uploader,
        video_title=video_title,
        original_names=original_names
    )


def set_artists_in_flac_files(
        flac_folder: Path, artists_json: Path,
        original_names: dict[str, str] | None = None
) -> None:
    """Backward-compatible alias."""
    set_artists_for_format(
        'flac', audio_folder=flac_folder,
        artists_json=artists_json,
        original_names=original_names
    )


def set_tags_in_chapter_flac_files(
        flac_folder: Path,
        uploader: str | None = None,
        video_title: str | None = None,
        original_names: dict[str, str] | None = None
) -> int:
    """Backward-compatible alias."""
    return set_chapter_tags_for_format(
        'flac', audio_folder=flac_folder,
        uploader=uploader,
        video_title=video_title,
        original_names=original_names
    )


__all__ = [
    'set_artists_for_format',
    'set_chapter_tags_for_format',
    # Backward-compatible aliases
    'set_artists_in_mp3_files',
    'set_tags_in_chapter_mp3_files',
    'set_artists_in_m4a_files',
    'set_tags_in_chapter_m4a_files',
    'set_artists_in_flac_files',
    'set_tags_in_chapter_flac_files',
]
