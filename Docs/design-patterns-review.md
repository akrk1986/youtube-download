# Python Design Patterns Review

Review of the project codebase against KISS, SRP, Separation of Concerns, Composition over Inheritance, Rule of Three, Function Size, Dependency Injection, and Dead Code principles.

Excludes `Beta/` directory. Last updated: 2026-03-01.

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
- `funcs_audio_processing/mp3.py`, `m4a.py`, `flac.py` — clean wrappers (<25 lines each)
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

### 3. Code Duplication — Download Modules (High Priority)

**`funcs_for_main_yt_dlp/download_video.py`** (~150 lines) and **`download_audio.py`** (~135 lines) share ~60% of their logic:
- Both build yt-dlp command lists via scattered conditional `.insert()` calls
- Both have near-identical try/except/finally subprocess execution blocks
- Both handle timeout, format error, and general error the same way

**Applies:** Rule of Three, DRY

**Suggested fix:**
1. Extract `_build_yt_dlp_command(opts, format_str, extra_args)` — eliminates scattered `.insert()` logic
2. Extract `_run_yt_dlp_subprocess(cmd, timeout, show_progress)` — eliminates ~80 lines of duplication

---

### ~~4. Notification File-Count Duplication (Medium Priority)~~ ✅ RESOLVED

**Status:** Fixed in commit `ee4f104`. Extracted `_count_new_files()` helper, eliminating the 3x duplication of file-counting logic across success, cancelled, and failure notification handlers.

---

### 5. Mixed Concerns in `chapters.py` (Medium Priority)

**`display_chapters_and_confirm()`** (64 lines) does:
- Builds filename mapping
- Formats a display table
- Prints to console
- Returns mapping data

**`create_chapters_csv()`** (89 lines) also re-derives filename mapping internally.

**Applies:** SRP, DRY

**Suggested fix:** Build mapping once and pass it to both functions.

---

### 6. Near-Identical Tool Path Functions (Medium Priority)

**`funcs_for_main_yt_dlp/external_tools.py`** — `get_ffmpeg_path()` and `get_ytdlp_path()` are near-identical: Windows path check → Linux PATH check → exit on failure. Only the tool name and path differ.

**Applies:** KISS, DRY

**Suggested fix:** Create `_verify_tool_exists(tool_name, windows_path)` helper.

---

### 7. AudioBooster Hierarchy Over-Engineering (Medium Priority)

**`funcs_for_audio_utils/boost.py`** — `AudioBooster` base class + `MP3Booster` / `MP4Booster` subclasses. The only difference: MP4Booster adds `-c:v copy` to preserve the video stream. Two subclasses for a single boolean flag is over-engineering.

**Applies:** KISS, Composition over Inheritance

**Suggested fix:** Single class with `preserve_video: bool = True` parameter.

---

### 8. Command Building Mixed with Execution (Medium Priority)

**`download_video.py:55-105`** and **`download_audio.py:57-102`** — Commands are built via scattered conditional `.insert(1, ...)` calls interleaved with logic. Hard to see the final command without tracing all paths.

**Applies:** Separation of Concerns

**Suggested fix:** Separate command construction (pure logic) from execution (I/O).

---

### 9. Wrapper Duplication — Audio Processing (Medium Priority)

**`funcs_audio_processing/mp3.py`**, **`m4a.py`**, **`flac.py`** are nearly identical — each wraps `unified.py` with its handler class. The difference is only the handler type. A dispatch dict in `unified.py` would eliminate all three files.

**Applies:** DRY, KISS

---

### 10. Pointless Wrapper in `url_extraction.py` (Low Priority)

**`funcs_video_info/url_extraction.py:150`** — `_is_valid_domain()` is a one-liner that just calls `is_valid_domain_url()`. No added behavior.

**Applies:** Dead Code / KISS

**Suggested fix:** Remove wrapper, call `is_valid_domain_url()` directly.

---

### 11. Hard-Coded Dependencies (Low Priority)

- **`funcs_for_audio_utils/boost.py:11`** — `FFMPEG_EXE = get_ffmpeg_path()` called at module import time (side effect)
- **`funcs_for_audio_utils/conversion.py:13-55`** — ffmpeg path re-detected on every function call
- **`funcs_utils/logger_config.py:47`** — Log directory hard-coded to `Path(__file__).parent / 'Logs'`

**Applies:** Dependency Injection

**Suggested fix:** Accept paths as optional parameters with default getters.

---

## Convention Violations

In addition to the architectural issues above, the following project convention violations were found:

| Rule | Count | Files |
|---|---|---|
| `else`/`elif` after `return`/`exit` | 8 | `utilities.py`, `file_organization.py`, `url_validation.py`, `string_sanitization.py`, `chapter_extraction.py` |
| Missing type hints | 1 | `boost.py` (`__init__` missing `-> None`) |
| `datetime` instead of `arrow` | 1 | `logger_config.py:74` |
| ~~Hardcoded argparse default~~ | ~~0~~ | ~~Fixed in commit `ee4f104`~~ |
| ~~Missing type hint on `_execute_main` args~~ | ~~0~~ | ~~Fixed in commit `ee4f104`~~ |

---

## Priority Summary

| Priority | Issue | Principle | Status |
|---|---|---|---|
| ~~High~~ | ~~`_execute_main()` ~300-line god function~~ | ~~SRP, Function Size~~ | ✅ Resolved |
| ~~High~~ | ~~`main()` ~153-line function with duplicated notification logic~~ | ~~SRP, Function Size~~ | ✅ Resolved |
| High | `download_video.py` / `download_audio.py` ~60% duplication | Rule of Three, DRY | Open |
| ~~Medium~~ | ~~Notification file-count logic duplicated 3x in `main()`~~ | ~~Rule of Three~~ | ✅ Resolved |
| Medium | `chapters.py` filename mapping computed twice | SRP, DRY | Open |
| Medium | `get_ffmpeg_path()` / `get_ytdlp_path()` near-identical | KISS, DRY | Open |
| Medium | `AudioBooster` two subclasses for one boolean difference | KISS, Composition | Open |
| Medium | Command building mixed with execution | Separation of Concerns | Open |
| Medium | `mp3.py` / `m4a.py` / `flac.py` wrapper duplication | DRY, KISS | Open |
| Low | Pointless `_is_valid_domain()` wrapper | Dead Code | Open |
| Low | Hard-coded ffmpeg paths and log directory | Dependency Injection | Open |
| Low | 10 convention violations (elif/else, type hints, datetime) | Project Conventions | Open |

---

## Overall Assessment

The architecture is solid — good package boundaries, no circular dependencies, strong type safety, appropriate use of strategy pattern for audio handlers and notifications. Both god functions have been resolved: `_execute_main()` (previously ~300 lines) refactored into ~160 lines with 7 helpers, and `main()` (previously ~140 lines) refactored into ~65 lines with 3 helpers. The remaining weaknesses are **structural duplication** in the download and audio processing modules. None of these are fundamental design flaws; they're the natural result of organic growth and can be addressed incrementally.
