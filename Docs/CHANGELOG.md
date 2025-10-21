# CHANGELOG

This document tracks feature enhancements and major changes to the YouTube downloader project.

---

## 2025-10-21 16:19:50

**Bug Fix:** Removed `--force-keyframes-at-cuts` flag causing video corruption

**Problem:** Video chapter files were experiencing corruption issues:
- Incorrect durations displayed in video players (VLC)
- Timeline seeking caused video to disappear or freeze
- Playback issues due to re-encoding at chapter boundaries

**Root Cause:** The `--force-keyframes-at-cuts` flag added in version 2025-10-21 14:50:42 forces ffmpeg to re-encode video at chapter cut points, which:
- Is slow and CPU-intensive
- Can cause audio/video sync issues
- Creates corrupted frames at boundaries
- Results in malformed MP4 files

**Solution:** Removed `--force-keyframes-at-cuts` flag from video chapter splitting command. yt-dlp now uses the default behavior of cutting at the nearest natural keyframe without re-encoding.

**Changes made:**

1. **`main-yt-dlp.py`**:
   - Removed `--force-keyframes-at-cuts` from `_run_yt_dlp()` when splitting chapters
   - Video chapters now split cleanly using stream copy (no re-encoding)

2. **`funcs_utils.py`**:
   - Updated warning message in `display_chapters_and_confirm()` to explain that:
     - Videos are cut at nearest keyframe for clean, fast splits
     - Video durations may be slightly longer than metadata shows
     - Audio chapters match exact times

**Trade-offs:**

**Before (with --force-keyframes-at-cuts):**
- ✗ Slow processing (requires re-encoding)
- ✗ Corrupted video files
- ✗ VLC playback issues
- ✓ Exact chapter boundaries (in theory)

**After (without flag, default behavior):**
- ✓ Fast processing (stream copy, no re-encoding)
- ✓ Clean, playable video files
- ✓ Perfect VLC playback
- ✓ Slightly longer durations (extends to next keyframe, typically 2-10 seconds)

**Result:** Video chapter files are now clean, playable, and seekable in all players. The slight duration imprecision (extending to next keyframe) is a worthwhile trade-off for stable, corruption-free video files. Audio chapters continue to have exact timing since audio doesn't have keyframe constraints.

---

## 2025-10-21 14:50:42

**Feature Enhancement:** Chapter display and confirmation prompt

**Summary:** When using `--split-chapters`, the tool now displays a formatted chapter list with timing information and prompts for user confirmation before downloading.

**Changes made:**

1. **`funcs_utils.py`**:
   - Added `_format_duration()` helper function to convert seconds to HH:MM:SS or MM:SS format
   - Added `display_chapters_and_confirm()` function that:
     - Displays formatted table with chapter numbers, names, start/end times, and durations
     - Shows warning about video chapter duration differences due to keyframe alignment
     - Prompts user to continue (y/n) or abort download
     - Returns boolean indicating user's choice

2. **`main-yt-dlp.py`**:
   - Added `display_chapters_and_confirm` to imports
   - Integrated chapter confirmation prompt before download when `--split-chapters` is used
   - Exits cleanly (status 0) if user chooses to abort

3. **`README.md`**:
   - Updated `--split-chapters` description to mention chapter display and confirmation
   - Updated usage examples

4. **`Tests/test_chapter_display.py`** (NEW):
   - Created test suite for chapter display functionality
   - Tests duration formatting and chapter display with mock data

**Result:** Users can now review the complete chapter list with timing information before committing to a download. This helps verify chapter structure and avoid unwanted downloads.

---

## 2025-10-21 14:50:00

**Parameter Rename:** `--other-sites-timeout` → `--video-download-timeout` with enhanced functionality

**Summary:** Renamed timeout parameter and changed behavior to apply custom timeout to all sites when specified, not just non-YouTube/Facebook sites.

**Changes made:**

1. **`funcs_utils.py`**:
   - Renamed parameter in `get_timeout_for_url()` from `other_sites_timeout` to `video_download_timeout`
   - Changed logic: when `video_download_timeout` is specified, it now applies to ALL sites uniformly
   - Updated documentation to clarify new behavior

