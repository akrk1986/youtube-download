# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based YouTube downloader and media processing tool that uses `yt-dlp` for downloading videos/audio and processes metadata with special focus on Greek music. The tool can:

- Download YouTube videos/playlists as MP4 files
- Download ERTFlix (Greek public broadcaster) programs using token API URLs
- Extract audio as MP3, M4A, and/or FLAC with embedded metadata and thumbnails
- List a video's chapters and export a segments CSV for the losslesscut-csv split workflow
- Process audio tags to identify and set Greek artists
- Handle subtitle downloads in multiple languages (Greek, English, Hebrew)
- Sanitize filenames for multiple languages (English, French, Turkish, Greek, Hebrew)

## Core Architecture

The codebase follows a modular function-based architecture:

### Main Entry Points
- `main-yt-dlp.py` - Primary CLI tool for downloading and processing YouTube content
- `main-ertflix-series.py` - Interactive ERTFlix series browser (Playwright + Chromium): picks season/episode via arrow-key menus, captures the token API URL when Play is clicked, and hands off to `main-yt-dlp.py --ertflix-program`

### Utility Scripts (`Utils/`)
- `main-suggest-boost.py` - Loudness Boost Suggester: measure a URL's loudness and suggest an `FFMPEG_OPTS` boost (coupled to the download pipeline)
- `main-get-artists-from-trello.py` - Convert Trello board data to artist JSON (regenerates `Data/artists.json` for the main pipeline)
- `install-git-hooks.py` - Enable/disable the git pre-commit hook via `core.hooksPath` (see the Linting section)

> The audio-conversion, volume-boost, Dolby-Vision, Greek-singles duplicate, copy-tags-to-video, and qBittorrent utilities (and their `funcs_check_greek_singles/`, `funcs_copy_tags_to_video/`, `funcs_for_audio_utils/`, `funcs_for_qb_notify/` support packages) were moved to the sibling **`av-utils`** project (`../av-utils`) on 2026-06-05.

### Core Function Modules and Packages

The codebase uses a modular package-based architecture. Shared audio/video helpers (tag handlers, notifications, ffmpeg/probe/tags, `remove_diacritics`, `setup_logging`) live in the sibling `common-av-codebase` package (`common_av`).

**Packages:**

- `funcs_for_main_yt_dlp/` - Main script helpers
  - `_download_common.py` - Shared `DownloadOptions` dataclass, helpers, progress state
  - `download_video.py` - Video download (`run_yt_dlp`, `VIDEO_FORMAT_FALLBACKS`)
  - `download_audio.py` - Audio extraction (`extract_single_format`, `extract_audio_with_ytdlp`)
  - `audio_processing.py` - Audio tag processing coordination
  - `file_organization.py` - File organization and sanitization
  - `external_tools.py` - External tool path detection (ffmpeg, yt-dlp)
  - `url_validation.py` - URL validation and input handling
  - `utilities.py` - General utilities (time formatting, session ID)
  - `ertflix_token_handler.py` - ERTFlix token URL resolution

- `funcs_video_info/` - Video information (6 modules, 962 lines)
  - `metadata.py` - Video metadata retrieval using yt-dlp
  - `chapters.py` - Chapter detection, display, and CSV generation
  - `url_validation.py` - URL validation and timeout determination
  - `url_extraction.py` - URL extraction from text and ODF documents
  - `chapter_extraction.py` - Video chapter detection and processing
  - `composer_extraction.py` - Composer extraction from Greek video descriptions

- `funcs_utils/` - General utilities
  - `string_sanitization.py` - String/filename sanitization and Greek text handling (`remove_diacritics` re-exported from `common_av.text`)
  - `file_operations.py` - File organization and sanitization
  - `yt_dlp_utils.py` - yt-dlp specific utilities (error detection, cookies)
  - `security.py` - Security helpers for subprocess calls
  - `artist_search.py` - Greek artist name matching and search variants
  - `__init__.py` - also re-exports `setup_logging` from `common_av.log_config` (the public `funcs_utils` names are unchanged)

- `funcs_audio_processing/` - Audio tag processing
  - `__init__.py` - Dispatch dict (`_HANDLER_MAP`) + `set_artists_for_format()` / `set_chapter_tags_for_format()` + backward-compat aliases (tag handlers imported from `common_av.tag_handlers`)
  - `unified.py` - Unified audio tag processing across formats
  - `common.py` - Common audio tag processing functions

