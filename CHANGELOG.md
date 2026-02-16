# Changelog

All notable changes to this project will be documented in this file.

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
