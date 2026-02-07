# Plan: Add End-to-End Testing with Configurable Test Cases

## Overview
Add comprehensive end-to-end testing for `main-yt-dlp.py` that tests actual download scenarios with real URLs. Tests will execute the main script via subprocess (no mocking) and validate downloaded files.

## User Requirements
- Test multiple use cases: video only, audio only, both, video with chapters, playlist video+audio, playlist audio only
- Configuration file with dict structure: `{'use-case-name': [(url, optional_timeout), ...]}`
- User will populate URLs and timeouts after file creation
- Tests should execute actual downloads and verify results
- Interactive mode with Y/S/N prompts after each test
- State persistence to resume tests later

## Files to Create

### 1. `Tests/e2e_config.py` - Test case configuration file

This file contains the test URLs organized by use case. User will populate after creation.

```python
"""
End-to-end test configuration for main-yt-dlp.py

Each test case is a tuple: (url, optional_timeout_seconds)
If timeout is None, default timeout will be used based on test type.
"""

# Test case data structure: {'use-case-name': [(url, timeout), ...]}
E2E_TEST_CASES = {
    # Single video - download video only
    'video_only': [
        # Add URLs here - user will populate
        # Example: ('https://youtu.be/xxxxx', 120),
    ],

    # Single video - download audio only (MP3)
    'audio_only_mp3': [
        # Add URLs here - user will populate
    ],

    # Single video - download audio only (M4A)
    'audio_only_m4a': [
        # Add URLs here - user will populate
    ],

    # Single video - download audio only (FLAC)
    'audio_only_flac': [
        # Add URLs here - user will populate
    ],

    # Single video - download both video and audio
    'video_and_audio': [
        # Add URLs here - user will populate
    ],

    # Single video with chapters - download video with chapter splitting
    'video_with_chapters': [
        # Add URLs here - user will populate
        # These URLs MUST have chapters
    ],

    # Single video with chapters - download audio with chapter splitting
    'audio_with_chapters': [
        # Add URLs here - user will populate
        # These URLs MUST have chapters
    ],

    # Playlist - download video + audio
    'playlist_video_and_audio': [
        # Add URLs here - user will populate
        # Consider using small playlists for testing (2-5 videos)
    ],

    # Playlist - download audio only
    'playlist_audio_only': [
        # Add URLs here - user will populate
    ],

    # Multiple audio formats - download multiple formats (mp3,m4a,flac)
    'multiple_audio_formats': [
        # Add URLs here - user will populate
    ],
}

# Default timeouts for each test type (seconds)
DEFAULT_TIMEOUTS = {
    'video_only': 120,
    'audio_only_mp3': 90,
    'audio_only_m4a': 90,
    'audio_only_flac': 120,
    'video_and_audio': 150,
    'video_with_chapters': 180,
    'audio_with_chapters': 150,
    'playlist_video_and_audio': 600,  # 10 minutes for playlists
    'playlist_audio_only': 400,
    'multiple_audio_formats': 200,
}
```

### 2. `Tests/e2e_main.py` - End-to-end test runner

Main test execution script with **interactive mode** and **state persistence**.

**Key Components:**

#### Helper Functions
- `_cleanup_output_dirs()` - Clean yt-videos/, yt-audio/, yt-audio-m4a/, yt-audio-flac/ before tests
- `_show_file_counts(directory_paths)` - Display file counts with first few filenames
- `_check_prerequisites()` - Verify yt-dlp and ffmpeg are available (platform-aware)
- `_run_test_case(url, args, timeout, description)` - Execute main script with subprocess.run()
- `_validate_download(use_case, expected_files)` - Verify files were created correctly
- `_get_file_counts(dirs)` - Count files in output directories
- `_load_state()` - Load test progress from state file
- `_save_state(state)` - Save test progress to state file
- `_prompt_user(use_case, url_index, result)` - Interactive prompt with Y/S/N options
- `_show_validation_checklist(use_case, files_created)` - Display what user should verify

#### State Persistence
State file: `Tests/e2e_state.json`