- `funcs_ertflix_automation/` - ERTFlix series browser automation (see the ERTFlix section)

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

# Download with audio extraction (default: M4A)
python main-yt-dlp.py --with-audio "https://youtube.com/playlist?list=..."

# Download with specific audio format (mp3, m4a, or flac)
python main-yt-dlp.py --only-audio --audio-format m4a "URL"

# Download with multiple audio formats (comma-separated)
python main-yt-dlp.py --only-audio --audio-format mp3,m4a,flac "URL"

# List chapters and create the segments CSV (downloads full video, then stops)
python main-yt-dlp.py --list-chapters manual "https://youtube.com/watch?v=..."

# With subtitles and JSON metadata
python main-yt-dlp.py --with-audio --subs --json "URL"

# With custom title, artist, and album (single videos only)
python main-yt-dlp.py --only-audio --title "Custom Title" --artist "Artist Name" --album "Album" "URL"

# Interactive prompts for metadata (use 'ask' or 'prompt')
python main-yt-dlp.py --only-audio --title ask --artist prompt "URL"

# Verbose logging with URL debugging (WARNING: may expose Slack webhook)
python main-yt-dlp.py --verbose --show-urls --only-audio "URL"

# ERTFlix program download (video only, uses token API)
export YTDLP_USE_COOKIES=firefox
python main-yt-dlp.py --ertflix-program "https://api.ertflix.opentv.com/..."
```

### ERTFlix Interactive Series Browser (`main-ertflix-series.py`)

Top-level CLI that collapses the manual DevTools-console-paste dance into a single command. Drives Chromium via Playwright to an ERTFlix series page, scrapes seasons + episodes, lets the user pick via arrow-key menus, captures the token API URL when Play is clicked, then hands off to `main-yt-dlp.py --ertflix-program` as a subprocess.

**Setup (one time):**
```bash
source ../.venv-av-linux/bin/activate  # Windows: ..\.venv-av-windows\Scripts\activate
pip install -r requirements.txt        # installs playwright, questionary, rich
python -m playwright install chromium  # downloads Chromium under ~/.cache/ms-playwright
```

**Usage:**
```bash
# Arrow-key pick + download (unknown flags forward to main-yt-dlp.py)
python main-ertflix-series.py https://www.ertflix.gr/vod/vod.345646-parea \
    --only-audio --audio-format mp3

# With program name: sets --title "Parea S02E26" and NOTIF_MSG to the same string
python main-ertflix-series.py https://www.ertflix.gr/vod/vod.345646-parea \
    --program Parea --only-audio --audio-format mp3

# Print would-be hand-off command (uses shlex.join for shell-safe quoting) and exit
python main-ertflix-series.py <URL> --program Parea --dry-run --only-audio

# Dump rendered DOM + selector probes to Logs/ for diagnosis
python main-ertflix-series.py <URL> --debug-dom
```

**Flags:**
- `--program <name>` — program label prepended to the `S<NN>E<NN>` formatter. Accepts Greek.
- `--profile-dir <path>` — Chromium persistent user-data dir (default `.ertflix-profile/`, gitignored).
- `--headless` — run Chromium without a visible window (default is headed so the user can log in).
- `--debug-dom` — dump `Logs/ertflix-debug-<ts>.html` and exit before episode selection.
- `--token-timeout <float>` — seconds to wait for the token URL after clicking Play (default 10).
- `--dry-run` — log the hand-off argv + env overrides instead of invoking the subprocess.

**Behavior notes:**
- Seasons + episodes are numbered newest-to-oldest, matching the page order. `S02E26` = season 2, 26th episode (= the oldest in that season).
- Episodes are identified by the Play-button's `aria-label` (the title shown in the UI), NOT by regex against image URLs. This is resilient to naming-scheme changes.
- The episode table shows four columns: `#`, `Duration`, `Title`, `Description` — scraped from the sibling DOM elements of each `.asset-card`.
- After the page loads, the script pauses and notifies the user that now is the time to switch the page language in the browser if desired, before pressing Enter to continue scraping.
- In the season picker, `q`/`0` quits. In the episode picker, `q`/`0` quits and `s` returns to the season selector.
- `discover_episodes` polls a single `page.evaluate(...)` snapshot until the set of hydrated titles stabilizes for several rounds — captures all 25–30 cards even when Angular renders them in bursts.
- The token interceptor uses `page.on('request', ...)` (observational). Do NOT use `page.route()` — blocking the request prevents ERTFlix from generating a valid `content_URL`.
- `ensure_authenticated()` detects a redirect to `#/landing` or `#/login` and pauses so the user can sign in inside the headed window, then re-navigates and waits for `.asset-card`.
- When the console can't host `prompt_toolkit` (e.g. PyCharm Run console → `NoConsoleScreenBufferError`), falls back to a plain numbered `input()` prompt. The displayed numbers match the Rich table (not list position).
- `NOTIFICATIONS=ALL` is always set in the subprocess environment. `NOTIF_MSG` is set only when `--program` is provided.

