"""Shared pytest fixtures for main-yt-dlp tests."""
import argparse
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from project_defs import DEFAULT_AUDIO_FORMAT


@pytest.fixture
def mock_slack_webhook() -> Generator[MagicMock, None, None]:
    """Patch SLACK_WEBHOOK to None to disable Slack notifications."""
    with patch('main-yt-dlp.SLACK_WEBHOOK', None) as mock:
        yield mock


@pytest.fixture
def mock_gmail_params() -> Generator[MagicMock, None, None]:
    """Patch GMAIL_PARAMS to None to disable Gmail notifications."""
    with patch('main-yt-dlp.GMAIL_PARAMS', None) as mock:
        yield mock


@pytest.fixture
def mock_subprocess_run() -> Generator[MagicMock, None, None]:
    """Mock subprocess.run to avoid actual yt-dlp/ffmpeg execution."""
    with patch('subprocess.run') as mock:
        mock.return_value = MagicMock(returncode=0, stdout='', stderr='')
        yield mock


@pytest.fixture
def mock_requests_post() -> Generator[MagicMock, None, None]:
    """Mock requests.post for Slack notification testing."""
    with patch('requests.post') as mock:
        mock.return_value = MagicMock(ok=True, status_code=200)
        yield mock


@pytest.fixture
def mock_input() -> Generator[MagicMock, None, None]:
    """Mock builtins.input for interactive prompt testing."""
    with patch('builtins.input') as mock:
        yield mock


@pytest.fixture
def sample_args() -> argparse.Namespace:
    """Create sample argparse.Namespace with default values."""
    return argparse.Namespace(
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        audio_format=DEFAULT_AUDIO_FORMAT,
        split_chapters=False,
        video_download_timeout=None,
        subs=False,
        json=False,
        no_log_file=True,
        progress=False,
        verbose=False,
        show_urls=False,
        rerun=False,
        title=None,
        artist=None,
        album=None,
        with_audio=False,
        only_audio=False
    )


@pytest.fixture
def temp_output_dirs(tmp_path: Path) -> dict[str, Path]:
    """Create temporary output directories for testing.

    Returns:
        Dictionary with 'video', 'mp3', 'm4a', 'flac' directory paths.
    """
    dirs = {
        'video': tmp_path / 'yt-videos',
        'mp3': tmp_path / 'yt-audio',
        'm4a': tmp_path / 'yt-audio-m4a',
        'flac': tmp_path / 'yt-audio-flac',
    }
    for dir_path in dirs.values():
        dir_path.mkdir(parents=True, exist_ok=True)
    return dirs


@pytest.fixture
def mock_video_info() -> dict:
    """Create sample video metadata dictionary."""
    return {
        'id': 'dQw4w9WgXcQ',
        'title': 'Test Video Title',
        'uploader': 'Test Channel',
        'duration': 212,
        'description': 'Test description',
        'upload_date': '20210101',
        'webpage_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'extractor': 'youtube',
        'chapters': [
            {'start_time': 0, 'end_time': 60, 'title': 'Chapter 1'},
            {'start_time': 60, 'end_time': 120, 'title': 'Chapter 2'},
            {'start_time': 120, 'end_time': 212, 'title': 'Chapter 3'},
        ]
    }


@pytest.fixture
def mock_video_info_no_chapters() -> dict:
    """Create sample video metadata without chapters."""
    return {
        'id': 'dQw4w9WgXcQ',
        'title': 'Test Video Title',
        'uploader': 'Test Channel',
        'duration': 212,
        'description': 'Test description',
        'upload_date': '20210101',
        'webpage_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'extractor': 'youtube',
        'chapters': None
    }
