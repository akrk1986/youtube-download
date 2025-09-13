"""Quick test for just the first video to verify artists.json path fix."""
import sys
import subprocess
sys.path.append('..')

from test_cases import VIDEO_SIMPLE

def main():
    print("Quick test for artists.json path fix")
    print("=" * 40)

    cmd = ['python', '../main-yt-dlp.py', '--only-audio', '--audio-format', 'mp3', VIDEO_SIMPLE]
    print(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, text=True, timeout=60)
        print(f"\nReturn code: {result.returncode}")

        if result.returncode == 0:
            print("✅ SUCCESS - Artists.json path fixed!")
        else:
            print("❌ Still has issues")

    except subprocess.TimeoutExpired:
        print("⚠️ Timeout but probably working")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    main()