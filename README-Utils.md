# Utility Scripts

Documentation for the standalone helper scripts that ship with this project. The main downloader (`main-yt-dlp.py`) and the ERTFlix series browser (`main-ertflix-series.py`) are documented in the [main README](README.md).

> **Note:** The audio-conversion, volume-boost, Dolby-Vision, Greek-singles duplicate, copy-tags-to-video, and qBittorrent utilities were moved out of this repo into the sibling **`av-utils`** project (`../av-utils`) on 2026-06-05. See `av-utils/README-Utils.md` for those.

Change history for the remaining utilities lives in [CHANGELOG-Utils.md](CHANGELOG-Utils.md).

## Contents

- [URL Extraction Utility](#url-extraction-utility) — `Tests/main-test-url-extraction.py`
- [Loudness Boost Suggester](#loudness-boost-suggester-utilsmain-suggest-boostpy) — `Utils/main-suggest-boost.py`
- [Trello → Artists JSON](#trello--artists-json-utilsmain-get-artists-from-trellopy) — `Utils/main-get-artists-from-trello.py`

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

