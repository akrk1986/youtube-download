"""Read the copied tag fields from an .m4a or .mp3 audio file into a common_av AudioTags.

Reuses the project's funcs_audio_tag_handlers strategy classes (the same readers the
duplicate-finder uses in funcs_check_greek_singles/audio_reader.py) rather than hand-rolled
mutagen reads. FLAC is intentionally unsupported (no use case for FLAC->video tags).
"""
import logging
from pathlib import Path

from common_av.tags import MP4_COMMENT, MP4_COMPOSER, MP4_DATE, AudioTags
from mutagen.id3 import ID3, ID3NoHeaderError

from funcs_audio_tag_handlers import M4ATagHandler, MP3TagHandler
from funcs_audio_tag_handlers.base import AudioTagHandler
from funcs_check_greek_singles.normalize import extract_year

logger = logging.getLogger(__name__)

# Handlers are stateless; build once (mirrors funcs_check_greek_singles/audio_reader.py).
_HANDLERS_BY_EXT: dict[str, AudioTagHandler] = {
    '.m4a': M4ATagHandler(),
    '.mp3': MP3TagHandler(),
}

# EasyID3 (mp3) keys for fields not exposed as handler TAG_* constants.
_MP3_DATE_KEY = 'date'
_MP3_COMPOSER_KEY = 'composer'


def _read_mp3_comment(audio_path: Path) -> str:
    """Read the first COMM (comment) frame from an MP3 via raw ID3.

    EasyID3 (used by MP3TagHandler) does not expose COMM, so it is read directly.

    Args:
        audio_path: Path to the .mp3 file.

    Returns:
        str: The comment text, or '' when absent/unreadable.
    """
    try:
        id3 = ID3(audio_path)
    except (ID3NoHeaderError, OSError, ValueError) as exc:
        logger.debug('Could not read ID3 comment from %s: %s', audio_path.name, exc)
        return ''
    for frame in id3.getall('COMM'):
        if getattr(frame, 'text', None):
            return str(frame.text[0]).strip()
    return ''


def read_audio_tags(audio_path: Path) -> AudioTags:
    """Read the six copied tag fields from an .m4a or .mp3 audio file.

    Args:
        audio_path: Path to the audio source file.

    Returns:
        AudioTags: The metadata to copy into the matching video (composer/comment may be '').

    Raises:
        ValueError: If the file extension is not .m4a or .mp3.
    """
    ext = audio_path.suffix.lower()
    handler = _HANDLERS_BY_EXT.get(ext)
    if handler is None:
        raise ValueError(f'Unsupported audio extension: {audio_path.suffix}')

    audio = handler.open_audio_file(file_path=audio_path)
    title = handler.get_tag(audio=audio, tag_name=handler.TAG_TITLE).strip()
    artist = handler.get_tag(audio=audio, tag_name=handler.TAG_ARTIST).strip()
    album = handler.get_tag(audio=audio, tag_name=handler.TAG_ALBUM).strip()

    if ext == '.m4a':
        date_value = handler.get_tag(audio=audio, tag_name=MP4_DATE).strip()
        composer = handler.get_tag(audio=audio, tag_name=MP4_COMPOSER).strip()
        comment = handler.get_tag(audio=audio, tag_name=MP4_COMMENT).strip()
    else:  # .mp3
        date_value = handler.get_tag(audio=audio, tag_name=_MP3_DATE_KEY).strip()
        composer = handler.get_tag(audio=audio, tag_name=_MP3_COMPOSER_KEY).strip()
        comment = _read_mp3_comment(audio_path=audio_path)

    return AudioTags(
        title=title,
        artist=artist,
        album=album,
        year=extract_year(date_tag_value=date_value),
        composer=composer,
        comment=comment,
    )
