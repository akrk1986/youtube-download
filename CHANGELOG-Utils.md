# Changelog — Utilities

All notable changes to the standalone utility scripts (`Utils/` and the URL-extraction helper in `Tests/`) are documented in this file. Main-script history is in [CHANGELOG.md](CHANGELOG.md); project-wide tooling/dependency history is in [CHANGELOG-Project.md](CHANGELOG-Project.md).

## [2026-05-20-2103] - Greek singles checker: cross-month duplicate mode

### Added
- **`funcs_check_greek_singles/`**: new `range` dupe mode that pools every month folder in the scanned range and clusters duplicates *across* months (a song downloaded into both `2021-03` and `2021-07` shows as one cluster — the per-folder check never grouped them because each month held only one copy). New `CrossMonthDupRow` dataclass (with `dup_count` / `distinct_months` properties), `query_cross_month_duplicates` query, `_add_cross_month_dup_table` renderer, and a `cross_month_duplicates` CSV section. The range report prints the active `DURATION_MATCH_MARGIN_SECONDS` at the top (e.g. `Duration margin: 4.0 secs`). `01-Singles-All` is excluded from the cross-month pool; the section is mode-only (not shown in the default full report).
- **`funcs_check_greek_singles/models.py`**: `InFolderDupMember` gained a `month_folder` field (per-file folder, needed because cross-month members span folders).
- **`funcs_check_greek_singles/database.py`**: extracted the duration single-linkage sweep into a shared `_cluster_by_duration(rows, key_func, margin)` generator, now used by both `query_in_folder_duplicates` and `query_cross_month_duplicates`.

### Changed
- **`Utils/main-check-greek-singles.py`** (**breaking CLI change**): replaced the boolean `--dupes-only` flag with `--dupes-scope {folder,range}` (default unset = full report). `--dupes-scope folder` = the old `--dupes-only` behavior (within-folder dupes); `--dupes-scope range` = the new cross-month mode and requires `--start-month`/`--end-month` (exits 2 otherwise). Still mutually exclusive with `--missing-action`.
- **`Utils/main-check-greek-singles.py`**: `DURATION_MATCH_MARGIN_SECONDS` default raised to `4.0` (now lives in `funcs_check_greek_singles/config.py`).

## [2026-05-20-1957] - Greek singles checker: parameterize duration margin in SQL (bandit B608)

### Fixed
- **`funcs_check_greek_singles/database.py`**: the three cross-folder match queries interpolated `DURATION_MATCH_MARGIN_SECONDS` into the SQL via f-string, which bandit flagged as B608 (possible SQL injection via string construction) — a false positive (project-controlled float) but a real anti-pattern. Switched to a bound `?` placeholder passed through `conn.execute(...)`, so the value never enters the SQL text. bandit Medium count 3 → 0; 100 tests still pass.

## [2026-05-20-1926] - Greek singles checker: extract duration margin to config module

### Changed
- **`funcs_check_greek_singles/config.py`** (new): owns `DURATION_MATCH_MARGIN_SECONDS` — a domain tuning value that didn't belong in the persistence layer. `database.py` and the tests import it from here; `__init__.py` lists the module in its architecture doc. Fixed a stale "default 1.0s" comment (the value is 3.0). Pure refactor, no behavior change.
- **`Utils/main-check-greek-singles.py`**: `VERSION` bumped to `2026-05-20-1926`.

## [2026-05-20-1900] - Greek singles checker: per-dupe rows in the duplicates table

### Changed
- **`funcs_check_greek_singles/models.py`**: new `InFolderDupMember` (file_path, raw_album, duration_seconds); `InFolderDupRow` now holds `members: tuple[InFolderDupMember, ...]` instead of a single representative album/duration. `dup_count` and `file_paths` became computed properties (existing call sites/tests unchanged).
- **`funcs_check_greek_singles/report.py`**: the in-folder duplicates table renders one row per file. Folder/Title/Artist print only on the first row of each cluster; every row carries a per-dupe serial (1, 2, 3...), the file's own album and duration, and the basename. A horizontal delimiter (`Table.add_section`) separates clusters. CSV gains per-file album + duration.
- **`funcs_check_greek_singles/database.py`**: `_build_in_folder_cluster` builds the per-file `members` tuple (sorted by file_path).
- **`Utils/main-check-greek-singles.py`**: `VERSION` bumped to `2026-05-20-1900`.

