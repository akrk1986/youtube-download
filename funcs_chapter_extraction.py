""" Functions to extract YouTube video chapters using yt-dlp."""
import csv
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from funcs_utils import get_video_info


def _parse_time_to_seconds(time_str: str) -> int:
    """Convert time string (HH:MM:SS or MM:SS) to seconds."""
    parts = time_str.strip().split(':')
    if len(parts) == 2:  # MM:SS
        minutes, seconds = map(int, parts)
        return minutes * 60 + seconds
    elif len(parts) == 3:  # HH:MM:SS
        hours, minutes, seconds = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds
    else:
        raise ValueError(f'Invalid time format: {time_str}')

def _extract_chapters_from_description(description: str) -> List[Dict[str, Any]]:
    """Extract chapters from video description using regex patterns."""
    chapters = []

    # Common patterns for chapter timestamps in descriptions
    patterns = [
        r'(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–—]\s*(.+?)(?=\n|$)',  # 12:34 - Chapter Name
        r'(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+?)(?=\n|$)',  # 12:34 Chapter Name
        r'(\d{1,2}:\d{2}(?::\d{2})?)\s*[:\-–—]\s*(.+?)(?=\n|$)',  # 12:34: Chapter Name
    ]

    for pattern in patterns:
        matches = re.findall(pattern, description, re.MULTILINE | re.IGNORECASE)
        if matches:
            for i, (time_str, title) in enumerate(matches):
                try:
                    start_seconds = _parse_time_to_seconds(time_str)
                    chapters.append({
                        'start_time': start_seconds,
                        'title': title.strip(),
                        'index': i + 1
                    })
                except ValueError:
                    continue
            break  # Use first successful pattern

    # Sort chapters by start time
    chapters.sort(key=lambda x: x['start_time'])

    # Calculate end times
    for i in range(len(chapters)):
        if i + 1 < len(chapters):
            chapters[i]['end_time'] = chapters[i + 1]['start_time']
        else:
            chapters[i]['end_time'] = None  # Will be set to video duration

    return chapters

def extract_youtube_chapters(yt_dlp_path: Path, url: str) -> Optional[str]:
    """
    Extract chapters from a YouTube video and save to CSV.

    Args:
        yt_dlp_path: Path to the yt-dlp executable
        url: YouTube video URL

    Returns:
        Path to the created CSV file if successful, None if no chapters found
    """
    # Get video information
    video_info = get_video_info(yt_dlp_path, url)

    video_title = video_info.get('title', 'Unknown')
    video_duration = video_info.get('duration', 0)
    description = video_info.get('description', '')

    # Try to get chapters from yt-dlp first (native chapters)
    chapters = video_info.get('chapters', [])

    # If no native chapters, try to extract from description
    if not chapters and description:
        extracted_chapters = _extract_chapters_from_description(description)
        if extracted_chapters:
            chapters = extracted_chapters

    if not chapters:
        print(f'No chapters found for video: {video_title}')
        return None

    # Create CSV filename based on video title
    safe_title = re.sub(r'[^\w\s-]', '', video_title).strip()
    safe_title = re.sub(r'[-\s]+', '_', safe_title)
    csv_filename = f'{safe_title}_chapters.csv'

    # Write chapters to CSV
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Chapter #', 'Start (seconds)', 'End (seconds)', 'Chapter Name'])

        for i, chapter in enumerate(chapters, 1):
            if isinstance(chapter, dict):
                # Handle both native chapters and extracted chapters
                start_time = chapter.get('start_time', 0)
                end_time = chapter.get('end_time')
                title = chapter.get('title', f'Chapter {i}')

                # If end_time is None (last chapter), use video duration
                if end_time is None:
                    end_time = video_duration

            else:
                # Fallback for unexpected chapter format
                start_time = 0
                end_time = video_duration
                title = str(chapter)

            writer.writerow([i, start_time, end_time, title])

    print(f'Chapters extracted successfully to: {csv_filename}')
    print(f'Total chapters: {len(chapters)}')

    return csv_filename
