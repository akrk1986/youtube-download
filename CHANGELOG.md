# Changelog

All notable changes to this project will be documented in this file.

## [2026-04-20-2238] - Refactor main-yt-dlp.py: move helpers into support modules

### Changed
- **`main-yt-dlp.py`** reduced from 747 to 413 lines by moving 9 helper functions into existing modules:
  - `funcs_for_main_yt_dlp/file_organization.py`: `cleanup_leftover_files`, `check_output_dirs_empty`, `count_initial_files`, `count_new_files`
  - `funcs_for_main_yt_dlp/utilities.py`: `parse_arguments`, `parse_and_validate_audio_formats`, `get_custom_metadata`, `validate_list_chapters_only`, `determine_audio_mode`
  - `funcs_video_info/chapters.py`: `detect_chapters` (formerly `_detect_chapters`)
- `__init__.py` exports updated for both packages.
- Test patches updated: `get_chapter_count` mock replaced with `detect_chapters` mock.
- Pylint score: 8.78 → 8.79.

## [2026-04-20-2205] - ERTFlix: refactor dom_scraper into focused modules + UX polish

### Changed
- **`funcs_ertflix_automation/dom_scraper.py`** (445 lines) split into three focused modules:
  - `season_scraper.py` — `Season` dataclass, `discover_seasons`, `select_season`, selectors.
  - `episode_scraper.py` — `Episode` dataclass, `discover_episodes`, `dump_debug_dom`, polling helper.
  - `player_scraper.py` — `click_episode_play`, `extract_player_info`, info-dialog selectors.
- `__init__.py`, `cli_prompts.py`, and `main-ertflix-series.py` updated to import from the new modules.
- `dom_scraper.py` removed.

## [2026-04-20-1257] - ERTFlix series browser: episode enrichment + UX improvements

### Added
- **Episode table** now shows four columns: `#`, `Duration`, `Title`, `Description` — `_BROWSER_SCRAPE_SCRIPT` traverses the sibling `.row` container to extract duration (`h4.clr-pri-text-f` first text node) and description (`p[aria-label]`). `Episode` dataclass gains `episode_id`, `duration`, `description` fields (default `''`).
- **Language change window**: after the page loads and before scraping begins, the script notifies the user that now is the time to switch the page language in the browser if desired, then waits for Enter.
- **Navigation in pickers**: `q`/`0` quits from either picker; `s` in the episode picker goes back to the season selector. `BackToSeasons` exception added to `errors.py`.

### Fixed
- Season selector no longer matches episode play buttons whose titles contain the word "season" — removed `button[aria-label*="season" i]` from `SEASON_BUTTON_SELECTORS` (season pickers are `<div>` elements, not `<button>`s); dropped the `button` prefix from the two Greek-word selectors for the same reason.

### Changed
- `main()` season+episode selection loop extracted into `_pick_season_and_episode()` helper to reduce local-variable and statement counts (pylint 9.08 → 9.26).

## [2026-04-19-2157] - Interactive ERTFlix series browser (`main-ertflix-series.py`)

