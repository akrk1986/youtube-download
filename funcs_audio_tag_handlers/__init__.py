"""
Audio tag handler classes for different audio formats.
Implements strategy pattern to eliminate code duplication between MP3, M4A, and FLAC processing.

This package is organized into:
- base: Abstract base class for audio tag handlers
- mp3_handler: MP3 tag handler using EasyID3
- m4a_handler: M4A tag handler using MP4
- flac_handler: FLAC tag handler using Vorbis Comments
"""

# Import all classes to maintain backward compatibility
from funcs_audio_tag_handlers.base import AudioTagHandler
from funcs_audio_tag_handlers.flac_handler import FLACTagHandler
from funcs_audio_tag_handlers.m4a_handler import M4ATagHandler
from funcs_audio_tag_handlers.mp3_handler import MP3TagHandler

__all__ = [
    'AudioTagHandler',
    'MP3TagHandler',
    'M4ATagHandler',
    'FLACTagHandler',
]
