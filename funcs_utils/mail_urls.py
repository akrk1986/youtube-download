"""Find self-sent mails that carry a single FB/YT video link, and track them with Gmail labels.

A mail qualifies when it comes from one of the allowed sender addresses and its body, once the
signature is removed, is exactly one non-blank line holding a YouTube/Facebook video URL. Forwarded
mails are supported: an inline forward's header block (``---------- Forwarded message ---------``,
From/Date/Subject/To) and every signature section are dropped before the one-line rule is applied;
mails forwarded as attachments (``message/rfc822``, what Gmail sends when several mails are
forwarded at once) are each classified on their own. Qualifying mails get the queue
label; after a successful download they move to the done label. Mails that do not qualify are never
labelled. Labels are changed through Gmail's ``X-GM-LABELS`` IMAP extension, which adds/removes a
label without moving or deleting the mail.
"""

import imaplib
import logging
import re
from dataclasses import dataclass
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parseaddr
from html.parser import HTMLParser
from typing import Any

from funcs_utils.media_url import extract_media_url

GMAIL_IMAP_HOST = 'imap.gmail.com'
MAILBOX = 'INBOX'
# RFC 3676 signature delimiter ('-- '). A signature starts at a line that is the delimiter alone
# (its trailing space is often stripped in transit) or that begins with it ('-- Amir', a signature
# whose text sits on the delimiter line).
SIGNATURE_DELIMITER = '--'
# HTML tags that start a new line when an HTML-only body is flattened to text.
_BLOCK_TAGS = frozenset({'br', 'div', 'p', 'li', 'tr', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'})

# The line that opens a forwarded message inline (Gmail, Outlook, Apple Mail).
_FORWARD_MARKER_RE = re.compile(
    r'^-{2,}\s*(?:Forwarded message|Original Message)\s*-{2,}$|^Begin forwarded message:$',
    re.IGNORECASE,
)
# A link rendered as 'text <target>' or '<target>' in a plain-text part.
_ANGLE_LINK_RE = re.compile(r'^(?:(\S+)\s+)?<(\S+)>$')

SKIP_OTHER_SENDER = 'sender not allowed'
SKIP_EMPTY_BODY = 'empty body'
SKIP_MULTIPLE_LINES = 'more than one line'
SKIP_NOT_MEDIA_URL = 'not a FB/YT video URL'
SKIP_TEXT_WITH_ATTACHMENTS = 'text besides the forwarded mails'
SKIP_NO_ATTACHED_LINK = 'no forwarded mail holds a single FB/YT link'

logger = logging.getLogger(__name__)


@dataclass
class MailCandidate:
    """One scanned mail: its IMAP UID, subject, and either its media URLs or the reason it was skipped.

    A mail holds one URL, or several when it carries several forwarded mails as attachments.
    """
    uid: str
    subject: str
    urls: list[str]
    skip_reason: str | None


class _TextExtractor(HTMLParser):
    """Collect the text of an HTML document, starting a new line at block-level tags."""

    def __init__(self) -> None:
        """Start with an empty text buffer."""
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Break the line before a block-level element.

        Args:
            tag: The tag name.
            attrs: The tag attributes (unused).
        """
        del attrs  # required by the HTMLParser signature
        if tag in _BLOCK_TAGS:
            self.parts.append('\n')

    def handle_data(self, data: str) -> None:
        """Keep a run of text.

        Args:
            data: The text between tags.
        """
        self.parts.append(data)


def _html_to_text(html: str) -> str:
    """Flatten an HTML body to plain text, one line per block element.

    Args:
        html: The HTML body.

    Returns:
        str: The text content.
    """
    extractor = _TextExtractor()
    extractor.feed(html)
    extractor.close()
    return ''.join(extractor.parts)


def _body_text(msg: EmailMessage) -> str:
    """Return the mail body as text, preferring the text/plain part over text/html.

    Args:
        msg: The parsed mail.

    Returns:
        str: The body text, or '' when the mail has no text part.
    """
    plain = msg.get_body(preferencelist=('plain',))
    if plain is not None:
        return plain.get_content()
    html = msg.get_body(preferencelist=('html',))
    if html is not None:
        return _html_to_text(html=html.get_content())
    return ''


def _unwrap_angle_link(line: str) -> str:
    """Reduce '<url>' or 'url <url>' (how plain-text parts render a link) to the bare URL.

    Args:
        line: A stripped body line.

    Returns:
        str: The bare URL, or the line unchanged when it isn't such a link.
    """
    match = _ANGLE_LINK_RE.match(line)
    if match and match.group(1) in (None, match.group(2)):
        return match.group(2)
    return line


def _content_lines(text: str) -> list[str]:
    """Return the non-blank body lines, without signatures and inline-forward header blocks.

    A signature section runs from a '-- ' line to the next forward marker (or the end),
    so the forwarder's own signature above a forwarded message doesn't hide that message.

    Args:
        text: The body text.

    Returns:
        list[str]: The remaining lines, stripped, links reduced to bare URLs.
    """
    lines: list[str] = []
    in_signature = False
    in_forward_header = False
    for raw in text.splitlines():
        line = raw.strip()
        if _FORWARD_MARKER_RE.match(line):
            in_signature = False
            in_forward_header = True
            continue
        if in_forward_header:
            # The header block (From/Date/Subject/To, a long Subject wrapped onto extra lines)
            # ends at the first blank line.
            in_forward_header = bool(line)
            continue
        if raw.rstrip() == SIGNATURE_DELIMITER or raw.startswith(f'{SIGNATURE_DELIMITER} '):
            in_signature = True
            continue
        if line and not in_signature:
            lines.append(_unwrap_angle_link(line=line))
    return lines


def _classify_body(msg: EmailMessage) -> tuple[str | None, str | None]:
    """Apply the one-line rule to a mail body.

    Args:
        msg: The mail (or a forwarded mail attached to it).

    Returns:
        tuple[str | None, str | None]: ``(url, None)`` when the body is a single media URL, else
            ``(None, skip_reason)``.
    """
    lines = _content_lines(text=_body_text(msg=msg))
    if not lines:
        return None, SKIP_EMPTY_BODY
    if len(lines) > 1:
        return None, SKIP_MULTIPLE_LINES
    url = extract_media_url(lines[0])
    if url is None:
        return None, SKIP_NOT_MEDIA_URL
    return url, None


def _attached_messages(msg: EmailMessage) -> list[EmailMessage]:
    """Return the mails forwarded as attachments (message/rfc822 parts).

    Args:
        msg: The mail.

    Returns:
        list[EmailMessage]: The attached mails, in order.
    """
    attached: list[EmailMessage] = []
    for part in msg.iter_attachments():
        if part.get_content_type() == 'message/rfc822':
            inner = part.get_content()
            if isinstance(inner, EmailMessage):
                attached.append(inner)
    return attached


def classify_message(msg: EmailMessage, senders: set[str]) -> tuple[list[str], str | None]:
    """Decide whether a mail qualifies and extract its URLs.

    Args:
        msg: The parsed mail.
        senders: The allowed sender addresses, lower-case.

    Returns:
        tuple[list[str], str | None]: ``(urls, None)`` for a qualifying mail, else
            ``([], skip_reason)``.
    """
    sender = parseaddr(str(msg.get('From', '')))[1]
    if sender.lower() not in senders:
        return [], SKIP_OTHER_SENDER
    attached = _attached_messages(msg=msg)
    if not attached:
        url, skip_reason = _classify_body(msg=msg)
        return ([url], None) if url is not None else ([], skip_reason)
    if _content_lines(text=_body_text(msg=msg)):
        return [], SKIP_TEXT_WITH_ATTACHMENTS
    urls: list[str] = []
    for inner in attached:
        url, skip_reason = _classify_body(msg=inner)
        if url is None:
            logger.info(f"  forwarded mail '{inner.get('Subject', '')}' skipped: {skip_reason}")
        elif url not in urls:
            urls.append(url)
    return (urls, None) if urls else ([], SKIP_NO_ATTACHED_LINK)


def connect(address: str, app_password: str) -> imaplib.IMAP4_SSL:
    """Log in to Gmail over IMAP.

    Args:
        address: The Gmail address.
        app_password: A Gmail App Password (the one used for SMTP notifications works).

    Returns:
        imaplib.IMAP4_SSL: The logged-in connection.
    """
    imap = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST)
    imap.login(address, app_password)
    return imap


def ensure_labels(imap: imaplib.IMAP4, labels: list[str]) -> None:
    """Create Gmail labels that do not exist yet (an existing label makes CREATE fail harmlessly).

    Args:
        imap: The logged-in connection.
        labels: The label names.
    """
    for label in labels:
        status, _ = imap.create(f'"{label}"')
        logger.debug(f"CREATE label '{label}': {status}")


def _check(status: str, data: list[Any], action: str) -> list[Any]:
    """Raise when an IMAP command did not return OK.

    Args:
        status: The command status.
        data: The command response data.
        action: What was attempted, for the error message.

    Returns:
        list[Any]: The response data, unchanged.

    Raises:
        imaplib.IMAP4.error: When the status is not OK.
    """
    if status != 'OK':
        raise imaplib.IMAP4.error(f'IMAP {action} failed: {status} {data!r}')
    return data


def search_candidates(imap: imaplib.IMAP4, senders: set[str], done_label: str) -> list[str]:
    """Return the UIDs of inbox mails from the allowed senders that do not carry the done label.

    Mails that already carry the queue label are included, so a failed download is retried.

    Args:
        imap: The connection, with the inbox selected.
        senders: The allowed sender addresses.
        done_label: The label marking mails whose download succeeded.

    Returns:
        list[str]: The matching UIDs, oldest first.
    """
    from_terms = ' OR '.join(f'from:{sender}' for sender in sorted(senders))
    status, data = imap.uid('SEARCH', 'X-GM-RAW', f'"({from_terms}) -label:{done_label}"')
    data = _check(status=status, data=data, action='SEARCH')
    return data[0].decode().split() if data and data[0] else []


def fetch_message(imap: imaplib.IMAP4, uid: str) -> EmailMessage:
    """Fetch and parse one mail without marking it read.

    Args:
        imap: The connection, with the inbox selected.
        uid: The mail's UID.

    Returns:
        EmailMessage: The parsed mail.
    """
    status, data = imap.uid('FETCH', uid, '(BODY.PEEK[])')
    data = _check(status=status, data=data, action=f'FETCH {uid}')
    raw = next(part[1] for part in data if isinstance(part, tuple))
    msg = message_from_bytes(raw, policy=policy.default)
    assert isinstance(msg, EmailMessage)  # nosec B101 - policy.default always yields EmailMessage
    return msg


def change_label(imap: imaplib.IMAP4, uid: str, label: str, add: bool) -> None:
    """Add or remove one Gmail label on a mail.

    Args:
        imap: The connection, with the inbox selected read-write.
        uid: The mail's UID.
        label: The label name.
        add: True to add the label, False to remove it.
    """
    op = '+X-GM-LABELS' if add else '-X-GM-LABELS'
    status, data = imap.uid('STORE', uid, op, f'("{label}")')
    _check(status=status, data=data, action=f'STORE {op} {label} on {uid}')


def scan_mailbox(imap: imaplib.IMAP4, senders: set[str], queue_label: str, done_label: str,
                 apply_labels: bool) -> list[MailCandidate]:
    """Classify every candidate mail and, when asked, add the queue label to the qualifying ones.

    Args:
        imap: The connection, with the inbox selected (read-write when ``apply_labels``).
        senders: The allowed sender addresses, lower-case.
        queue_label: The label added to qualifying mails.
        done_label: The label marking mails already downloaded (those are not scanned).
        apply_labels: False for a dry run: classify only, change nothing.

    Returns:
        list[MailCandidate]: One entry per scanned mail, accepted and skipped alike.
    """
    results: list[MailCandidate] = []
    for uid in search_candidates(imap=imap, senders=senders, done_label=done_label):
        msg = fetch_message(imap=imap, uid=uid)
        urls, skip_reason = classify_message(msg=msg, senders=senders)
        results.append(MailCandidate(uid=uid, subject=str(msg.get('Subject', '')), urls=urls,
                                     skip_reason=skip_reason))
        if urls and apply_labels:
            change_label(imap=imap, uid=uid, label=queue_label, add=True)
    return results


def mark_done(imap: imaplib.IMAP4, uid: str, queue_label: str, done_label: str) -> None:
    """Move a mail from the queue label to the done label after its download succeeded.

    Args:
        imap: The connection, with the inbox selected read-write.
        uid: The mail's UID.
        queue_label: The label to remove.
        done_label: The label to add.
    """
    change_label(imap=imap, uid=uid, label=done_label, add=True)
    change_label(imap=imap, uid=uid, label=queue_label, add=False)
