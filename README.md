# youtube-download

A Python-based YouTube downloader and media processing tool that uses `yt-dlp` for downloading videos/audio and processes metadata with special focus on Greek music.

## Features

- Download YouTube videos and playlists as MP4 files with embedded URL metadata
- Extract audio as MP3, M4A, and/or FLAC with embedded metadata and thumbnails
- Split videos by chapters automatically
- Process audio tags to identify and set Greek artists
- Handle subtitle downloads in multiple languages (Greek, English, Hebrew)
- Sanitize filenames for multiple languages (English, French, Turkish, Greek, Hebrew)
- Automatic artist detection from a curated database of Greek musicians
- Store source YouTube URL in both video and audio file metadata
- Automatic format fallback when preferred video/audio formats are unavailable

## Usage

```
usage: main-yt-dlp.py [-h] [--audio-format AUDIO_FORMAT] [--split-chapters]
                      [--video-download-timeout VIDEO_DOWNLOAD_TIMEOUT]
                      [--subs] [--json] [--no-log-file] [--progress]
                      [--verbose] [--rerun] [--title TITLE] [--artist ARTIST]
                      [--album ALBUM] [--version]
                      [--with-audio | --only-audio]
                      [video_url]

Download YouTube playlist/video, optionally with subtitles.

positional arguments:
  video_url             Playlist/video URL (optional - will prompt if not provided)

options:
  -h, --help            Show this help message and exit

  --audio-format AUDIO_FORMAT
                        Audio format for extraction: mp3, m4a, flac, or comma-separated
                        list (e.g., mp3,m4a). (default: mp3)

  --split-chapters      Process videos with chapters:
                        - Displays chapter list with timing information
                        - Creates CSV file (segments-hms-full.txt) with chapter metadata
                        - For audio: splits into separate files per chapter
                        - For video: downloads full video (no chapter splitting)

  --video-download-timeout VIDEO_DOWNLOAD_TIMEOUT
                        Timeout in seconds for video downloads. If specified, applies to all sites.
                        If not specified, uses defaults: 300s for YouTube/Facebook, 3600s for other sites

  --subs                Download subtitles in Greek, English, and Hebrew (converted to SRT)

  --json                Write video metadata to JSON file using yt-dlp's --write-info-json

  --no-log-file         Disable logging to file (logs only to console)
                        By default, logs are written to Logs/yt-dlp_YYYYMMDD_HHMMSS.log

  --progress            Show yt-dlp progress bar and log detailed output to Logs/yt-dlp-progress.log

  --verbose, -v         Enable verbose (DEBUG) logging for detailed troubleshooting

  --rerun               Reuse URL from previous run (stored in Data/last_url.txt)
                        Ignored if video_url is provided

  --title TITLE         Custom title for output filename (ignored for playlists)
                        Use --title ask or --title prompt to be prompted for the title

  --artist ARTIST       Custom artist tag for audio files (ignored for playlists)
                        Use --artist ask or --artist prompt to be prompted for the artist

  --album ALBUM         Custom album tag for audio files (ignored for playlists)
                        Use --album ask or --album prompt to be prompted for the album

  --version             Show program's version number and exit

audio extraction mode (mutually exclusive):
  --with-audio          Download videos AND extract audio (format specified by --audio-format)

  --only-audio          Extract ONLY audio, delete video files after extraction
                        (audio format specified by --audio-format)
```

### Parameter Details

**Positional Arguments:**
- `video_url` - YouTube or supported video site URL. If not provided, the script will prompt interactively.

**Audio Options:**
- `--audio-format` - Specify one or more formats: `mp3` (default), `m4a`, `flac`, or comma-separated (e.g., `mp3,m4a,flac`)
- `--with-audio` - Downloads both video (MP4) and audio in specified format(s)
- `--only-audio` - Downloads only audio, videos are deleted after extraction

**Video Processing:**
- `--split-chapters` - Process videos with chapters:
  - Displays chapter list with names, start/end times, and durations
  - Creates `segments-hms-full.txt` CSV file with chapter metadata (includes video title, uploader, URL, and pre-filled year)
  - For audio: splits into separate files per chapter with track numbers
  - For video: downloads full video without splitting (CSV provides chapter reference)
- `--subs` - Downloads subtitles in Greek (el), English (en), and Hebrew (he), converted to SRT format
- `--json` - Saves complete video metadata in JSON format alongside the downloaded file

**Performance & Timeout:**
- `--video-download-timeout` - Override default timeout for video downloads (in seconds)
  - When specified: applies to all sites (YouTube, Facebook, and others)
  - When not specified: uses automatic defaults based on site
    - YouTube/Facebook: 300 seconds (5 minutes)
    - Other sites (e.g., ertflix.gr): 3600 seconds (1 hour)
  - Useful for slow connections or large files

**Logging & Debugging:**
- `--no-log-file` - Logs only to console, doesn't create log files in Logs/ directory
- `--progress` - Shows yt-dlp's progress bar and writes verbose download logs to `Logs/yt-dlp-progress.log`
- `--verbose` / `-v` - Enables DEBUG level logging for troubleshooting
- By default, application logs are written to `Logs/yt-dlp_YYYYMMDD_HHMMSS.log` (keeps last 5 log files)

