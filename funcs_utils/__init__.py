"""Utility functions package for yt-dlp scripts.

This package is organized into:
- file_operations: File handling and organization
- string_sanitization: String and filename sanitization
- yt_dlp_utils: yt-dlp specific utilities
- security: Security helper functions
"""

# Import all functions to maintain backward compatibility
from funcs_utils.file_operations import (
    organize_media_files,
    organize_media_files_silent,
    sanitize_filenames_in_folder,
)
from funcs_utils.security import (
    sanitize_url_for_subprocess,
    validate_file_path_security,
)
from funcs_utils.string_sanitization import (
    greek_search,
    remove_diacritics,
    sanitize_string,
)
from funcs_utils.yt_dlp_utils import (
    get_cookie_args,
    is_format_error,
)

__all__ = [
    # File operations
    'organize_media_files',
    'organize_media_files_silent',
    'sanitize_filenames_in_folder',
    # String sanitization
    'sanitize_string',
    'remove_diacritics',
    'greek_search',
    # yt-dlp utils
    'is_format_error',
    'get_cookie_args',
    # Security
    'sanitize_url_for_subprocess',
    'validate_file_path_security',
]