Structure:
```json
{
  "last_run": "2026-02-06T15:30:00",
  "completed_tests": [
    {"use_case": "video_only", "url_index": 0, "status": "passed"},
    {"use_case": "video_only", "url_index": 1, "status": "passed"},
    {"use_case": "audio_only_mp3", "url_index": 0, "status": "failed"}
  ],
  "skipped_use_cases": ["playlist_audio_only"],
  "current_use_case": "audio_only_mp3",
  "current_url_index": 1
}
```

State is saved:
- After each test completes
- When user chooses to skip use case (S)
- When user stops tests (N)
- Can be resumed with `--resume` flag

#### Main Execution Flow
1. Load test cases from `e2e_config.py`
2. Check for `--resume` flag:
   - If resuming: Load state, skip completed tests
   - If fresh: Clean output directories, create new state
3. Display test plan (all use cases and URL counts)
4. Check prerequisites (yt-dlp, ffmpeg)
5. For each use case:
   - Skip if in `skipped_use_cases`
   - For each URL in use case:
     - Skip if already completed (when resuming)
     - Build appropriate arguments based on use case
     - Run main-yt-dlp.py with timeout
     - Display results and file counts
     - Show validation checklist (what user should verify)
     - **Wait for user input:**
       - **Y (Yes/Proceed)** → Continue to next test
       - **S (Skip)** → Skip remaining URLs in this use case
       - **N (No/Stop)** → Save state and exit
     - Save state after each test
6. Print final summary report
7. Clean up state file on successful completion

#### Argument Mapping by Use Case
```python
USE_CASE_ARGS = {
    'video_only': [],
    'audio_only_mp3': ['--only-audio', '--audio-format', 'mp3'],
    'audio_only_m4a': ['--only-audio', '--audio-format', 'm4a'],
    'audio_only_flac': ['--only-audio', '--audio-format', 'flac'],
    'video_and_audio': ['--with-audio'],
    'video_with_chapters': ['--split-chapters'],
    'audio_with_chapters': ['--only-audio', '--split-chapters'],
    'playlist_video_and_audio': ['--with-audio'],
    'playlist_audio_only': ['--only-audio'],
    'multiple_audio_formats': ['--only-audio', '--audio-format', 'mp3,m4a,flac'],
}
```

#### Error Handling
- Handle `subprocess.TimeoutExpired` gracefully
- Handle missing prerequisites (yt-dlp, ffmpeg)
- Handle empty test case lists (skip with warning)
- Handle invalid URLs (catch and report)

#### Output Format with Interactive Prompts
```
========================================
END-TO-END TEST SUITE (INTERACTIVE MODE)
========================================

Loaded test cases:
  video_only: 2 URLs
  audio_only_mp3: 3 URLs
  ...

Total: 15 test cases across 10 use case types

Resume mode: No (fresh run)
State file: Tests/e2e_state.json

🧹 Cleaning output directories...
✅ Cleaned yt-videos/ (0 files removed)
✅ Cleaned yt-audio/ (3 files removed)
...

🔍 Checking prerequisites...
✅ yt-dlp found
✅ ffmpeg found

========================================
USE CASE: video_only [1/10]
========================================
Description: Download video files only (no audio extraction)
Total URLs in this use case: 2

[1/2] Testing URL: https://youtu.be/xxxxx
Args: []
Timeout: 120s
----------------------------------------
Running: python ../main-yt-dlp.py https://youtu.be/xxxxx
[main-yt-dlp.py output appears here...]
----------------------------------------
✅ TEST PASSED (45.3s)

📁 Files created:
  Video files: 1 new file(s)
    - video_title.mp4
  Audio files: 0 new file(s)

✔ VALIDATION CHECKLIST - Please verify:
  [ ] Video file exists in yt-videos/
  [ ] Video plays correctly
  [ ] No audio files were created
  [ ] Filename is properly sanitized

Continue testing?
  [Y] Yes - Proceed to next test
  [S] Skip - Skip remaining tests in 'video_only' use case
  [N] No - Stop and save progress

Your choice (Y/S/N): _
```