**Package layout (`funcs_ertflix_automation/`):**
- `browser_session.py` — Playwright lifecycle, persistent-context launch, token request interceptor, authentication-redirect detection.
- `season_scraper.py` — `Season` dataclass, `discover_seasons`, `select_season`, season-button selectors.
- `episode_scraper.py` — `Episode` dataclass, `discover_episodes`, `dump_debug_dom`, DOM polling helper.
- `player_scraper.py` — `click_episode_play`, `extract_player_info`, info-dialog selectors.
- `cli_prompts.py` — Rich tables + questionary selects with numbered-input fallback. `pick_season` / `pick_episode` support `q`/`0` quit and `s` back-to-seasons navigation.
- `handoff.py` — subprocess hand-off to `main-yt-dlp.py`; accepts `env_overrides` merged on top of `os.environ`.
- `errors.py` — exception hierarchy (`ErtflixAutomationError`, `BackToSeasons`, `TokenCaptureTimeout`, `NoSeasonsOrEpisodesFound`, `BrowserLaunchFailed`).

**Tests:** `Tests/test_ertflix_automation.py` (10 pytest tests — argv builder, pickers, token-URL fragment).

### ERTFlix Support (manual token URL flow)

The tool supports downloading from ERTFlix (Greek public broadcaster) using token API URLs:

**Token URL Resolution:**
- ERTFlix uses token API URLs that contain the actual playback URL as a parameter
- The script automatically extracts and decodes the `content_URL` parameter
- No API calls needed - simple URL parsing and decoding

**Usage:**
```bash
# Capture token URLs using browser console script
# (See JS-files/capture-working-play-click.js)

# Set browser cookies for authentication
export YTDLP_USE_COOKIES=firefox  # or chrome

# Download ERTFlix program (video only)
python main-yt-dlp.py --ertflix-program "TOKEN_URL"

# Download audio only
python main-yt-dlp.py --only-audio "TOKEN_URL"
```

**Browser Scripts:**
- Production script in `JS-files/`:
  - `capture-working-play-click.js` - Captures token API URLs from Play buttons with concise summary
- Obsolete scripts in `JS-files-diag/`:
  - `obsolete-extract-ertflix-urls.js` - Outdated (site changed)
  - `obsolete-extract-parea-urls-v4.js` - Outdated (site changed)
- Diagnostic scripts in `JS-files-diag/` (for debugging)

**Capture Script Features (`capture-working-play-click.js`):**
- **Automatic concise summary**: After 3 seconds, displays title, duration, and deduplicated URLs
- **Clipboard copy**: Token API URL automatically copied to clipboard when captured
- **File download**: Summary auto-saved to Downloads folder as `concise-summary-YYYY-MM-DD-HHMMSS.txt`
- **Video metadata**: Captures title from Play button and duration from video player
- **URL tracking**: Records all URLs in order with type labels (TOKEN_API, SHAKA_PLAYER, VIDEO_RELATED)
- **Duplicate prevention**: Prevents multiple summaries from multiple Play button clicks
- **Capture control**: Automatically stops URL capturing after summary to prevent console clutter
- **Manual control functions**:
  - `window.__printUrlSummary()` - Print summary again
  - `window.__printUrlSummary(true)` - Force reprint summary
  - `window.__enableCapture()` - Re-enable URL capturing
  - `window.__disableCapture()` - Stop URL capturing
- **Debug output**: Instance ID tracking and state change logging for troubleshooting
- **Multi-instance detection**: Warns if script is pasted/run multiple times

