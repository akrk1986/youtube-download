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

### Core Function Modules
- `funcs_utils.py` - General utilities (file operations, string sanitization, Greek text handling)
- `funcs_video_info.py` - Video information retrieval, URL validation, chapter display, CSV generation
- `funcs_yt_dlp_download.py` - yt-dlp download and audio extraction functions
- `funcs_for_main_yt_dlp.py` - Helper functions for main-yt-dlp.py (validation, file organization, tag processing coordination)
- `funcs_process_mp3_tags.py` - MP3 ID3v2 tag processing and artist detection
- `funcs_process_m4a_tags.py` - M4A MP4/iTunes metadata processing
- `funcs_process_flac_tags.py` - FLAC Vorbis Comments processing
- `funcs_process_audio_tags_common.py` - Common audio tag processing functions
- `funcs_process_audio_tags_unified.py` - Unified audio tag processing across formats
- `funcs_audio_tag_handlers.py` - Audio tag handler classes (MP3TagHandler, M4ATagHandler, FLACTagHandler)
- `funcs_artist_search.py` - Greek artist name matching and search variants
- `funcs_chapter_extraction.py` - Video chapter detection and processing
- `funcs_url_extraction.py` - URL extraction from text and ODF documents
- `funcs_audio_conversion.py` - Audio format conversion utilities
- `funcs_audio_boost.py` - Audio volume boosting utilities

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
```

### Testing Individual Components
Test files are in the `Tests/` directory:
```bash
python Tests/test_chapter_regex.py  # Test chapter extraction regex
python Tests/main_greek_search.py  # Test Greek text search functionality
python Tests/find-artists-main.py  # Test artist detection in strings
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

## Greek Text Processing

The codebase has specialized handling for Greek text:
- Diacritic removal for search matching
- Filename sanitization for Greek, English, Hebrew characters
- Artist name variants generation (supports different name orders and abbreviations)
- Artist database maintained in Trello, exported to `Data/artists.json`

## Development Notes

- No formal test framework - uses standalone test scripts in `Tests/`
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