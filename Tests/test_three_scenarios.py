"""
Test script for three YouTube URL scenarios:
1. Simple single video (extract audio)
2. Video with chapters (extract video only)
3. Playlist (extract audio)

The script will automatically detect chapters and handle each scenario appropriately.
"""
import os
import platform
import subprocess
import sys
from pathlib import Path

# Add parent directory to path to import functions
sys.path.append('..')
from funcs_utils import is_playlist, get_chapter_count

def _show_file_counts():
    """Show current file counts in output directories."""
    video_dir = Path("../yt-videos")
    audio_dir = Path("../yt-audio")

    if video_dir.exists():
        video_files = [f for f in video_dir.glob("*") if f.is_file()]
        print(f"  Video files: {len(video_files)}")
        for f in video_files[:3]:  # Show first 3
            print(f"    - {f.name}")
        if len(video_files) > 3:
            print(f"    ... and {len(video_files) - 3} more")

    if audio_dir.exists():
        mp3_files = [f for f in audio_dir.glob("*.mp3") if f.is_file()]
        m4a_files = [f for f in audio_dir.glob("*.m4a") if f.is_file()]
        print(f"  Audio files: {len(mp3_files)} MP3, {len(m4a_files)} M4A")
        for f in (mp3_files + m4a_files)[:3]:  # Show first 3
            print(f"    - {f.name}")
        if len(mp3_files) + len(m4a_files) > 3:
            print(f"    ... and {len(mp3_files) + len(m4a_files) - 3} more")

def run_main_script(url: str, args: list, description: str) -> bool:
    """
    Run the main script with given URL and arguments.

    Args:
        url: YouTube URL to process
        args: List of command line arguments
        description: Description of what this test does

    Returns:
        bool: True if successful, False if failed
    """
    print(f"\n{'='*60}")
    print(f"TEST: {description}")
    print(f"URL: {url}")
    print(f"Args: {' '.join(args)}")
    print(f"{'='*60}")

    # Build command
    cmd = ['python', '../main-yt-dlp.py'] + args + [url]

    print(f"Running: {' '.join(cmd)}")
    print(f"{'='*60}")

    try:
        # Run the command with real-time output
        result = subprocess.run(cmd, text=True, timeout=300)

        print(f"Return code: {result.returncode}")

        if result.returncode == 0:
            print("✅ TEST PASSED")
            return True
        else:
            print("❌ TEST FAILED")
            return False

    except subprocess.TimeoutExpired:
        print("❌ TEST TIMEOUT (5 minutes)")
        return False
    except Exception as e:
        print(f"❌ TEST ERROR: {e}")
        return False