**Usage Instructions:**
1. Navigate to ERTFlix video page (e.g., `https://www.ertflix.gr/#/details/ERT_PS054741_E0`)
2. Open DevTools (F12) — DevTools must **not change the width** of the main window. Use the ⋮ menu in DevTools > Dock side and choose **"Dock to bottom"** or **"Undock into separate window"**. Docking to the left or right side narrows the main window below ERTFlix's responsive breakpoint and replaces the episode page with a "use the mobile app" screen. Applies to both Chrome and Firefox.
3. Go to the Console tab and clear it (Firefox: trash icon, Chrome: circle with diagonal line)
4. Paste the script and press Enter
5. Click any Play button
6. Wait 3 seconds for automatic summary
7. Token URL is in clipboard, summary file in Downloads folder

**Main Script Features:**
- `--ertflix-program` flag: Download video only (ignores audio flags)
- Automatic token URL detection and resolution
- CDN-independent timeout (1.5 hours based on original ERTFlix domain)
- Browser cookie support via `YTDLP_USE_COOKIES` environment variable

**Token URL Format:**
```
https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?
  content_id=DRM_PS027282_DASH&
  type=account&
  content_URL=https%3A%2F%2Fert-ucdn.broadpeak-aas.com%2F...%2Findex.mpd
```

The script extracts the URL-encoded `content_URL` parameter, which contains the actual CDN playback URL.

### Testing Individual Components
The project has three categories of tests:

**Pytest tests** (in `Tests/` directory):
```bash
pytest Tests/                                    # Run all pytest tests (112 tests)
pytest Tests/test_main_ytdlp.py                  # Main script tests (37 tests)
pytest Tests/test_security_measures.py           # Security tests (20 tests)
pytest Tests/test_ertflix_token_handler.py       # ERTFlix token handler tests (10 tests)
pytest Tests/test_ertflix_automation.py          # ERTFlix automation tests (10 tests)
pytest Tests/test_notifications.py               # Notification tests (35 tests)
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
python Utils/main-get-artists-from-trello.py
```

## Output Structure

- `yt-videos/` - Downloaded MP4 video files
- Downloaded audio files, one top-level directory per format (constants in `project_defs.py`):
  - `yt-audio/` - M4A files (the default format → primary audio dir; `AUDIO_OUTPUT_DIR_M4A`)
  - `yt-audio-mp3/` - MP3 files (lossy, ID3v2 tags; `AUDIO_OUTPUT_DIR_MP3`)
  - `yt-audio-flac/` - FLAC files (lossless, Vorbis Comments; `AUDIO_OUTPUT_DIR_FLAC`)
  - Legacy `yt-audio-m4a/` from before the m4a-default remap is left as-is (no migration)
- `yt-chapters/` holds the segments CSV (`segments-hms-full.txt`) created by `--list-chapters`

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
- `VIDEO_FORMAT_FALLBACKS` in `funcs_for_main_yt_dlp/download_video.py` - List of formats to try
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

### CHANGELOG Rule

Every commit that modifies project files (excluding docs-only changes) must have a corresponding changelog entry. The changelog is split into three files by audience — record the entry in the one that matches what changed:
- **`CHANGELOG.md`** — the main scripts (`main-yt-dlp.py`, `main-ertflix-series.py`, and their ERTFlix capture helpers).
- **`CHANGELOG-Utils.md`** — the remaining standalone utilities (`Utils/main-suggest-boost.py`, `Utils/main-get-artists-from-trello.py`, and the URL-extraction helper in `Tests/`). The extracted audio/dedupe/qBittorrent utilities are tracked in `av-utils/CHANGELOG.md`.
- **`CHANGELOG-Project.md`** — project-wide tooling/dependency changes (linters, type checkers, `pip-audit`/CVE bumps, the shared virtual environment, security review).

Conventions (same across all three files):
- Use the actual commit timestamp: `git log -1 --format=%cd --date=format:'%Y-%m-%d-%H%M'`
- Record under `### Added`, `### Changed`, or `### Fixed` as appropriate
- Can be included in the same commit or a follow-up commit

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
- **Modern union syntax**: Use `X | None` instead of `Optional[X]`, use `X | Y` instead of `Union[X, Y]`
- **Parameterized generics**: Use `dict[str, Any]` not bare `dict`, `list[str]` not bare `list`

