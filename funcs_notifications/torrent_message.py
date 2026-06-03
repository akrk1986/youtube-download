"""Shared good/bad message formatting for torrent-completion notifications.

Used by the qBittorrent post-download notifiers (Gmail and Slack) so the
status -> emoji/headline logic is identical regardless of transport. Only the
delivery mechanism (SMTP vs Slack webhook) differs between the two scripts.
"""
from funcs_notifications.message_builder import EmailMessage


def torrent_status_display(is_bad: bool) -> tuple[str, str]:
    """Return (unicode_emoji, headline) for a torrent-completion status.

    Args:
        is_bad: True when the content is DoVi profile 5 (problematic for Plex).

    Returns:
        tuple[str, str]: The unicode emoji and the headline text.
    """
    if is_bad:
        return '⚠️', 'Torrent Complete — DoVi Profile 5 (may not play on Plex)'
    return '✅', 'Torrent Complete'


def build_torrent_slack_message(name: str, path: str, is_bad: bool) -> str:
    """Build the Slack markdown body for a completed torrent.

    Args:
        name: Torrent name.
        path: Full path to the downloaded content.
        is_bad: True when the content is DoVi profile 5.

    Returns:
        str: Slack-formatted message using emoji shortcodes.
    """
    shortcode = ':warning:' if is_bad else ':white_check_mark:'
    _, headline = torrent_status_display(is_bad=is_bad)
    return (
        f'{shortcode} *{headline}*\n'
        f'*Name:* {name}\n'
        f'*Location:* `{path}`'
    )


def build_torrent_email_message(name: str, path: str, is_bad: bool) -> EmailMessage:
    """Build the Gmail subject + HTML body for a completed torrent.

    Args:
        name: Torrent name.
        path: Full path to the downloaded content.
        is_bad: True when the content is DoVi profile 5.

    Returns:
        EmailMessage: Subject and HTML body using unicode emoji.
    """
    emoji, headline = torrent_status_display(is_bad=is_bad)
    subject = f'{emoji} {headline}'
    html_body = (
        f'<h3>{emoji} {headline}</h3>\n'
        f'<p><b>Name:</b> {name}</p>\n'
        f'<p><b>Location:</b> <code>{path}</code></p>'
    )
    return EmailMessage(subject=subject, html_body=html_body)