def main():
    """Main test function - uses URLs from test_cases.py."""
    print("YouTube Download Test Suite")
    print("=" * 50)

    # Import URLs from test_cases.py
    try:
        from test_cases import VIDEO_SIMPLE, VIDEO_WITH_CHAPTERS, VIDEO_PLAYLIST
        url1 = VIDEO_SIMPLE
        url2 = VIDEO_WITH_CHAPTERS
        url3 = VIDEO_PLAYLIST

        print(f"\nLoaded test URLs:")
        print(f"1. Simple single video: {url1}")
        print(f"2. Video with chapters: {url2}")
        print(f"3. Playlist: {url3}")

        if not all([url1, url2, url3]):
            print("❌ All three URLs are required in test_cases.py!")
            return

    except ImportError as e:
        print(f"❌ Could not import test_cases.py: {e}")
        return

    # Check current directory
    print(f"\nCurrent working directory: {os.getcwd()}")

    # Clean up output directories at start
    print(f"\n🧹 Cleaning up output directories...")
    video_dir = Path("../yt-videos")
    audio_dir = Path("../yt-audio")

    if video_dir.exists():
        video_files = list(video_dir.glob("*"))
        for f in video_files:
            if f.is_file():
                f.unlink()
                print(f"  Deleted: {f.name}")
        print(f"✅ Cleaned {len([f for f in video_files if f.is_file()])} video files")
    else:
        video_dir.mkdir(exist_ok=True)
        print("✅ Created yt-videos directory")

    if audio_dir.exists():
        audio_files = list(audio_dir.glob("*"))
        for f in audio_files:
            if f.is_file():
                f.unlink()
                print(f"  Deleted: {f.name}")
        print(f"✅ Cleaned {len([f for f in audio_files if f.is_file()])} audio files")
    else:
        audio_dir.mkdir(exist_ok=True)
        print("✅ Created yt-audio directory")

    # Initialize test results
    results = []

    # Verify we have the necessary executables
    print("\n🔍 Checking prerequisites...")

    # Detect platform and set appropriate executable paths (same logic as main script)
    system_platform = platform.system().lower()

    if system_platform == "windows":
        # Windows paths
        home_dir = Path.home()
        yt_dlp_dir = home_dir / "Apps" / "yt-dlp"
        yt_dlp_exe = yt_dlp_dir / "yt-dlp.exe"
        ffmpeg_exe = yt_dlp_dir / "ffmpeg.exe"

        if not yt_dlp_exe.exists():
            print(f"❌ YT-DLP not found at: {yt_dlp_exe}")
            print("Tests may fail!")
        else:
            print(f"✅ YT-DLP found at: {yt_dlp_exe}")

        if not ffmpeg_exe.exists():
            print(f"❌ FFMPEG not found at: {ffmpeg_exe}")
            print("Tests may fail!")
        else:
            print(f"✅ FFMPEG found at: {ffmpeg_exe}")
    else:
        # Linux/Mac - use system-wide installations
        yt_dlp_exe = "yt-dlp"
        ffmpeg_exe = "ffmpeg"

        # Check if commands are available in PATH
        try:
            subprocess.run([yt_dlp_exe, "--version"], capture_output=True, check=True)
            print(f"✅ YT-DLP found in PATH")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"❌ YT-DLP not found in PATH. Tests may fail!")

        try:
            subprocess.run([ffmpeg_exe, "-version"], capture_output=True, check=True)
            print(f"✅ FFMPEG found in PATH")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"❌ FFMPEG not found in PATH. Tests may fail!")

    # Test 1: Simple single video (extract audio as MP3)
    print(f"\n🔍 Analyzing URL1 for chapters...")
    try:
        is_url1_playlist = is_playlist(url1)
        if not is_url1_playlist:
            chapters_count1 = get_chapter_count(ytdlp_exe=yt_dlp_exe, playlist_url=url1)
            print(f"URL1 has {chapters_count1} chapters")
        else:
            print("URL1 is actually a playlist!")
            chapters_count1 = 0
    except Exception as e:
        print(f"Error checking URL1: {e}")
        chapters_count1 = 0

    result1 = run_main_script(
        url1,
        ['--with-audio', '--audio-format', 'both'],
        "Single video - Extract both video + audio (MP3 & M4A)"
    )
    results.append(("Test 1 (Single Video -> Video + Both Audio Formats)", result1))

    # Show files after Test 1
    print(f"\n📁 Files after Test 1:")
    _show_file_counts()

    # Test 2: Video with chapters (extract video only)
    print(f"\n🔍 Analyzing URL2 for chapters...")
    try:
        is_url2_playlist = is_playlist(url2)
        if not is_url2_playlist:
            chapters_count2 = get_chapter_count(ytdlp_exe=yt_dlp_exe, playlist_url=url2)
            print(f"URL2 has {chapters_count2} chapters")
            has_chapters = chapters_count2 > 0

            # CRITICAL: VIDEO_WITH_CHAPTERS must have chapters, otherwise fail the test
            if not has_chapters:
                print("❌ CRITICAL ERROR: VIDEO_WITH_CHAPTERS has no chapters detected!")
                print("This test case is supposed to have chapters. Test FAILED.")
                result2 = False
                results.append(("Test 2 (Chapters Video -> Video Only)", False))
            else:
                # For video with chapters, extract video only, with chapter splitting
                args2 = ['--subs', '--split-chapters']
                description2 = "Video with chapters - Extract video only (split by chapters)"
                result2 = run_main_script(url2, args2, description2)
                results.append(("Test 2 (Chapters Video -> Video Only)", result2))
        else:
            print("❌ CRITICAL ERROR: URL2 is actually a playlist, not a video!")
            result2 = False
            results.append(("Test 2 (Chapters Video -> Video Only)", False))
    except Exception as e:
        print(f"❌ Error checking URL2: {e}")
        result2 = False
        results.append(("Test 2 (Chapters Video -> Video Only)", False))

    # Show files after Test 2
    print(f"\n📁 Files after Test 2:")
    _show_file_counts()

    # Test 3: Playlist (extract audio as M4A)
    print(f"\n🔍 Analyzing URL3...")
    try:
        is_url3_playlist = is_playlist(url3)
        if is_url3_playlist:
            print("URL3 is confirmed to be a playlist")
        else:
            print("URL3 is not a playlist - treating as single video")
    except Exception as e:
        print(f"Error checking URL3: {e}")

    result3 = run_main_script(
        url3,
        ['--with-audio', '--audio-format', 'both'],
        "Playlist - Extract both video + audio (MP3 & M4A)"
    )
    results.append(("Test 3 (Playlist -> Video + Both Audio Formats)", result3))

    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")

    passed = 0
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{len(results)} tests passed")

    # Check output directories
    print(f"\n📁 Output directories:")
    video_dir = Path("../yt-videos")
    audio_dir = Path("../yt-audio")

    if video_dir.exists():
        video_files = list(video_dir.glob("*.mp4"))
        print(f"Video files in {video_dir}: {len(video_files)}")
        for f in video_files[:5]:  # Show first 5
            print(f"  - {f.name}")
        if len(video_files) > 5:
            print(f"  ... and {len(video_files) - 5} more")

    if audio_dir.exists():
        mp3_files = list(audio_dir.glob("*.mp3"))
        m4a_files = list(audio_dir.glob("*.m4a"))
        print(f"Audio files in {audio_dir}: {len(mp3_files)} MP3, {len(m4a_files)} M4A")
        for f in (list(mp3_files) + list(m4a_files))[:5]:  # Show first 5
            print(f"  - {f.name}")
        if len(mp3_files) + len(m4a_files) > 5:
            print(f"  ... and {len(mp3_files) + len(m4a_files) - 5} more")

    print(f"\n🎉 Test suite completed!")

if __name__ == '__main__':
    main()