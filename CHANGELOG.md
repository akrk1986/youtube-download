# Changelog

All notable changes to this project will be documented in this file.

## [2026-02-27-2106] - LosslessCut-csv Format + Output Dir Checks + chapters/ Directory

### Changed
- **CSV format updated** to match LosslessCut-csv input format:
  - `album art timestamp` column added as column 2 (between `start time` and `end time`)
  - Each data row has an empty field for this column (LosslessCut-csv auto-selects)
  - File: `funcs_video_info/chapters.py`

### Added
- **Pre-flight directory check** for `--split-chapters` runs:
  - Aborts with a clear error if any output directory is non-empty before starting
  - Prevents mixing chapters from different videos in the same output directory
  - New helper `_check_output_dirs_empty()` in `main-yt-dlp.py`
- **Dedicated `chapters/` output directory** for the segments CSV file:
  - CSV is now written to `chapters/segments-hms-full.txt` instead of `yt-videos/`
  - The directory is created automatically when needed
  - `chapters/` is excluded from git (added to `.gitignore`)
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