**Custom Metadata (Single Videos Only):**
- `--title TITLE` - Override the output filename with a custom title
  - Use `--title ask` or `--title prompt` to be prompted interactively
  - Ignored for playlists (each video uses its own title)
  - The title is sanitized for safe filenames
- `--artist ARTIST` - Set custom artist tag in audio files
  - Use `--artist ask` or `--artist prompt` to be prompted interactively
  - Sets both artist and album artist tags
  - Ignored for playlists
- `--album ALBUM` - Set custom album tag in audio files
  - Use `--album ask` or `--album prompt` to be prompted interactively
  - Ignored for playlists

**Other:**
- `--rerun` - Reuse URL from previous run without having to paste it again
  - Every run saves the validated URL to `Data/last_url.txt`
  - Use `--rerun` without providing a URL to reuse the last URL
  - Ignored if a URL is provided on the command line
  - Useful for repeated testing/downloading of the same URL
- `--version` - Displays the program version (matches CHANGELOG timestamp)
- `-h` / `--help` - Shows help message with all options

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
- Displays chapter list with timing information (start time, end time, duration)
- **Creates a CSV file** (`segments-hms-full.txt`) with chapter metadata for manual editing:
  - Columns: start time, end time, song name, original song name, artist name, album name, year, composer, comments
  - Includes comment lines with video title, artist/uploader, and URL
  - Pre-fills chapter titles and year (from video upload date if available)
- **For videos** (without `--only-audio`):
  - Downloads the full video without chapter splitting
  - CSV file provides chapter information for reference
- **For audio** (`--only-audio` or `--with-audio`):
  - Splits audio into separate files per chapter
  - Automatically sets track numbers and titles based on chapter names
  - Organizes files into a subdirectory
  - Each audio format gets its own chapter files

**Example:**
```bash
# Audio only - splits audio by chapters + creates CSV
python main-yt-dlp.py --only-audio --split-chapters --audio-format m4a "https://youtube.com/watch?v=VIDEO_ID"

# Video + Audio - downloads full video, splits audio by chapters + creates CSV
python main-yt-dlp.py --with-audio --split-chapters "https://youtube.com/watch?v=VIDEO_ID"

# Video only - downloads full video + creates CSV (no audio splitting)
python main-yt-dlp.py --split-chapters "https://youtube.com/watch?v=VIDEO_ID"
```

**CSV File Output:**
The generated `segments-hms-full.txt` file contains:
```csv
start time,end time,song name,original song name,artist name,album name,year,composer,comments
# Title: 'Video Title Here'
# Artist/Uploader: 'Channel Name'
# URL: https://youtube.com/watch?v=VIDEO_ID
000000,000300,Chapter 1 Title,,,,2023,,
000300,000700,Chapter 2 Title,,,,2023,,
```
This CSV can be manually edited to add missing metadata (original song names, artists, composers, etc.) before importing into other tools.

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

### Audio only with chapter splitting and CSV generation
```bash
python main-yt-dlp.py --only-audio --split-chapters "https://youtube.com/watch?v=VIDEO_ID"
# Creates: individual chapter audio files + segments-hms-full.txt
```

### Download with subtitles and JSON metadata
```bash
python main-yt-dlp.py --with-audio --subs --json "https://youtube.com/watch?v=VIDEO_ID"
```

### Download playlist with multiple audio formats
```bash
python main-yt-dlp.py --only-audio --audio-format mp3,m4a "https://youtube.com/playlist?list=PLxxxxxxxx"
```

### Rerun with same URL (convenient for testing)
```bash
# First run - saves URL to Data/last_url.txt
python main-yt-dlp.py --only-audio "https://youtube.com/watch?v=VIDEO_ID"

# Subsequent runs - reuse the saved URL
python main-yt-dlp.py --rerun --only-audio

# Try different options with same URL
python main-yt-dlp.py --rerun --with-audio --audio-format m4a
python main-yt-dlp.py --rerun --split-chapters
```

### Download with custom timeout (useful for slow connections)
```bash
# Set 10-minute timeout for all sites
python main-yt-dlp.py --only-audio --video-download-timeout 600 "https://youtube.com/watch?v=VIDEO_ID"

# Set 30-minute timeout for slow sites
python main-yt-dlp.py --with-audio --video-download-timeout 1800 "https://www.ertflix.gr/video/VIDEO_ID"
```

### Download with custom metadata
```bash
# Set custom title, artist, and album
python main-yt-dlp.py --only-audio --title "My Song Title" --artist "Artist Name" --album "Album Name" "URL"

# Be prompted for custom metadata interactively
python main-yt-dlp.py --only-audio --title ask --artist ask --album ask "URL"

# Mix: specify some, prompt for others
python main-yt-dlp.py --only-audio --title "Known Title" --artist prompt "URL"
```