2. **`main-yt-dlp.py`**:
   - Renamed `--other-sites-timeout` to `--video-download-timeout`
   - Removed default value (was 3600)
   - Updated help text to explain new behavior:
     - When specified: applies to all sites (YouTube, Facebook, and others)
     - When not specified: uses domain-specific defaults (300s for YouTube/Facebook, 3600s for others)
   - Updated all function signatures and calls:
     - `_run_yt_dlp()`
     - `_extract_single_format()`
     - `_extract_audio_with_ytdlp()`

3. **`README.md`**:
   - Updated usage syntax and parameter descriptions
   - Rewrote Performance & Timeout section with clear explanation of behavior
   - Added new usage examples showing custom timeout for different scenarios

4. **`Tests/test_timeout_parameter.py`** (NEW):
   - Created comprehensive test suite (7 tests)
   - Tests default timeouts for YouTube, Facebook, and other sites
   - Tests custom timeout override for all sites
   - All tests passing

**Behavioral Changes:**

**Before:**
- `--other-sites-timeout 1200` would set 1200s timeout only for non-YouTube/Facebook sites
- YouTube/Facebook always used 300s regardless of parameter

**After:**
- `--video-download-timeout 1200` sets 1200s timeout for ALL sites (YouTube, Facebook, others)
- Without parameter: uses smart defaults (300s for YouTube/Facebook, 3600s for others)

**Result:** More intuitive and flexible timeout control. Users can now override timeouts for YouTube/Facebook if needed (e.g., slow connections), while still benefiting from sensible defaults when the parameter is omitted.

---

## 2025-10-19 12:00:00

**Code Quality:** Standardized function calls to use named parameters

**Summary:** Updated all function calls to local project functions to use named parameters, improving code readability and maintainability.

**Changes made:**

All Python files in the project (excluding Tests/ and Beta/ directories) were updated to ensure function calls with type-hinted parameters use named arguments:

1. **`funcs_artist_search.py`**:
   - Updated `remove_diacritics()` calls to use `text=` parameter

2. **`funcs_process_audio_tags_common.py`**:
   - Updated `_remove_emojis()` calls to use `text=` parameter
   - Updated `_sanitize_filename()` calls to use `filename=` parameter
   - Updated `re.match()` calls to use `pattern=` and `string=` parameters

3. **`main-get-artists-from-trello.py`**:
   - Updated `capitalize_greek_name()` calls to use `name=` parameter
   - Updated `parse_card_name()` calls to use `card_name=` parameter
   - Updated `extract_artists()` calls to use `trello_data=` parameter

4. **`funcs_chapter_extraction.py`**:
   - Updated `get_video_info()` calls to use `yt_dlp_path=` and `url=` parameters
   - Updated `_extract_chapters_from_description()` calls to use `description=` parameter
   - Updated `_parse_time_to_seconds()` calls to use `time_str=` parameter

5. **`funcs_process_mp3_tags.py`**, **`funcs_process_mp4_tags.py`**, **`funcs_process_flac_tags.py`**:
   - Updated `set_artists_in_audio_files()` calls to use all named parameters
   - Updated `set_tags_in_chapter_audio_files()` calls to use all named parameters

6. **`funcs_process_audio_tags_unified.py`**:
   - Updated all `AudioTagHandler` method calls to use named parameters:
     - `open_audio_file(file_path=...)`
     - `get_tag(audio=..., tag_name=...)`
     - `set_tag(audio=..., tag_name=..., value=...)`
     - `handle_format_specific_tasks(audio=...)`
     - `has_track_number(audio=...)`
     - `clear_track_number(audio=...)`
     - `set_track_number(audio=..., track_number=...)`
     - `set_original_filename(audio=..., file_path=..., original_filename=...)`
     - `save_audio_file(audio=..., file_path=...)`
   - Updated helper function calls:
     - `find_artists_in_string(text=..., artists=...)`
     - `sanitize_album_name(title=...)`
     - `extract_chapter_info(file_name=...)`

7. **`main-yt-dlp.py`**:
   - Updated `sanitize_url_for_subprocess()` calls to use `url=` parameter
   - Updated `get_timeout_for_url()` calls to use `url=` parameter
   - Updated `validate_and_get_url()` calls to use `provided_url=` parameter

