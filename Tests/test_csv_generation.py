"""Test the chapters CSV generation functionality."""

import sys
from pathlib import Path

# Add parent directory to path to import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from funcs_utils import create_chapters_csv


def test_csv_generation():
    """Test creating a CSV file from chapter information."""
    # Mock video info with chapters
    video_info = {
        'title': 'Test Video with Chapters',
        'uploader': 'Test Channel',
        'webpage_url': 'https://youtube.com/watch?v=test123',
        'upload_date': '20231015',
        'chapters': [
            {'start_time': 0, 'end_time': 180, 'title': 'Introduction'},
            {'start_time': 180, 'end_time': 420, 'title': 'Main Content'},
            {'start_time': 420, 'end_time': 3725, 'title': 'Conclusion - Final Thoughts'},
        ]
    }

    output_dir = 'Tests/test_output'
    video_title = video_info['title']

    # Create the CSV
    create_chapters_csv(video_info=video_info, output_dir=output_dir, video_title=video_title)

    # Check if file was created
    csv_path = Path(output_dir) / 'segments-hms-full.txt'
    assert csv_path.exists(), f'CSV file not created at {csv_path}'

    # Read and verify content
    with open(csv_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print(f'\n✓ CSV file created: {csv_path}')
    print(f'✓ Number of lines: {len(lines)}')
    print('\nCSV Content:')
    print('='*80)
    for line in lines:
        print(line.rstrip())
    print('='*80)

    # Verify header
    expected_header = 'start time,end time,song name,original song name,artist name,album name,year,composer,comments'
    assert lines[0].strip() == expected_header, f'Header is incorrect. Expected: {expected_header}, Got: {lines[0].strip()}'

    # Verify comment lines with metadata
    expected_comment1 = "# Title: 'Test Video with Chapters'"
    assert lines[1].strip() == expected_comment1, f'Title comment line incorrect. Expected: {expected_comment1}, Got: {lines[1].strip()}'

    expected_comment2 = "# Artist/Uploader: 'Test Channel'"
    assert lines[2].strip() == expected_comment2, f'Artist comment line incorrect. Expected: {expected_comment2}, Got: {lines[2].strip()}'

    expected_comment3 = '# URL: https://youtube.com/watch?v=test123'
    assert lines[3].strip() == expected_comment3, f'URL comment line incorrect. Expected: {expected_comment3}, Got: {lines[3].strip()}'

    # Verify first chapter (9 columns total = 8 commas, year should be populated)
    expected_line1 = '000000,000300,Introduction,,,,2023,,'
    assert lines[4].strip() == expected_line1, f'First chapter line incorrect. Expected: {expected_line1}, Got: {lines[4].strip()}'

    # Verify second chapter
    expected_line2 = '000300,000700,Main Content,,,,2023,,'
    assert lines[5].strip() == expected_line2, f'Second chapter line incorrect. Expected: {expected_line2}, Got: {lines[5].strip()}'

    # Verify third chapter (over 1 hour)
    expected_line3 = '000700,010205,Conclusion - Final Thoughts,,,,2023,,'
    assert lines[6].strip() == expected_line3, f'Third chapter line incorrect. Expected: {expected_line3}, Got: {lines[6].strip()}'

    # Clean up
    csv_path.unlink()
    # Clean up any other files that might exist in the directory
    import shutil
    if Path(output_dir).exists():
        shutil.rmtree(output_dir)

    print('\n✓ All assertions passed!')


def test_csv_generation_no_date():
    """Test creating a CSV file when video has no upload date."""
    # Mock video info without upload_date
    video_info = {
        'title': 'Test Video No Date',
        'uploader': 'Test Channel',
        'webpage_url': 'https://youtube.com/watch?v=test456',
        'chapters': [
            {'start_time': 0, 'end_time': 100, 'title': 'Chapter 1'},
        ]
    }

    output_dir = 'Tests/test_output'
    video_title = video_info['title']

    # Create the CSV
    create_chapters_csv(video_info=video_info, output_dir=output_dir, video_title=video_title)

    # Check if file was created
    csv_path = Path(output_dir) / 'segments-hms-full.txt'
    assert csv_path.exists(), f'CSV file not created at {csv_path}'

    # Read and verify content
    with open(csv_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print(f'\n✓ CSV file created without date: {csv_path}')
    print('\nCSV Content (no date):')
    print('='*80)
    for line in lines:
        print(line.rstrip())
    print('='*80)

    # Verify chapter has empty year field
    expected_line = '000000,000140,Chapter 1,,,,,,'
    assert lines[4].strip() == expected_line, f'Chapter line incorrect. Expected: {expected_line}, Got: {lines[4].strip()}'

    # Clean up
    csv_path.unlink()
    import shutil
    if Path(output_dir).exists():
        shutil.rmtree(output_dir)

    print('\n✓ All assertions passed for no-date scenario!')


if __name__ == '__main__':
    print('='*80)
    print('Testing Chapters CSV Generation')
    print('='*80)

    try:
        test_csv_generation()

        print('\n' + '='*80)
        print('Testing CSV Generation - No Date Scenario')
        print('='*80)

        test_csv_generation_no_date()

        print('\n' + '='*80)
        print('All tests completed successfully!')
        print('='*80)

    except AssertionError as e:
        print(f'\n✗ Test failed: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'\n✗ Unexpected error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