### Download age-restricted or private videos using browser cookies
```bash
# Use cookies from Chrome browser (Windows, Linux, WSL)
export YTDLP_USE_COOKIES=chrome
python main-yt-dlp.py --only-audio "https://youtube.com/watch?v=VIDEO_ID"

# Use cookies from Firefox browser
export YTDLP_USE_COOKIES=firefox
python main-yt-dlp.py --with-audio "https://youtube.com/watch?v=VIDEO_ID"

# On Windows (PowerShell):
$env:YTDLP_USE_COOKIES="chrome"
python main-yt-dlp.py --only-audio "https://youtube.com/watch?v=VIDEO_ID"
```

**Note:** Browser cookies allow downloading videos that require authentication or age verification. The tool will use your logged-in browser session to access the video. Supported browsers: Chrome and Firefox.

**Important:** When using cookies, the tool automatically:
- Disables yt-dlp's cache (`--no-cache-dir`) to ensure fresh authentication for each operation
- Adds 1-second delay between requests (`--sleep-requests 1`) to avoid YouTube rate limiting
- This prevents 403 errors and makes downloads more reliable, especially with `--split-chapters`
- Downloads will be slower but much more stable for authenticated content

### Configure download retry behavior

By default, yt-dlp will retry failed downloads up to 100 times. This handles temporary network issues and YouTube throttling. You can customize this behavior:

```bash
# Set custom retry limit (Linux, WSL, macOS)
export YTDLP_RETRIES=50
python main-yt-dlp.py --only-audio "https://youtube.com/watch?v=VIDEO_ID"

# On Windows (PowerShell):
$env:YTDLP_RETRIES="50"
python main-yt-dlp.py --only-audio "https://youtube.com/watch?v=VIDEO_ID"

# Use default of 100 retries (no environment variable needed)
python main-yt-dlp.py --only-audio "https://youtube.com/watch?v=VIDEO_ID"
```

**Note:** The retry count must be a positive integer. If `YTDLP_RETRIES` is unset or empty, the default of 100 retries is used. This is particularly useful for:
- Large files that may experience intermittent connection drops
- YouTube throttling on certain videos
- Unreliable network connections

## URL Extraction Utility

The project includes a utility for extracting URLs from text and ODF documents, filtering only valid video site URLs (YouTube, Facebook, ERTFlix).

### Usage

```bash
# Extract URLs from a text file
python Tests/main-test-url-extraction.py path/to/file.txt

# Extract URLs from an ODT file
python Tests/main-test-url-extraction.py path/to/document.odt
```

### Features

- **Supported formats**: Plain text (.txt) and OpenDocument Text (.odt) files
- **Smart filtering**: Only extracts URLs from valid domains (YouTube, Facebook, ERTFlix)
- **Case-insensitive**: Handles domain variations (YouTube, YOUTUBE, youtube)
- **Subdomain support**: Works with www.youtube.com, m.youtube.com, youtu.be, etc.
- **Security**: Rejects similar domain names and subdomain attacks

### Example Output

```bash
$ python Tests/main-test-url-extraction.py my-urls.txt
Found 5 URL(s) in my-urls.txt:

1. https://www.youtube.com/watch?v=dQw4w9WgXcQ
2. https://youtu.be/abc123
3. https://www.facebook.com/video/12345
4. https://ertflix.gr/series/greek-music
5. https://m.youtube.com/playlist?list=PLxxxxxxxx
```

**Note**: URLs from other domains (GitHub, Google, etc.) are automatically filtered out.

For more details, see [URL Validation Summary](Docs/URL-VALIDATION-SUMMARY.md).

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
- Python packages: `mutagen`, `yt-dlp`, `arrow`, `emoji`, `odfpy` (see `requirements.txt`)

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
- **[URL Validation Summary](Docs/URL-VALIDATION-SUMMARY.md)** - URL extraction utility and domain validation implementation details
- **[Code Quality Recommendations](Docs/code-quality-recommendations.md)** - Development guidelines and best practices
- **[CHANGELOG](Docs/CHANGELOG.md)** - Feature enhancements and major changes history

## Greek Music Features

The tool includes specialized functionality for Greek music:

- **Artist Detection**: Automatically detects Greek artist names in video titles
- **Artist Database**: Curated list of ~100 Greek musicians maintained in Trello and exported to `Data/artists.json`
- **Name Variants**: Handles different name orders and Greek text variations
- **Filename Sanitization**: Properly handles English, French, Turkish, Greek, and Hebrew characters in filenames
- **Metadata Tagging**: Sets artist and album artist tags automatically for detected Greek artists

## Project Structure

- `main-yt-dlp.py` - Main entry point
- `funcs_*.py` - Modular function libraries for different tasks
- `Data/artists.json` - Greek artists database (exported from Trello)
- `Tests/` - Test scripts for individual components
- `Docs/` - Documentation files
- `Beta/` - Experimental features (excluded from global changes)

## Automatic Format Fallback

The tool automatically handles videos where preferred formats are unavailable:

- **Video downloads**: Tries multiple format combinations (MP4+M4A → any video+audio → best available)
- **Audio downloads**: Falls back to best available audio format
- **Silent operation**: Format errors are suppressed; only shows error if no format works at all
- **No user action required**: The fallback happens automatically without any configuration

This eliminates confusing "Requested format is not available" error messages while still downloading successfully using alternative formats.

## License

This project is for personal use.