8. **`main-convert.py`**:
   - Updated `arrow.get()` calls to use `obj=` and `arg=` parameters
   - Updated `normalize_year()` calls to use `year_str=` parameter
   - Updated `extract_mp3_tags()` and `extract_m4a_tags()` calls to use `file_path=` parameter
   - Updated `apply_mp3_tags()` and `apply_m4a_tags()` calls to use `file_path=` and `tags=` parameters
   - Updated `convert_mp3_to_m4a()` and `convert_m4a_to_mp3()` calls to use named parameters

9. **`funcs_utils.py`**:
   - Updated `sanitize_url_for_subprocess()` calls to use `url=` parameter
   - Updated `get_timeout_for_url()` calls to use `url=` parameter
   - Updated `urlparse()` calls to use `url=` parameter

10. **`funcs_for_main_yt_dlp.py`**:
    - Updated `validate_video_url()` calls to use `url=` parameter

**Result:** All function calls now explicitly name their parameters, making the code more self-documenting and reducing the chance of parameter order errors. This aligns with the project's coding standards specified in CLAUDE.md requiring named parameters for functions with type hints.

---

## 2025-10-16

**Feature Enhancement:** Implemented URL-based timeout configuration for yt-dlp operations

**Summary:** Added dynamic timeout selection based on URL domain to accommodate slower video streaming sites while maintaining reasonable timeouts for YouTube.

**Changes made:**

1. **`project_defs.py`**:
   - Split `VALID_YOUTUBE_DOMAINS` into two separate constants:
     - `VALID_YOUTUBE_DOMAINS` - YouTube domains only (youtube.com, www.youtube.com, m.youtube.com, youtu.be)
     - `VALID_OTHER_DOMAINS` - Other supported sites (www.ertflix.gr, ertflix.gr)
   - Replaced single `SUBPROCESS_TIMEOUT_SECONDS` constant with two:
     - `SUBPROCESS_TIMEOUT_YOUTUBE = 300` (5 minutes for YouTube)
     - `SUBPROCESS_TIMEOUT_OTHER_SITES = 3600` (1 hour for slower sites)

2. **`funcs_utils.py`**:
   - Added `get_timeout_for_url()` function that determines appropriate timeout based on URL domain
     - Returns 300 seconds for YouTube URLs
     - Returns 3600 seconds for other supported sites
     - Defaults to 300 seconds for unknown domains
   - Renamed `validate_youtube_url()` to `validate_video_url()` and updated it to accept both YouTube and other supported video sites
   - Updated `get_video_info()` to use `get_timeout_for_url()` for dynamic timeout
   - Updated `get_chapter_count()` to use `get_timeout_for_url()` for dynamic timeout

3. **`funcs_for_main_yt_dlp.py`**:
   - Updated imports and function calls to use `validate_video_url` instead of `validate_youtube_url`

4. **`main-yt-dlp.py`**:
   - Updated `_run_yt_dlp()` to use dynamic timeout via `get_timeout_for_url()`
   - Updated `_extract_single_format()` to use dynamic timeout via `get_timeout_for_url()`
   - Updated imports to include `get_timeout_for_url` and removed `SUBPROCESS_TIMEOUT_SECONDS`

**Result:** YouTube downloads timeout after 5 minutes while other sites like ertflix.gr have 1 hour before timeout. This accommodates slow streaming sites while preventing excessive waits for fast sites. The timeout is automatically selected based on the URL domain.

---

## 2025-10-09 18:45:00

**Feature Enhancement:** Store video URL in MP4 video metadata

**Summary:** Added URL embedding in video file metadata for consistency with audio files.

**Changes made:**
- **`main-yt-dlp.py`**: Updated `_run_yt_dlp()` function to embed YouTube URL in video metadata
  - Added `--embed-metadata` and `--add-metadata` flags
  - Added `--parse-metadata 'webpage_url:%(meta_comment)s'` to store URL in comment field

**Result:** Downloaded MP4 video files now contain the source YouTube URL in their metadata comment field, making it easy to identify the source of any video file. This matches the behavior of audio files where the URL is stored in the COMMENT tag.

---

## 2025-10-09 17:25:00

