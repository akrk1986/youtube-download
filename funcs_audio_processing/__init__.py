"""Audio tag processing package."""
from funcs_audio_processing.mp3 import (
    set_artists_in_mp3_files,
    set_tags_in_chapter_mp3_files
)
from funcs_audio_processing.m4a import (
    set_artists_in_m4a_files,
    set_tags_in_chapter_m4a_files
)
from funcs_audio_processing.flac import (
    set_artists_in_flac_files,
    set_tags_in_chapter_flac_files
)

__all__ = [
    'set_artists_in_mp3_files',
    'set_tags_in_chapter_mp3_files',
    'set_artists_in_m4a_files',
    'set_tags_in_chapter_m4a_files',
    'set_artists_in_flac_files',
    'set_tags_in_chapter_flac_files',
]
