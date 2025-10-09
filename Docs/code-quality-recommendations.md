# Code Quality Recommendations

This document tracks Python best practices improvements for the YouTube downloader project.

**Last Updated:** 2025-10-08 19:15

## Summary

- **Completed:** 14/19 recommendations
- **Remaining:** 5/19 recommendations

---

## Completed ✓ (14/19)

### 1. ✓ Add logging
**Status:** Completed

Implemented centralized logging system in `logger_config.py` with propagation to all modules.

- Created `logger_config.py` with `setup_logging()` function
- All modules now use `logging.getLogger(__name__)`
- Replaced all `print()` statements with appropriate log levels
- Log files stored in `Logs/` directory (excluded from git)
- Console and file handlers with configurable verbosity

### 2. ✓ Add input validation
**Status:** Completed

Implemented `validate_youtube_url()` with retry mechanism and security checks.

- Created `validate_youtube_url()` in `funcs_utils.py`
- Validates URL scheme (http/https only)
- Validates YouTube domains
- Added retry mechanism (MAX_URL_RETRIES=3) for interactive input
- Blocks file:// and other potentially malicious URLs

### 3. ✓ Fix error handling
**Status:** Completed

Fixed all bare `except:` clauses, `check=False` issues, and broad exception handling.

- Fixed bare `except:` in `funcs_utils.py:334` (get_chapter_count)
- Fixed `subprocess.run(check=False)` in `main-yt-dlp.py` (2 locations)
- Fixed broad `except Exception:` in `funcs_process_mp3_tags.py`
- Fixed broad `except Exception:` in `funcs_process_mp4_tags.py` (2 locations)
- Added specific exception types (MutagenError, CalledProcessError, JSONDecodeError)
- All errors now logged with context

### 4. ✓ Replace assertions
**Status:** Completed

Replaced all assertions with proper if/else blocks and logging.

- Replaced `assert Path(yt_dlp_exe).exists()` in `main-yt-dlp.py:163`
- Replaced `raise AssertionError` in `main-yt-dlp.py:169`
- Used `logger.error()` + `sys.exit(1)` pattern
- Code now works correctly with `python -O` optimization flag

### 5. ✓ Extract constants
**Status:** Completed

Created `project_defs.py` with all project-wide constants.

- Created central `project_defs.py` file (no imports, no circular dependencies)
- Moved all magic numbers and strings to constants:
  - `DEFAULT_AUDIO_QUALITY = '192k'`
  - `DEFAULT_AUDIO_FORMAT = 'mp3'`
  - `AUDIO_FORMATS = ('mp3', 'm4a', 'both')`
  - `MAX_URL_RETRIES = 3`
  - `VALID_YOUTUBE_DOMAINS = (...)`
  - `MAX_ALBUM_NAME_LENGTH = 64`
  - `MAX_LOG_FILES = 5`
  - `VIDEO_OUTPUT_DIR = 'yt-videos'`
  - `AUDIO_OUTPUT_DIR = 'yt-audio'`
  - yt-dlp command flags
  - Regex patterns (CHAPTER_FILENAME_PATTERN, etc.)
  - File glob patterns (GLOB_MP3_FILES, GLOB_M4A_FILES, etc.)
- All modules updated to import from `project_defs`
- Tag names defined as constants in respective files (TAG_TITLE, TAG_ARTIST, etc.)

### 6. ✓ Add file validation
**Status:** Completed

Added artists.json existence check with clear error messages.

- Validates `Data/artists.json` exists before processing
- Provides clear error message with expected path
- Exits gracefully with `sys.exit(1)` if missing

### 7. ✓ Implement log rotation
**Status:** Completed

Added log file limit (MAX_LOG_FILES=5) with automatic cleanup.

- Keeps only the 5 most recent log files
- Automatic cleanup before creating new log file
- Sorts by modification time
- Silently ignores deletion errors (locked files, permissions)

### 8. ✓ Function complexity
**Status:** Completed

Refactored `main()` function in main-yt-dlp.py to reduce complexity.

**What was done:**
- Created `funcs_for_main_yt_dlp.py` with extracted helper functions:
  - `validate_and_get_url()` - URL validation with retry mechanism
  - `organize_and_sanitize_files()` - File organization and sanitization
  - `process_audio_tags()` - Audio tag processing for MP3/M4A