### Added
- **`main-ertflix-series.py`**: new top-level CLI that drives Chromium (via Playwright) to an ERTFlix series URL, scrapes seasons + episodes, prompts the user via arrow-key menus (with a numbered `input()` fallback for consoles where `prompt_toolkit` can't drive the TTY), captures the token API URL when Play is clicked, and hands off to `main-yt-dlp.py --ertflix-program`. Unknown flags are forwarded verbatim to the downloader.
  - `--program <name>` — sets `--title "<program> S<NN>E<NN>"` on the hand-off and mirrors the same string into `NOTIF_MSG` for Slack/Gmail notifications (e.g. `Parea S02E08`). Greek program names work too.
  - Always sets `NOTIFICATIONS=ALL` in the subprocess environment so the download emits start/success/failure notifications.
  - `--headless`, `--debug-dom`, `--token-timeout`, `--dry-run`, `--verbose`, `--profile-dir`.
  - Persistent Chromium profile at `.ertflix-profile/` (gitignored) — log in once, cookies survive across runs. `ensure_authenticated()` detects `#/landing` / `#/login` redirects and pauses the script so the user can sign in inside the headed window.
  - Season + episode numbering mirrors the page's newest-to-oldest order: the newest season/episode receives the highest index, so `S02E26` refers to the 2nd season's 26th episode (oldest in that season).
  - Dry-run uses `shlex.join()` for shell-safe quoting — the printed hand-off command is copy-paste-runnable even when `--title` contains whitespace.
- **`funcs_ertflix_automation/`** package — `browser_session`, `season_scraper`, `episode_scraper`, `player_scraper`, `cli_prompts`, `handoff`, `errors`.
- **`Tests/test_ertflix_automation.py`** — 10 pytest tests (argv builder, season/episode pickers, token-URL fragment constant).
- **Dependencies**: `playwright`, `questionary`, `rich` added to `pyproject.toml` and `requirements.txt`. One-time install: `uv sync && python -m playwright install chromium`.
- **`.gitignore`**: `.ertflix-profile/` and `Logs/ertflix-debug-*.html`.

### Notes
- Episodes are identified by their Play-button `aria-label` (i.e. the title shown in the UI), not by a regex against image URLs — the DOM-based scrape is resilient to ID naming-scheme changes on the ERTFlix side.
- `discover_episodes` polls a single `page.evaluate(...)` snapshot until the set of hydrated titles is stable for several rounds, so all 25–30 cards are captured even when Angular renders them in bursts.
- The browser interceptor attaches a `page.on('request', ...)` listener (observational) rather than `page.route()` — blocking the request would prevent ERTFlix from generating a token URL with a valid `content_URL`.

## [2026-03-20-1703] - main-convert.py: copy cover art when syncing tags

### Added
- **`main-convert.py`**: cover art (album artwork) is now copied from source to target file when syncing tags — previously only text tags were transferred
  - New `_extract_cover_art(file_path, fmt)` helper reads `APIC` frame (MP3) or `covr` atom (M4A)
  - New `_apply_cover_art(file_path, fmt, cover_data, mime)` helper writes the art after text tags are saved (so the ID3 save inside `apply_mp3_tags` does not overwrite the new `APIC` frame)
- **`Docs/main-convert-README.md`**: updated features list, optional arguments (`--prefix`), tag mapping table (cover art row), default directories, and notes to reflect all current functionality

## [2026-03-13-1803] - Fix ERTFlix mobile redirect when DevTools docked to side

### Fixed
- **`JS-files/capture-working-play-click.js`**: Added instruction to dock DevTools to the bottom (not the side). Docking to the side narrows the main window below ERTFlix's responsive breakpoint, causing it to show a mobile-app suggestion page instead of the episode list. Applies to both Chrome and Firefox. VERSION bumped to `2026-03-13-1803`.

## [2026-03-10-1818] - Sync run-linters improvements from LosslessCut-csv

### Changed
- **`pyproject.toml`**: added `[tool.bandit]` section with `exclude_dirs` and `skips = ['B101']` — bandit config now centralised alongside other tool configs
- **`run-linters.py`**: simplified bandit command to `bandit -r . -c pyproject.toml` (dropped inline `-x` and `--skip` flags); removed unused `root: Path` parameter from `_print_grouped_by_files()`
- **`CLAUDE.md`**: noted that bandit exclusions are configured in `pyproject.toml`

## [2026-03-09-1831] - Remove flake8 (replaced by ruff)

### Changed
- **`requirements.txt`**: removed `flake8` package (replaced by `ruff`)
- **`.flake8`**: deleted config file (no longer needed)
- **`CLAUDE.md`**: removed flake8 and isort from linting tools list (replaced by `ruff`)

## [2026-03-09-1817] - Security Review Fixes

### Fixed
- **`funcs_utils/security.py`**: replace `str.startswith()` with `Path.is_relative_to()` in `validate_file_path_security()` — fixes path-prefix bypass where a sibling directory (e.g. `yt-audio2`) could falsely pass the parent check for `yt-audio`
- **`funcs_video_info/url_validation.py`**: remove dead `except urllib.error.URLError` block in `get_timeout_for_url()` (urlparse never raises it); narrow broad `except Exception` to `except (ValueError, AttributeError)` in `validate_video_url()`
- **`funcs_utils/yt_dlp_utils.py`**: log a warning when `YTDLP_USE_COOKIES` is set to an unrecognized browser value instead of silently defaulting to Firefox

### Added
- **`Tests/test_security_measures.py`**: new `test_path_prefix_bypass` test covering the path-prefix fix (20 security tests, was 19)

## [2026-03-08-1924] - run-linters.py: --group-by-files mode

### Added
- **`run-linters.py`**: new `--group-by-files` flag that re-groups linting findings by source file instead of by tool
  - Works with `--tool <name>` (one tool) or alone (all tools sequentially)
  - New `Issue` dataclass (`filename`, `tool`, `text`)
  - `_run_tool_capture()` — silent variant of `_run_tool` that returns `(exit_code, output)`
  - Per-tool output parsers: `_parse_line_colon` (mypy/pylint/vulture/jshint), `_parse_ruff`, `_parse_bandit`, `_parse_radon`, `_parse_eslint`, `_parse_pyupgrade`
  - `_run_tool_grouped()` and `_print_grouped_by_files()` — grouped execution and display
  - `_build_cmd()` — centralised command builder (refactors all `run_*` functions to use it)
  - Fixed pydoclint parser: uses `_parse_radon` (bare filename + indented issues format)

## [2026-03-08-1923] - Linting Orchestration Script

### Added
- **`run-linters.py`**: new script that runs any of 10 linting tools (ruff, mypy, bandit, pydoclint, pylint, vulture, radon, pyupgrade, eslint, jshint) via `--tool <name>`; `--list` prints tool names for Claude sub-agent discovery
- **CLAUDE.md**: new "Linting" section documents all tools and the Claude parallel sub-agent workflow

### Fixed
- Pre-existing ruff E501/F401 violations in `file_organization.py`, `main-yt-dlp.py`, and `Tests-Standalone/scrape-with-selenium.py`

## [2026-03-08-1837] - pydoclint Docstring Fixes

### Fixed
- **DOC203** (return type mismatch): Added type prefixes to Returns sections across 30+ functions in `funcs_for_main_yt_dlp/`, `funcs_utils/`, `funcs_audio_processing/`, `funcs_notifications/`, `funcs_video_info/`, `main-yt-dlp.py`, `main-qb-notify.py`
- **DOC101/103** (missing args): Added missing `video_dir`/`chapter_name_map` to `organize_media_files` and `data` to `MessageBuilder.build_message`
- **DOC111** (type hints in docstring args): Removed type hints from Args sections in `greek_search` and `get_chapter_count`
- **DOC201** (no return section): Added Returns section to `parse_arguments`
- **DOC501/503** (missing Raises): Added `Raises` sections to `_extract_text_from_odt` (ImportError) and `get_timeout_for_url` (ValueError)
- **DOC502** (spurious Raises): Removed erroneous `SystemExit` Raises section from `validate_and_get_url` (uses `sys.exit()`, not `raise`)
- **pyproject.toml**: Added `allow-init-docstring = true` to suppress DOC301 globally (policy: document `__init__` args at the function, not the class)

## [2026-03-08-1708] - Ruff Linter Setup + Lint Fixes

### Added
- **`ruff.toml`**: ruff linter configuration (`line-length = 120`, rules E/W/F, `Beta/` and `.venv-*` excluded, I001 import-sorting suppressed)
- **`ruff` package**: added to `requirements.txt`

### Fixed
- **F401** (unused imports): removed or `# noqa`-suppressed unused imports across 12 files including `ertflix_token_handler.py`, `e2e_main.py`, standalone test scripts
- **F541** (f-strings without placeholders): removed `f` prefix from ~30 plain strings across test and main scripts
- **E501** (lines too long): wrapped long lines in `unified.py`, `chapter_remux.py`, `main-convert.py`, `main-yt-dlp.py`, and multiple standalone test files
- **W292** (no newline at end of file): added missing trailing newlines in 10 standalone test files
- **W293** (blank lines with whitespace): stripped trailing whitespace from blank lines in `main_greek_search.py` and `main-boost-mp3-or-mp4.py`
- **F841** (unused variables): replaced unused `result` with `_` in `test_rerun.py`; removed `as e` from 3 bare exception handlers
- **E402** (import not at top): moved `import smtplib` to top of `test_gmail_auth.py`

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
