# Changelog — Main Scripts

All notable changes to the main scripts (`main-yt-dlp.py`, `main-ertflix-series.py`, and their ERTFlix capture helpers) are documented in this file. Utility-script history is in [CHANGELOG-Utils.md](CHANGELOG-Utils.md); project-wide tooling/dependency history is in [CHANGELOG-Project.md](CHANGELOG-Project.md).

## [2026-06-15-1324] - CLI help: --version last; README sync

### Changed
- **`funcs_for_main_yt_dlp/utilities.py`** (`VERSION` → `2026-06-15-1324`): `--version` is now the last option before the mutually-exclusive audio group in `--help` (was listed before `--list-chapters`).
- **`README.md`**: synced the usage/help block with the current CLI — added the missing `--list-chapters {json,manual}` and `--show-urls` entries and reordered `--version` to last.

## [2026-06-15-1240] - Chapter CSV: --list-chapters json|manual, tracklist recovery, cleanups

### Changed
- **BREAKING — flag rename**: `--list-chapters-only` (boolean) → **`--list-chapters {json,manual}`**. `json` keeps the previous behavior (CSV from yt-dlp's native chapters); `manual` parses a title-first numbered tracklist from the description. `validate_list_chapters_only` → `validate_list_chapters` (`funcs_for_main_yt_dlp/utilities.py`, `__init__.py`); `main-yt-dlp.py` updated throughout.
- **`funcs_video_info/chapters.py`** (`VERSION` → `2026-06-15-1240`):
  - **Manual tracklist parser** (`_parse_numbered_tracklist`, `NUMBERED_TRACKLIST_PATTERN` in `project_defs.py`): recovers segments YouTube's auto-chapters drop when their start times overlap/precede the previous line (title-first `NN. Title  START - END` format). Emits every row as-is (no sort/dedup/overlap-filter); `manual` warns and falls back to native chapters when no tracklist is found. The chapter source is resolved once in `detect_chapters` so the count, on-screen display, and CSV are consistent.
  - **Song-title cleanup** (`_clean_song_title`): strips a leading `NN.`/`N.` track sequence and trailing periods (applied to the CSV song name and the split filename map).
  - **Duplicate handling**: identical CSV song names get a unique suffix (`name(01)`, `name(02)`, …) and every occurrence of any repeated name is marked **`SKIP`** in the comment column (e.g. recurring `Συνέντευξη` interview breaks), so the losslesscut-csv step skips them.
  - **Year column**: written only in the first CSV row; subsequent rows use `-`.

### Fixed
- **`main-yt-dlp.py`**: force UTF-8 stdout/stderr at startup (`_force_utf8_console`), fixing a `UnicodeEncodeError: 'charmap'` crash when printing Greek chapter titles on a cp1252 Windows console.

## [2026-06-14-1720] - Composer label matching: case/diacritics-insensitive + extendable

### Changed
- **`funcs_video_info/composer_extraction.py`** (`main-yt-dlp.py` `VERSION` → `2026-06-14-1720`): composer-credit matching is now case- and diacritics-insensitive and accepts all three orderings — `Μουσική`, `Μουσική/Στίχοι`, and `Στίχοι/Μουσική` (lyrics-only is ignored). The music/lyrics words come from extendable module-level lists (`MUSIC_LABELS` / `LYRICS_LABELS`) so synonyms can be added later. The description is scanned line by line and the first non-empty music credit wins; the captured name keeps its original spacing and diacritics.
- **`funcs_for_main_yt_dlp/download_audio.py`**: removed the `Video has uploader: ...` log line.
- **Tests**: `Tests/test_composer_extraction.py` extended for the reversed order, uppercase/accent-less labels, name-diacritics preservation, and lyrics-only being ignored.

## [2026-06-14-1658] - Set Composer tag from the Greek song description

### Added
- **`funcs_video_info/composer_extraction.py`** (new): `extract_composer_from_description()` parses a Greek video description for a `Μουσική:` or `Μουσική/Στίχοι:` (music / music & lyrics) credit and returns the composer name. Whitespace around the slash and colon is tolerated; the name keeps its internal spacing and is captured to the end of that line. Re-exported from `funcs_video_info`.
- **`funcs_for_main_yt_dlp/download_audio.py`** (`main-yt-dlp.py` `VERSION` → `2026-06-14-1658`): when extracting audio from a single video, the composer parsed from the (already-fetched) description is embedded as the **Composer** tag in mp3/m4a/flac via a yt-dlp `--parse-metadata` directive (sets `meta_composer`), and logged. `extract_single_format()` gained a `composer_pat` parameter. Skipped for playlists, consistent with `artist` handling.
- **Tests**: `Tests/test_composer_extraction.py` (10 tests for the parser) and `TestComposerEmbedding` in `Tests/test_main_ytdlp.py` (3 tests — directive injection + derivation from the description).

## [2026-06-05-1404] - Source shared tag handlers + notifications from common_av

### Changed
- **`main-yt-dlp.py`**: notifications are now imported from `common_av.notifications` instead of the in-repo `funcs_notifications` package (promoted to the shared `common-av-codebase`). Behaviour is unchanged.
- **`funcs_audio_processing/` (`__init__.py`, `unified.py`)**: audio tag handlers are now imported from `common_av.tag_handlers` instead of the in-repo `funcs_audio_tag_handlers` package (also promoted to `common-av-codebase`).
- **`funcs_utils/`**: `setup_logging` and `remove_diacritics` are re-exported from `common_av.log_config` / `common_av.text` (the bodies moved to `common-av-codebase`); the public `funcs_utils` names are unchanged so existing imports keep working. Removed `funcs_utils/logger_config.py`.

## [2026-06-02-1714] - UTF-8 decode for captured subprocess output

### Fixed
- **`funcs_for_main_yt_dlp/_download_common.py`, `funcs_for_main_yt_dlp/external_tools.py`, `funcs_video_info/chapters.py`, `funcs_video_info/metadata.py`** (plus `Tests/e2e_main.py`, `Tests-Standalone/setup-chromedriver-windows.py`, `Tests-Standalone/test_real_mp3_tags.py`): added `encoding='utf-8', errors='replace'` to every text-mode output-capturing `subprocess.run` call (yt-dlp download + `--version`, the ffprobe chapter-count / video-info probes, and test helpers). On Windows the default cp1252 codec crashes the stdout/stderr reader thread on non-Latin-1 bytes (e.g. Greek filenames) in yt-dlp/ffprobe output, leaving `stdout`/`stderr` as `None`. Mirrors the `common_av.boost` fix that surfaced this class of bug.

## [2026-06-01-1932] - Default audio format m4a; remap audio output dirs

### Changed
- **`main-yt-dlp.py`** (`VERSION` → `2026-06-01-1932`): the default `--audio-format` is now **m4a** (was mp3).
- **`project_defs.py`**: `DEFAULT_AUDIO_FORMAT` `'mp3'` → `'m4a'`. Replaced the generic `AUDIO_OUTPUT_DIR` constant with format-specific dirs: `AUDIO_OUTPUT_DIR_M4A='yt-audio'` (m4a is the default → primary dir), `AUDIO_OUTPUT_DIR_MP3='yt-audio-mp3'` (new), `AUDIO_OUTPUT_DIR_FLAC='yt-audio-flac'` (unchanged). `EXCLUDED_DIRS` and `.gitignore` add `yt-audio-mp3`.
- **`funcs_for_main_yt_dlp/file_organization.py`, `funcs_utils/file_operations.py`, `Utils/main-convert.py`**: use the format-specific output-dir constants.
- **Tests**: `conftest.py` fixtures and `test_main_ytdlp.py` assertions updated for the new default format and output dirs. Legacy `yt-audio-m4a/` on disk is left as-is (no migration).

## [2026-06-01-1206] - Skip playlist/chapter probes for non-YouTube URLs

### Changed
- **`main-yt-dlp.py`**: the playlist check (`is_playlist`) and chapter check (`detect_chapters`) — both YouTube-specific network probes — now run only for domains known to support those capabilities. Non-YouTube URLs (e.g. resolved ERTFlix CDN playback URLs, Facebook) skip the probes and are treated as not-a-playlist / no-chapters, avoiding wasted yt-dlp round-trips.
  - **`project_defs.py`**: added `PLAYLIST_CAPABLE_DOMAINS` / `CHAPTER_CAPABLE_DOMAINS` (both `= VALID_YOUTUBE_DOMAINS` today). A new domain is opted into either check by editing one tuple.
  - **`funcs_video_info/url_validation.py`**: added `are_playlists_supported()` / `are_chapters_supported()` (exported from `funcs_video_info`), used to gate the two checks.
- **Tests**: added capability-helper unit tests and a non-YouTube flow test asserting the probes are not called (40 tests pass).

## [2026-05-23-2218] - Stop filling Album Artist (reserve it for dupe staging)

### Changed
- The download/tagging pipeline no longer writes **Album Artist** (it had duplicated the Artist value). The Greek-singles duplicate-staging workflow uses Album Artist for its `DUPE-ORIGIN` marker, so the field is now left unset; **Artist is still set** everywhere it was.
  - **`funcs_audio_processing/unified.py`**: Greek-artist detection and the chapter-file uploader fallback set only the Artist tag.
  - **`funcs_for_main_yt_dlp/download_audio.py`**: dropped the yt-dlp `--parse-metadata album_artist:%(...)s` injection (and the now-unused `album_artist_pat` parameter of `extract_single_format`); still embeds `artist`.
  - **`funcs_for_main_yt_dlp/_download_common.py`**: `--artist` custom metadata no longer also writes `album_artist`.
- Affects new downloads only. Existing files keep their Album Artist until the dupe workflow processes them (staging overwrites it, restore clears it).

## [2026-05-15-1551] - Add FFMPEG_OPTS env var for audio-extraction filter

### Added
- **`funcs_for_main_yt_dlp/download_audio.py`**: `extract_single_format()` now reads `FFMPEG_OPTS` from the environment and passes it to yt-dlp as `--postprocessor-args ExtractAudio+ffmpeg:-af <opts>`. Lets the user boost (`volume=2.0`) or normalise (`loudnorm=I=-16:TP=-1.5:LRA=11`) extracted audio without a separate post-pass. Mirrors the FFMPEG_OPTS convention used in the sister `losslesscut-csv` project. Scoped to the `ExtractAudio` postprocessor only — a bare `ffmpeg:` prefix would also apply `-af` to `EmbedThumbnail` / `Metadata` / `FixupM4a` (all of which use `-c copy`) and crash the embed step, leaving an orphan `.webp` and a tag-less m4a.

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

## [2026-03-13-1803] - Fix ERTFlix mobile redirect when DevTools docked to side

### Fixed
- **`JS-files/capture-working-play-click.js`**: Added instruction to dock DevTools to the bottom (not the side). Docking to the side narrows the main window below ERTFlix's responsive breakpoint, causing it to show a mobile-app suggestion page instead of the episode list. Applies to both Chrome and Firefox. VERSION bumped to `2026-03-13-1803`.

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
