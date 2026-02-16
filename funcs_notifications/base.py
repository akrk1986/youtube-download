"""Abstract base class for notification handlers."""
from abc import ABC, abstractmethod
from typing import Optional


class NotificationHandler(ABC):
    """Base class for all notification handlers (Slack, Gmail, etc.)."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if this notifier has valid credentials configured."""

    @abstractmethod
    def send(self, status: str, url: str, args_dict: dict,
             session_id: str, elapsed_time: Optional[str] = None,
             video_count: int = 0, audio_count: int = 0,
             failure_reason: Optional[str] = None,
             script_version: Optional[str] = None,
             ytdlp_version: Optional[str] = None,
             notif_msg_suffix: str = '') -> bool:
        """Send a notification about download status.

        Args:
            status: 'start', 'success', 'failure', or 'cancelled'
            url: The video/playlist URL that was downloaded
            args_dict: Dictionary of script arguments
            session_id: Unique session identifier [YYYY-mm-dd HH:MM hostname]
            elapsed_time: Optional elapsed time string (e.g., '5m 23s')
            video_count: Number of video files created
            audio_count: Number of audio files created
            failure_reason: Optional reason string for failure notifications
            script_version: Optional script version string (for start notifications)
            ytdlp_version: Optional yt-dlp version string (for start notifications)
            notif_msg_suffix: Optional suffix to append to notification titles (e.g., 'PROD')

        Returns:
            True if notification was sent successfully, False otherwise
        """
