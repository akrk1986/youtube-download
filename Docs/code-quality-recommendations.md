# Code Quality Recommendations

This document tracks Python best practices improvements for the YouTube downloader project.

**Last Updated:** 2025-10-08

## Summary

- **Completed:** 7/19 recommendations
- **Remaining:** 12/19 recommendations

---

## Completed ✓ (7/19)

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
  - yt-dlp command flags
- All modules updated to import from `project_defs`

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

---

## Remaining (12/19)

### High Priority

#### 8. Function complexity
**Status:** Not started

**Issue:** `main()` in main-yt-dlp.py is 179 lines; violates single responsibility principle.

**Suggested refactoring:**
- Extract URL validation logic into `validate_and_get_url()`
- Extract video download logic into `download_video()`
- Extract audio processing logic into `process_audio_files()`
- Extract file organization logic into `organize_output_files()`

**Benefits:**
- Improved testability
- Better code reusability
- Easier to understand control flow

#### 9. Code duplication
**Status:** Not started

**Issue:** Similar code patterns in MP3/M4A processing modules (95% identical).

**Duplicated functions:**
- `set_artists_in_mp3_files()` vs `set_artists_in_m4a_files()`
- `set_tags_in_chapter_mp3_files()` vs `set_tags_in_chapter_m4a_files()`

**Suggested solution:**
- Create generic `set_artists_in_audio_files(audio_format)` function
- Create generic `set_tags_in_chapter_audio_files(audio_format)` function
- Use polymorphism or strategy pattern for format-specific operations
- Keep format-specific tag key mappings in `project_defs.py`

#### 10. Type hint inconsistency
**Status:** Not started

**Issue:** Mix of `tuple[str, str]` (Python 3.10+) and `Tuple[str, str]` (typing module).

**Files affected:**
- `funcs_process_audio_tags_common.py` uses `Tuple` from typing
- `funcs_utils.py` uses built-in `tuple`

**Suggested fix:**
- Standardize to Python 3.10+ syntax (`tuple`, `list`, `dict`) throughout
- Remove `from typing import Tuple` imports
- Update all type hints consistently

### Medium Priority

#### 11. Hardcoded paths
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

#### 12. Missing unit tests
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

#### 13. Magic strings
**Status:** Not started

**Issue:** Some format strings and patterns still hardcoded in functions.

**Examples:**
- Regex pattern in `extract_chapter_info()` (line 83)
- File glob patterns like `'*.mp3'`, `'yt-dlp_*.log'`

**Suggested fix:**
- Move regex patterns to `project_defs.py`:
  ```python
  CHAPTER_FILENAME_PATTERN = r'^(.*?)\s*-\s*(\d{3})\s+(.*?)\s*\[([^\s\[\]]+)\]\.(?:mp3|m4a|MP3|M4A)$'
  LOG_FILE_PATTERN = 'yt-dlp_*.log'
  ```

#### 14. Error messages
**Status:** Not started

**Issue:** Some error messages lack context (URL, filename, etc.).

**Examples:**
- "Failed to download video" could include URL/video title
- File operation errors could include full path

**Suggested improvement:**
- Include relevant context in all error messages
- Use f-strings consistently: `f"Failed to download '{video_title}' from {url}: {error}"`

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
