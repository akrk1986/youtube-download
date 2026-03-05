# Changelog

All notable changes to this project will be documented in this file.

## [2026-03-05-1139] - Type Safety Review + PEP 8 Blank Lines

### Changed
- **Type annotations**: replaced bare `dict`/`list` with parameterized generics (`dict[str, Any]`, `list[NotificationHandler]`) across 9 files
- **Modern union syntax**: replaced `Optional[str]` with `str | None` in `funcs_notifications/message_builder.py`
- **Type narrowing**: added explicit `video_info is not None` guards in `main-yt-dlp.py` to fix mypy `union-attr` errors
- **PEP 8 blank lines**: fixed all E302/E303/E305 violations — added missing 2-blank-line separators between top-level functions in 5 files (`common.py`, `unified.py`, `artist_search.py`, `logger_config.py`, `main-get-artists-from-trello.py`)
- **CLAUDE.md**: documented type annotation conventions (modern union syntax, parameterized generics) and PEP 8 blank line rules

## [2026-03-04-1303] - ERTFlix Tests Rewrite + Code Style Fixes


### Fixed
- **ERTFlix token handler tests**: rewrote `TestResolveErtflixTokenUrl` to match the current URL-parsing implementation (8 obsolete subprocess-mocking tests replaced with 4 accurate tests). The handler no longer calls yt-dlp as a subprocess — it extracts the playback URL directly from the `content_URL` query parameter.
  - File: `Tests/test_ertflix_token_handler.py`

### Changed
- **Code style fixes** across recently refactored modules:
  - `funcs_audio_processing/__init__.py`: replaced deprecated `from typing import Type` with built-in `type[]` (Python 3.9+)
  - `funcs_for_audio_utils/boost.py`: fixed function signature indentation to hanging-indent style
  - `funcs_for_audio_utils/conversion.py`: removed redundant type annotations from `Args:` docstrings; dropped unnecessary `_ = subprocess.run(...)` discards
  - `funcs_video_info/url_extraction.py`: widened `file_path` parameters to `Path | str`; replaced `open()` with `Path.read_text()`
- **CLAUDE.md**: updated test counts (101 total: 37 main, 19 security, 10 ertflix, 35 notifications)
- **Docs/CHANGELOG.md**: renamed to `Docs/CHANGELOG-old.md`

## [2026-02-28-1504] - Add --list-chapters-only Flag

### Added
- **`--list-chapters-only` flag**: lists chapters, creates segments CSV in `yt-chapters/`, downloads the video, then stops — skipping chapter remux, audio extraction, file organization, and audio tagging
  - Aborts with a clear error if the video has no chapters
  - Aborts with a clear error if a playlist URL is provided
  - Mutually exclusive with `--with-audio`, `--only-audio`, `--subs`, `--split-chapters`
  - Files: `main-yt-dlp.py`, `Tests/conftest.py`

## [2026-02-27-2128] - LosslessCut-csv Format + Output Dir Checks + yt-chapters/ Directory

### Changed
- **CSV format updated** to match LosslessCut-csv input format:
  - `album art timestamp` column added as column 2 (between `start time` and `end time`)
  - Each data row has an empty field for this column (LosslessCut-csv auto-selects)
  - `song name` field is sanitized to a valid filename (Linux + Windows), stripped of whitespace, and truncated to 60 characters
  - `artist name` and `album name` are mandatory in LosslessCut-csv: first row gets `Artist-name` / `Album-name` as placeholders; subsequent rows get `-`
  - File: `funcs_video_info/chapters.py`

### Added
- **Pre-flight directory check** for `--split-chapters` runs:
  - Aborts with a clear error if any output directory is non-empty before starting
  - Prevents mixing chapters from different videos in the same output directory
  - New helper `_check_output_dirs_empty()` in `main-yt-dlp.py`
- **Dedicated `yt-chapters/` output directory** for the segments CSV file:
  - CSV is now written to `yt-chapters/segments-hms-full.txt` instead of `yt-videos/`
  - The directory is created automatically when needed
  - `yt-chapters/` is excluded from git (added to `.gitignore`)
  - CSV is now created for both video and audio-only runs (`--only-audio --split-chapters` now also produces the CSV)

## [2026-02-27-1827] - Shared Virtual Environment

### Added
- **Shared virtual environment** at the `PycharmProjects` root level, replacing per-project venvs for both `LosslessCut-csv` and `youtube-download`
  - Windows: `C:\Users\user\PycharmProjects\.venv-3.14\` (Python 3.14)
  - Linux/WSL: `/mnt/c/Users/user/PycharmProjects/.venv-linux\` (system Python)
  - Combined `requirements.txt` at `PycharmProjects\requirements.txt`
- Updated `README.md` installation section to reference the shared venv

## [2026-02-18-1051] - Embed Thumbnail in Downloaded Videos

### Added
- **Embedded thumbnail in MP4 video downloads**: yt-dlp now embeds the YouTube thumbnail as cover art directly into the MP4 container
  - Windows Explorer displays the video thumbnail instead of the generic player icon
  - Implemented by adding `--embed-thumbnail` flag to `run_yt_dlp()` in `funcs_for_main_yt_dlp/download.py`
  - Chapter remuxing (`remux_video_chapters`) preserves the embedded thumbnail automatically via stream copy
  - Audio downloads (`extract_single_format`) already had `--embed-thumbnail` — no change needed there

## [2026-02-16-1738] - Enhanced Notification System

### Added
- **NOTIFICATIONS environment variable** now supports granular control:
  - `S` or `s` - Slack notifications only
  - `G` or `g` - Gmail notifications only
  - `ALL` or `all` - Both Slack and Gmail notifications
  - Empty / `N` / `NO` - No notifications (default)
- **NOTIF_MSG environment variable** for adding custom suffixes to notification titles
  - Helps distinguish notifications from different environments (e.g., "PROD", "TEST", "DEV")
  - Applied to Slack message title, Gmail subject line, and Gmail HTML body `<h3>` tag
  - Whitespace-only values are ignored

### Changed
- **BREAKING**: Default notification behavior changed from enabled to disabled (opt-in model)
- **BREAKING**: Removed legacy `Y`/`YES` values for NOTIFICATIONS - use `ALL` instead
- Invalid NOTIFICATIONS values now log warning and disable notifications (previously enabled them)

### Technical Details
- Modified 6 files in `funcs_notifications/` package to support `notif_msg_suffix` parameter
- Added `notif_msg_suffix` parameter to all notification functions and handlers
- Created comprehensive test suite: 35 new tests in `Tests/test_notifications.py`
- All tests passing, mypy clean, no new flake8 errors

### Migration Guide
Users need to update their environments:
- Change `NOTIFICATIONS=Y` or `NOTIFICATIONS=YES` → `NOTIFICATIONS=ALL`
- If relying on default enabled behavior, explicitly set `NOTIFICATIONS=ALL`

## [2026-02-15-1621] - Previous Version

(Earlier changes documented elsewhere)