**If user enters Y:**
```
✅ Continuing to next test...

[2/2] Testing URL: https://youtu.be/yyyyy
...
```

**If user enters S:**
```
⏭ Skipping remaining tests in 'video_only' use case (1 test skipped)
💾 State saved

========================================
USE CASE: audio_only_mp3 [2/10]
========================================
...
```

**If user enters N:**
```
🛑 Stopping test suite...
💾 State saved to: Tests/e2e_state.json

Progress so far:
  video_only: 1/2 completed

To resume later, run: python e2e_main.py --resume

Exiting.
```

**When resuming:**
```
========================================
END-TO-END TEST SUITE (RESUME MODE)
========================================

📂 Loading state from: Tests/e2e_state.json
✅ Loaded previous progress (last run: 2026-02-06 15:30)

Progress summary:
  ✅ video_only: 1/2 completed
  ⏭ Skipped use cases: playlist_audio_only

Resuming from: video_only [test 2/2]

[2/2] Testing URL: https://youtu.be/yyyyy
...
```

## Files to Reference

### Existing Patterns
- `Tests/test_three_scenarios.py` - Main pattern to follow (subprocess execution, cleanup, file counting)
- `Tests/test_cases.py` - Current URL storage pattern
- `Tests/conftest.py` - Pytest fixtures (not used for e2e tests)

### Functions to Import
- `funcs_video_info.is_playlist()` - Check if URL is playlist
- `funcs_video_info.get_chapter_count()` - Detect chapters in video
- `funcs_for_main_yt_dlp.get_ytdlp_path()` - Get platform-specific yt-dlp path
- `funcs_for_main_yt_dlp.get_ffmpeg_path()` - Get platform-specific ffmpeg path

### Key Dependencies
- `subprocess` - For executing main-yt-dlp.py
- `pathlib.Path` - For file operations
- `platform` - For platform detection
- `time` - For timing tests
- `sys` - For path manipulation
- `json` - For state file persistence
- `argparse` - For command-line argument parsing

## Design Decisions

### 1. Configuration File Structure
Use dictionary with lists of tuples for flexibility:
```python
{
    'use_case_name': [
        (url1, timeout1),  # explicit timeout
        (url2, None),      # use default timeout
        (url3, 180),       # custom timeout
    ]
}
```

### 2. Separate Config from Execution
- `e2e_config.py` - User edits to add URLs
- `e2e_main.py` - Never needs editing (reads config)
- Allows users to update test URLs without modifying test logic

### 3. Pre-test Cleanup Only
- Clean directories before test suite starts (fresh run only)
- Leave downloaded files after tests for manual inspection
- Matches pattern from `test_three_scenarios.py`

### 4. Platform-Aware Executable Detection
```python
if platform.system().lower() == "windows":
    yt_dlp_exe = Path.home() / "Apps" / "yt-dlp" / "yt-dlp.exe"
else:
    yt_dlp_exe = "yt-dlp"  # Must be in PATH
```

### 5. Timeout Strategy
- Default timeouts per use case type
- User can override with explicit timeout in tuple
- Handle `subprocess.TimeoutExpired` gracefully

### 6. Not Using pytest Framework
- These are integration tests, not unit tests
- Run as standalone Python script (like `test_three_scenarios.py`)
- Can be run directly: `python e2e_main.py`
- Simpler output for manual test observation

## Interactive Validation Checklists

Different use cases have different validation checklists shown to the user:

### video_only
```
✔ VALIDATION CHECKLIST - Please verify:
  [ ] Video file(s) exist in yt-videos/
  [ ] Video plays correctly (check with media player)
  [ ] No audio files were created in yt-audio/
  [ ] Filename is properly sanitized (no special characters)
```

