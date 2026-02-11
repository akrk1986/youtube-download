# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based YouTube downloader and media processing tool that uses `yt-dlp` for downloading videos/audio and processes metadata with special focus on Greek music. The tool can:

- Download YouTube videos/playlists as MP4 files
- Extract audio as MP3, M4A, and/or FLAC with embedded metadata and thumbnails
- Split videos by chapters automatically
- Process audio tags to identify and set Greek artists
- Handle subtitle downloads in multiple languages (Greek, English, Hebrew)
- Sanitize filenames for multiple languages (English, French, Turkish, Greek, Hebrew)

## Core Architecture

The codebase follows a modular function-based architecture:

### Main Entry Points
- `main-yt-dlp.py` - Primary CLI tool for downloading and processing YouTube content
- `main-get-artists-from-trello.py` - Utility to convert Trello board data to artist JSON

### Core Function Modules and Packages

The codebase uses a modular package-based architecture for better organization:

**Packages (refactored for better modularity):**
- `funcs_utils/` - General utilities package
  - `file_operations.py` - File organization and sanitization
  - `string_sanitization.py` - String/filename sanitization and Greek text handling
  - `yt_dlp_utils.py` - yt-dlp specific utilities (error detection, cookies)
  - `security.py` - Security helpers for subprocess calls
- `funcs_video_info/` - Video information package
  - `url_validation.py` - URL validation and timeout determination
  - `metadata.py` - Video metadata retrieval using yt-dlp
  - `chapters.py` - Chapter detection, display, and CSV generation
- `funcs_for_main_yt_dlp/` - Main script helpers package
  - `external_tools.py` - External tool path detection (ffmpeg, yt-dlp)
  - `url_validation.py` - URL validation and input handling
  - `file_organization.py` - File organization and sanitization
  - `audio_processing.py` - Audio tag processing coordination
  - `utilities.py` - General utilities (time formatting, session ID)
- `funcs_audio_tag_handlers/` - Audio tag handler classes package (strategy pattern)
  - `base.py` - Abstract base class (AudioTagHandler)
  - `mp3_handler.py` - MP3TagHandler with UTF-16 encoding support
  - `m4a_handler.py` - M4ATagHandler for MP4/iTunes metadata
  - `flac_handler.py` - FLACTagHandler for Vorbis Comments

**Standalone Modules:**
- `funcs_yt_dlp_download.py` - yt-dlp download and audio extraction functions
- `funcs_process_mp3_tags.py` - MP3 ID3v2 tag processing and artist detection
- `funcs_process_m4a_tags.py` - M4A MP4/iTunes metadata processing
- `funcs_process_flac_tags.py` - FLAC Vorbis Comments processing
- `funcs_process_audio_tags_common.py` - Common audio tag processing functions
- `funcs_process_audio_tags_unified.py` - Unified audio tag processing across formats
- `funcs_artist_search.py` - Greek artist name matching and search variants
- `funcs_chapter_extraction.py` - Video chapter detection and processing
- `funcs_url_extraction.py` - URL extraction from text and ODF documents
- `funcs_audio_conversion.py` - Audio format conversion utilities
- `funcs_audio_boost.py` - Audio volume boosting utilities
- `funcs_notifications/` - Notification handlers package (Slack, Gmail)

### Data Files
- `Data/artists.json` - Greek music artists database (~17KB)
- `Data/trello - greek-music-artists.json` - Raw Trello export (~1.7MB)

## Key Dependencies

The project requires:
- `yt-dlp` executable
  - **Windows**: Expected at `~/Apps/yt-dlp/yt-dlp.exe`
  - **Linux**: Must be in `$PATH`
- `ffmpeg` executable
  - **Windows**: Expected at `~/Apps/yt-dlp/ffmpeg.exe`
  - **Linux**: Must be in `$PATH`
- Python packages: `mutagen`, `yt-dlp` (imported as module), `arrow`, `emoji`

## Common Commands

