"""Shared message formatting for notification handlers."""
from typing import Optional


def _get_status_display(status: str) -> tuple[str, str]:
    """Return (emoji, title_word) for a given status."""
    status_map = {
        'start': ('🚀', 'STARTED'),
        'success': ('✅', 'SUCCESS'),
        'cancelled': ('🛑', 'CANCELLED'),
    }
    emoji, word = status_map.get(status, ('❌', 'FAILURE'))
    return emoji, word


def _format_param_lines(status: str, args_dict: dict) -> list[tuple[str, str]]:
    """Return list of (key, value) tuples for display parameters."""
    param_lines: list[tuple[str, str]] = []

    if status == 'start':
        filter_keys = ['with_audio', 'only_audio', 'split_chapters', 'title', 'artist', 'album']
        for key in filter_keys:
            value = args_dict.get(key)
            if value:
                param_lines.append((key, str(value)))
    else:
        for key, value in args_dict.items():
            if value is not None and value is not False:
                if key != 'video_url':
                    param_lines.append((key, str(value)))

    return param_lines


def build_slack_message(status: str, url: str, args_dict: dict,
                        session_id: str, elapsed_time: Optional[str] = None,
                        video_count: int = 0, audio_count: int = 0,
                        failure_reason: Optional[str] = None,
                        script_version: Optional[str] = None,
                        ytdlp_version: Optional[str] = None,
                        notif_msg_suffix: str = '') -> str:
    """Build a Slack-formatted notification message.

    Args:
        notif_msg_suffix: Optional suffix to append to title (e.g., 'PROD')

    Returns:
        Slack markdown message string.
    """
    emoji, word = _get_status_display(status)
    title = f'{emoji} Download {word}'
    if notif_msg_suffix:
        title = f'{title} - {notif_msg_suffix}'

    param_lines = _format_param_lines(status=status, args_dict=args_dict)
    if param_lines:
        params_text = '\n'.join(f'  • {key}: {value}' for key, value in param_lines)
    else:
        params_text = '  (default parameters)'

    message = f'{title}\n\n*Session:* {session_id}\n\n*URL:* {url}\n\n*Parameters:*\n{params_text}'

    # Add version info for start notifications
    if status == 'start' and (script_version or ytdlp_version):
        version_parts = []
        if script_version:
            version_parts.append(f'Script: {script_version}')
        if ytdlp_version:
            version_parts.append(f'yt-dlp: {ytdlp_version}')
        message += f'\n\n*Versions:*\n  • {"\n  • ".join(version_parts)}'

    if status == 'failure' and failure_reason:
        message += f'\n\n*Reason:* {failure_reason}'

    if status in ['success', 'failure', 'cancelled'] and (video_count > 0 or audio_count > 0):
        files_text = []
        if video_count > 0:
            files_text.append(f'{video_count} video file(s)')
        if audio_count > 0:
            files_text.append(f'{audio_count} audio file(s)')
        message += f'\n\n*Files created:* {", ".join(files_text)}'

    if elapsed_time:
        message += f'\n\n*Elapsed time:* {elapsed_time}'

    return message


def build_email_message(status: str, url: str, args_dict: dict,
                        session_id: str, elapsed_time: Optional[str] = None,
                        video_count: int = 0, audio_count: int = 0,
                        failure_reason: Optional[str] = None,
                        script_version: Optional[str] = None,
                        ytdlp_version: Optional[str] = None,
                        notif_msg_suffix: str = '') -> tuple[str, str]:
    """Build an email notification message.

    Args:
        notif_msg_suffix: Optional suffix to append to subject and body title

    Returns:
        Tuple of (subject, html_body).
    """
    emoji, word = _get_status_display(status)
    subject = f'{emoji} yt-dlp Download {word}'
    if notif_msg_suffix:
        subject = f'{subject} - {notif_msg_suffix}'

    # Build HTML body
    html_title = f'{emoji} Download {word}'
    if notif_msg_suffix:
        html_title = f'{html_title} - {notif_msg_suffix}'

    lines = [
        f'<h3>{html_title}</h3>',
        f'<p><b>Session:</b> {session_id}</p>',
        f'<p><b>URL:</b> {url}</p>',
    ]

    param_lines = _format_param_lines(status=status, args_dict=args_dict)
    if param_lines:
        lines.append('<p><b>Parameters:</b></p><ul>')
        for key, value in param_lines:
            lines.append(f'<li>{key}: {value}</li>')
        lines.append('</ul>')
    else:
        lines.append('<p><b>Parameters:</b> (default parameters)</p>')

    # Add version info for start notifications
    if status == 'start' and (script_version or ytdlp_version):
        lines.append('<p><b>Versions:</b></p><ul>')
        if script_version:
            lines.append(f'<li>Script: {script_version}</li>')
        if ytdlp_version:
            lines.append(f'<li>yt-dlp: {ytdlp_version}</li>')
        lines.append('</ul>')

    if status == 'failure' and failure_reason:
        lines.append(f'<p><b>Reason:</b> {failure_reason}</p>')

    if status in ['success', 'failure', 'cancelled'] and (video_count > 0 or audio_count > 0):
        files_parts = []
        if video_count > 0:
            files_parts.append(f'{video_count} video file(s)')
        if audio_count > 0:
            files_parts.append(f'{audio_count} audio file(s)')
        lines.append(f'<p><b>Files created:</b> {", ".join(files_parts)}</p>')

    if elapsed_time:
        lines.append(f'<p><b>Elapsed time:</b> {elapsed_time}</p>')

    html_body = '\n'.join(lines)
    return subject, html_body
