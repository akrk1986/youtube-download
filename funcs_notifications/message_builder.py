"""Shared message formatting for notification handlers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class NotificationData:
    """Data for building notification messages."""
    status: str
    url: str
    args_dict: dict
    session_id: str
    elapsed_time: Optional[str] = None
    video_count: int = 0
    audio_count: int = 0
    failure_reason: Optional[str] = None
    script_version: Optional[str] = None
    ytdlp_version: Optional[str] = None
    notif_msg_suffix: str = ''


@dataclass
class EmailMessage:
    """Email message with subject and HTML body."""
    subject: str
    html_body: str


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


class MessageBuilder(ABC):
    """Abstract base class for notification message builders."""

    @abstractmethod
    def build_message(self, data: NotificationData) -> Any:
        """Build a notification message from data.

        Returns:
            Message in format specific to the builder (str for Slack, EmailMessage for Email).
        """
        pass


class SlackMessageBuilder(MessageBuilder):
    """Build Slack-formatted notification messages."""

    def build_message(self, data: NotificationData) -> str:
        """Build a Slack markdown notification message."""
        emoji, word = _get_status_display(data.status)
        title = f'{emoji} Download {word}'
        if data.notif_msg_suffix:
            title = f'{title} - {data.notif_msg_suffix}'

        param_lines = _format_param_lines(status=data.status, args_dict=data.args_dict)
        if param_lines:
            params_text = '\n'.join(f'  • {key}: {value}' for key, value in param_lines)
        else:
            params_text = '  (default parameters)'

        message = f'{title}\n\n*Session:* {data.session_id}\n\n*URL:* {data.url}\n\n*Parameters:*\n{params_text}'

        # Add version info for start notifications
        if data.status == 'start' and (data.script_version or data.ytdlp_version):
            version_parts = []
            if data.script_version:
                version_parts.append(f'Script: {data.script_version}')
            if data.ytdlp_version:
                version_parts.append(f'yt-dlp: {data.ytdlp_version}')
            message += f'\n\n*Versions:*\n  • {"\n  • ".join(version_parts)}'

        if data.status == 'failure' and data.failure_reason:
            message += f'\n\n*Reason:* {data.failure_reason}'

        if data.status in ['success', 'failure', 'cancelled'] and (data.video_count > 0 or data.audio_count > 0):
            files_text = []
            if data.video_count > 0:
                files_text.append(f'{data.video_count} video file(s)')
            if data.audio_count > 0:
                files_text.append(f'{data.audio_count} audio file(s)')
            message += f'\n\n*Files created:* {", ".join(files_text)}'

        if data.elapsed_time:
            message += f'\n\n*Elapsed time:* {data.elapsed_time}'

        return message


class EmailMessageBuilder(MessageBuilder):
    """Build email notification messages."""

    def build_message(self, data: NotificationData) -> EmailMessage:
        """Build an email notification message with subject and HTML body."""
        emoji, word = _get_status_display(data.status)
        subject = f'{emoji} yt-dlp Download {word}'
        if data.notif_msg_suffix:
            subject = f'{subject} - {data.notif_msg_suffix}'

        # Build HTML body
        html_title = f'{emoji} Download {word}'
        if data.notif_msg_suffix:
            html_title = f'{html_title} - {data.notif_msg_suffix}'

        lines = [
            f'<h3>{html_title}</h3>',
            f'<p><b>Session:</b> {data.session_id}</p>',
            f'<p><b>URL:</b> {data.url}</p>',
        ]

        param_lines = _format_param_lines(status=data.status, args_dict=data.args_dict)
        if param_lines:
            lines.append('<p><b>Parameters:</b></p><ul>')
            for key, value in param_lines:
                lines.append(f'<li>{key}: {value}</li>')
            lines.append('</ul>')
        else:
            lines.append('<p><b>Parameters:</b> (default parameters)</p>')

        # Add version info for start notifications
        if data.status == 'start' and (data.script_version or data.ytdlp_version):
            lines.append('<p><b>Versions:</b></p><ul>')
            if data.script_version:
                lines.append(f'<li>Script: {data.script_version}</li>')
            if data.ytdlp_version:
                lines.append(f'<li>yt-dlp: {data.ytdlp_version}</li>')
            lines.append('</ul>')

        if data.status == 'failure' and data.failure_reason:
            lines.append(f'<p><b>Reason:</b> {data.failure_reason}</p>')

        if data.status in ['success', 'failure', 'cancelled'] and (data.video_count > 0 or data.audio_count > 0):
            files_parts = []
            if data.video_count > 0:
                files_parts.append(f'{data.video_count} video file(s)')
            if data.audio_count > 0:
                files_parts.append(f'{data.audio_count} audio file(s)')
            lines.append(f'<p><b>Files created:</b> {", ".join(files_parts)}</p>')

        if data.elapsed_time:
            lines.append(f'<p><b>Elapsed time:</b> {data.elapsed_time}</p>')

        html_body = '\n'.join(lines)
        return EmailMessage(subject=subject, html_body=html_body)
