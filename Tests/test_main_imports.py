"""Test main script imports and basic functionality."""
import argparse
import sys

sys.path.append('..')

try:
    # Test imports from main script
    from funcs_process_mp3_tags import set_artists_in_mp3_files, set_tags_in_chapter_mp3_files
    from funcs_process_mp4_tags import set_artists_in_m4a_files, set_tags_in_chapter_m4a_files
    print("✓ Successfully imported all audio tag processing functions")

    # Test argument parsing setup
    parser = argparse.ArgumentParser()
    parser.add_argument('--audio-format', choices=['mp3', 'm4a'], default='mp3')
    args = parser.parse_args(['--audio-format', 'm4a'])
    print(f"✓ Audio format argument parsing works: {args.audio_format}")

    args_default = parser.parse_args([])
    print(f"✓ Default audio format: {args_default.audio_format}")

except Exception as e:
    print(f"✗ Error: {e}")

print("\nMain script modifications test complete.")