**Feature Enhancement:** Added FLAC audio format support

**Summary:** Implemented complete FLAC support with full feature parity to MP3 and M4A formats.

**Core Features:**
1. **Multi-format support** with comma-separated selection (`--audio-format mp3,m4a,flac`)
2. **FLACTagHandler** class using Vorbis Comments tagging system
3. **Best audio quality** (quality=0) for lossless encoding
4. **Format-specific subdirectories** (`yt-audio/flac/`)

**Tag Processing:**
- **TITLE**: Video title or chapter name
- **ARTIST/ALBUMARTIST**: Greek artist detection or uploader
- **ALBUM**: Playlist or video title
- **DATE**: Auto-converts YYYYMMDD → YYYY
- **COMMENT**: Copies from PURL field (video URL)
- **ENCODEDBY**: Original filename (without extension)
- **TRACKNUMBER**: Track numbers for chapter files

**Special Features:**
- Date format normalization (YYYYMMDD → YYYY)
- PURL → COMMENT copying for consistency with MP3/M4A
- Original filename storage in ENCODEDBY tag
- Greek text handling and artist detection
- Chapter file processing

**Changes made:**
1. **`project_defs.py`**:
   - Changed `AUDIO_FORMATS` tuple to `VALID_AUDIO_FORMATS` set
   - Added `'flac'` to valid formats
   - Added FLAC glob patterns (`GLOB_FLAC_FILES`, `GLOB_FLAC_FILES_UPPER`)
   - Updated `CHAPTER_FILENAME_PATTERN` regex to include `.flac` extension

2. **`funcs_audio_tag_handlers.py`**:
   - Created `FLACTagHandler` class with Vorbis Comments support
   - Implemented `handle_format_specific_tasks()` for date format fixing and PURL→COMMENT copying
   - Added `set_original_filename()` to store original filename in ENCODEDBY tag
   - Removed unused `TAG_GENRE` constant

3. **`funcs_process_flac_tags.py`** (NEW):
   - Created wrapper functions for FLAC processing
   - `set_artists_in_flac_files()` - Artist detection and tagging
   - `set_tags_in_chapter_flac_files()` - Chapter file processing

4. **`main-yt-dlp.py`**:
   - Changed `--audio-format` to accept comma-separated values
   - Updated `_extract_single_format()` to use quality '0' for FLAC (best/lossless)
   - Added format validation and duplicate removal

5. **`funcs_for_main_yt_dlp.py`**:
   - Updated `organize_and_sanitize_files()` to handle list of formats
   - Updated return value to include FLAC original names mapping
   - Updated `process_audio_tags()` to loop through formats and process FLAC files

6. **`funcs_utils.py`**:
   - Updated `organize_media_files()` to handle FLAC files
   - Added FLAC file moving and organization logic

**Documentation:**
- Updated `README.md` with FLAC format examples and audio format selection guide
- Updated `Docs/Configuring mp3tag to display yt-dlp generated audio files.md` with FLAC tag mapping
- Updated `CLAUDE.md` with FLACTagHandler details and FLAC support information

**Result:** FLAC files now have full feature parity with MP3 and M4A formats, including Greek artist detection, chapter processing, original filename tracking, and proper metadata handling. FLAC provides lossless audio quality while maintaining complete compatibility with the existing processing pipeline.

---

## 2025-10-08 19:15

**Feature Enhancement:** Implemented original filename tracking from yt-dlp

**Problem:** The TENC (MP3) and lyrics (M4A) tags were saving the sanitized/renamed filenames instead of the original filenames from yt-dlp.

**Solution:** Implemented filename tracking through the entire processing pipeline:

**Changes made:**
1. **`funcs_utils.py`**:
   - Updated `organize_media_files()` to return mapping of `final_path -> original_filename`
   - Updated `sanitize_filenames_in_folder()` to accept and update filename mappings through renames

2. **`funcs_for_main_yt_dlp.py`**:
   - Updated `organize_and_sanitize_files()` to collect and return filename mappings
   - Updated `process_audio_tags()` to accept and pass through `original_names` parameter

3. **`main-yt-dlp.py`**:
   - Wired pipeline to capture filename mappings and pass to tag processing