### Running the Main Tool
```bash
# Download video only
python main-yt-dlp.py "https://youtube.com/watch?v=..."

# Download with audio extraction (default: MP3)
python main-yt-dlp.py --with-audio "https://youtube.com/playlist?list=..."

# Download with specific audio format (mp3, m4a, or flac)
python main-yt-dlp.py --only-audio --audio-format m4a "URL"

# Download with multiple audio formats (comma-separated)
python main-yt-dlp.py --only-audio --audio-format mp3,m4a,flac "URL"

# Audio only with chapters (delete videos after extraction)
python main-yt-dlp.py --only-audio --split-chapters "https://youtube.com/watch?v=..."

# With subtitles and JSON metadata
python main-yt-dlp.py --with-audio --subs --json "URL"

# With custom title, artist, and album (single videos only)
python main-yt-dlp.py --only-audio --title "Custom Title" --artist "Artist Name" --album "Album" "URL"

# Interactive prompts for metadata (use 'ask' or 'prompt')
python main-yt-dlp.py --only-audio --title ask --artist prompt "URL"

# Verbose logging with URL debugging (WARNING: may expose Slack webhook)
python main-yt-dlp.py --verbose --show-urls --only-audio "URL"
```

### Testing Individual Components
The project has three categories of tests:

**Pytest tests** (in `Tests/` directory):
```bash
pytest Tests/                           # Run all pytest tests (49 tests)
pytest Tests/test_main_ytdlp.py         # Main script tests (30 tests)
pytest Tests/test_security_measures.py  # Security tests (19 tests)
```

**End-to-end tests** (in `Tests/` directory):
```bash
python Tests/e2e_main.py           # Interactive E2E test runner
python Tests/e2e_main.py --resume  # Resume from saved state
```

**Standalone test scripts** (in `Tests-Standalone/` directory):
```bash
python Tests-Standalone/test_chapter_regex.py  # Test chapter extraction regex
python Tests-Standalone/main_greek_search.py   # Test Greek text search functionality
python Tests-Standalone/find-artists-main.py   # Test artist detection in strings
```

### Updating Artist Database
When the Trello board is updated:
```bash
python main-get-artists-from-trello.py
```

## Output Structure

- `yt-videos/` - Downloaded MP4 video files
- `yt-audio/` - Downloaded audio files organized by format:
  - `yt-audio/mp3/` - MP3 files (lossy, ID3v2 tags)
  - `yt-audio/m4a/` - M4A files (lossy, MP4/iTunes atoms)
  - `yt-audio/flac/` - FLAC files (lossless, Vorbis Comments)
- Chapter files are automatically organized into subdirectories when `--split-chapters` is used

## Audio Tagging System

The project uses a strategy pattern for handling different audio formats:

### Tag Handler Classes
- **MP3TagHandler**: Uses `mutagen.id3` for ID3v2 tags
  - Original filename stored in TENC (Encoded by) tag
  - Standard tags: TIT2, TPE1, TALB, TPE2, TDRC, TCON, COMM, APIC

- **M4ATagHandler**: Uses `mutagen.mp4` for MP4/iTunes atoms
  - Original filename stored in ©lyr (Lyrics) tag
  - Standard tags: ©nam, ©ART, ©alb, aART, ©day, trkn, covr
  - Auto-converts YYYYMMDD date format to YYYY

- **FLACTagHandler**: Uses `mutagen.flac` for Vorbis Comments
  - Original filename stored in ENCODEDBY tag
  - Standard tags: TITLE, ARTIST, ALBUM, ALBUMARTIST, DATE, COMMENT, TRACKNUMBER, ENCODEDBY
  - Picture block for album art
  - Auto-converts YYYYMMDD date format to YYYY
  - Copies PURL to COMMENT field for consistency with MP3/M4A

### Processing Pipeline
1. Download audio with yt-dlp (basic metadata embedded)
2. Organize files by format into subdirectories
3. Sanitize filenames for Greek/English/Hebrew text
4. Detect Greek artists from database (~100 artists)
5. Update audio tags with detected artists and original filename
6. For chapter files: Set track numbers and album tags

