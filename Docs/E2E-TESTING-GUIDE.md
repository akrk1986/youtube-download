# End-to-End Testing Guide

## Overview

The end-to-end (E2E) testing system allows you to test `main-yt-dlp.py` with real YouTube URLs across multiple download scenarios. Tests run interactively, allowing you to manually validate each download and decide whether to continue, skip, or stop.

## Key Features

- **Real Downloads**: Tests execute actual downloads with `main-yt-dlp.py` (no mocking)
- **Interactive Validation**: After each test, you verify the download and choose to proceed/skip/stop
- **State Persistence**: Progress is saved - you can stop and resume tests anytime
- **Multiple Use Cases**: Tests video-only, audio-only, chapters, playlists, multiple formats
- **Configurable Timeouts**: Set custom timeout per URL or use defaults

## Files

- `Tests/test_e2e_config.py` - Test URLs and timeouts (you populate this)
- `Tests/test_e2e_main.py` - Test runner (don't modify)
- `Tests/test_e2e_state.json` - Progress state (auto-generated)

## Test Use Cases

The following use cases are supported:

| Use Case | Description | Arguments | Default Timeout |
|----------|-------------|-----------|-----------------|
| `video_only` | Download video files only | (none) | 120s |
| `audio_only_mp3` | Download audio as MP3 | `--only-audio --audio-format mp3` | 90s |
| `audio_only_m4a` | Download audio as M4A | `--only-audio --audio-format m4a` | 90s |
| `audio_only_flac` | Download audio as FLAC | `--only-audio --audio-format flac` | 120s |
| `video_and_audio` | Download both video + audio | `--with-audio` | 150s |
| `video_with_chapters` | Download video with chapters | `--split-chapters` | 180s |
| `audio_with_chapters` | Download audio with chapters | `--only-audio --split-chapters` | 150s |
| `playlist_video_and_audio` | Download playlist (video+audio) | `--with-audio` | 600s |
| `playlist_audio_only` | Download playlist (audio only) | `--only-audio` | 400s |
| `multiple_audio_formats` | Download mp3, m4a, flac | `--only-audio --audio-format mp3,m4a,flac` | 200s |

## Setup

### 1. Configure Test URLs

Edit `Tests/test_e2e_config.py` and add URLs to the use cases you want to test:

```python
E2E_TEST_CASES = {
    'video_only': [
        ('https://youtu.be/xxxxx', 120),  # URL with custom timeout
        ('https://youtu.be/yyyyy', None), # URL with default timeout
    ],

    'audio_only_mp3': [
        ('https://youtu.be/zzzzz', None),
    ],

    # ... add more URLs to other use cases
}
```

**Tips for choosing test URLs:**
- Use short videos (1-3 minutes) for faster testing
- For chapter tests, verify URLs actually have chapters
- For playlists, use small playlists (2-5 videos) to keep tests manageable
- Consider using unlisted videos to avoid copyright issues

### 2. Prerequisites

Ensure these are installed:
- `yt-dlp` executable (in PATH on Linux, or `~/Apps/yt-dlp/yt-dlp.exe` on Windows)
- `ffmpeg` executable (in PATH on Linux, or `~/Apps/yt-dlp/ffmpeg.exe` on Windows)
- Python virtual environment activated

## Running Tests

### Fresh Test Run

Start a new test session (cleans output directories):

```bash
cd Tests
python test_e2e_main.py
```

### Resume Test Run

Resume from where you left off:

```bash
cd Tests
python test_e2e_main.py --resume
```

### Help

```bash
python test_e2e_main.py --help
```

## Interactive Test Flow

### Test Execution

For each test URL, the runner will:

1. Show test information (use case, URL, arguments, timeout)
2. **Show previous status** if test was run before (succeeded/failed/skipped)
3. **Prompt you BEFORE running the test: Y/S/Q**
4. If you choose Y (Yes):
   - Execute `main-yt-dlp.py` with the URL (output shown in real-time)
   - Show test result (passed/failed/timeout)
   - Display file counts (what was created)
   - Show validation checklist (what to verify manually)
   - Save status (succeeded/failed)
5. If you choose S (Skip):
   - Skip this test and proceed to next
   - Save status as 'skipped'
6. If you choose Q (Quit):
   - Save progress and exit

### User Input Options

BEFORE each test runs, you choose:

- **Y (Yes)** → Run this test
- **S (Skip)** → Skip this test, proceed to next
- **Q (Quit)** → Save progress and exit (can resume later)

### Example Output

**First run - no previous status:**

```
========================================
USE CASE: video_only [1/10]
========================================
Description: Download video files only (no audio extraction)
Total URLs in this use case: 2

[1/2] URL: https://youtu.be/xxxxx
Args: []
Timeout: 120s
------------------------------------------------------------

What do you want to do?
  [Y] Yes - Run this test
  [S] Skip - Skip this test, proceed to next
  [Q] Quit - Save progress and exit

Your choice (Y/S/Q): Y

▶️  Running test...

Running: python main-yt-dlp.py https://youtu.be/xxxxx
----------------------------------------
[main-yt-dlp.py output appears here...]
----------------------------------------
✅ TEST PASSED (45.3s)

📁 Files created:
  yt-videos/: 1 new file(s)
    - video_title.mp4
  yt-audio/: 0 new file(s)

✔ VALIDATION CHECKLIST - Please verify:
  [ ] Video file exists in yt-videos/
  [ ] Video plays correctly (check with media player)
  [ ] No audio files were created in yt-audio/
  [ ] Filename is properly sanitized (no special characters)

💾 Status saved: succeeded
```

**Resuming - shows previous status:**

```
[1/2] URL: https://youtu.be/xxxxx
Args: []
Timeout: 120s
------------------------------------------------------------
Previous run: ✅ SUCCEEDED

What do you want to do?
  [Y] Yes - Run this test
  [S] Skip - Skip this test, proceed to next
  [Q] Quit - Save progress and exit

Your choice (Y/S/Q): S

⏭ Skipping this test...
```

## Validation Checklists

Each use case has a specific checklist to verify. Here are some examples:

### video_only
- Video file(s) exist in `yt-videos/`
- Video plays correctly (check with media player)
- No audio files were created
- Filename is properly sanitized

### audio_only_mp3 / audio_only_m4a / audio_only_flac
- Audio file(s) exist in correct directory
- Audio plays correctly
- No video files were created
- Metadata tags are correct (artist, title, album)
- Thumbnail embedded as album art
- Original filename stored in tags

### video_with_chapters / audio_with_chapters
- Multiple files created (one per chapter)
- Files organized in chapter subdirectory
- Track numbers set correctly (audio only)
- CSV file created with chapter info (video only)
- Filenames include chapter numbers (001, 002, etc.)

### playlist_video_and_audio / playlist_audio_only
- Multiple files created (one per playlist item)
- All playlist items downloaded successfully
- Files are NOT in subdirectory (flat structure)
- File count matches expected playlist size

### multiple_audio_formats
- Files created in `yt-audio/`, `yt-audio-m4a/`, `yt-audio-flac/`
- Each format has same number of files
- All formats play correctly
- FLAC files are larger (lossless)
- Metadata preserved across formats

## State Management

### State File

Progress is automatically saved to `Tests/test_e2e_state.json` after each action.

State includes:
- Test results with status for each test (succeeded/failed/skipped)
- Use case and URL index for each test
- Last run timestamp

### Test Status Values

Each test can have one of three status values:
- **succeeded** - Test ran and passed
- **failed** - Test ran but failed (exit code != 0 or timeout)
- **skipped** - User chose to skip the test

### When State is Saved

State saves when:
- You run a test (Y) - saves 'succeeded' or 'failed'
- You skip a test (S) - saves 'skipped'
- You quit (Q) - preserves current state
- You press Ctrl+C (interrupt) - preserves current state

### Resuming Tests

When you run with `--resume`:
- Loads state file
- Shows progress summary (succeeded/failed/skipped counts)
- Shows previous status when prompting for each test
- Allows you to re-run tests (change status from failed to succeeded, etc.)
- You control which tests to run/skip/quit

### Starting Fresh

When you run without `--resume`:
- Cleans all output directories
- Creates new state file
- Starts from first test

## Output Directories

Tests create files in these directories:
- `yt-videos/` - Video files (MP4)
- `yt-audio/` - MP3 audio files
- `yt-audio-m4a/` - M4A audio files
- `yt-audio-flac/` - FLAC audio files

**Note:** Fresh runs clean these directories before starting. Files are NOT deleted between individual tests.

## Tips

### Choosing Good Test URLs

- **Short videos (1-3 min)**: Faster testing
- **Unlisted videos**: Avoid copyright issues
- **Verify chapters**: For chapter tests, check URL has chapters first
- **Small playlists**: Use 2-5 videos for playlist tests

### Managing Long Test Sessions

- Don't try to run all tests in one session
- Use S to skip use cases you're not interested in
- Use N to stop and resume later (state is preserved)
- Tests can run over multiple days

### Debugging Failed Tests

If a test fails:
- Check the output from `main-yt-dlp.py`
- Verify prerequisites (yt-dlp, ffmpeg)
- Check URL is valid and accessible
- Try running the command manually
- Check timeout is sufficient

### Cleaning Up

After successful completion:
- State file is automatically deleted
- Downloaded files remain in output directories
- Manually delete output directories if needed

## Troubleshooting

### State File Corrupted

If state file is corrupted:
- You'll be prompted to start fresh
- Backup is saved as `test_e2e_state.json.bak`

### Prerequisites Missing

If yt-dlp or ffmpeg not found:
- Tests will not run
- Check installation and PATH
- Verify platform-specific paths (Windows vs Linux)

### Timeout Errors

If tests timeout frequently:
- Increase timeout in config file
- Check internet connection
- Use shorter videos

### Keyboard Interrupt (Ctrl+C)

If you press Ctrl+C during test:
- Current test is interrupted
- Progress is saved automatically
- Run with `--resume` to continue

## Example Workflow

### Initial Setup

1. Edit `Tests/test_e2e_config.py`
2. Add 1-2 URLs to each use case
3. Use short test videos

### First Run

```bash
cd Tests
python test_e2e_main.py
```

### During Testing

- Press Y to run a test
- Verify downloads manually using validation checklist
- Press S to skip tests you don't want to run
- Press Q when you need a break (saves progress)

### Resume Later

```bash
cd Tests
python test_e2e_main.py --resume
```

### After Completion

- Review downloaded files
- Clean up output directories
- Update config with more URLs if needed

## Advanced Usage

### Custom Timeouts

Override default timeout for specific URLs:

```python
'video_only': [
    ('https://youtu.be/short-video', 60),   # Quick video, 60s timeout
    ('https://youtu.be/long-video', 300),   # Long video, 5min timeout
]
```

### Testing Specific Use Cases

To test only specific use cases:
1. Leave other use cases empty in config
2. Or use S to skip use cases during testing

## Limitations

- Tests run serially (not parallel)
- Requires internet connection
- Requires manual validation (no automated assertions)
- Long test sessions for many URLs
- No automatic video quality verification

## Best Practices

1. **Start small**: Begin with 1-2 URLs per use case
2. **Use short videos**: Keeps test time manageable
3. **Test incrementally**: Don't run everything at once
4. **Resume often**: Use N/S to break up long sessions
5. **Verify carefully**: Check validation checklists thoroughly
6. **Keep config updated**: Remove broken URLs, add new ones
7. **Clean periodically**: Delete old output files between sessions
