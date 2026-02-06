"""
End-to-end test configuration for main-yt-dlp.py

Each test case is a tuple: (url, optional_timeout_seconds)
If timeout is None, default timeout will be used based on test type.
"""

# Test case data structure: {'use-case-name': [(url, timeout), ...]}
E2E_TEST_CASES = {
    # Single video - download video only
    'video_only': [
        # Add URLs here - user will populate
        # Example: ('https://youtu.be/xxxxx', 120),
    ],

    # Single video - download audio only (MP3)
    'audio_only_mp3': [
        # Add URLs here - user will populate
    ],

    # Single video - download audio only (M4A)
    'audio_only_m4a': [
        # Add URLs here - user will populate
    ],

    # Single video - download audio only (FLAC)
    'audio_only_flac': [
        # Add URLs here - user will populate
    ],

    # Single video - download both video and audio
    'video_and_audio': [
        # Add URLs here - user will populate
    ],

    # Single video with chapters - download video with chapter splitting
    'video_with_chapters': [
        # Add URLs here - user will populate
        # These URLs MUST have chapters
    ],

    # Single video with chapters - download audio with chapter splitting
    'audio_with_chapters': [
        # Add URLs here - user will populate
        # These URLs MUST have chapters
    ],

    # Playlist - download video + audio
    'playlist_video_and_audio': [
        # Add URLs here - user will populate
        # Consider using small playlists for testing (2-5 videos)
    ],

    # Playlist - download audio only
    'playlist_audio_only': [
        # Add URLs here - user will populate
    ],

    # Multiple audio formats - download multiple formats (mp3,m4a,flac)
    'multiple_audio_formats': [
        # Add URLs here - user will populate
    ],
}

# Default timeouts for each test type (seconds)
DEFAULT_TIMEOUTS = {
    'video_only': 120,
    'audio_only_mp3': 90,
    'audio_only_m4a': 90,
    'audio_only_flac': 120,
    'video_and_audio': 150,
    'video_with_chapters': 180,
    'audio_with_chapters': 150,
    'playlist_video_and_audio': 600,  # 10 minutes for playlists
    'playlist_audio_only': 400,
    'multiple_audio_formats': 200,
}
