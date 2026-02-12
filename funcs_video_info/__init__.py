"""Video information and URL validation utilities for yt-dlp scripts.

This package is organized into:
- url_validation: URL validation and timeout determination
- metadata: Video metadata retrieval using yt-dlp
- chapters: Chapter detection, display, and CSV generation
"""

# Import all functions to maintain backward compatibility
from funcs_video_info.chapters import (
    _format_duration,
    create_chapters_csv,
    display_chapters_and_confirm,
    get_chapter_count,
)
from funcs_video_info.metadata import (
    get_video_info,
    is_playlist,
)
from funcs_video_info.url_validation import (
    get_timeout_for_url,
    validate_video_url,
)

__all__ = [
    # URL validation
    'get_timeout_for_url',
    'validate_video_url',
    # Metadata
    'get_video_info',
    'is_playlist',
    # Chapters
    'get_chapter_count',
    'display_chapters_and_confirm',
    'create_chapters_csv',
    '_format_duration',
]
