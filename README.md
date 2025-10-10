# youtube-download

A Python-based YouTube downloader and media processing tool that uses `yt-dlp` for downloading videos/audio and processes metadata with special focus on Greek music.

## Features

- Download YouTube videos and playlists as MP4 files with embedded URL metadata
- Extract audio as MP3, M4A, and/or FLAC with embedded metadata and thumbnails
- Split videos by chapters automatically
- Process audio tags to identify and set Greek artists
- Handle subtitle downloads in multiple languages (Greek, English, Hebrew)
- Sanitize filenames for Greek, English, and Hebrew text
- Automatic artist detection from a curated database of Greek musicians
- Store source YouTube URL in both video and audio file metadata

## Usage

```
usage: main-yt-dlp.py [-h] [--with-audio] [--audio-format AUDIO_FORMAT]
                      [--only-audio] [--split-chapters] [--subs] [--json]
                      [--verbose] [--no-log-file]
                      [playlist_url]

Download YouTube playlist/video, optionally with subtitles.

positional arguments:
  playlist_url          YouTube playlist/video URL

options:
  -h, --help            show this help message and exit
  --with-audio          Also extract audio (format specified by --audio-format)
  --audio-format AUDIO_FORMAT
                        Audio format for extraction: mp3, m4a, flac, or comma-
                        separated (e.g., mp3,m4a) (default: mp3)
  --only-audio          Delete video files after extraction
  --split-chapters      Split to chapters
  --subs                Download subtitles
  --json                Write JSON file
  --verbose, -v         Enable verbose (DEBUG) logging
  --no-log-file         Disable logging to file
```

## Input URL Types

The tool supports different types of YouTube URLs, each with different behavior:

### Single Video Without Chapters
**URL format:** `https://youtube.com/watch?v=VIDEO_ID`

Downloads a single video file. If `--with-audio` is specified, extracts audio with metadata (title, uploader, thumbnail).

**Example:**
```bash
python main-yt-dlp.py --with-audio "https://youtube.com/watch?v=dQw4w9WgXcQ"
```

### Single Video With Chapters
**URL format:** `https://youtube.com/watch?v=VIDEO_ID` (video must have chapters in description)

When combined with `--split-chapters`, the tool:
- Detects chapter timestamps in the video description
- Splits the video/audio into separate files per chapter
- Automatically sets track numbers and titles based on chapter names
- Organizes files into a subdirectory

**Example:**
```bash
python main-yt-dlp.py --only-audio --split-chapters --audio-format m4a "https://youtube.com/watch?v=VIDEO_ID"
```

### Playlist
**URL format:** `https://youtube.com/playlist?list=PLAYLIST_ID`

Downloads all videos in the playlist. Each video is processed individually with its own metadata.

**Example:**
```bash
python main-yt-dlp.py --with-audio --subs "https://youtube.com/playlist?list=PLxxxxxxxx"
```

### Audio Format Selection

You can choose one or more output audio formats using comma-separated values:

- `--audio-format mp3` (default) - Extract as MP3 with ID3v2 tags (lossy)
- `--audio-format m4a` - Extract as M4A with MP4/iTunes atoms (lossy)
- `--audio-format flac` - Extract as FLAC with Vorbis Comments (lossless, larger files)
- `--audio-format mp3,m4a` - Extract both MP3 and M4A formats
- `--audio-format mp3,m4a,flac` - Extract all three formats

**Examples:**
```bash
# Single format - FLAC (lossless)
python main-yt-dlp.py --only-audio --audio-format flac "https://youtube.com/watch?v=VIDEO_ID"

# Multiple formats - MP3 and M4A
python main-yt-dlp.py --with-audio --audio-format mp3,m4a "https://youtube.com/watch?v=VIDEO_ID"

# All formats with chapters
python main-yt-dlp.py --only-audio --audio-format mp3,m4a,flac --split-chapters "https://youtube.com/playlist?list=PLxxxxxxxx"
```

