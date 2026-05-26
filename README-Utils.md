# Utility Scripts

Documentation for the standalone helper scripts that ship with this project. The main downloader (`main-yt-dlp.py`) and the ERTFlix series browser (`main-ertflix-series.py`) are documented in the [main README](README.md).

Change history for these utilities lives in [CHANGELOG-Utils.md](CHANGELOG-Utils.md).

## Contents

- [URL Extraction Utility](#url-extraction-utility) — `Tests/main-test-url-extraction.py`
- [Audio Format Converter](#audio-format-converter-utilsmain-convertpy) — `Utils/main-convert.py`
- [Greek Singles Cross-Checker](#greek-singles-cross-checker-utilsmain-check-greek-singlespy) — `Utils/main-check-greek-singles.py`
- [Verify Dupe Groups](#verify-dupe-groups-utilsmain-verify-dupe-groupspy) — `Utils/main-verify-dupe-groups.py`
- [Inspect Dupe Groups](#inspect-dupe-groups-utilsmain-inspect-dupe-groupspy) — `Utils/main-inspect-dupe-groups.py`
- [Audio Volume Booster](#audio-volume-booster-utilsmain-boost-audio-trackpy) — `Utils/main-boost-audio-track.py`
- [Loudness Boost Suggester](#loudness-boost-suggester-utilsmain-suggest-boostpy) — `Utils/main-suggest-boost.py`
- [qBittorrent Slack Notification](#qbittorrent-slack-notification-utilsmain-qb-notifypy) — `Utils/main-qb-notify.py`
- [qBittorrent Gmail Notification](#qbittorrent-gmail-notification-utilsmain-qb-notify-gmailpy) — `Utils/main-qb-notify-gmail.py`
- [Trello → Artists JSON](#trello--artists-json-utilsmain-get-artists-from-trellopy) — `Utils/main-get-artists-from-trello.py`
- [M4A Faststart Fix](#m4a-faststart-fix-utilsfix_m4a_faststartpy) — `Utils/fix_m4a_faststart.py`

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

## Audio Format Converter (`Utils/main-convert.py`)

Converts audio files between MP3, M4A, and FLAC formats. All metadata (tags + cover art) is preserved during conversion. No conversion *to* FLAC is supported.

### Usage

```bash
# MP3 → M4A (default target when source is mp3)
python Utils/main-convert.py --source mp3

# M4A → MP3 (default target when source is m4a)
python Utils/main-convert.py --source m4a

# FLAC → MP3
python Utils/main-convert.py --source flac --target mp3

# FLAC → M4A
python Utils/main-convert.py --source flac --target m4a

# FLAC → both MP3 and M4A
python Utils/main-convert.py --source flac --target both

# Convert files from a custom directory tree instead of the default output dirs
python Utils/main-convert.py --source flac --target mp3 --top-level-directory /path/to/music
```

### Arguments

| Argument | Values | Description |
|---|---|---|
| `--source` | `mp3`, `m4a`, `flac` | Source format to convert from |
| `--target` | `mp3`, `m4a`, `both` | Target format(s). Required when `--source flac`. For `mp3`/`m4a` sources, defaults to the opposite format. |
| `--top-level-directory` | path | Root directory containing `MP3/`, `M4A/`, `FLAC/` subdirectories. Defaults to the project output dirs. |
| `--create-missing-files` | flag | Create output directory if it does not exist. |

### Validation Rules

- `--source mp3`: `--target` must be omitted or `m4a` (cannot be `mp3` or `both`)
- `--source m4a`: `--target` must be omitted or `mp3` (cannot be `m4a` or `both`)
- `--source flac`: `--target` is required (`mp3`, `m4a`, or `both`)

### Default Directories

| Format | Default directory |
|---|---|
| MP3 | `yt-audio/mp3/` |
| M4A | `yt-audio/m4a/` |
| FLAC | `yt-audio/flac/` |

## Greek Singles Cross-Checker (`Utils/main-check-greek-singles.py`)

Cross-checks a Greek music library organised into two parallel trees and reports mismatches and duplicates. It reads audio tags with `mutagen`, loads everything into an ephemeral SQLite snapshot (`Data/songs.sqlite`, recreated each run), and prints a Rich report to the console.

Expected layout under `--root` (default `~/Music/Greek/`):

| Directory | Contents |
|---|---|
| `01-Singles-All/` | The flat "master" collection — every song kept once. |
| `03-Singles-by-Month/<YYYY-MM[-suffix]>/` | The same songs filed by download month (e.g. `2023-06`, `2025-11-Nykhta Stasou`). |

**Matching key.** Two files are the same song when their normalised `(title, artist)` match **and** their durations differ by at most `DURATION_MATCH_MARGIN_SECONDS` (set in `funcs_check_greek_singles/config.py`, default `4.0`). Album is intentionally excluded. Duration disambiguates same-tagged-but-different recordings (e.g. studio vs live).

### Report sections

1. **Only in 01-Singles-All** — master songs with no match under any month folder (suppressed when a month range is active).
2. **Only in 03-Singles-by-Month** — month-folder songs missing from the master, with total disk size.
3. **In multiple month folders** — master songs that appear in 2+ month folders.
4. **Untagged** — files missing a title and/or artist.
5. **Duplicate within a single folder** — clusters of ≥2 files in the *same* folder sharing the matching key. One row per file (per-dupe serial, album, duration, basename), one cluster per delimited group.

The **cross-month duplicate** section (`--dupes-scope range`) is mode-only and not part of the default report: it pools every month folder in the range and clusters duplicates *across* months, so a song downloaded into two different months surfaces as one cluster (with the distinct-month count). The report prints the active duration margin at the top.

### Usage

```bash
# Full report over the whole library
python Utils/main-check-greek-singles.py

# Restrict the month-folder scan to a range (yyyy-mm or yyyy; the bare year
# expands to -01 for start, -12 for end). Suppresses the "only in All" section.
python Utils/main-check-greek-singles.py --start-month 2021-01 --end-month 2021-12

# Only check title-prefixed songs (Greek, diacritic-insensitive)
python Utils/main-check-greek-singles.py --title-prefix "Θέλω"

# Copy songs missing from 01-Singles-All into per-month subfolders under All/.
# Prompts before acting: reply 'n' (cancel), 'all', or a number to cap the count.
python Utils/main-check-greek-singles.py --missing-action copy

# Same, but group the copies by year (All/<YYYY>/) instead of by month folder
python Utils/main-check-greek-singles.py --missing-action move --target-is-year

# Duplicate-check only: no cross-folder checks, no copy/move. 'folder' clusters
# within each folder; without a range it scans 01-Singles-All/, with a range it
# scans the in-range month folders only.
python Utils/main-check-greek-singles.py --dupes-scope folder
python Utils/main-check-greek-singles.py --dupes-scope folder --start-month 2023-01 --end-month 2023-12

# 'range' clusters across all month folders in the range (requires a month range).
# A song present in two different months shows as one cluster.
python Utils/main-check-greek-singles.py --dupes-scope range --start-month 2023-01 --end-month 2023-12
```

### Arguments

| Argument | Values | Description |
|---|---|---|
| `--root` | path | Greek music root containing `01-Singles-All` and `03-Singles-by-Month`. Default `~/Music/Greek`. |
| `--title-prefix` | text | Only check songs whose normalised title starts with this Greek prefix (diacritic-insensitive). |
| `--start-month` / `--end-month` | `yyyy-mm` or `yyyy` | Inclusive month-folder range. When set, the "only in All" section is suppressed. |
| `--missing-action` | `copy`, `move` | Copy/move songs missing from `01-Singles-All` into per-folder subdirs under All/. Prompts before acting. Mutually exclusive with `--dupes-scope`. |
| `--target-is-year` | flag | With `--missing-action`, group targets by year (`All/<YYYY>/`) instead of by month-folder name. Ignored otherwise. |
| `--dupes-scope` | `folder`, `range` | Duplicate-check only (skips cross-folder queries and the action prompt). `folder` clusters within each folder (`01-Singles-All/` without a range, the in-range month folders with one). `range` clusters across all month folders in the range and requires `--start-month`/`--end-month`. Mutually exclusive with `--missing-action`. |
| `--console-width` | int | Console width for Rich tables. Defaults to detected terminal width (or 140 under IDE consoles). |
| `--verbose` | flag | DEBUG-level logging. |

The action prompt (`--missing-action`) accepts `n` (cancel), `all` (process every file), or a positive integer to cap the count — files are processed in filename order, file timestamps (mtime) are preserved, and existing targets are overwritten.

## Verify Dupe Groups (`Utils/main-verify-dupe-groups.py`)

Sanity-checks the result of a `--stage-dupes` run: every `Staging-Dupes/grp-NNNN/`
folder should hold the copies of **one** song. The script re-reads each staged
file's title/artist tags from disk (so it catches a file moved into the wrong group
*after* the run, which the run's DB wouldn't reflect), normalises them with the same
logic the staging used, and reports each group's status.

### Usage

```bash
# Verify the default staging folder (<root>/Staging-Dupes)
python Utils/main-verify-dupe-groups.py

# Point at a specific tree, or directly at a staging folder
python Utils/main-verify-dupe-groups.py --root /mnt/c/Users/user/Music/Greek
python Utils/main-verify-dupe-groups.py --staging-dir /path/to/Staging-Dupes
```

### Status per group

| Status | Meaning | Verdict |
|---|---|---|
| `ok` | ≥2 files, all one normalised (title, artist) | pass |
| `misgrouped` | ≥2 *different* songs in one folder | **FAIL** |
| `singleton` | only 1 file (a group should have ≥2) | **FAIL** |
| `empty` | no audio files | **FAIL** |
| `untagged` | a file missing title/artist — can't verify | CHECK |

Prints a Rich table (one row per group) plus a summary line and an overall **PASS** /
**FAIL** / **CHECK**. **Exit code**: `0` when every group is `ok`, `1` when any group
is not, `2` on a usage error (staging folder missing).

### Arguments

| Argument | Values | Description |
|---|---|---|
| `--root` | path | Greek music root containing the staging folder. Default `~/Music/Greek`. |
| `--staging-dir` | path | Folder holding the `grp-NNNN` subfolders. Default `<root>/Staging-Dupes`. |
| `--verbose` | flag | DEBUG-level logging. |

## Inspect Dupe Groups (`Utils/main-inspect-dupe-groups.py`)

Replaces the manual tag-app step of the dupe workflow (step 3 in
[README-Dupes.md](README-Dupes.md)). Give it a range of staging groups; it shows the
files' tags in a table grouped by song, builds a **cover-art collage** so you can
compare the artwork at a glance, then walks you through each file to record a verdict.
It only writes the verdict into the Copyright tag — run
`main-check-greek-singles.py --post-inspection` afterwards to actually move/restore
the files.

Each song is labelled by group: `A1`/`A2` are the copies in the first group folder,
`B1`/`B2`/`B3` the next, and so on. The collage puts one group per row (with a thin
divider between groups), cover art cropped to fill each cell and an empty box for
files with no art; it is written to `<root>/Dupes-images/grp-NNNN-to-grp-MMMM.png`
and opened automatically. Clean that folder out yourself when done (it is gitignored).

Built for the **Windows + PyCharm Run window** (plain `input()`, no arrow-key menus).

### Usage

```bash
# Inspect groups 8 and 9 (Windows: default --root resolves to C:\Users\<you>\Music\Greek)
python Utils/main-inspect-dupe-groups.py 8-9

# WSL: point at the C:-drive tree
python Utils/main-inspect-dupe-groups.py 8-9 --root /mnt/c/Users/user/Music/Greek

# A single group; skip the collage; a specific player
python Utils/main-inspect-dupe-groups.py 8 --no-collage
python Utils/main-inspect-dupe-groups.py 41,42 --player "C:\Program Files\foobar2000\foobar2000.exe"
```

The range accepts `N1-N2`, `N1,N2`, or a single `N`.

### Per-file actions

At each `<n>-<label> [verdict]  audio[a]/next[n]/prev[p]/dupl[d]/orig[o]/clear[c]/view[v]/quit[q]:` prompt:

| Key | Action |
|---|---|
| `a` | Play the file in the audio player (single-instance: plays in the already-open window) |
| `v` | Open just this file's cover art |
| `n` / *blank* | Next file (no verdict change) |
| `p` | Previous file |
| `d` | Verdict **duplicate** → advance |
| `o` | Verdict **original** → advance |
| `c` | Clear this file's verdict → stay |
| `q` | Quit (EOF also quits) |

### Arguments

| Argument | Values | Description |
|---|---|---|
| `groups` | `N1-N2` / `N1,N2` / `N` | Group range to inspect (positional, required). |
| `--root` | path | Greek music root containing the staging folder. Default `~/Music/Greek`. |
| `--staging-dir` | path | Folder holding the `grp-NNNN` subfolders. Default `<root>/Staging-Dupes`. |
| `--images-dir` | path | Folder for the cover-art collage. Default `<root>/Dupes-images`. |
| `--player` | path | Audio player executable. Default: foobar2000 on Windows/WSL, audacious/rhythmbox on Linux, else the OS default app. |
| `--no-collage` | flag | Do not build/open the collage (the per-file `v` still works). |
| `--width` | int | Console width override. Default: auto-detect (fallback 140). |
| `--verbose` | flag | DEBUG-level logging. |

Requires **Pillow** for the collage (already in `requirements.txt`).

## Audio Volume Booster (`Utils/main-boost-audio-track.py`)

Boosts the volume of MP3, M4A, and MP4 files in a directory using ffmpeg (FLAC files are not handled). By default it auto-detects each file's level and calculates the gain needed to reach a target peak; alternatively it can apply the `loudnorm` normalisation filter or a fixed volume multiplier. Files already at/above the target are skipped, and files whose name already ends in `-boost` are ignored so reruns don't double-process.

### Usage

```bash
# Auto-detect levels and boost each file toward the target peak (default mode)
python Utils/main-boost-audio-track.py /path/to/media

# Use the ffmpeg loudnorm filter instead of a calculated boost
python Utils/main-boost-audio-track.py /path/to/media --loudnorm yes

# Apply a fixed volume multiplier
python Utils/main-boost-audio-track.py /path/to/media --boost 2.0
```

### Arguments

| Argument | Values | Description |
|---|---|---|
| `input_dir` | path | Directory containing the MP3/MP4/M4A files to process (extensions matched case-insensitively). |
| `--loudnorm` | `yes`, `no` | Use the ffmpeg `loudnorm` filter for normalisation. Mutually exclusive with `--boost`. |
| `--boost` | float | Use a fixed volume multiplier (default `3.0`). Mutually exclusive with `--loudnorm`. |

For MP4/M4A inputs the video stream is preserved (audio-only boost). A summary of boosted, skipped, and failed files is printed at the end.

## Loudness Boost Suggester (`Utils/main-suggest-boost.py`)

Measures a URL's integrated loudness (EBU R128, via ffmpeg's `ebur128` filter) and suggests an `FFMPEG_OPTS` `volume=` factor that would bring it up to the loudness of a local baseline file. The suggestion pairs with the `FFMPEG_OPTS` environment variable supported by `main-yt-dlp.py`. For a single video (or any non-YouTube URL) it prints a baseline / measured / suggestion block; for a YouTube playlist it prints one row per entry as each measurement completes (the baseline is measured once). If the target is already at/above the baseline, the suggestion is the literal `no boost`.

### Usage

```bash
# Suggest a volume= factor for a single video, matching a local file's loudness
python Utils/main-suggest-boost.py "https://youtube.com/watch?v=..." --baseline /path/to/reference.m4a

# Playlist — one suggestion row per entry
python Utils/main-suggest-boost.py "https://youtube.com/playlist?list=..." --baseline reference.mp3

# Tighten the true-peak clipping ceiling
python Utils/main-suggest-boost.py "<URL>" --baseline reference.mp3 --target-peak-db -1.5
```

### Arguments

| Argument | Values | Description |
|---|---|---|
| `url` | text | YouTube/Facebook/ERTFlix URL — a single video or a YouTube playlist. |
| `--baseline` | path (required) | Local audio/video file whose loudness the suggested boost should target. |
| `--target-peak-db` | float | True-peak ceiling (dBTP) for the clipping safeguard. |
| `--verbose` / `-v` | flag | Enable DEBUG logging to stderr. |

## qBittorrent Slack Notification (`Utils/main-qb-notify.py`)

Sends a Slack message when a torrent finishes downloading. Intended to be wired into qBittorrent's "Run external program on torrent completion" hook. Requires `git_excluded.py` (not tracked by git) to define `SLACK_WEBHOOK` — see the Notifications setup in the [main README](README.md).

### Usage

```bash
# Standalone
python Utils/main-qb-notify.py --name "My Torrent" --path "/downloads/My Torrent"

# In qBittorrent → Options → Downloads → Run external program on torrent completion:
python Utils/main-qb-notify.py --name "%N" --path "%F"
```

### Arguments

| Argument | Values | Description |
|---|---|---|
| `--name` | text (required) | Name of the completed torrent. |
| `--path` | path (required) | Full path to the downloaded content. |

## qBittorrent Gmail Notification (`Utils/main-qb-notify-gmail.py`)

Same as the Slack notifier, but sends a Gmail message via SMTP. Requires `git_excluded.py` to define `GMAIL_PARAMS` (`sender_email`, `sender_app_password`, `recipient_email`) — see the Notifications setup in the [main README](README.md). The app password is a Gmail App Password, not the account password.

### Usage

```bash
# Standalone
python Utils/main-qb-notify-gmail.py --name "My Torrent" --path "/downloads/My Torrent"

# In qBittorrent → Options → Downloads → Run external program on torrent completion:
python Utils/main-qb-notify-gmail.py --name "%N" --path "%F"
```

### Arguments

| Argument | Values | Description |
|---|---|---|
| `--name` | text (required) | Name of the completed torrent. |
| `--path` | path (required) | Full path to the downloaded content. |

## Trello → Artists JSON (`Utils/main-get-artists-from-trello.py`)

Converts a Greek-artists Trello board export into the simpler `Data/artists.json` consumed by the main downloader's artist detection. Card names are split on `" - "` into Greek and English names; all-uppercase Greek names are title-cased; closed lists and cards are skipped; a card name with only one part emits a warning.

### Usage

```bash
# Regenerate Data/artists.json from the default Trello export
python Utils/main-get-artists-from-trello.py

# Custom input/output paths
python Utils/main-get-artists-from-trello.py --trello-json export.json --artists-json out.json
```

### Arguments

| Argument | Values | Description |
|---|---|---|
| `--trello-json` | path | Trello JSON export. Default `Data/Trello - greek-music-artists.json`. |
| `--artists-json` | path | Output path for the artists JSON. Default `Data/artists.json`. |

See also [Artists File from Trello Update Guide](Docs/Artists-file-from-trello-update-guide.md).

## M4A Faststart Fix (`Utils/fix_m4a_faststart.py`)

Bulk-fixes M4A files whose `moov` atom comes after the `mdat` atom. Some hardware players (e.g. HiBy M300) parse `moov` to read metadata and show empty tags when it sits at the end of a large file. This script remuxes affected files with ffmpeg's `-movflags +faststart`, relocating `moov` before `mdat` with zero quality loss. Files that are already correct are reported `OK` and left untouched.

### Usage

```bash
# Dry-run: report which M4A files would be fixed
python Utils/fix_m4a_faststart.py /path/to/music --dry-run

# Fix in place, recursing into subdirectories
python Utils/fix_m4a_faststart.py /path/to/music --recursive
```

### Arguments

| Argument | Values | Description |
|---|---|---|
| `folder` | path | Folder to scan for M4A files. |
| `--recursive` | flag | Also scan subdirectories. |
| `--dry-run` | flag | Report which files would be fixed without changing them. |
| `--ffmpeg` | path | Path to the ffmpeg executable (default: auto-detected). |
