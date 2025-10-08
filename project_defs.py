"""Project-wide constants and configuration values for the YouTube downloader application."""

# Audio processing constants
DEFAULT_AUDIO_QUALITY = '192k'
DEFAULT_AUDIO_FORMAT = 'mp3'
AUDIO_FORMATS = ('mp3', 'm4a', 'both')

# YouTube URL validation
MAX_URL_RETRIES = 3
VALID_YOUTUBE_DOMAINS = ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be')

# File processing constants
MAX_ALBUM_NAME_LENGTH = 64

# yt-dlp command-line flags
YT_DLP_WRITE_JSON_FLAG = '--write-info-json'
YT_DLP_SPLIT_CHAPTERS_FLAG = '--split-chapters'
YT_DLP_IS_PLAYLIST_FLAG = '--yes-playlist'

# Legacy constant (example playlist URL)
GREEK_PLAYLIST_URL = 'https://www.youtube.com/playlist?list=PLRXnwzqAlx1NehOIsFdwtVbsZ0Orf71cE'