**Note:** FLAC is a lossless format that preserves audio quality but produces larger file sizes compared to MP3/M4A.

## Common Workflows

### Download video only
```bash
python main-yt-dlp.py "https://youtube.com/watch?v=VIDEO_ID"
```

### Download with audio extraction (MP3)
```bash
python main-yt-dlp.py --with-audio "https://youtube.com/playlist?list=PLxxxxxxxx"
```

### Audio only, delete videos after extraction
```bash
python main-yt-dlp.py --only-audio --split-chapters "https://youtube.com/watch?v=VIDEO_ID"
```

### Download with subtitles and JSON metadata
```bash
python main-yt-dlp.py --with-audio --subs --json "https://youtube.com/watch?v=VIDEO_ID"
```

### Download playlist with multiple audio formats
```bash
python main-yt-dlp.py --only-audio --audio-format mp3,m4a "https://youtube.com/playlist?list=PLxxxxxxxx"
```

## Output Structure

- `yt-videos/` - Downloaded MP4 video files
- `yt-audio/` - Downloaded audio files organized by format:
  - `yt-audio/mp3/` - MP3 files
  - `yt-audio/m4a/` - M4A files
  - `yt-audio/flac/` - FLAC files
- Chapter-split files are automatically organized into subdirectories

## Requirements

### Supported Platforms
- **Windows** - Fully supported
- **Linux** - Fully supported (tested on WSL2)

### Dependencies
- Python 3.10+
- `yt-dlp` executable
  - **Windows**: Expected at `~/Apps/yt-dlp/yt-dlp.exe`
  - **Linux**: Must be in `$PATH`
- `ffmpeg` executable
  - **Windows**: Expected at `~/Apps/yt-dlp/ffmpeg.exe`
  - **Linux**: Must be in `$PATH`
- Python packages: `mutagen`, `yt-dlp`, `arrow`, `emoji` (see `requirements.txt`)

## Installation

### Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Install yt-dlp and ffmpeg

**Windows:**
```bash
# Ensure yt-dlp and ffmpeg are available in ~/Apps/yt-dlp/
# Download from:
# - yt-dlp: https://github.com/yt-dlp/yt-dlp/releases
# - ffmpeg: https://ffmpeg.org/download.html
```

**Linux:**
```bash
# Install via package manager or download binaries
# Ensure both executables are in your $PATH

# Ubuntu/Debian example:
sudo apt install yt-dlp ffmpeg

# Or install yt-dlp via pip:
pip install yt-dlp

# Verify installation:
which yt-dlp
which ffmpeg
```

## Documentation

- **[Configuring mp3tag to Display yt-dlp Generated Audio Files](Docs/Configuring%20mp3tag%20to%20display%20yt-dlp%20generated%20audio%20files.md)** - Guide for viewing and editing metadata in mp3tag for MP3, M4A, and FLAC files
- **[Artists File from Trello Update Guide](Docs/Artists-file-from-trello-update-guide.md)** - How to update the Greek artists database from Trello
- **[Code Quality Recommendations](Docs/code-quality-recommendations.md)** - Development guidelines and best practices

## Greek Music Features

The tool includes specialized functionality for Greek music:

- **Artist Detection**: Automatically detects Greek artist names in video titles
- **Artist Database**: Curated list of ~100 Greek musicians maintained in Trello and exported to `Data/artists.json`
- **Name Variants**: Handles different name orders and Greek text variations
- **Filename Sanitization**: Properly handles Greek, English, and Hebrew characters in filenames
- **Metadata Tagging**: Sets artist and album artist tags automatically for detected Greek artists

## Project Structure

- `main-yt-dlp.py` - Main entry point
- `funcs_*.py` - Modular function libraries for different tasks
- `Data/artists.json` - Greek artists database (exported from Trello)
- `Tests/` - Test scripts for individual components
- `Docs/` - Documentation files
- `Beta/` - Experimental features (excluded from global changes)

## License

This project is for personal use.
