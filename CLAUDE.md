# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based YouTube downloader and media processing tool that uses `yt-dlp` for downloading videos/audio and processes metadata with special focus on Greek music. The tool can:

- Download YouTube videos/playlists as MP4 files
- Extract audio as MP3 with embedded metadata and thumbnails
- Split videos by chapters automatically
- Process MP3 tags to identify and set Greek artists
- Handle subtitle downloads in multiple languages (Greek, English, Hebrew)
- Sanitize filenames for Greek, English, and Hebrew text

## Core Architecture

The codebase follows a modular function-based architecture:

### Main Entry Points
- `main-yt-dlp.py` - Primary CLI tool for downloading and processing YouTube content
- `main-get-artists-from-trello.py` - Utility to convert Trello board data to artist JSON

### Core Function Modules
- `funcs_utils.py` - General utilities (file operations, Greek text handling, yt-dlp integration)
- `funcs_process_mp3_tags.py` - MP3 ID3 tag processing and artist detection
- `funcs_process_audio_tags_common.py` - Common audio tag processing functions
- `funcs_process_mp4_tags.py` - MP4 metadata processing (new, for M4A support)
- `funcs_artist_search.py` - Greek artist name matching and search variants
- `funcs_chapter_extraction.py` - Video chapter detection and processing

### Data Files
- `Data/artists.json` - Greek music artists database (~17KB)
- `Data/trello - greek-music-artists.json` - Raw Trello export (~1.7MB)

## Key Dependencies

The project requires:
- `yt-dlp` executable (expected at `~/Apps/yt-dlp/yt-dlp.exe`)
- `ffmpeg` executable (expected at `~/Apps/yt-dlp/ffmpeg.exe`)
- Python packages: `mutagen`, `yt-dlp` (imported as module)

## Common Commands

### Running the Main Tool
```bash
# Download video only
python main-yt-dlp.py "https://youtube.com/watch?v=..."

# Download with audio extraction
python main-yt-dlp.py --with-audio "https://youtube.com/playlist?list=..."

# Audio only (delete videos after extraction)
python main-yt-dlp.py --only-audio --split-chapters "https://youtube.com/watch?v=..."

# With subtitles and JSON metadata
python main-yt-dlp.py --with-audio --subs --json "URL"
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
- `yt-audio/` - Downloaded MP3 audio files
- Chapter files are automatically organized into subdirectories when `--split-chapters` is used

## Greek Text Processing

The codebase has specialized handling for Greek text:
- Diacritic removal for search matching
- Filename sanitization for Greek, English, Hebrew characters
- Artist name variants generation (supports different name orders and abbreviations)

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