## [2026-05-20-1811] - Greek singles checker: margin-aware in-folder duplicate clustering

### Fixed
- **`funcs_check_greek_singles/database.py`**: the in-folder duplicate query bucketed by `GROUP BY ROUND(duration_seconds)`, which ignored `DURATION_MATCH_MARGIN_SECONDS` entirely — 168s and 171s landed in different ROUND buckets regardless of margin, so a 3-file cluster (2:48, 2:51, 2:51) reported as only the two 2:51s. Replaced the GROUP-BY query with a Python single-linkage sweep: `_QUERY_IN_FOLDER_CANDIDATES` fetches all tagged rows ordered by `(side, month_folder, norm_title, norm_artist, duration_seconds)`; `query_in_folder_duplicates` partitions via `itertools.groupby` and splits each partition wherever the consecutive-duration gap exceeds the margin (now a function parameter defaulting to the module constant, raised to `3.0`).

## [2026-05-19-1842] - Greek singles checker: in-folder duplicates + --dupes-only + configurable duration margin

### Added
- **`funcs_check_greek_singles/`**: fifth report section — clusters of ≥2 files within the *same* folder (`01-Singles-All` or a single month folder) sharing `(norm_title, norm_artist, duration within margin)`. New `InFolderDupRow` dataclass, `query_in_folder_duplicates`, `_add_in_folder_dup_table`, and a `in_folder_duplicates` CSV section. Summary line gains `Folder-dups: N`.
- **`Utils/main-check-greek-singles.py`**: `--dupes-only` flag runs only the in-folder duplicate check (skips cross-folder queries and the action prompt). Without a month range it scans `01-Singles-All/`; with one it scans the in-range month folders only. Mutually exclusive with `--missing-action`.

### Changed
- **`funcs_check_greek_singles/database.py`**: duration matching switched from `ROUND(a) = ROUND(b)` to `ABS(a - b) <= DURATION_MATCH_MARGIN_SECONDS` (new constant) across the three cross-folder queries. Inlined into the SQL via f-string (project-controlled value, no injection risk). Fixes the X.5 boundary case where 222.4 and 222.7 rounded to different integers and failed to match.

## [2026-05-19-1635] - Greek singles checker: deterministic action order + duration-aware match key

### Added
- **`Tests/test_check_greek_singles.py`**: new `TestDurationDisambiguation` class (4 tests) locks in the duration-aware matching — different durations don't match, identical durations do, `in_multiple_months` requires duration agreement, `in_multiple_months` still fires when all three durations align. `_make_song` / `_insert` test helpers gained an optional `duration_seconds` parameter (existing tests still pass since both sides default to `0.0`).

### Changed
- **`funcs_check_greek_singles/file_actions.py`**: `apply_missing_action` sorts candidates by filename before slicing to `limit`, so the partial-run prompt (`n` / `all` / `<N>`) selects a deterministic first-N across reruns. Previously the order followed the SQL query (by normalized title), which doesn't match the `ls`-like mental model the user works from.
- **`funcs_check_greek_singles/database.py`**: cross-folder match key extended from `(norm_title, norm_artist)` to `(norm_title, norm_artist, ROUND(duration_seconds))` in all three matching queries (`_QUERY_ONLY_IN_ALL`, `_QUERY_ONLY_IN_MONTHS`, `_QUERY_IN_MULTIPLE_MONTHS`). The `_QUERY_IN_MULTIPLE_MONTHS` `GROUP BY` extended with the same bucket so two different-duration singles don't collate. Motivating case: `BandaLaika.mp3` and `BandaLaika #2.mp3` carry identical `(title, artist)` tags but are different recordings; the duration bucket separates them so the missing one surfaces in `only_in_months` and becomes eligible for `--missing-action`. `SongKey` (the in-memory "is this song matchable" indicator) is unchanged — only the SQL predicate widened.
- **`Utils/main-check-greek-singles.py`**: `VERSION` bumped to `2026-05-19-1635`.

## [2026-05-19-1217] - Greek singles checker: --missing-action {copy,move} + --target-is-year

