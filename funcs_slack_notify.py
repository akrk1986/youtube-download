"""Send Slack notifications for download status."""
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def send_slack_notification(webhook_url: str, status: str, url: str,
                           args_dict: dict,
                           elapsed_time: Optional[str] = None,
                           video_count: int = 0,
                           audio_count: int = 0) -> bool:
    """
    Send a Slack notification about download status.

    SECURITY NOTE: The webhook_url parameter must NEVER be logged or printed
    to avoid exposing the secret webhook URL in logs.

    Args:
        webhook_url: Slack webhook URL (NEVER log this value)
        status: 'start', 'success', or 'failure'
        url: The video/playlist URL that was downloaded
        args_dict: Dictionary of script arguments
        elapsed_time: Optional elapsed time string (e.g., '5m 23s')
        video_count: Number of video files created
        audio_count: Number of audio files created

    Returns:
        True if notification was sent successfully, False otherwise
    """
    if not webhook_url or webhook_url == 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL':
        logger.debug('Slack webhook not configured, skipping notification')
        return False

    # Build the message
    if status == 'start':
        icon = '🚀'
        title = f'{icon} Download STARTED'
    elif status == 'success':
        icon = '✅'
        title = f'{icon} Download SUCCESS'
    else:
        icon = '❌'
        title = f'{icon} Download FAILURE'

    # Format parameters for display
    param_lines = []

    # For start message, only show specific parameters
    if status == 'start':
        # Only show these parameters: with-audio, only-audio, split-chapters, title, artist, album
        filter_keys = ['with_audio', 'only_audio', 'split_chapters', 'title', 'artist', 'album']
        for key in filter_keys:
            value = args_dict.get(key)
            # Only show if value is truthy (not None, not False, not empty string)
            if value:
                param_lines.append(f'  • {key}: {value}')
    else:
        # For success/failure, show all non-empty parameters
        for key, value in args_dict.items():
            if value is not None and value is not False:
                # Skip the URL since it's shown separately
                if key != 'video_url':
                    param_lines.append(f'  • {key}: {value}')

    params_text = '\n'.join(param_lines) if param_lines else '  (default parameters)'

    # Build message text
    message_text = f'{title}\n\n*URL:* {url}\n\n*Parameters:*\n{params_text}'

    # Add file counts if status is success or failure
    if status in ['success', 'failure'] and (video_count > 0 or audio_count > 0):
        files_text = []
        if video_count > 0:
            files_text.append(f'{video_count} video file(s)')
        if audio_count > 0:
            files_text.append(f'{audio_count} audio file(s)')
        message_text += f'\n\n*Files created:* {", ".join(files_text)}'

    # Add elapsed time if provided
    if elapsed_time:
        message_text += f'\n\n*Elapsed time:* {elapsed_time}'

    # Create Slack message payload
    payload = {
        'text': message_text,
        'username': 'yt-dlp Bot',
        'icon_emoji': ':movie_camera:'
    }

    try:
        # Send POST request to Slack webhook
        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.ok:
            logger.debug(f'Slack notification sent: {status} (HTTP {response.status_code})')
            return True
        else:
            logger.warning(f'Slack notification failed with HTTP status {response.status_code}')
            return False

    except requests.Timeout:
        logger.warning('Failed to send Slack notification: Request timed out')
        return False
    except requests.ConnectionError:
        logger.warning('Failed to send Slack notification: Connection error')
        return False
    except requests.RequestException:
        # Generic request exception (avoid logging exception details that might contain webhook URL)
        logger.warning('Failed to send Slack notification: Request failed')
        return False
    except Exception as e:
        # Log exception type but not the message to avoid leaking webhook URL
        logger.warning(f'Unexpected error sending Slack notification: {type(e).__name__}')
        return False
