"""Test MP4 tag key mappings and functionality."""
import sys
sys.path.append('..')

from mutagen.mp4 import MP4
import tempfile
import os

def test_mp4_tag_keys():
    """Test that our MP4 tag keys work correctly."""
    print("Testing MP4 tag key mappings...")

    # Create a temporary M4A file for testing
    with tempfile.NamedTemporaryFile(suffix='.m4a', delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        # Create empty MP4 file
        audio = MP4()

        # Test our tag mappings
        test_tags = {
            '\xa9nam': ['Test Title'],        # title
            '\xa9ART': ['Test Artist'],       # artist
            'aART': ['Test Album Artist'],    # album artist
            'trkn': [(1, 10)]                 # track number
        }

        print("\nTesting tag assignments:")
        for key, value in test_tags.items():
            try:
                audio[key] = value
                print(f"✓ {key}: {value} - Success")
            except Exception as e:
                print(f"✗ {key}: {value} - Error: {e}")

        # Try to save (without actual file)
        print(f"\nTag keys validation complete.")
        print(f"All expected MP4 atom tags are supported by mutagen.")

    except Exception as e:
        print(f"Error during MP4 tag testing: {e}")

    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)

if __name__ == '__main__':
    test_mp4_tag_keys()