### audio_only_mp3 / audio_only_m4a / audio_only_flac
```
✔ VALIDATION CHECKLIST - Please verify:
  [ ] Audio file(s) exist in yt-audio/ (or yt-audio-m4a/, yt-audio-flac/)
  [ ] Audio plays correctly
  [ ] No video files were created in yt-videos/
  [ ] Metadata tags are correct (artist, title, album)
  [ ] Thumbnail embedded as album art
  [ ] Original filename stored in tags
```

### video_and_audio
```
✔ VALIDATION CHECKLIST - Please verify:
  [ ] Video file(s) exist in yt-videos/
  [ ] Audio file(s) exist in yt-audio/
  [ ] Both video and audio play correctly
  [ ] Filenames match (same base name)
  [ ] Audio has correct metadata tags
```

### video_with_chapters
```
✔ VALIDATION CHECKLIST - Please verify:
  [ ] Multiple video files created (one per chapter)
  [ ] Files organized in chapter subdirectory
  [ ] CSV file created with chapter information
  [ ] Each video file contains only its chapter content
  [ ] Filenames include chapter numbers (001, 002, etc.)
```

### audio_with_chapters
```
✔ VALIDATION CHECKLIST - Please verify:
  [ ] Multiple audio files created (one per chapter)
  [ ] Files organized in chapter subdirectory
  [ ] Track numbers set correctly in metadata
  [ ] Album name set to video title
  [ ] Each audio file duration matches chapter length
```

### playlist_video_and_audio / playlist_audio_only
```
✔ VALIDATION CHECKLIST - Please verify:
  [ ] Multiple files created (one per playlist item)
  [ ] All playlist items downloaded successfully
  [ ] Files are NOT organized in subdirectory (flat structure)
  [ ] Each file has unique filename
  [ ] Check file count matches expected playlist size
```

### multiple_audio_formats
```
✔ VALIDATION CHECKLIST - Please verify:
  [ ] Files created in multiple directories:
      - yt-audio/ (MP3 files)
      - yt-audio-m4a/ (M4A files)
      - yt-audio-flac/ (FLAC files)
  [ ] Each format has the same number of files
  [ ] All formats play correctly
  [ ] FLAC files are larger (lossless quality)
  [ ] Metadata preserved across all formats
```

## Implementation Details

### State Management

State file location: `Tests/e2e_state.json`

Functions:
- `_load_state()` → Returns state dict or None if no state file
- `_save_state(state)` → Writes state dict to JSON file
- `_is_test_completed(state, use_case, url_index)` → Check if test already done
- `_mark_test_completed(state, use_case, url_index, status)` → Update state
- `_mark_use_case_skipped(state, use_case)` → Add to skipped list

State is saved immediately after:
- Each test completes
- User enters S (skip)
- User enters N (stop)

### User Input Handling

```python
def _prompt_user(use_case: str, url_index: int, result: bool) -> str:
    """
    Prompt user for action after test completes.

    Returns:
        'Y' - Proceed to next test
        'S' - Skip remaining tests in this use case
        'N' - Stop test suite
    """
    while True:
        choice = input('Your choice (Y/S/N): ').strip().upper()
        if choice in ['Y', 'S', 'N']:
            return choice
        print('❌ Invalid input. Please enter Y, S, or N.')
```

### Command Line Arguments

```python
# e2e_main.py supports:
python e2e_main.py           # Fresh run (cleans directories)
python e2e_main.py --resume  # Resume from saved state
python e2e_main.py --help    # Show usage information
```

### File Counting Logic
Count files before and after each test:
```python
before_counts = _get_file_counts({
    'video': Path('../yt-videos'),
    'mp3': Path('../yt-audio'),
    'm4a': Path('../yt-audio-m4a'),
    'flac': Path('../yt-audio-flac'),
})

# Run test...

after_counts = _get_file_counts(...)
new_files = {k: after_counts[k] - before_counts[k] for k in before_counts}
```

### Validation by Use Case
Different use cases expect different outputs:
- `video_only` → video files created, no audio files
- `audio_only_mp3` → MP3 files created, no video files
- `video_with_chapters` → multiple video files (one per chapter)
- `playlist_*` → multiple files
- `multiple_audio_formats` → files in mp3/, m4a/, flac/ directories

