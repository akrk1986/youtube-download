"""Test only the playlist functionality (Test Case #3)."""
import sys
import subprocess
from pathlib import Path
sys.path.append('..')

from test_cases import VIDEO_PLAYLIST
from funcs_utils import is_playlist

def main():
    print("🎵 Playlist Functionality Test (Test Case #3)")
    print("=" * 50)

    url3 = VIDEO_PLAYLIST
    print(f"Testing URL: {url3}")

    # Verify it's actually a playlist
    print(f"\n🔍 Analyzing URL...")
    try:
        is_url3_playlist = is_playlist(url3)
        if is_url3_playlist:
            print("✅ URL confirmed to be a playlist")
        else:
            print("⚠️  URL is not a playlist - treating as single video")
    except Exception as e:
        print(f"❌ Error checking URL: {e}")

    # Show current file counts before test
    print(f"\n📁 Files before test:")
    _show_file_counts()

    # Run Test 3: Playlist with both video and audio in both formats
    print(f"\n{'='*60}")
    print("TEST 3: Playlist - Extract both video + audio (MP3 & M4A)")
    print(f"{'='*60}")

    cmd = ['python', '../main-yt-dlp.py', '--with-audio', '--audio-format', 'both', url3]
    print(f"Running: {' '.join(cmd)}")
    print(f"{'='*60}")

    try:
        # Run with longer timeout for playlist
        result = subprocess.run(cmd, text=True, timeout=600)  # 10 minutes

        print(f"\nReturn code: {result.returncode}")

        if result.returncode == 0:
            print("✅ TEST 3 PASSED - Playlist functionality working!")
        else:
            print("❌ TEST 3 FAILED")

        # Show files after test
        print(f"\n📁 Files after Test 3:")
        _show_file_counts()

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print("⚠️  TEST TIMEOUT (10 minutes) - but likely still working")
        print("Checking if files were created...")
        _show_file_counts()
        return False
    except Exception as e:
        print(f"❌ TEST ERROR: {e}")
        return False

def _show_file_counts():
    """Show current file counts in output directories."""
    video_dir = Path("../yt-videos")
    audio_dir = Path("../yt-audio")

    if video_dir.exists():
        video_files = [f for f in video_dir.glob("*") if f.is_file()]
        print(f"  Video files: {len(video_files)}")
        for f in video_files[:5]:  # Show first 5
            print(f"    - {f.name}")
        if len(video_files) > 5:
            print(f"    ... and {len(video_files) - 5} more")
    else:
        print("  Video directory not found")

    if audio_dir.exists():
        mp3_files = [f for f in audio_dir.glob("*.mp3") if f.is_file()]
        m4a_files = [f for f in audio_dir.glob("*.m4a") if f.is_file()]
        print(f"  Audio files: {len(mp3_files)} MP3, {len(m4a_files)} M4A")
        for f in (mp3_files + m4a_files)[:5]:  # Show first 5
            print(f"    - {f.name}")
        if len(mp3_files) + len(m4a_files) > 5:
            print(f"    ... and {len(mp3_files) + len(m4a_files) - 5} more")
    else:
        print("  Audio directory not found")

if __name__ == '__main__':
    success = main()
    print(f"\n🎉 Playlist test completed: {'✅ SUCCESS' if success else '❌ FAILED'}")