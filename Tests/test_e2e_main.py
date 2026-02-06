#!/usr/bin/env python3
"""
End-to-end test runner for main-yt-dlp.py

Executes real download scenarios with actual URLs from test_e2e_config.py.
Tests run interactively - user chooses to run/skip/quit BEFORE each test.
State is persisted to allow resuming test sessions.

Usage:
    python test_e2e_main.py           # Fresh run (cleans directories)
    python test_e2e_main.py --resume  # Resume from saved state
    python test_e2e_main.py --help    # Show usage information
"""

import argparse
import json
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import arrow

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from funcs_for_main_yt_dlp.external_tools import get_ffmpeg_path, get_ytdlp_path
from funcs_video_info.chapters import get_chapter_count
from test_e2e_config import DEFAULT_TIMEOUTS, E2E_TEST_CASES

# State file location
STATE_FILE = Path(__file__).parent / 'test_e2e_state.json'

# Output directories
OUTPUT_DIRS = {
    'video': Path(__file__).parent.parent / 'yt-videos',
    'mp3': Path(__file__).parent.parent / 'yt-audio',
    'm4a': Path(__file__).parent.parent / 'yt-audio-m4a',
    'flac': Path(__file__).parent.parent / 'yt-audio-flac',
}

# Use case argument mapping
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

# Use case descriptions
USE_CASE_DESCRIPTIONS = {
    'video_only': 'Download video files only (no audio extraction)',
    'audio_only_mp3': 'Download audio only as MP3',
    'audio_only_m4a': 'Download audio only as M4A',
    'audio_only_flac': 'Download audio only as FLAC',
    'video_and_audio': 'Download both video and audio',
    'video_with_chapters': 'Download video with chapter splitting',
    'audio_with_chapters': 'Download audio with chapter splitting',
    'playlist_video_and_audio': 'Download playlist (video + audio)',
    'playlist_audio_only': 'Download playlist (audio only)',
    'multiple_audio_formats': 'Download multiple audio formats (mp3,m4a,flac)',
}

# Validation checklists for each use case
VALIDATION_CHECKLISTS = {
    'video_only': [
        'Video file(s) exist in yt-videos/',
        'Video plays correctly (check with media player)',
        'No audio files were created in yt-audio/',
        'Filename is properly sanitized (no special characters)',
    ],
    'audio_only_mp3': [
        'Audio file(s) exist in yt-audio/',
        'Audio plays correctly',
        'No video files were created in yt-videos/',
        'Metadata tags are correct (artist, title, album)',
        'Thumbnail embedded as album art',
        'Original filename stored in tags',
    ],
    'audio_only_m4a': [
        'Audio file(s) exist in yt-audio-m4a/',
        'Audio plays correctly',
        'No video files were created in yt-videos/',
        'Metadata tags are correct (artist, title, album)',
        'Thumbnail embedded as album art',
        'Original filename stored in tags',
    ],
    'audio_only_flac': [
        'Audio file(s) exist in yt-audio-flac/',
        'Audio plays correctly',
        'No video files were created in yt-videos/',
        'Metadata tags are correct (artist, title, album)',
        'Thumbnail embedded as album art',
        'Original filename stored in tags',
    ],
    'video_and_audio': [
        'Video file(s) exist in yt-videos/',
        'Audio file(s) exist in yt-audio/',
        'Both video and audio play correctly',
        'Filenames match (same base name)',
        'Audio has correct metadata tags',
    ],
    'video_with_chapters': [
        'Multiple video files created (one per chapter)',
        'Files organized in chapter subdirectory',
        'CSV file created with chapter information',
        'Each video file contains only its chapter content',
        'Filenames include chapter numbers (001, 002, etc.)',
    ],
    'audio_with_chapters': [
        'Multiple audio files created (one per chapter)',
        'Files organized in chapter subdirectory',
        'Track numbers set correctly in metadata',
        'Album name set to video title',
        'Each audio file duration matches chapter length',
    ],
    'playlist_video_and_audio': [
        'Multiple files created (one per playlist item)',
        'All playlist items downloaded successfully',
        'Files are NOT organized in subdirectory (flat structure)',
        'Each file has unique filename',
        'Check file count matches expected playlist size',
    ],
    'playlist_audio_only': [
        'Multiple files created (one per playlist item)',
        'All playlist items downloaded successfully',
        'Files are NOT organized in subdirectory (flat structure)',
        'Each file has unique filename',
        'Check file count matches expected playlist size',
    ],
    'multiple_audio_formats': [
        'Files created in multiple directories:',
        '  - yt-audio/ (MP3 files)',
        '  - yt-audio-m4a/ (M4A files)',
        '  - yt-audio-flac/ (FLAC files)',
        'Each format has the same number of files',
        'All formats play correctly',
        'FLAC files are larger (lossless quality)',
        'Metadata preserved across all formats',
    ],
}


