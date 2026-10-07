# Utility Scripts

Documentation for the standalone helper scripts that ship with this project. The main downloader (`main-yt-dlp.py`) and the ERTFlix series browser (`main-ertflix-series.py`) are documented in the [main README](README.md).

> **Note:** The audio-conversion, volume-boost, Dolby-Vision, Greek-singles duplicate, copy-tags-to-video, and qBittorrent utilities were moved out of this repo into the sibling **`av-utils`** project (`../av-utils`) on 2026-06-05. See `av-utils/README-Utils.md` for those.

Change history for the remaining utilities lives in [CHANGELOG-Utils.md](CHANGELOG-Utils.md).

## Contents

- [URL Extraction Utility](#url-extraction-utility) — `Tests/main-test-url-extraction.py`
- [Mail Link Fetcher](#mail-link-fetcher-utilsmain-fetch-mail-urlspy) — `Utils/main-fetch-mail-urls.py`
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

## Mail Link Fetcher (`Utils/main-fetch-mail-urls.py`)

Downloads the Facebook/YouTube videos you mail to yourself, so you don't have to open each mail and paste its link into the web app. It reads the Gmail inbox of the `GMAIL_PARAMS` account (`git_excluded.py`) over IMAP with the same App Password used for notifications, so no new credentials are needed.

A mail qualifies when both of these hold (the subject is not checked):
1. It is from an allowed sender. By default these are `recipient_email` and `sender_email` of `GMAIL_PARAMS`; `--sender` (repeatable) overrides the list.
2. Its body is exactly one non-blank line holding a FB/YT video URL. Signatures (any line starting with `-- ` and what follows it) don't count. Forwarded mails work too: the `---------- Forwarded message ---------` header block is dropped, and mails forwarded several at once (as attachments) are each checked.

Gmail labels track progress. A qualifying mail gets `yt-queue`, and after its download succeeds it moves to `yt-done`. Mails that don't qualify are never labelled. Mails labelled `yt-done` are not scanned again, while `yt-queue` mails are, so a failed download is retried on the next run.

### Usage

```bash
# List qualifying mails and write yt-queue/dl-candidates-<timestamp>.txt (no downloads, no label changes)
./Utils/main-fetch-mail-urls.py --from-mail --dry-run

# Label, download, and mark done; unknown flags go to main-yt-dlp.py
./Utils/main-fetch-mail-urls.py --from-mail --download --only-audio

# Download every URL in a .txt/.odt file (e.g. a dl-candidates file); no mail access
./Utils/main-fetch-mail-urls.py --url-file yt-queue/dl-candidates-2026-10-07-1750.txt --only-audio
```

### Arguments

| Argument | Description |
|---|---|
| `--from-mail` | Scan the Gmail inbox for qualifying mails (one of `--from-mail` / `--url-file` is required) |
| `--url-file PATH` | Download every URL in this `.txt`/`.odt` file |
| `--download` | With `--from-mail`: download the found URLs and label each mail `yt-done` on success |
| `--dry-run` | With `--from-mail`: write the dl-candidates file, but download nothing and change no labels |
| `--out-file PATH` | Where to write the found URLs (default: `yt-queue/dl-candidates-<timestamp>.txt`) |
| `--sender ADDRESS` | Accept mails from this address (repeatable) |
| `--queue-label` / `--done-label` | Label names (default `yt-queue` / `yt-done`; created on first use) |
| `--verbose`, `-v` | DEBUG logging |

`main-yt-dlp.py` runs once per URL. Only the first run shows the linter-freshness prompt; the rest get `LINTER_GATE=off`.

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