### Added
- **`funcs_check_greek_singles/file_actions.py`** (new): `ActionSummary` dataclass, `prompt_action_limit`, `apply_missing_action`, `_target_folder_name`. Post-report copy/move action for songs flagged as missing from `01-Singles-All/`. Source is the row's stored `file_path`; target is `01-Singles-All/<month-folder>/` (default) or `01-Singles-All/<YYYY>/` (with `--target-is-year`). Existing targets are overwritten. Per-file `OSError` is logged and counted as `failed`; the loop never aborts. Missing source files are counted as `skipped`.
- **`Utils/main-check-greek-singles.py`**: `--missing-action {copy,move}` (default: `None` = report-only, today's behavior) and `--target-is-year` (boolean, modifies action target naming; silently ignored without `--missing-action`). Both wire into a post-CSV block in `main()` that prompts the user before acting.
- **Three-way prompt** (`prompt_action_limit`): replaces the originally-planned y/N with `n` / `all` / `<integer N>` (case-insensitive, EOF→cancel). `n` cancels, `all` processes every row, `<N>` truncates to the first N (sorted by filename) for incremental/testing runs. Loops on invalid input with an error message.
- **`Tests/test_check_greek_singles.py`**: 12 new tests in `TestApplyMissingAction` covering copy/move semantics, overwrite, missing-source skipping, limit truncation, and the three-way prompt's accept/reject/clamp/re-prompt branches.

## [2026-05-18-2041] - Greek singles checker: typed query rows (refactor)

### Changed
- **`funcs_check_greek_singles/models.py`**: 3 new frozen dataclasses `MatchedRow` / `MultiMonthRow` / `UntaggedRow` to model query results explicitly. Eliminates the `sqlite3.Row` (untyped, dict-like) leak across module boundaries.
- **`funcs_check_greek_singles/database.py`**: `_row_to_matched` / `_row_to_multi_month` / `_row_to_untagged` mappers collapse the `or ''` / `or 0` NULL fallbacks into one place. The 4 query functions (`query_only_in_all` / `query_only_in_months` / `query_in_multiple_months` / `query_untagged`) now return typed lists.
- **`funcs_check_greek_singles/report.py`**: `_display_path(file_path, month_folder)` takes the two fields directly — the previous `'month_folder' in row.keys()` introspection is gone. Table builders, `render_console`, and `write_csv` consume the typed dataclasses; the total-size sum drops its `or 0` fallback (`size_bytes` is a non-Optional `int`).
- **`Utils/main-check-greek-singles.py`**: `only_in_all` annotation switches to `list[MatchedRow]`; `import sqlite3` dropped (no longer referenced); `VERSION` bumped to `2026-05-18-2041`.
- **`Tests/test_check_greek_singles.py`**: 8 dict-access sites flipped to attribute access; new `TestRowMappers.test_matched_row_handles_null_columns` exercises the mapper's NULL path via a raw SQL INSERT.

Schema unchanged, SQL queries unchanged, no new deps. Net win: mypy / Pyright now catch any future column-rename slip at the renderer/CSV boundary that previously would have produced a silent runtime `KeyError`.

## [2026-05-18-2010] - gitignore *.sqlite

### Changed
- **`.gitignore`**: added `*.sqlite`. The `Data/songs*.sqlite` snapshots produced by `Utils/main-check-greek-singles.py` are runtime artifacts (rolled over each run), not source — no need to surface them in `git status`.

## [2026-05-18-1933] - Greek singles checker: size totals, friendlier paths, serial #, fitted tables

### Added
- **`funcs_check_greek_singles/models.py`**, **`audio_reader.py`**, **`database.py`**: `Song` dataclass gains `size_bytes`; populated via `Path.stat().st_size` in `read_song`; mirrored into the `songs` table as `size_bytes INTEGER NOT NULL DEFAULT 0`.
- **`funcs_check_greek_singles/report.py`**: `_format_size()` (MB up to 1 GB, GB above). `only_in_months` section title now reads `Only in 03-Singles-by-Month (N of TOTAL songs are missing from 01-Singles-All, total size <X.XX GB|MB>)` — supports the user's mirroring workflow (every song kept twice: once in its month folder, once in `01-Singles-All/`).
- **`funcs_check_greek_singles/report.py`**: leftmost `#` column on every section table (4-char, right-justified, dim).
- **`Utils/main-check-greek-singles.py`**: `--console-width N` flag plus a `_resolve_console_width()` helper that uses `shutil.get_terminal_size(fallback=(140, 24))` so the Rich table fits the visible width even when PyCharm's Run console pipes stdout (no TTY → detection falls back).
- **`pyrightconfig.json`** + **`[tool.pyright]`** in `pyproject.toml`: point Pyright at the shared parent-dir `.venv-av-linux` venv so editor-side diagnostics stop flagging `arrow`/`pytest`/`mutagen` as unresolved imports. Mirrors the existing `[tool.mypy]` / `[tool.ty.environment]` configuration.

### Changed
- **`funcs_check_greek_singles/report.py`**: file paths in matched, multi-month and untagged tables now render as `All/<name>` (singles-all side) or `<month-folder>/<name>` (month side) via a new `_display_path()` helper — keyed off the row's `month_folder` column. Applied to both Rich tables and the CSV writer (only_in_all, only_in_months, in_multiple_months, untagged sections).
- **`funcs_check_greek_singles/report.py`**: tables switch to `expand=True` with `ratio=` priorities (Title/Artist/Album = 2, File/Found-in = 3) so they fill the console width and the right border stays visible. Removed the earlier `min_width=32` on the File column which was forcing the table wider than the terminal and clipping the right edge.
- **`funcs_check_greek_singles/report.py`**: section titles left-justified (`title_justify='left'`) — Rich's default centering looked misaligned against the surrounding left-aligned log/notice lines.
- **`funcs_check_greek_singles/report.py`**, **`Utils/main-check-greek-singles.py`**: section titles and log lines use full verbs for clearer reporting — e.g. `486 of 517 songs **are** missing from 01-Singles-All`, `Title-prefix filter **is** active`, `Month range **is** active`, `X songs are in 01-Singles-All AND missing from 03-Singles-by-Month/`, `X files are untagged (missing title and/or artist)`.

### Fixed
- **`funcs_check_greek_singles/audio_reader.py`**: `MONTH_FOLDER_RE` now `^\d{4}-(0[1-9]|1[0-2])([- ].+)?$` — the suffix separator is hyphen **or** space, so `2025-11-Nykhta Stasou` is correctly recognised as a month folder (previously rejected; only space-separated suffixes matched).

## [2026-05-18-1753] - Greek singles checker: month range filter + verbose progress

### Added
- **`Utils/main-check-greek-singles.py`**, **`funcs_check_greek_singles/audio_reader.py`**, **`funcs_check_greek_singles/database.py`**: `--start-month` / `--end-month` optional CLI args (format `yyyy-mm` or `yyyy`; the bare year expands to `yyyy-01` for start, `yyyy-12` for end). `iter_month_folders` now accepts inclusive bounds; `parse_month_arg` helper validates and normalizes the CLI value. When either bound is set, the `only_in_all` section is suppressed (3 reports instead of 4) — singles-all has no per-file month attribute, so narrowing only the months side would flood that section with false positives.
- **`funcs_check_greek_singles/audio_reader.py`**: `collect_songs` gained an optional `progress_every` parameter that emits a `Scanned N/total files in <dir>...` line at DEBUG every N files. Wired up for the 01-Singles-All scan (every 200 files) so a `--verbose` run on a 2k-song library shows pacing without per-file noise.

### Changed
- **`funcs_check_greek_singles/database.py`**, **`funcs_check_greek_singles/report.py`**, **`Utils/main-check-greek-singles.py`**, **`Tests/test_check_greek_singles.py`**: renamed `only_in_singles` section / query / CSV label to `only_in_all` — "01-Singles-All" is the "all" side and the new name reads cleanly alongside `only_in_months`.

## [2026-05-18-1221] - Add main-check-greek-singles utility

### Added
- **`Utils/main-check-greek-singles.py`** + **`funcs_check_greek_singles/`** (new package: `models`, `normalize`, `audio_reader`, `database`, `report`): cross-checks `~/Music/Greek/01-Singles-All/` against `~/Music/Greek/03-Singles-by-Month/<yyyy-mm>/`. Surfaces (a) songs in singles-all with no month-folder match, (b) songs in month folders with no singles-all match, (c) songs whose `(title, artist)` appears in 2+ distinct month folders, (d) files missing title/artist (the 'untagged' bucket). Matching key is `(title, artist)` normalized lowercase + diacritic-stripped + non-alphanumeric-stripped + whitespace-collapsed; album is displayed but excluded from the key so album-variants of the same logical song render as adjacent rows for manual review. Optional `--title-prefix '<greek>'` filter narrows both sides before diffing (diacritic- and case-insensitive). Each run snapshots to `Data/songs.sqlite` (previous file renamed to `Data/songs-<YYYY-MM-DD-HHmm>.sqlite` using its own mtime, with `-1`/`-2`/... on collision), plus a timestamped CSV in `Logs/`.
- **`Tests/test_check_greek_singles.py`**: 48 pytest cases covering each module (normalize, dataclasses, untagged routing, year/duration formatters, month-folder regex, prefix matching, all four diff queries against an in-memory DB, and the `archive_previous_db` collision logic via `tmp_path`).

## [2026-05-09-2155] - Move utility scripts to Utils/

### Changed
- **`Utils/`**: New directory for standalone utility scripts. Moved from project root: `main-boost-mp3-or-mp4.py`, `main-convert.py`, `main-get-artists-from-trello.py`, `main-qb-notify-gmail.py`, `main-qb-notify.py`. Moved from `Tests-Standalone/`: `fix_m4a_faststart.py`.

## [2026-05-09-2123] - Ensure M4A files always have moov atom before mdat (faststart)

### Fixed
- **`funcs_for_audio_utils/conversion.py`**: Added `-movflags +faststart` to `convert_mp3_to_m4a()` and `convert_flac_to_m4a()` — ffmpeg now places the `moov` atom before `mdat` in all directly-produced M4A files, preventing hardware players (e.g. HiBy M300) from showing empty tags when the cover art is large
- **`funcs_for_main_yt_dlp/download_audio.py`**: Added `--postprocessor-args ffmpeg:-movflags +faststart` to `extract_single_format()` for M4A — applies to all of yt-dlp's internal ffmpeg invocations (`FFmpegExtractAudio` + `EmbedThumbnail`) so faststart survives thumbnail embedding

### Added
- **`Tests-Standalone/fix_m4a_faststart.py`**: Standalone bulk-repair script that scans a folder for M4A files with `moov` after `mdat` and remuxes them in-place with faststart. Supports `--recursive`, `--dry-run`, `--ffmpeg`.

## [2026-05-07-2006] - Add FLAC → MP3/M4A conversion to main-convert.py

### Added
- **`main-convert.py`**: `--source flac` support; new `--target {mp3,m4a,both}` argument with validation (required when source is FLAC; must be omitted or opposite format for mp3/m4a source); `extract_flac_tags()` reads all Vorbis Comment fields including cover art; FLAC cover art extraction branch in `_extract_cover_art()`; outer loop over target formats so `--target both` runs two passes
- **`funcs_for_audio_utils/conversion.py`**: `convert_flac_to_mp3()` and `convert_flac_to_m4a()` — mirror existing conversion functions; FLAC→MP3 uses libmp3lame VBR q2; FLAC→M4A uses AAC 192k
- **`funcs_for_audio_utils/__init__.py`**: exported `convert_flac_to_mp3` and `convert_flac_to_m4a`

## [2026-03-20-1703] - main-convert.py: copy cover art when syncing tags

### Added
- **`main-convert.py`**: cover art (album artwork) is now copied from source to target file when syncing tags — previously only text tags were transferred
  - New `_extract_cover_art(file_path, fmt)` helper reads `APIC` frame (MP3) or `covr` atom (M4A)
  - New `_apply_cover_art(file_path, fmt, cover_data, mime)` helper writes the art after text tags are saved (so the ID3 save inside `apply_mp3_tags` does not overwrite the new `APIC` frame)
- **`Docs/main-convert-README.md`**: updated features list, optional arguments (`--prefix`), tag mapping table (cover art row), default directories, and notes to reflect all current functionality