4. **`funcs_process_mp3_tags.py` and `funcs_process_mp4_tags.py`**:
   - Added `original_names` parameter to all wrapper functions

5. **`funcs_process_audio_tags_unified.py`**:
   - Updated unified functions to accept and use `original_names` mapping
   - Modified to look up original filename and pass to handlers

6. **`funcs_audio_tag_handlers.py`**:
   - Updated `set_original_filename()` abstract method to accept `original_filename` parameter
   - Updated `MP3TagHandler.set_original_filename()` to save original filename in TENC tag (without .mp3 extension)
   - Updated `M4ATagHandler.set_original_filename()` to save original filename in lyrics tag

**How it works:**
1. yt-dlp downloads files with original filenames based on `%(title)s.%(ext)s`
2. `organize_media_files()` captures original names before moving to subfolders
3. `sanitize_filenames_in_folder()` tracks renames and updates the mapping
4. Tag processing functions use the mapping to retrieve each file's original yt-dlp filename
5. Original filename (without extension for MP3) is saved in TENC/lyrics tags

**Result:** TENC and lyrics tags now correctly store the original yt-dlp filename before any sanitization or renaming. All changes are backward-compatible with optional parameters.

---

## 2025-10-08 18:59

**Code Quality:** Completed recommendation #14 (Code duplication)

**Accomplishment:** Eliminated code duplication between MP3 and M4A processing modules using strategy pattern.

**Changes made:**
- Created `funcs_audio_tag_handlers.py` with `AudioTagHandler` abstract base class
- Implemented `MP3TagHandler` and `M4ATagHandler` concrete implementations
- Created `funcs_process_audio_tags_unified.py` with unified processing functions
- Refactored `funcs_process_mp3_tags.py` - reduced from 126 to 53 lines (-58%)
- Refactored `funcs_process_mp4_tags.py` - reduced from 154 to 54 lines (-65%)
- Created `Tests/test_audio_tag_handlers.py` - all tests passing
- Total code reduction: ~173 lines of duplicated code eliminated

**Impact:**
- Single source of truth for audio tag processing logic
- Zero breaking changes - existing API preserved
- Adding new audio formats now trivial
- Better testability and maintainability

---

## 2025-10-08 18:31

**Code Quality:** Completed security test suite for recommendation #13

**Changes made:**
- Created comprehensive test suite `Tests/test_security_measures.py` (19 tests)
- Removed ampersand (&) from blocked characters (safe with subprocess list format)
- Updated `funcs_utils.py` to document why & is allowed
- Added pytest to requirements.txt
- All tests passing on Linux (cross-platform compatible)

---

## 2025-10-08 18:18

**Code Quality:** Completed recommendations #8, #9, #10, #11, #12, and #13

In this session, we completed multiple code quality improvements:

1. **Function complexity (#8)** - Refactored main() by creating funcs_for_main_yt_dlp.py with helper functions
2. **Type hint inconsistency (#9)** - Standardized to Python 3.10+ syntax across all files
3. **Magic strings (#10)** - Extracted all regex patterns and file globs to constants
4. **Error messages (#11)** - Enhanced all error messages with relevant context
5. **Type coverage (#12)** - Added missing type hints to all functions across the codebase
6. **Subprocess security (#13)** - Added URL sanitization, path validation, and timeouts to all subprocess calls

**Additional improvements:**
- Moved local functions before global functions in logger_config.py
- Fixed hardcoded path in error message (line 200 of main-yt-dlp.py)
- Added VIDEO_OUTPUT_DIR and AUDIO_OUTPUT_DIR constants for easy configuration
- Replaced all hardcoded '*.mp3', '*.m4a' strings with GLOB constants
- Added tag name constants to funcs_process_mp3_tags.py (TAG_TITLE, TAG_ARTIST, etc.)
- Added tag name constants to funcs_process_mp4_tags.py (TAG_TITLE, TAG_ARTIST, etc.)
- Changed main() in main-staging.py to return int (0 for success, 1 for errors) instead of None
- Created comprehensive security test suite with 19 tests (all passing)
- Added pytest to requirements.txt
- Ampersand (&) intentionally allowed in URLs (safe with subprocess list format, common in YouTube URLs)
