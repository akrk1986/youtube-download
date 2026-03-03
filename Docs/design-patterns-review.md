# Python Design Patterns Review

Review of the project codebase against KISS, SRP, Separation of Concerns, Composition over Inheritance, Rule of Three, Function Size, Dependency Injection, and Dead Code principles.

Excludes `Beta/` directory. Last updated: 2026-03-03.

---

## What's Working Well (Clean Modules)

### Strategy Pattern — Excellent
- `funcs_audio_tag_handlers/` — `AudioTagHandler` base class with MP3/M4A/FLAC handlers. Proper polymorphism for format-specific tag operations.
- `funcs_notifications/` — `NotificationHandler` base class with Slack/Gmail implementations. Clean strategy pattern.
- `funcs_notifications/message_builder.py` — `MessageBuilder` base with Slack/Email implementations. Clean format separation.

### Dataclasses for Parameter Grouping — Good
`DownloadOptions` in `_download_common.py` groups 8+ parameters into a single dataclass, avoiding long positional argument lists.

### Dependency Organization — Good
No circular dependencies. Clean package hierarchy: `main` → `funcs_for_main_yt_dlp` → `funcs_utils` / `funcs_video_info`. No upward dependencies.

### Security Layer — Good
`funcs_utils/security.py` — single-responsibility module with explicit allow-list for characters, list-based subprocess calls throughout.

### Clean Small Modules
- `funcs_video_info/chapters.py` — well-focused chapter display and CSV creation
- `funcs_utils/string_sanitization.py` — each function does one thing
- `funcs_utils/artist_search.py` — focused artist detection
- `funcs_audio_processing/__init__.py` — dispatch dict with backward-compatible aliases
- `main-get-artists-from-trello.py` — simple, focused
- `main-qb-notify.py` — simple, focused

---

## Issues Found

### ~~1. God Function — `_execute_main()` (High Priority)~~ ✅ RESOLVED