### Linting Tools
- **ruff**: Style + unused imports
- **mypy**: Static type checking
- **ty**: Fast type checker (Astral; stricter than mypy)
- **bandit**: Security scanning
- **pip-audit**: Dependency CVE scanner
- **deptry**: Unused/missing/misplaced dependency detection
- **pylint**: Code quality metrics, unused variable detection
- **pydoclint**: Docstring linting
- **vulture**: Dead code detection
- **pyupgrade**: Syntax modernisation (modifies files in place)
- **eslint** / **jshint**: JavaScript linting (`JS-files/`)

### Path Handling Convention
- **Use `pathlib.Path`** for all file/directory operations
- **Avoid `os.path`** functions (join, abspath, exists, etc.)
- Use `Path.resolve()` instead of `os.path.abspath()`
- Use `Path.mkdir()` instead of `os.makedirs()`
- Use `Path / 'file'` instead of `os.path.join()`
- **Exception**: `os.getenv()` is acceptable for environment variables (not a path operation)

### Blank Line Rules (PEP 8)
- **2 blank lines** before and after top-level function and class definitions
- **2 blank lines** after the last top-level function/class (before `if __name__`)
- **1 blank line** between methods inside a class
- **Maximum 2** consecutive blank lines allowed

### Code Organization
- No unused imports or variables
- Functions accept `Path | str` for flexibility
- Convert to Path early, work with Path throughout

### Subprocess Output Encoding
- Any `subprocess.run` / `subprocess.Popen` / `subprocess.check_output` call that **captures output in text mode** (`capture_output=True`, `stdout=PIPE`, or `stderr=PIPE`, together with `text=True`) MUST pass `encoding='utf-8', errors='replace'`.
- **Why**: on Windows, text mode defaults to the cp1252 codec. External tools (yt-dlp, ffmpeg/ffprobe, git) emit UTF-8 — file paths, tags, commit messages — often with non-Latin-1 characters (Greek, Hebrew, CJK). cp1252 can't decode them, so the stdout/stderr reader thread crashes silently and `result.stdout` / `result.stderr` come back `None`, causing a confusing downstream error (e.g. `expected string or bytes-like object, got 'NoneType'`).
- Byte-mode captures (no `text=True`) return `bytes` and are unaffected; uncaptured calls have no buffer to decode and need nothing.

## Environment Variables

The tool supports several environment variables for configuration:

### LINTER_GATE
Controls the linter-freshness gate that runs at the start of `main()`.

- **Default**: gate enabled. `main-yt-dlp.py` calls `gate_on_linter_freshness()` (from the shared `common_linters.watch_state`) right after parsing arguments.
- **Behaviour**: `pip-audit` and `freshness` drift without any code change (new CVEs, new releases). If neither has run in the last 24 hours, the script prints what is stale and prompts `Exit now and run the linters? [Y/n]` (Enter/`y` aborts with `exit 1`, `n` continues). The prompt shows even in PyCharm's Run window (where `isatty()` is False); a genuinely headless stdin continues without blocking, so the qB-launched path never hangs.
- **Set `LINTER_GATE=off`** to skip the gate entirely.
- **Refresh the state** it reads with `python run-linters.py --tool pip-audit freshness`, or let the `av-utils` background watcher (`Utils/main-linter-watch.py`) do it on a schedule. State lives in `av-utils/Data/linter-watch-state-<os>.json`.

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

**Implementation:** `_get_download_retries()` in `funcs_for_main_yt_dlp/_download_common.py` validates the value and raises `ValueError` if not a positive integer.

### NOTIFICATIONS
Controls whether Slack and/or Gmail notifications are sent.

- **Valid values**: empty/`N`/`NO` (none), `S` (Slack), `G` (Gmail), `ALL` (both) - case-insensitive
- **Default**: Disabled (opt-in model) if not set
- **Purpose**: Granular control over notification channels

**Usage:**
```bash
# No notifications (default)
python main-yt-dlp.py --only-audio "URL"

# Slack only
export NOTIFICATIONS=S
python main-yt-dlp.py --only-audio "URL"

# Gmail only
export NOTIFICATIONS=G
python main-yt-dlp.py --only-audio "URL"

# Both Slack and Gmail
export NOTIFICATIONS=ALL
python main-yt-dlp.py --only-audio "URL"
```