- Reduced `main()` from 179 lines to 124 lines
- All internal functions renamed to use underscore prefix (_run_yt_dlp, _extract_audio_with_ytdlp)
- Improved testability and code organization

### 9. ✓ Type hint inconsistency
**Status:** Completed

Standardized all type hints to Python 3.10+ syntax throughout the codebase.

**Updated files:**
- `funcs_process_audio_tags_common.py` - Changed `Tuple` → `tuple`
- `funcs_utils.py` - Changed `Dict[str, Any]` → `dict[str, any]`
- `funcs_chapter_extraction.py` - Changed `List`, `Dict`, `Optional` → `list`, `dict`, `|None`
- `funcs_artist_search.py` - Changed `List`, `Dict`, `Tuple`, `Set` → `list`, `dict`, `tuple`, `set`
- `main-get-artists-from-trello.py` - Removed all typing imports, used built-in types

**Result:** Removed all `from typing import` statements from main codebase (Beta files excluded per project instructions).

### 10. ✓ Magic strings
**Status:** Completed

Extracted all magic strings (regex patterns and file globs) to constants in `project_defs.py`.

**Added constants:**
- `CHAPTER_FILENAME_PATTERN` - Pattern for chapter filenames
- `LEADING_NONALNUM_PATTERN` - Remove leading non-alphanumeric chars
- `MULTIPLE_SPACES_PATTERN` - Match multiple whitespace
- `CHAPTER_TIMESTAMP_PATTERNS` - Tuple of 3 chapter timestamp patterns
- `SAFE_FILENAME_PATTERN` - Remove invalid filename chars
- `WHITESPACE_TO_UNDERSCORE_PATTERN` - Convert whitespace to underscores
- `GLOB_MP3_FILES`, `GLOB_M4A_FILES`, `GLOB_MP4_FILES` - File glob patterns
- `GLOB_MP3_FILES_UPPER`, `GLOB_M4A_FILES_UPPER` - Uppercase variants
- `GLOB_LOG_FILES` - Log file pattern

**Updated files:**
- `funcs_process_audio_tags_common.py` - Uses `CHAPTER_FILENAME_PATTERN`
- `funcs_utils.py` - Uses all glob patterns and regex patterns
- `logger_config.py` - Uses `GLOB_LOG_FILES`
- `funcs_chapter_extraction.py` - Uses chapter timestamp and filename patterns
- `funcs_process_mp3_tags.py` - Uses `GLOB_MP3_FILES` and local tag constants
- `funcs_process_mp4_tags.py` - Uses `GLOB_M4A_FILES` and local tag constants

### 11. ✓ Error messages
**Status:** Completed

Enhanced all error messages with relevant context (URLs, filenames, folder paths).

**Updated files:**
- `main-yt-dlp.py` - Added URL context to download errors, fixed hardcoded path in error message
- `funcs_utils.py` - Added URL context to video info and chapter count errors
- `funcs_process_mp3_tags.py` - Added filename and folder path to all error messages
- `funcs_process_mp4_tags.py` - Added filename and folder path to all error messages

**Quoting convention:** All error messages with embedded values use double quotes for outer string and single quotes for inner values (per project requirements).

### 12. ✓ Type coverage
**Status:** Completed

Added missing type hints to all functions across the codebase.

**Updated files:**
- `funcs_audio_conversion.py` - Added type hints to all functions:
  - `_get_ffmpeg_tool_path(tool_name: str) -> str`
  - `get_ffmpeg_path() -> str`
  - `get_ffprobe_path() -> str`
  - `convert_mp3_to_m4a(mp3_file: Path | str, m4a_file: Path | str | None = None) -> Path | None`
  - `convert_m4a_to_mp3(m4a_file: Path | str, mp3_file: Path | str | None = None) -> Path | None`
- `main-staging.py` - Added type hints to all functions:
  - `normalize_year(year_str: str | int | None) -> str`
  - `extract_mp3_tags(file_path: Path) -> dict[str, str] | None`
  - `extract_m4a_tags(file_path: Path) -> dict[str, str] | None`
  - `apply_mp3_tags(file_path: Path, tags: dict[str, str]) -> bool`
  - `apply_m4a_tags(file_path: Path, tags: dict[str, str]) -> bool`
  - `main() -> int` (changed to return exit code: 0 for success, 1 for errors)