def _load_state() -> dict[str, Any] | None:
    """Load test progress from state file."""
    if not STATE_FILE.exists():
        return None

    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f'❌ Warning: State file corrupted ({e})')
        print(f'State file: {STATE_FILE}')
        choice = input('Start fresh? [Y/n]: ').strip().upper()
        if choice in ['Y', '']:
            STATE_FILE.unlink(missing_ok=True)
            return None
        print('Exiting.')
        sys.exit(1)


def _save_state(state: dict[str, Any]) -> None:
    """Save test progress to state file."""
    # Backup existing state file
    if STATE_FILE.exists():
        backup = STATE_FILE.with_suffix('.json.bak')
        shutil.copy2(STATE_FILE, backup)

    state['last_run'] = arrow.now().isoformat()

    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        print(f'❌ Warning: Failed to save state ({e})')


def _get_test_status(state: dict[str, Any] | None, use_case: str, url_index: int) -> str | None:
    """
    Get previous status of a test.

    Returns:
        'succeeded' - Test passed
        'failed' - Test failed
        'skipped' - Test was skipped by user
        None - No previous status
    """
    if not state:
        return None

    for test in state.get('test_results', []):
        if test['use_case'] == use_case and test['url_index'] == url_index:
            return test['status']
    return None


def _update_test_status(state: dict[str, Any], use_case: str, url_index: int, status: str) -> None:
    """
    Update or add test status in state.

    Status can be: 'succeeded', 'failed', 'skipped'
    """
    if 'test_results' not in state:
        state['test_results'] = []

    # Remove existing entry for this test if present
    state['test_results'] = [
        t for t in state['test_results']
        if not (t['use_case'] == use_case and t['url_index'] == url_index)
    ]

    # Add new entry
    state['test_results'].append({
        'use_case': use_case,
        'url_index': url_index,
        'status': status,
    })


def _cleanup_output_dirs() -> None:
    """Clean output directories before tests."""
    print('\n🧹 Cleaning output directories...')

    for dir_name, dir_path in OUTPUT_DIRS.items():
        if not dir_path.exists():
            print(f'✅ Skipped {dir_path.name}/ (does not exist)')
            continue

        files = list(dir_path.rglob('*'))
        file_count = sum(1 for f in files if f.is_file())

        if file_count == 0:
            print(f'✅ Cleaned {dir_path.name}/ (0 files removed)')
            continue

        # Remove all files and subdirectories
        for item in dir_path.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

        print(f'✅ Cleaned {dir_path.name}/ ({file_count} files removed)')


def _get_file_counts(dirs: dict[str, Path]) -> dict[str, int]:
    """Count files in directories."""
    counts = {}
    for key, path in dirs.items():
        if not path.exists():
            counts[key] = 0
            continue
        files = [f for f in path.rglob('*') if f.is_file()]
        counts[key] = len(files)
    return counts


