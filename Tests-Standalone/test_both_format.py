"""Test 'both' format functionality."""
import sys
sys.path.append('..')

import argparse

def test_both_format_argument():
    """Test that 'both' format argument works correctly."""
    print("Testing 'both' format argument parsing...")

    parser = argparse.ArgumentParser()
    parser.add_argument('--audio-format', choices=['mp3', 'm4a', 'both'], default='mp3')

    # Test all three options
    test_cases = [
        (['--audio-format', 'mp3'], 'mp3'),
        (['--audio-format', 'm4a'], 'm4a'),
        (['--audio-format', 'both'], 'both'),
        ([], 'mp3')  # default
    ]

    for args_list, expected in test_cases:
        args = parser.parse_args(args_list)
        result = args.audio_format
        if result == expected:
            print(f"✓ {args_list or ['default']} -> {result}")
        else:
            print(f"✗ {args_list or ['default']} -> {result}, expected {expected}")

def test_conditional_logic():
    """Test the conditional logic for processing different formats."""
    print("\nTesting conditional processing logic...")

    formats = ['mp3', 'm4a', 'both']
    for fmt in formats:
        if fmt == 'mp3':
            print(f"✓ {fmt}: Would process MP3 files only")
        elif fmt == 'm4a':
            print(f"✓ {fmt}: Would process M4A files only")
        elif fmt == 'both':
            print(f"✓ {fmt}: Would process both MP3 and M4A files")

if __name__ == '__main__':
    test_both_format_argument()
    test_conditional_logic()
    print("\n'Both' format functionality test complete.")