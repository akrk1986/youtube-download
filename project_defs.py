"""Project-wide constants and configuration values for the YouTube downloader application."""

# Audio processing constants
DEFAULT_AUDIO_QUALITY = '192k'
DEFAULT_AUDIO_FORMAT = 'mp3'
VALID_AUDIO_FORMATS = {'mp3', 'm4a', 'flac'}

# YouTube URL validation
MAX_URL_RETRIES = 3
VALID_YOUTUBE_DOMAINS = ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be')
VALID_OTHER_DOMAINS = ('www.ertflix.gr', 'ertflix.gr')

# File processing constants
MAX_ALBUM_NAME_LENGTH = 64

# Output directories
VIDEO_OUTPUT_DIR = 'yt-videos'
AUDIO_OUTPUT_DIR = 'yt-audio'

# Logging constants
MAX_LOG_FILES = 5  # Maximum number of log files to keep

# Subprocess timeout constants (in seconds)
SUBPROCESS_TIMEOUT_YOUTUBE = 300  # 5 minutes for YouTube yt-dlp operations
SUBPROCESS_TIMEOUT_OTHER_SITES = 3600  # 1 hour for other sites (some are very slow)
FFMPEG_TIMEOUT_SECONDS = 600  # 10 minutes for audio/video conversion

# Regex patterns
CHAPTER_FILENAME_PATTERN = r'^(.*?)\s*-\s*(\d{3})\s+(.*?)\s*\[([^\s\[\]]+)\]\.(?:mp3|m4a|flac|MP3|M4A|FLAC)$'
LEADING_NONALNUM_PATTERN = r'^[^a-zA-Z0-9\u0370-\u03FF\u05d0-\u05ea]+'
MULTIPLE_SPACES_PATTERN = r'\s+'
CHAPTER_TIMESTAMP_PATTERNS = (
    r'(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–—]\s*(.+?)(?=\n|$)',  # 12:34 - Chapter Name
    r'(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+?)(?=\n|$)',  # 12:34 Chapter Name
    r'(\d{1,2}:\d{2}(?::\d{2})?)\s*[:\-–—]\s*(.+?)(?=\n|$)',  # 12:34: Chapter Name
)
SAFE_FILENAME_PATTERN = r'[^\w\s-]'
WHITESPACE_TO_UNDERSCORE_PATTERN = r'[-\s]+'

# File glob patterns
GLOB_MP3_FILES = '*.mp3'
GLOB_M4A_FILES = '*.m4a'
GLOB_FLAC_FILES = '*.flac'
GLOB_MP3_FILES_UPPER = '*.MP3'
GLOB_M4A_FILES_UPPER = '*.M4A'
GLOB_FLAC_FILES_UPPER = '*.FLAC'
GLOB_MP4_FILES = '*.mp4'
GLOB_LOG_FILES = 'yt-dlp_*.log'

# yt-dlp command-line flags
YT_DLP_WRITE_JSON_FLAG = '--write-info-json'
YT_DLP_SPLIT_CHAPTERS_FLAG = '--split-chapters'
YT_DLP_IS_PLAYLIST_FLAG = '--yes-playlist'

# Legacy constant (example playlist URL)
GREEK_PLAYLIST_URL = 'https://www.youtube.com/playlist?list=PLRXnwzqAlx1NehOIsFdwtVbsZ0Orf71cE'