- `main-yt-dlp.py` - Fixed type hints:
  - `_extract_single_format()` - Changed `artist_pat: str = None` to `artist_pat: str | None = None`
  - `_extract_single_format()` - Changed `album_artist_pat: str = None` to `album_artist_pat: str | None = None`
- `funcs_process_mp3_tags.py` - Fixed type hints:
  - `set_tags_in_chapter_mp3_files()` - Changed `uploader: str = None` to `uploader: str | None = None`
  - `set_tags_in_chapter_mp3_files()` - Changed `video_title: str = None` to `video_title: str | None = None`
- `funcs_process_mp4_tags.py` - Fixed type hints:
  - `set_tags_in_chapter_m4a_files()` - Changed `uploader: str = None` to `uploader: str | None = None`
  - `set_tags_in_chapter_m4a_files()` - Changed `video_title: str = None` to `video_title: str | None = None`

**Result:** All main functions now have complete type hints using Python 3.10+ syntax (no typing module required).

### 13. ✓ Subprocess security
**Status:** Completed

Enhanced subprocess security with defense-in-depth measures: URL sanitization, path validation, and timeouts.

**Security measures implemented:**
1. **URL Sanitization** - Created `sanitize_url_for_subprocess()` to validate URLs don't contain shell metacharacters
2. **Path Validation** - Created `validate_file_path_security()` to prevent path traversal attacks
3. **Timeouts** - Added timeouts to all subprocess calls to prevent hanging
4. **Constants Added** - `SUBPROCESS_TIMEOUT_SECONDS = 300` (5 min) and `FFMPEG_TIMEOUT_SECONDS = 600` (10 min)

**Updated files:**
- `project_defs.py` - Added timeout constants
- `funcs_utils.py` - Added security helper functions:
  - `sanitize_url_for_subprocess(url: str) -> str` - Validates URL safety
  - `validate_file_path_security(file_path: Path, expected_parent: Path | None = None) -> None`
- `funcs_utils.py` - Updated subprocess calls:
  - `get_video_info()` - Added URL sanitization and timeout
  - `get_chapter_count()` - Added URL sanitization and timeout
- `main-yt-dlp.py` - Updated subprocess calls:
  - `_run_yt_dlp()` - Added URL sanitization and timeout
  - `_extract_single_format()` - Added URL sanitization and timeout
- `funcs_audio_conversion.py` - Updated subprocess calls:
  - `convert_mp3_to_m4a()` - Added timeout handling
  - `convert_m4a_to_mp3()` - Added timeout handling

**Security principles applied:**
- Defense in depth: Multiple layers of validation even though using list format (not shell=True)
- All subprocess calls already used list format ✓ (verified no shell=True usage)
- Added timeout handling with appropriate error messages
- Validates URLs don't contain shell metacharacters (|, ;, $, `, newlines, <, >)
- Ampersand (&) intentionally allowed - safe with list format and common in YouTube URLs
- Path validation prevents directory traversal attacks

**Test coverage:**
- Created comprehensive test suite in `Tests/test_security_measures.py`
- 19 tests covering URL sanitization, path validation, and cross-platform compatibility
- Tests verify security measures work correctly on both Windows and Linux
- All tests passing ✓

**Result:** All subprocess calls now have comprehensive security measures with timeouts, input validation, and full test coverage.

### 14. ✓ Code duplication
**Status:** Completed

Eliminated ~173 lines of duplicated code between MP3 and M4A processing using strategy pattern.

**Problem:** MP3 and M4A tag processing modules contained 95% identical code with only format-specific differences.

**Solution:** Implemented strategy pattern with handler classes:
- Created `AudioTagHandler` abstract base class
- Implemented `MP3TagHandler` for EasyID3 operations
- Implemented `M4ATagHandler` for MP4 operations
- Created unified processing functions that work with any handler