**Status:** Fixed in commit `ee4f104`. Extracted 7 private helper functions, reducing `_execute_main()` from ~300 lines to ~160 lines of orchestration:
- `_parse_and_validate_audio_formats()` — format parsing, validation, deduplication
- `_resolve_url()` — `--rerun`, interactive input, ERTFlix timeout, URL resolution
- `_get_custom_metadata()` — `--title`/`--artist`/`--album` prompting + playlist warnings
- `_detect_chapters()` — chapter detection, video info fetch, display
- `_validate_list_chapters_only()` — mutual exclusivity validation
- `_determine_audio_mode()` — ERTFlix mode + need_audio determination
- `_count_new_files()` — file counting for notifications (was duplicated 3x, see #4)

---

### ~~2. God Function — `main()` (High Priority)~~ ✅ RESOLVED

**Status:** Fixed. Extracted 3 private helper functions, reducing `main()` from ~140 lines to ~65 lines:
- `_build_notifiers()` — notifier construction based on `NOTIFICATIONS` env var
- `_count_initial_files()` — pre-download file counting
- `_send_completion_notification()` — consolidated success/cancelled/failure notification logic (was duplicated 3x)

Also moved the success notification out of `_execute_main()` into `main()`, simplifying `_execute_main()`'s signature by removing 3 parameters (`start_time`, `initial_video_count`, `initial_audio_count`).

---

### ~~3. Code Duplication — Download Modules (High Priority)~~ ✅ RESOLVED

**Status:** Fixed in commit `0d56f28`. Extracted shared helpers into `_download_common.py`:
- `build_yt_dlp_command()` — unified command construction for both video and audio
- `run_yt_dlp_subprocess()` — unified subprocess execution with error handling
Both `download_video.py` and `download_audio.py` now delegate to these shared functions.

---

### ~~4. Notification File-Count Duplication (Medium Priority)~~ ✅ RESOLVED

**Status:** Fixed in commit `ee4f104`. Extracted `_count_new_files()` helper, eliminating the 3x duplication of file-counting logic across success, cancelled, and failure notification handlers.

---

### ~~5. Mixed Concerns in `chapters.py` (Medium Priority)~~ ✅ RESOLVED

**Status:** Fixed in commit `4088d9c`. Extracted `_sanitize_chapter_title()` helper that centralizes the `sanitize_string()` + truncation pattern. Called by `_build_filename_mapping()` (for video title and chapter titles) and `create_chapters_csv()` (for song names), eliminating duplicated inline sanitization logic.

---

### ~~6. Near-Identical Tool Path Functions (Medium Priority)~~ ✅ RESOLVED

**Status:** Fixed in commit `4088d9c`. Extracted `_verify_tool_path(tool_path, version_flag, install_hint)` helper. Both `get_ffmpeg_path()` and `get_ytdlp_path()` are now 3-line wrappers that delegate to the shared helper.

---

### ~~7. AudioBooster Hierarchy Over-Engineering (Medium Priority)~~ ✅ RESOLVED

**Status:** Fixed. Replaced `AudioBooster` (ABC) + `MP3Booster` + `MP4Booster` with a single concrete `AudioBooster` class with `preserve_video: bool = False` parameter. Removed `abc` imports. Also made `ffmpeg_exe` lazy (no longer called at module import time).

---

### ~~8. Command Building Mixed with Execution (Medium Priority)~~ ✅ RESOLVED

**Status:** Fixed in commit `0d56f28`. Command construction (`build_yt_dlp_command()`) is now separated from execution (`run_yt_dlp_subprocess()`) in `_download_common.py`.

---

### ~~9. Wrapper Duplication — Audio Processing (Medium Priority)~~ ✅ RESOLVED

**Status:** Fixed. Replaced `mp3.py`, `m4a.py`, `flac.py` with a `_HANDLER_MAP` dispatch dict in `funcs_audio_processing/__init__.py`. Added `set_artists_for_format()` and `set_chapter_tags_for_format()` dispatch functions. Old function names kept as backward-compatible aliases. Simplified `audio_processing.py` from 3-branch if/elif to a simple loop.

---

### ~~10. Pointless Wrapper in `url_extraction.py` (Low Priority)~~ ✅ RESOLVED

**Status:** Fixed. Removed `_is_valid_domain()` wrapper, replaced with direct call to `is_valid_domain_url()`.

---

### ~~11. Hard-Coded Dependencies (Low Priority)~~ ✅ RESOLVED

**Status:** Fixed. All three cases now accept optional parameters with lazy defaults:
- `boost.py`: Removed module-level `FFMPEG_EXE = get_ffmpeg_path()`. Both `AudioBooster.__init__()` and `detect_audio_levels()` accept optional `ffmpeg_exe` parameter, auto-detected if `None`.
- `conversion.py`: `convert_mp3_to_m4a()` and `convert_m4a_to_mp3()` accept optional `ffmpeg_path` parameter, auto-detected if `None`.
- `logger_config.py`: `setup_logging()` accepts optional `log_dir` parameter, defaults to `funcs_utils/Logs/` if `None`.

---

## Convention Violations

In addition to the architectural issues above, the following project convention violations were found:

| Rule | Count | Files |
|---|---|---|
| ~~`else`/`elif` after `return`/`exit`~~ | ~~0~~ | ~~Fixed: `utilities.py`, `url_validation.py`, `string_sanitization.py`~~ |
| ~~Missing type hints~~ | ~~0~~ | ~~Fixed: `boost.py` (`__init__` now has `-> None`)~~ |
| ~~`datetime` instead of `arrow`~~ | ~~0~~ | ~~Fixed: `logger_config.py` now uses `arrow.now()`~~ |
| ~~Hardcoded argparse default~~ | ~~0~~ | ~~Fixed in commit `ee4f104`~~ |
| ~~Missing type hint on `_execute_main` args~~ | ~~0~~ | ~~Fixed in commit `ee4f104`~~ |

---

## Priority Summary

| Priority | Issue | Principle | Status |
|---|---|---|---|
| ~~High~~ | ~~`_execute_main()` ~300-line god function~~ | ~~SRP, Function Size~~ | ✅ Resolved |
| ~~High~~ | ~~`main()` ~153-line function with duplicated notification logic~~ | ~~SRP, Function Size~~ | ✅ Resolved |
| ~~High~~ | ~~`download_video.py` / `download_audio.py` ~60% duplication~~ | ~~Rule of Three, DRY~~ | ✅ Resolved |
| ~~Medium~~ | ~~Notification file-count logic duplicated 3x in `main()`~~ | ~~Rule of Three~~ | ✅ Resolved |
| ~~Medium~~ | ~~`chapters.py` chapter title sanitization duplicated~~ | ~~SRP, DRY~~ | ✅ Resolved |
| ~~Medium~~ | ~~`get_ffmpeg_path()` / `get_ytdlp_path()` near-identical~~ | ~~KISS, DRY~~ | ✅ Resolved |
| ~~Medium~~ | ~~`AudioBooster` two subclasses for one boolean difference~~ | ~~KISS, Composition~~ | ✅ Resolved |
| ~~Medium~~ | ~~Command building mixed with execution~~ | ~~Separation of Concerns~~ | ✅ Resolved |
| ~~Medium~~ | ~~`mp3.py` / `m4a.py` / `flac.py` wrapper duplication~~ | ~~DRY, KISS~~ | ✅ Resolved |
| ~~Low~~ | ~~Pointless `_is_valid_domain()` wrapper~~ | ~~Dead Code~~ | ✅ Resolved |
| ~~Low~~ | ~~Hard-coded ffmpeg paths and log directory~~ | ~~Dependency Injection~~ | ✅ Resolved |
| ~~Low~~ | ~~Convention violations (elif/else, type hints, datetime)~~ | ~~Project Conventions~~ | ✅ Resolved |

---

## Post-Review Anti-Pattern Fixes (2026-03-03)

After the design pattern refactoring, the `python-anti-patterns` skill checklist identified two additional issues in the changed code:

### Bare `except Exception` Catching Its Own Exception (`boost.py`)

`detect_audio_levels()` raised `RuntimeError('Failed to parse volume information')` inside a `try` block, which was then caught by `except Exception as e` and re-wrapped as `RuntimeError('Error detecting audio levels: RuntimeError: Failed to parse volume information')`. This double-wrapping obscured the real error.

**Fix:** The `try`/`except` now only wraps the `subprocess.run()` call, catching only `OSError` and `subprocess.SubprocessError`. The parse failure raises `RuntimeError` directly outside the `try` block.

### Missing Input Validation on Dispatch Dict Lookup (`funcs_audio_processing/__init__.py`)

`set_artists_for_format()` and `set_chapter_tags_for_format()` called `_HANDLER_MAP[audio_format]` without validation, raising a cryptic `KeyError` for unknown format strings.

**Fix:** Both functions now check `audio_format not in _HANDLER_MAP` and raise `ValueError` with a clear message listing valid options.

---

## Overall Assessment

The architecture is solid — good package boundaries, no circular dependencies, strong type safety, appropriate use of strategy pattern for audio handlers and notifications. All 11 issues from the review have been resolved. Key improvements: god functions broken down (items #1-#2), code duplication eliminated (items #3-#6, #9), over-engineering flattened (item #7), dead code removed (item #10), hard-coded dependencies made injectable (item #11), and convention violations fixed.
