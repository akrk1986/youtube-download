"""Test M4A tag processing functions."""
import sys
from pathlib import Path

sys.path.append('..')

try:
    from funcs_process_m4a_tags import set_artists_in_m4a_files, set_tags_in_chapter_m4a_files
    print("✓ Successfully imported M4A tag processing functions")
    print("✓ Available functions:")
    print("  - set_artists_in_m4a_files()")
    print("  - set_tags_in_chapter_m4a_files()")
except ImportError as e:
    print(f"✗ Import error: {e}")

# Test if mutagen MP4 is available
try:
    from mutagen.mp4 import MP4
    print("✓ Mutagen MP4 support is available")
except ImportError as e:
    print(f"✗ Mutagen MP4 not available: {e}")

if __name__ == '__main__':
    print("\nM4A tag processing module test complete.")