"""Helper functions package for main-yt-dlp.py.

This package is organized into:
- _download_common: Shared dataclass, helpers, and progress state
- download_video: Video download functions
- download_audio: Audio extraction functions
- chapter_remux: Chapter remux post-processing
- external_tools: External tool path detection (ffmpeg, yt-dlp)
- url_validation: URL validation and input handling
- file_organization: File organization and sanitization
- audio_processing: Audio tag processing
- utilities: General utility functions
- ertflix_token_handler: ERTFlix token API URL resolution
"""

# Import all functions to maintain backward compatibility
from funcs_for_main_yt_dlp._download_common import DownloadOptions
from funcs_for_main_yt_dlp.audio_processing import process_audio_tags
from funcs_for_main_yt_dlp.chapter_remux import remux_video_chapters
from funcs_for_main_yt_dlp.download_audio import extract_audio_with_ytdlp
from funcs_for_main_yt_dlp.download_video import run_yt_dlp
from funcs_for_main_yt_dlp.ertflix_token_handler import (
    is_ertflix_token_url,
    resolve_ertflix_token_url,
)
from funcs_for_main_yt_dlp.external_tools import (
    get_ffmpeg_path,
    get_ytdlp_path,
    get_ytdlp_version,
    quote_if_needed,
)
from funcs_for_main_yt_dlp.file_organization import (
    count_files,
    get_audio_dir_for_format,
    organize_and_sanitize_files,
)
from funcs_for_main_yt_dlp.url_validation import validate_and_get_url
from funcs_for_main_yt_dlp.utilities import (
    format_elapsed_time,
    generate_session_id,
)

__all__ = [
    # Download
    'DownloadOptions',
    'run_yt_dlp',
    'extract_audio_with_ytdlp',
    'remux_video_chapters',
    # External tools
    'get_ytdlp_path',
    'get_ytdlp_version',
    'get_ffmpeg_path',
    'quote_if_needed',
    # URL validation
    'validate_and_get_url',
    # File organization
    'organize_and_sanitize_files',
    'get_audio_dir_for_format',
    'count_files',
    # Audio processing
    'process_audio_tags',
    # Utilities
    'format_elapsed_time',
    'generate_session_id',
    # ERTFlix token handling
    'is_ertflix_token_url',
    'resolve_ertflix_token_url',
]