def _show_file_counts(dirs: dict[str, Path], before: dict[str, int], after: dict[str, int]) -> None:
    """Display file counts with first few filenames."""
    print('\n📁 Files created:')

    for key, path in dirs.items():
        new_count = after[key] - before[key]
        if new_count == 0:
            print(f'  {path.name}/: 0 new file(s)')
            continue

        print(f'  {path.name}/: {new_count} new file(s)')

        # Show first 3 filenames
        if path.exists():
            files = sorted([f for f in path.rglob('*') if f.is_file()], key=lambda x: x.stat().st_mtime, reverse=True)
            for i, file in enumerate(files[:3]):
                rel_path = file.relative_to(path)
                print(f'    - {rel_path}')
            if len(files) > 3:
                print(f'    ... and {len(files) - 3} more')


def _show_validation_checklist(use_case: str) -> None:
    """Display validation checklist for use case."""
    checklist = VALIDATION_CHECKLISTS.get(use_case, [])
    if not checklist:
        return

    print('\n✔ VALIDATION CHECKLIST - Please verify:')
    for item in checklist:
        if item.startswith('  '):
            print(f'  {item}')
        else:
            print(f'  [ ] {item}')


def _prompt_user_before_test(use_case: str, url_index: int, url: str, prev_status: str | None) -> str:
    """
    Prompt user for action BEFORE running test.

    Args:
        use_case: Test use case name
        url_index: Index of URL in use case
        url: The URL to test
        prev_status: Previous test status ('succeeded', 'failed', 'skipped', or None)

    Returns:
        'Y' - Run the test
        'S' - Skip this test
        'Q' - Quit the script
    """
    print('\n' + '-' * 60)

    # Show previous status if exists
    if prev_status:
        status_emoji = {
            'succeeded': '✅',
            'failed': '❌',
            'skipped': '⏭',
        }
        emoji = status_emoji.get(prev_status, '❓')
        print(f'Previous run: {emoji} {prev_status.upper()}')

    print('\nWhat do you want to do?')
    print('  [Y] Yes - Run this test')
    print('  [S] Skip - Skip this test, proceed to next')
    print('  [Q] Quit - Save progress and exit')

    while True:
        choice = input('\nYour choice (Y/S/Q): ').strip().upper()
        if choice in ['Y', 'S', 'Q']:
            return choice
        print('❌ Invalid input. Please enter Y, S, or Q.')


def _check_prerequisites() -> bool:
    """Verify yt-dlp and ffmpeg are available."""
    print('\n🔍 Checking prerequisites...')

    # Check yt-dlp
    ytdlp_path = get_ytdlp_path()
    if isinstance(ytdlp_path, Path):
        if not ytdlp_path.exists():
            print(f'❌ yt-dlp not found at: {ytdlp_path}')
            return False
        print(f'✅ yt-dlp found at: {ytdlp_path}')
    else:
        # Check if in PATH
        result = subprocess.run(['which', 'yt-dlp'], capture_output=True, text=True)
        if result.returncode != 0:
            print('❌ yt-dlp not found in PATH')
            return False
        print('✅ yt-dlp found in PATH')

    # Check ffmpeg
    ffmpeg_path = get_ffmpeg_path()
    if isinstance(ffmpeg_path, Path):
        if not ffmpeg_path.exists():
            print(f'❌ ffmpeg not found at: {ffmpeg_path}')
            return False
        print(f'✅ ffmpeg found at: {ffmpeg_path}')
    else:
        # Check if in PATH
        result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
        if result.returncode != 0:
            print('❌ ffmpeg not found in PATH')
            return False
        print('✅ ffmpeg found in PATH')

    return True