**Files created:**
- `funcs_audio_tag_handlers.py` - Handler base class and implementations (197 lines)
- `funcs_process_audio_tags_unified.py` - Unified processing logic (164 lines)
- `Tests/test_audio_tag_handlers.py` - Handler tests (all passing)

**Files refactored:**
- `funcs_process_mp3_tags.py` - Reduced from 126 to 53 lines (-73 lines, -58%)
- `funcs_process_mp4_tags.py` - Reduced from 154 to 54 lines (-100 lines, -65%)

**Benefits:**
- Eliminated ~173 lines of duplicated code
- Single source of truth for audio tag processing logic
- Adding new formats now trivial (just create new handler)
- Zero breaking changes - existing API preserved
- Better testability - handlers can be tested independently
- Bug fixes now apply to all formats automatically

**Architecture:**
```
AudioTagHandler (abstract)
├── MP3TagHandler (EasyID3-specific)
└── M4ATagHandler (MP4-specific)

Unified functions:
- set_artists_in_audio_files(folder, artists_json, handler)
- set_tags_in_chapter_audio_files(folder, handler, uploader, video_title)

Public API (unchanged):
- set_artists_in_mp3_files() → calls unified function with MP3Handler
- set_tags_in_chapter_mp3_files() → calls unified function with MP3Handler
- set_artists_in_m4a_files() → calls unified function with M4AHandler
- set_tags_in_chapter_m4a_files() → calls unified function with M4AHandler
```

**Result:** Code duplication eliminated, maintainability improved, no breaking changes to existing callers.

---

## Remaining (5/19)

### Medium Priority

#### 15. Hardcoded paths
**Status:** Not started

**Issue:** Executable paths are hardcoded in main-yt-dlp.py.

**Current:**
```python
yt_dlp_exe = Path.home() / 'Apps' / 'yt-dlp' / 'yt-dlp.exe'
ffmpeg_exe = Path.home() / 'Apps' / 'yt-dlp' / 'ffmpeg.exe'
```

**Suggested solution:**
- Use environment variables with fallback defaults
- Example: `os.getenv('YT_DLP_PATH', default_path)`
- Document required environment variables in README

#### 16. Missing unit tests
**Status:** Not started

**Issue:** Only manual test scripts in `Tests/` directory; no automated test framework.

**Suggested implementation:**
- Add `pytest` to requirements.txt
- Create `tests/` directory with proper test structure
- Add unit tests for:
  - URL validation
  - String sanitization functions
  - Greek text processing
  - Chapter extraction regex
  - Artist name matching
- Add integration tests for end-to-end workflows
- Set up CI/CD with test coverage reporting

### Lower Priority

#### 17. Documentation
**Status:** Not started

**Issue:** Missing or incomplete module-level docstrings.

**Files with good docstrings:**
- `logger_config.py` ✓
- `project_defs.py` ✓
- `funcs_process_audio_tags_common.py` ✓
- `funcs_for_main_yt_dlp.py` ✓

**Files needing improvement:**
- `main-yt-dlp.py` - could explain overall workflow
- `funcs_artist_search.py` - could explain algorithm
- Test files - could explain what they test

#### 18. Function cohesion
**Status:** Not started

**Issue:** `funcs_utils.py` contains unrelated utilities (low cohesion).

**Current contents:**
- Greek text processing
- File operations
- URL validation
- Video information retrieval

**Suggested refactoring:**
- `file_utils.py` - organize_media_files, sanitize_filenames_in_folder
- `url_utils.py` - validate_youtube_url, get_video_info, is_playlist
- `text_utils.py` - sanitize_string, remove_diacritics, greek_search

#### 19. Configuration management
**Status:** Not started

**Issue:** Audio quality and formats are constants but could be user-configurable.

**Current:** Hardcoded in `project_defs.py`

**Suggested enhancement:**
- Add optional config file support (YAML/JSON)
- Allow CLI overrides for quality settings
- Example: `--audio-quality 320k` or config file with defaults
- Keep current constants as fallback defaults

---

## Notes

- This document should be updated as recommendations are implemented
- Priority levels are suggestions and can be adjusted based on project needs
- Some recommendations may be split into multiple tasks during implementation
- **Session-specific changes have been moved to [CHANGELOG.md](CHANGELOG.md)**