### Chapter Detection
For `video_with_chapters` and `audio_with_chapters`:
```python
if use_case.endswith('with_chapters'):
    # Verify URL has chapters before running test
    chapter_count = get_chapter_count(ytdlp_exe, url)
    if chapter_count == 0:
        print(f"❌ WARNING: URL has no chapters but test expects chapters!")
        # Mark as validation failure
```

## Verification

After implementation, test by:

1. **Empty Config Test**
   ```bash
   cd Tests
   python e2e_main.py
   ```
   Should show: "No test cases configured" warnings and exit gracefully

2. **Help Command**
   ```bash
   python e2e_main.py --help
   ```
   Should display usage information and available options

3. **Add Single URL to Config**
   Add one simple video to `video_only` use case in `e2e_config.py`:
   ```python
   'video_only': [
       ('https://youtu.be/xxxxx', 120),
   ]
   ```
   Run test:
   ```bash
   python e2e_main.py
   ```
   Should:
   - Clean directories
   - Download video
   - Show validation checklist
   - Wait for Y/S/N input

4. **Test Interactive Features**
   - Enter **Y** after first test → Should proceed to next test
   - Run again, enter **S** → Should skip remaining tests in use case
   - Run again, enter **N** → Should save state and exit
   - Verify state file created: `e2e_state.json`

5. **Test Resume Feature**
   After stopping with N:
   ```bash
   python e2e_main.py --resume
   ```
   Should:
   - Load state file
   - Show progress summary
   - Resume from where it stopped
   - Skip already completed tests

6. **Test Invalid Input Handling**
   When prompted for Y/S/N:
   - Try invalid inputs (X, 123, blank) → Should re-prompt
   - Only Y/S/N (case insensitive) should be accepted

7. **User Populates Full Config**
   User adds URLs to all use cases
   ```bash
   python e2e_main.py
   ```
   Run full test suite interactively
   - Can stop and resume at any point
   - Each test shows validation checklist

8. **Verify Output Directories**
   Check that files are created in correct locations:
   - `../yt-videos/` - video files
   - `../yt-audio/` - MP3 files
   - `../yt-audio-m4a/` - M4A files
   - `../yt-audio-flac/` - FLAC files

9. **Verify State File Cleanup**
   After completing full test suite successfully:
   - State file should be removed automatically
   - Next run should start fresh

10. **Verify Cleanup Works**
    Run test with fresh start (no --resume):
    - Should clean all output directories
    - Should show count of files removed

## Edge Cases and Error Handling

### State File Corruption
- If state file is corrupted/invalid JSON → warn user and offer fresh start
- Backup state file before modifying: `e2e_state.json.bak`

### URL Changes in Config
- If URLs in config change while state exists → warn user about mismatch
- Option: ignore state and start fresh, or continue with old state

### Keyboard Interrupt (Ctrl+C)
- Catch KeyboardInterrupt during test execution
- Save current state before exiting
- Show message: "Tests interrupted. Progress saved. Run with --resume to continue."

### Test Failures
- Test failure doesn't stop suite - user can still choose Y/S/N
- Failed tests marked as "failed" in state (can be re-run by starting fresh)

### Empty Use Case
- If use case has no URLs → skip with message: "No URLs configured for [use_case]"
- Don't prompt user for empty use cases

### Prerequisites Missing
- If yt-dlp or ffmpeg not found → show error and exit before running any tests
- Don't prompt user if prerequisites are missing

## Notes

- Tests are intentionally run serially (not parallel) to avoid file system conflicts
- Each test is independent - failure of one test doesn't stop execution
- Real downloads are performed - requires internet connection and yt-dlp access
- Test execution time depends on video length and number of URLs
- User should use short videos (1-3 minutes) for faster testing
- Consider using private/unlisted YouTube videos to avoid copyright issues
- Interactive mode allows user to verify each download manually
- State persistence enables long test sessions (can run over multiple days)
- State file is automatically cleaned up on successful completion
- User can delete state file manually to force fresh start