def _run_test_case(url: str, args: list[str], timeout: int, description: str) -> tuple[bool, float]:
    """
    Execute main-yt-dlp.py with given arguments.

    Returns:
        (success, elapsed_time)
    """
    main_script = Path(__file__).parent.parent / 'main-yt-dlp.py'
    cmd = [sys.executable, str(main_script)] + args + [url]

    print(f'\nRunning: python main-yt-dlp.py {" ".join(args)} {url}')
    print('----------------------------------------')

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=False,  # Show output in real-time
            text=True,
        )
        elapsed = time.time() - start_time
        print('----------------------------------------')

        if result.returncode == 0:
            print(f'✅ TEST PASSED ({elapsed:.1f}s)')
            return True, elapsed

        print(f'❌ TEST FAILED (exit code {result.returncode}, {elapsed:.1f}s)')
        return False, elapsed

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print('----------------------------------------')
        print(f'❌ TEST TIMEOUT (exceeded {timeout}s)')
        return False, elapsed
    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        print('\n----------------------------------------')
        print(f'⚠️  TEST INTERRUPTED (after {elapsed:.1f}s)')
        raise


def _run_test_suite(resume: bool = False) -> None:
    """Main test execution flow."""
    print('=' * 60)
    if resume:
        print('END-TO-END TEST SUITE (RESUME MODE)')
    else:
        print('END-TO-END TEST SUITE (INTERACTIVE MODE)')
    print('=' * 60)

    # Load test cases
    total_urls = sum(len(urls) for urls in E2E_TEST_CASES.values())
    total_use_cases = len(E2E_TEST_CASES)

    print(f'\nLoaded test cases:')
    for use_case, urls in E2E_TEST_CASES.items():
        if urls:
            print(f'  {use_case}: {len(urls)} URL(s)')

    print(f'\nTotal: {total_urls} test case(s) across {total_use_cases} use case type(s)')

    # Handle state
    state = None
    if resume:
        state = _load_state()
        if not state:
            print('\n❌ No saved state found. Starting fresh run.')
            resume = False
        else:
            print(f'\n📂 Loading state from: {STATE_FILE}')
            last_run = arrow.get(state['last_run']).format('YYYY-MM-DD HH:mm')
            print(f'✅ Loaded previous progress (last run: {last_run})')

            # Show progress summary
            print('\nProgress summary:')
            results_by_use_case = {}
            for test in state.get('test_results', []):
                uc = test['use_case']
                status = test['status']
                if uc not in results_by_use_case:
                    results_by_use_case[uc] = {'succeeded': 0, 'failed': 0, 'skipped': 0}
                results_by_use_case[uc][status] += 1

            for use_case, urls in E2E_TEST_CASES.items():
                if not urls:
                    continue
                if use_case not in results_by_use_case:
                    continue
                results = results_by_use_case[use_case]
                total = len(urls)
                completed = results['succeeded'] + results['failed'] + results['skipped']
                print(f'  {use_case}: {completed}/{total} tests')
                if results['succeeded'] > 0:
                    print(f'    ✅ Succeeded: {results["succeeded"]}')
                if results['failed'] > 0:
                    print(f'    ❌ Failed: {results["failed"]}')
                if results['skipped'] > 0:
                    print(f'    ⏭ Skipped: {results["skipped"]}')

    if not resume:
        state = {
            'test_results': [],
        }
        print(f'\nResume mode: No (fresh run)')
        print(f'State file: {STATE_FILE}')
        _cleanup_output_dirs()
        _save_state(state)

    # Check prerequisites
    if not _check_prerequisites():
        print('\n❌ Prerequisites check failed. Exiting.')
        sys.exit(1)

    # Run tests
    try:
        use_case_index = 0
        for use_case, test_urls in E2E_TEST_CASES.items():
            use_case_index += 1

            # Skip if no URLs
            if not test_urls:
                print(f'\n⚠️  Skipping {use_case}: No URLs configured')
                continue

            # Show use case header
            print('\n' + '=' * 60)
            print(f'USE CASE: {use_case} [{use_case_index}/{total_use_cases}]')
            print('=' * 60)
            description = USE_CASE_DESCRIPTIONS.get(use_case, 'No description')
            print(f'Description: {description}')
            print(f'Total URLs in this use case: {len(test_urls)}')

            # Process each URL
            for url_index, (url, timeout) in enumerate(test_urls):
                # Use default timeout if not specified
                if timeout is None:
                    timeout = DEFAULT_TIMEOUTS.get(use_case, 120)

                # Show test header
                print(f'\n[{url_index + 1}/{len(test_urls)}] URL: {url}')
                args = USE_CASE_ARGS.get(use_case, [])
                print(f'Args: {args if args else "[none]"}')
                print(f'Timeout: {timeout}s')

                # Get previous status
                prev_status = _get_test_status(state=state, use_case=use_case, url_index=url_index)

                # Prompt user BEFORE test
                choice = _prompt_user_before_test(
                    use_case=use_case,
                    url_index=url_index,
                    url=url,
                    prev_status=prev_status,
                )

                if choice == 'Q':
                    # Quit - save and exit
                    print('\n🛑 Quitting test suite...')
                    _save_state(state)
                    print(f'💾 State saved to: {STATE_FILE}')
                    print(f'\nTo resume later, run: python {Path(__file__).name} --resume')
                    print('\nExiting.')
                    sys.exit(0)

                elif choice == 'S':
                    # Skip this test
                    print('\n⏭ Skipping this test...')
                    _update_test_status(state=state, use_case=use_case, url_index=url_index, status='skipped')
                    _save_state(state)
                    continue

                else:  # choice == 'Y'
                    # Run the test
                    print('\n▶️  Running test...')

                    # Get file counts before
                    before_counts = _get_file_counts(OUTPUT_DIRS)

                    # Run test
                    success, elapsed = _run_test_case(url=url, args=args, timeout=timeout, description=description)

                    # Get file counts after
                    after_counts = _get_file_counts(OUTPUT_DIRS)

                    # Show file counts
                    _show_file_counts(dirs=OUTPUT_DIRS, before=before_counts, after=after_counts)

                    # Show validation checklist
                    _show_validation_checklist(use_case=use_case)

                    # Update status
                    status = 'succeeded' if success else 'failed'
                    _update_test_status(state=state, use_case=use_case, url_index=url_index, status=status)
                    _save_state(state)

                    print(f'\n💾 Status saved: {status}')

    except KeyboardInterrupt:
        print('\n\n⚠️  Tests interrupted by user (Ctrl+C)')
        _save_state(state)
        print(f'💾 Progress saved to: {STATE_FILE}')
        print(f'\nTo resume later, run: python {Path(__file__).name} --resume')
        sys.exit(130)

    # All tests completed
    print('\n' + '=' * 60)
    print('✅ ALL TESTS COMPLETED')
    print('=' * 60)

    # Show final summary
    test_results = state.get('test_results', [])
    succeeded = sum(1 for t in test_results if t['status'] == 'succeeded')
    failed = sum(1 for t in test_results if t['status'] == 'failed')
    skipped = sum(1 for t in test_results if t['status'] == 'skipped')

    print(f'\nFinal summary:')
    print(f'  Total tests: {len(test_results)}')
    print(f'  ✅ Succeeded: {succeeded}')
    print(f'  ❌ Failed: {failed}')
    print(f'  ⏭ Skipped: {skipped}')

    # Clean up state file
    if STATE_FILE.exists():
        STATE_FILE.unlink()
        print(f'\n🗑️  State file removed: {STATE_FILE}')


def main() -> None:
    """Parse arguments and run test suite."""
    parser = argparse.ArgumentParser(
        description='End-to-end test runner for main-yt-dlp.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s              # Start fresh test run
  %(prog)s --resume     # Resume from saved state

State file location: Tests/test_e2e_state.json

Configure test URLs in: Tests/test_e2e_config.py
        """,
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from saved state',
    )

    args = parser.parse_args()

    _run_test_suite(resume=args.resume)


if __name__ == '__main__':
    main()