## Format Fallback System

The download functions implement automatic format fallback to handle videos where preferred formats are unavailable:

### Video Downloads
- Tries formats in sequence: `bestvideo[ext=mp4]+bestaudio[ext=m4a]` → `bestvideo+bestaudio` → `best` → `bv*+ba/b`
- Format errors are suppressed (logged at DEBUG level only)
- Only shows error if ALL format options fail

### Audio Downloads
- Uses `bestaudio/best` with automatic fallback
- Format errors are silently handled

### Key Components
- `is_format_error()` in `funcs_utils/yt_dlp_utils.py` - Detects format-related errors
- `VIDEO_FORMAT_FALLBACKS` in `funcs_yt_dlp_download.py` - List of formats to try
- `_SilentLogger` in `funcs_video_info/metadata.py` - Suppresses yt-dlp library error output
- `--no-warnings` and `--ignore-config` flags added to yt-dlp commands

## Greek Text Processing

The codebase has specialized handling for Greek text:
- Diacritic removal for search matching
- Filename sanitization for Greek, English, Hebrew characters
- Artist name variants generation (supports different name orders and abbreviations)
- Artist database maintained in Trello, exported to `Data/artists.json`

## Development Notes

### Test Organization
The project uses a three-tier testing approach:
- **pytest tests** (`Tests/`): Formal test suite with 49 tests (`test_main_ytdlp.py`, `test_security_measures.py`)
  - Configuration: `pytest.ini` in project root with `testpaths = Tests`
  - Run with: `pytest Tests/`
- **E2E tests** (`Tests/`): Interactive end-to-end testing (`e2e_main.py`, `e2e_config.py`)
  - Files renamed without `test_` prefix to prevent pytest collection
  - Documentation in `Tests/README-E2E-TESTS.md` and `Docs/E2E-TESTING-GUIDE.md`
- **Standalone scripts** (`Tests-Standalone/`): Utility scripts and one-off tests
  - Contains ~40 standalone test/utility scripts
  - Includes test fixtures and data files

### General Notes
- Documentation is minimal - mainly workflow guides in `Docs/`
- Beta features and experiments are in `Beta/` directory
  - When making global changes, skip all files in the Beta/ directory
- The project expects Windows-style executable paths but runs on WSL/Linux, so both should be supported
- any python packages that you install should be added to requirements.txt file. make sure file is in git

- parse date strings with 'arrow' package
- quoted strings should use single quotes instead of double except for these cases:
  - the string to be displayed contains single quotes
  - use double quotes for docstrings
  - if there is an embedded single quote in a string, do not escape it with a backslash. instead, use double quotes around the whole string
- in the logger_config, move local functions (name start with _) before any global function. do the same whenever adding local functions

## Code Quality and Type Checking

The project uses multiple linting and type checking tools to maintain code quality:

### Type Checking with mypy
- **Status**: Full mypy compliance (0 errors)
- **Type stubs installed**: `types-requests`, `types-yt-dlp`
- **Path handling**: All path/directory operations use `pathlib.Path` instead of `os` module
- **Function signatures**: Use `Path | str` for parameters that accept both types
- **Type hints**: All functions have proper type annotations

### Linting Tools
- **flake8**: PEP 8 compliance, unused import detection
- **pylint**: Code quality metrics, unused variable detection
- **isort**: Import statement ordering
- **mypy**: Static type checking

### Path Handling Convention
- **Use `pathlib.Path`** for all file/directory operations
- **Avoid `os.path`** functions (join, abspath, exists, etc.)
- Use `Path.resolve()` instead of `os.path.abspath()`
- Use `Path.mkdir()` instead of `os.makedirs()`
- Use `Path / 'file'` instead of `os.path.join()`
- **Exception**: `os.getenv()` is acceptable for environment variables (not a path operation)

### Code Organization
- No unused imports or variables
- Functions accept `Path | str` for flexibility
- Convert to Path early, work with Path throughout

## Environment Variables

The tool supports several environment variables for configuration:

