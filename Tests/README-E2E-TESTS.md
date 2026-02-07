# End-to-End Testing

## Quick Start

1. **Configure test URLs** - Edit `e2e_config.py` and add YouTube URLs to test cases
2. **Run tests** - `python e2e_main.py`
3. **Choose action BEFORE each test** - Press Y to run, S to skip, or Q to quit
4. **Validate downloads** - After test runs, verify using validation checklist
5. **Resume anytime** - Press Q to quit, use `--resume` to continue later

## Files

- `e2e_config.py` - Configure test URLs here (you edit this)
- `e2e_main.py` - Test runner (don't edit)
- `e2e_state.json` - Progress state (auto-generated)

## Commands

```bash
# Fresh run (cleans directories)
python e2e_main.py

# Resume from saved state
python e2e_main.py --resume

# Show help
python e2e_main.py --help
```

## Interactive Controls

BEFORE each test runs, you choose:

- **Y** - Run this test
- **S** - Skip this test, proceed to next
- **Q** - Quit and save progress (resume later)

The script shows you the previous status (succeeded/failed/skipped) when you resume.

## Test Use Cases

The system tests these scenarios:

1. **video_only** - Download video files only
2. **audio_only_mp3** - Download audio as MP3
3. **audio_only_m4a** - Download audio as M4A
4. **audio_only_flac** - Download audio as FLAC
5. **video_and_audio** - Download both video + audio
6. **video_with_chapters** - Download video with chapter splitting
7. **audio_with_chapters** - Download audio with chapter splitting
8. **playlist_video_and_audio** - Download playlist (video + audio)
9. **playlist_audio_only** - Download playlist (audio only)
10. **multiple_audio_formats** - Download multiple formats (mp3, m4a, flac)

## Example Configuration

Edit `e2e_config.py`:

```python
E2E_TEST_CASES = {
    'video_only': [
        ('https://youtu.be/xxxxx', 120),  # Custom timeout
        ('https://youtu.be/yyyyy', None), # Default timeout
    ],

    'audio_only_mp3': [
        ('https://youtu.be/zzzzz', None),
    ],

    # Add URLs to other use cases...
}
```

## Tips

- Use **short videos** (1-3 minutes) for faster testing
- Use **small playlists** (2-5 videos) to keep tests manageable
- For chapter tests, verify URLs actually have chapters
- Tests can run over **multiple days** - progress is saved automatically

## Documentation

See `../Docs/E2E-TESTING-GUIDE.md` for complete documentation.

## State Management

- Progress is saved to `e2e_state.json` after each action
- State includes test results with status: succeeded, failed, or skipped
- Use `--resume` to continue - shows previous status for each test
- You can re-run failed tests by choosing Y when resuming
- State file is deleted automatically after successful completion

## Output Directories

Tests create files in:
- `../yt-videos/` - Video files
- `../yt-audio/` - MP3 audio files
- `../yt-audio-m4a/` - M4A audio files
- `../yt-audio-flac/` - FLAC audio files

Fresh runs clean these directories before starting.