**Implementation:** Checked in `main()` before building notifiers list. Invalid values log warning and disable notifications.

**Breaking changes (as of 2026-02-16):**
- Removed legacy `Y`/`YES` support → use `ALL` instead
- Default changed from enabled to disabled (opt-in model)

### NOTIF_MSG
Adds custom suffix to notification titles for environment identification.

- **Purpose**: Distinguish notifications from different environments (e.g., "PROD", "TEST", "DEV")
- **Format**: Appended to notification titles with dash separator
- **Applied to**: Slack message title, Gmail subject line, Gmail HTML body `<h3>` tag
- **Empty/whitespace handling**: Treated as "not set" (no suffix added)

**Usage:**
```bash
export NOTIFICATIONS=ALL
export NOTIF_MSG="PROD"
python main-yt-dlp.py --only-audio "URL"
# Slack: "🚀 Download STARTED - PROD"
# Gmail subject: "🚀 yt-dlp Download STARTED - PROD"
```

**Implementation:** Read in `main()` and passed to all `send_all_notifications()` calls.

### FFMPEG_OPTS
Optional ffmpeg audio-filter string injected into the `ExtractAudio` postprocessor during audio extraction. Mirrors the `FFMPEG_OPTS` convention in the sister `losslesscut-csv` project.

- **Format**: body of an ffmpeg `-af` filter chain (e.g. `'volume=2.0'`, `'loudnorm=I=-16:TP=-1.5:LRA=11'`)
- **Applied to**: audio extraction only (mp3 / m4a / flac). Video downloads are untouched.
- **Scope**: passed to yt-dlp as `--postprocessor-args ExtractAudio+ffmpeg:-af <value>` — confined to the audio-extraction PP so it does not break the `EmbedThumbnail` / `Metadata` / `FixupM4a` postprocessors (all of which use `-c copy` and would crash on `-af`).

**Usage:**
```bash
# Linux/WSL/macOS — double amplitude
FFMPEG_OPTS='volume=2.0' python main-yt-dlp.py --only-audio --audio-format m4a "URL"

# EBU R128 normalisation
FFMPEG_OPTS='loudnorm=I=-16:TP=-1.5:LRA=11' python main-yt-dlp.py --only-audio "URL"
```

**Implementation:** read in `extract_single_format()` (`funcs_for_main_yt_dlp/download_audio.py`); empty/unset is the normal case and is a no-op.

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
- **Start message**: URL, selected parameters (with-audio, only-audio, title, artist, album)
- **Success/failure/cancellation message**: All parameters, file counts, elapsed time
- **Slack format**: Markdown with `*bold*` and bullet points
- **Gmail format**: HTML email with subject line indicating status

### File Counting
The script accurately tracks only files created during the current run:
- Counts existing files in output directories before download starts
- Counts final files after download completes
- Reports the difference (newly created files only)
- Works correctly even if output directories contain files from previous runs
- Applies to video files (yt-videos/), audio files (yt-audio/, yt-audio-mp3/, yt-audio-flac/)

### Architecture
Notifications use a strategy pattern in the shared `common_av.notifications` package (promoted from this repo to `common-av-codebase`):
- `base.py` - NotificationHandler abstract base class
- `slack_notifier.py` - SlackNotifier implementation
- `gmail_notifier.py` - GmailNotifier implementation
- `message_builder.py` - Shared message formatting
- `__init__.py` - Exports + `send_all_notifications()` helper

`main-yt-dlp.py` imports these via `from common_av.notifications import ...`.

### Troubleshooting Gmail
If you get "Authentication failed" errors:
```bash
# Run diagnostic tool
python Tests-Standalone/test_gmail_auth.py
```
This will test your Gmail configuration and show specific error messages.

## Linting

The project uses `run-linters.py` (project root) to run all linting tools. Each tool can be run individually or all in parallel via Claude sub-agents.

### Available Tools

| Tool | Purpose |
|------|---------|
| `ruff` | Style + unused imports (replaces flake8 + isort) |
| `mypy` | Static type checking |
| `ty` | Fast type checker (Astral; stricter than mypy) |
| `bandit` | Security scanning |
| `pip-audit` | Dependency CVE scanning |
| `deptry` | Unused/missing/misplaced dependency detection |
| `pydoclint` | Docstring linting |
| `pylint` | Code quality |
| `vulture` | Dead code detection |
| `radon` | Cyclomatic complexity (informational only) |
| `freshness` | Outdated packages with release age + New/Stable badge; generates upgrade scripts (informational, opt-in) |
| `pyupgrade` | Syntax modernisation (modifies files in place) |
| `eslint` | JavaScript linting (`JS-files/`) |
| `jshint` | JavaScript linting (`JS-files/`) |