### YTDLP_RETRIES
Controls the number of download retries for handling YouTube throttling and connection drops.

- **Default**: 100 retries
- **Valid values**: Positive integers (1, 2, 3, ... 100, 500, etc.)
- **Location**: Set before running the script
- **Purpose**: YouTube often throttles or drops connections during large downloads. The retry mechanism allows yt-dlp to keep attempting until successful.

**Usage:**
```bash
# Linux/WSL/macOS
export YTDLP_RETRIES=50
python main-yt-dlp.py --only-audio "URL"

# Windows PowerShell
$env:YTDLP_RETRIES="50"
python main-yt-dlp.py --only-audio "URL"
```

**Implementation:** `_get_download_retries()` in `funcs_yt_dlp_download.py` validates the value and raises `ValueError` if not a positive integer.

### YTDLP_USE_COOKIES
Enables downloading age-restricted or private videos using browser cookies.

- **Valid values**: `chrome`, `firefox`
- **Purpose**: Use logged-in browser session to access restricted content
- **Auto-includes**: `--no-cache-dir` and `--sleep-requests 1` flags for reliability

**Usage:**
```bash
# Linux/WSL/macOS
export YTDLP_USE_COOKIES=firefox
python main-yt-dlp.py --only-audio "URL"

# Windows PowerShell
$env:YTDLP_USE_COOKIES="chrome"
python main-yt-dlp.py --only-audio "URL"
```

## Notifications (Slack and Gmail)

The tool can send notifications via Slack and/or Gmail for download start/success/failure/cancellation events.

### Setup
Create a file `git_excluded.py` in the project root (not tracked by git):

**For Slack notifications:**
```python
SLACK_WEBHOOK = 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
```

**For Gmail notifications:**
```python
GMAIL_PARAMS = {
    'sender_email': 'sender@gmail.com',
    'sender_app_password': 'xxxx xxxx xxxx xxxx',  # Gmail App Password (16 characters)
    'recipient_email': 'recipient@gmail.com',
}
```

**Important for Gmail:**
- You must use a Gmail **App Password**, not your regular Gmail password
- Enable 2-Step Verification first: https://myaccount.google.com/security
- Generate App Password: https://myaccount.google.com/apppasswords
- Select app: "Mail", device: "Other (custom name)"
- Copy the 16-character password exactly as shown

**Note:** You can configure one, both, or neither notification method. Each runs independently.

### Features
- **Multiple notifiers**: Slack and Gmail notifications run independently — one failure doesn't block the other
- **Session tracking**: Each run generates a unique session ID `[YYYY-MM-DD HH:mm hostname]` that appears in both start and end messages for easy correlation
- **Security**: Credentials are never logged, even with `--verbose` flag
  - urllib3 and requests loggers are suppressed by default
  - Use `--show-urls` flag only for debugging (exposes webhook URL in logs)

### Message Content
- **Start message**: URL, selected parameters (with-audio, only-audio, split-chapters, title, artist, album)
- **Success/failure/cancellation message**: All parameters, file counts, elapsed time
- **Slack format**: Markdown with `*bold*` and bullet points
- **Gmail format**: HTML email with subject line indicating status

### File Counting
The script accurately tracks only files created during the current run:
- Counts existing files in output directories before download starts
- Counts final files after download completes
- Reports the difference (newly created files only)
- Works correctly even if output directories contain files from previous runs
- Applies to video files (yt-videos/), audio files (yt-audio/, yt-audio-m4a/, yt-audio-flac/)

### Architecture
Notifications use a strategy pattern with a `funcs_notifications/` package:
- `base.py` - NotificationHandler abstract base class
- `slack_notifier.py` - SlackNotifier implementation
- `gmail_notifier.py` - GmailNotifier implementation
- `message_builder.py` - Shared message formatting
- `__init__.py` - Exports + `send_all_notifications()` helper

### Troubleshooting Gmail
If you get "Authentication failed" errors:
```bash
# Run diagnostic tool
python Tests-Standalone/test_gmail_auth.py
```
This will test your Gmail configuration and show specific error messages.