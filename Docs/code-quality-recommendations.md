# Code Quality Recommendations

This document tracks Python best practices improvements for the YouTube downloader project.

**Last Updated:** 2025-10-08

## Summary

- **Completed:** 11/19 recommendations
- **Remaining:** 8/19 recommendations

---

## Completed ✓ (11/19)

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

---

## Remaining (8/19)

### High Priority

#### 12. Code duplication
**Status:** Not started

**Issue:** Similar code patterns in MP3/M4A processing modules (95% identical).

**Duplicated functions:**
- `set_artists_in_mp3_files()` vs `set_artists_in_m4a_files()`
- `set_tags_in_chapter_mp3_files()` vs `set_tags_in_chapter_m4a_files()`

**Suggested solution:**
- Create generic `set_artists_in_audio_files(audio_format)` function
- Create generic `set_tags_in_chapter_audio_files(audio_format)` function
- Use polymorphism or strategy pattern for format-specific operations
- Tag constants already defined locally (TAG_TITLE, TAG_ARTIST, etc.)

**Note:** Tag name constants are now defined in each file, making unification easier.

### Medium Priority

#### 13. Hardcoded paths
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

#### 14. Missing unit tests
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

#### 15. Subprocess security
**Status:** Not started

**Issue:** Some subprocess calls could be more secure.

**Current practice:** Most calls already use list format ✓

**Review needed:**
- Ensure all subprocess.run() calls use list format (not shell=True)
- Validate any user input that goes into subprocess calls
- Consider using shlex.quote() for any dynamic values

### Lower Priority

#### 16. Documentation
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

#### 17. Type coverage
**Status:** Not started

**Issue:** Not all functions have complete type hints.

**Examples:**
- Some return types missing in utility functions
- Some parameter types missing
- Consider using mypy for type checking

**Suggested approach:**
- Add `mypy` to requirements.txt
- Run `mypy --strict` and fix issues incrementally
- Add type hints to all public functions

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

## Recent Session Accomplishments (2025-10-08)

In this session, we completed recommendations #8, #10, #13, and #14:

1. **Function complexity (#8)** - Refactored main() by creating funcs_for_main_yt_dlp.py with helper functions
2. **Type hint inconsistency (#10)** - Standardized to Python 3.10+ syntax across all files
3. **Magic strings (#13)** - Extracted all regex patterns and file globs to constants
4. **Error messages (#14)** - Enhanced all error messages with relevant context

Additional improvements:
- Moved local functions before global functions in logger_config.py
- Fixed hardcoded path in error message (line 200 of main-yt-dlp.py)
- Added VIDEO_OUTPUT_DIR and AUDIO_OUTPUT_DIR constants for easy configuration
- Replaced all hardcoded '*.mp3', '*.m4a' strings with GLOB constants
- Added tag name constants to funcs_process_mp3_tags.py (TAG_TITLE, TAG_ARTIST, etc.)
- Added tag name constants to funcs_process_mp4_tags.py (TAG_TITLE, TAG_ARTIST, etc.)