### Running One or More Tools
```bash
source ../.venv-av-linux/bin/activate && python run-linters.py --tool ruff
python run-linters.py --tool ruff mypy pylint   # several tools; rich PASS/FAIL summary at the end
```

`--tool` accepts one or more names. Each runs, its pass/fail is cached, and a `rich` columnar
summary of every invoked tool is printed at the end (the run-all path prints it too). Exit code
is `0` only if all passed, else `1`.

### List All Tools
```bash
python run-linters.py --list
```

### Running All Linters (Claude Sub-Agent Workflow)

When asked to "run linters" or "lint the code", Claude should:
1. Call `python run-linters.py --list` to get tool names
2. Spawn **one `general-purpose` sub-agent per tool in parallel** (single message, multiple Agent tool calls)
3. Each sub-agent runs: `source ../.venv-av-linux/bin/activate && python run-linters.py --tool <name>`
4. Report pass/fail summary after all sub-agents complete

### Notes
- `radon` always exits 0 (complexity is informational)
- `freshness` always exits 0 (opt-in via `--tool freshness`; needs network). Venv-scoped, so output is identical from any sibling; pre-releases and intentional caps (e.g. `skylos <4.12`) are excluded, mirroring what `pip-compile --upgrade` can move. Renders a `rich` table (Package / Current / Latest / Age (days) / Action) where **Age** is days since the latest release was published on PyPI with a red **`New`** (`< 8` days) / green **`Stable`** (`≥ 8` days) badge, and **Action** flags sdist-only releases as `⚠ build from source`. It then writes `pip-upgrade-stable.sh` + `pip-upgrade-stable.ps1` (gitignored) containing only the Stable packages and interactively offers to display/run the platform-appropriate one (non-interactive callers skip the prompts). Implemented by `run_freshness()` in the shared `common_linters/linters_funcs.py`
- `pyupgrade` detects modifications via file hashes (not `git diff`); exit code 1 means files were changed (review + commit required)
- `eslint` and `jshint` are skipped automatically when no JS files are found
- `EXCLUDED_DIRS` is defined in `project_defs.py` — edit there to change which directories are excluded from linting (most tools)
- `bandit` exclusions and skips are configured in `[tool.bandit]` in `pyproject.toml`
- `deptry` exclusions are configured in `[tool.deptry]` in `pyproject.toml`
- `ty` exclude list is hardcoded in `_build_cmd()` in `run-linters.py` (mirrors bandit exclude pattern)
- Running with no arguments runs all tools sequentially (radon excluded)
- `flake8` and `isort` were removed — replaced by `ruff`
- The tool list comes from the shared `common_av.linters_defs.LINTER_TOOLS` (single source of truth across the sibling projects). `run-linters.py` filters it locally via `_FULLY_EXCLUDED={'deadcode'}` / `_DEFAULT_SKIP={'skylos'}`; the canonical (blocking) subset for the hook is `common_av.linters_defs.CANONICAL_LINTER_TOOLS`

### Git Pre-Commit Hook

A tracked git hook lints staged `.py`/`.js` changes with the canonical linters before each commit. Enable it once per clone (`.git` is shared between WSL and Windows, so one install covers both):

```bash
python Utils/install-git-hooks.py              # enable  (sets core.hooksPath=git-hooks)
python Utils/install-git-hooks.py --uninstall  # disable (unsets core.hooksPath)
```

- `git-hooks/pre-commit` — POSIX `sh` shim selecting the shared per-OS venv; prepends its bin to `PATH` (hooks run without the venv activated).
- `git-hooks/pre_commit_lint.py` — runs `CANONICAL_LINTER_TOOLS` (ruff, mypy, bandit, pydoclint, pylint, vulture, pyupgrade) via `run-linters.py`; **skips** commits that touch only docs or only a `VERSION = ...` line; exits 1 (blocks) on any failure. Bypass with `git commit --no-verify`.
- The hook is **not active until installed** — `core.hooksPath` is a per-clone setting.