"""Send Slack notifications for download status."""
import logging

import requests

logger = logging.getLogger(__name__)


def send_slack_notification(webhook_url: str, status: str, url: str,
                           audio_formats: list[str], args_dict: dict) -> bool:
    """
    Send a Slack notification about download status.

    Args:
        webhook_url: Slack webhook URL
        status: 'success' or 'failure'
        url: The video/playlist URL that was downloaded
        audio_formats: List of audio formats used
        args_dict: Dictionary of script arguments

    Returns:
        True if notification was sent successfully, False otherwise
    """
    if not webhook_url or webhook_url == 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL':
        logger.debug('Slack webhook not configured, skipping notification')
        return False

    # Build the message
    icon = '✅' if status == 'success' else '❌'
    title = f'{icon} Download {status.upper()}'

    # Format parameters for display
    param_lines = []
    for key, value in args_dict.items():
        if value is not None and value is not False:
            # Skip the URL since it's shown separately
            if key != 'video_url':
                param_lines.append(f'  • {key}: {value}')

    params_text = '\n'.join(param_lines) if param_lines else '  (default parameters)'

    # Build message text
    message_text = f'{title}\n\n*URL:* {url}\n\n*Audio formats:* {", ".join(audio_formats)}\n\n*Parameters:*\n{params_text}'

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
            logger.warning(f'Slack notification failed with status {response.status_code}')
            return False

    except requests.RequestException as e:
        logger.warning(f'Failed to send Slack notification: {e}')
        return False
    except Exception as e:
        logger.warning(f'Unexpected error sending Slack notification: {e}')
        return False
