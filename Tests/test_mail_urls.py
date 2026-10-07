"""Tests for the self-sent mail scanner (funcs_utils.mail_urls) — no network, fake IMAP object."""

from email.message import EmailMessage

import pytest

from funcs_utils.mail_urls import (SKIP_EMPTY_BODY, SKIP_MULTIPLE_LINES, SKIP_NO_ATTACHED_LINK,
                                   SKIP_NOT_MEDIA_URL, SKIP_OTHER_SENDER, SKIP_TEXT_WITH_ATTACHMENTS,
                                   classify_message, mark_done, scan_mailbox)

ME = 'me@gmail.com'
SENDERS = {ME, 'main@gmail.com'}
YT_URL = 'https://www.youtube.com/watch?v=abc123'
FB_URL = 'https://www.facebook.com/reel/1234567890'


def _mail(body: str, subject: str = 'Video', sender: str = f'Me <{ME}>', html: str | None = None) -> EmailMessage:
    """Build a mail with a plain-text body and an optional HTML alternative.

    Args:
        body: The text/plain body ('' for an HTML-only mail when ``html`` is given).
        subject: The subject.
        sender: The From header.
        html: An optional text/html body.

    Returns:
        EmailMessage: The mail.
    """
    msg = EmailMessage()
    msg['From'] = sender
    msg['To'] = ME
    msg['Subject'] = subject
    if html is not None and not body:
        msg.set_content(html, subtype='html')
        return msg
    msg.set_content(body)
    if html is not None:
        msg.add_alternative(html, subtype='html')
    return msg


@pytest.mark.parametrize('subject', ['Song', 'Τραγούδι', 'שיר'])
def test_subject_language_does_not_matter(subject: str) -> None:
    """English, Greek and Hebrew subjects are all accepted."""
    assert classify_message(msg=_mail(body=f'{YT_URL}\n', subject=subject), senders=SENDERS) == ([YT_URL], None)


def test_signature_is_ignored() -> None:
    """Lines after the '-- ' delimiter don't count."""
    body = f'{FB_URL}\n\n-- \nAmir\nhttps://example.com\n'
    assert classify_message(msg=_mail(body=body), senders=SENDERS) == ([FB_URL], None)


def test_sender_match_is_case_insensitive() -> None:
    """The From address is compared case-insensitively."""
    assert classify_message(msg=_mail(body=YT_URL, sender='ME@Gmail.com'), senders=SENDERS) == ([YT_URL], None)


def test_other_sender_is_skipped() -> None:
    """A mail from someone else is skipped."""
    msg = _mail(body=YT_URL, sender='other@gmail.com')
    assert classify_message(msg=msg, senders=SENDERS) == ([], SKIP_OTHER_SENDER)


@pytest.mark.parametrize(('body', 'reason'), [
    (f'look at this\n{YT_URL}\n', SKIP_MULTIPLE_LINES),
    ('https://vimeo.com/12345\n', SKIP_NOT_MEDIA_URL),
    (f'see {YT_URL}\n', SKIP_NOT_MEDIA_URL),
    ('\n\n-- \nAmir\n', SKIP_EMPTY_BODY),
])
def test_body_rules(body: str, reason: str) -> None:
    """Only a single media-URL line qualifies."""
    assert classify_message(msg=_mail(body=body), senders=SENDERS) == ([], reason)


def test_gmail_inline_forward() -> None:
    """A real Gmail inline forward: header block with a wrapped Subject, '-- Amir' signatures."""
    body = ('---------- Forwarded message ---------\r\nFrom: Me <main@gmail.com>\r\n'
            'Date: Wed, 7 Oct 2026 at 10:49\r\nSubject: έβγαλα βόλτα τη μοναξιά μου;-Χαρούλα\r\n'
            'Χαρ Τ...\r\nTo: Me <main@gmail.com>\r\n\r\n\r\n' + YT_URL + '\r\n\r\n'
            '-- Amir אמיר\r\n\r\n\r\n-- \r\n-- Amir אמיר\r\n')
    msg = _mail(body=body, subject='Fwd: έβγαλα', sender='Me <main@gmail.com>')
    assert classify_message(msg=msg, senders=SENDERS) == ([YT_URL], None)


def test_signature_above_forward_does_not_hide_it() -> None:
    """The forwarder's signature section ends at the forward marker."""
    body = f'-- Amir\n---------- Forwarded message ---------\nFrom: Me <{ME}>\nTo: x\n\n{FB_URL}\n'
    assert classify_message(msg=_mail(body=body), senders=SENDERS) == ([FB_URL], None)


def _forward_as_attachments(*inner: EmailMessage, text: str = '') -> EmailMessage:
    """Build a mail that carries other mails as message/rfc822 attachments.

    Args:
        *inner: The forwarded mails.
        text: The outer body text.

    Returns:
        EmailMessage: The outer mail.
    """
    outer = _mail(body=text or '-- \nAmir\n')
    for msg in inner:
        outer.add_attachment(msg)
    return outer


def test_forward_as_attachments() -> None:
    """Each attached mail is classified; qualifying URLs are collected, duplicates once."""
    outer = _forward_as_attachments(_mail(body=YT_URL), _mail(body='two\nlines'), _mail(body=FB_URL),
                                    _mail(body=YT_URL))
    assert classify_message(msg=outer, senders=SENDERS) == ([YT_URL, FB_URL], None)


def test_forward_as_attachments_skips() -> None:
    """Outer text, or no qualifying attached mail, skips the mail."""
    with_text = _forward_as_attachments(_mail(body=YT_URL), text='see these')
    assert classify_message(msg=with_text, senders=SENDERS) == ([], SKIP_TEXT_WITH_ATTACHMENTS)
    no_link = _forward_as_attachments(_mail(body='hello'))
    assert classify_message(msg=no_link, senders=SENDERS) == ([], SKIP_NO_ATTACHED_LINK)


def test_angle_bracket_link() -> None:
    """A plain-text link rendered as 'url <url>' reduces to the URL."""
    assert classify_message(msg=_mail(body=f'{YT_URL} <{YT_URL}>'), senders=SENDERS) == ([YT_URL], None)


def test_gmail_redirect_is_unwrapped() -> None:
    """A Google-redirect-wrapped link yields the clean target URL."""
    wrapped = 'https://www.google.com/url?q=https://www.youtube.com/watch?v%3Dabc123&source=gmail'
    assert classify_message(msg=_mail(body=wrapped), senders=SENDERS) == ([YT_URL], None)


def test_html_only_body() -> None:
    """An HTML-only mail is flattened to text before the checks."""
    html = f'<div dir="ltr"><a href="{YT_URL}">{YT_URL}</a></div><br>-- <br><div>Amir</div>'
    assert classify_message(msg=_mail(body='', html=html), senders=SENDERS) == ([YT_URL], None)


class FakeImap:
    """Records UID commands and serves canned mails by UID."""

    def __init__(self, mails: dict[str, EmailMessage]) -> None:
        """Store the mails served by FETCH.

        Args:
            mails: The mails, keyed by UID.
        """
        self.mails = mails
        self.stores: list[tuple[str, str, str]] = []
        self.search_query = ''

    def uid(self, command: str, *args: str) -> tuple[str, list[object]]:
        """Answer SEARCH / FETCH / STORE like imaplib does.

        Args:
            command: The UID command.
            *args: The command arguments.

        Returns:
            tuple[str, list[object]]: The status and response data.
        """
        if command == 'SEARCH':
            self.search_query = args[1]
            return 'OK', [' '.join(self.mails).encode()]
        if command == 'FETCH':
            return 'OK', [(b'1 (BODY[] {0}', self.mails[args[0]].as_bytes()), b')']
        self.stores.append((args[0], args[1], args[2]))
        return 'OK', [b'']


def test_scan_labels_only_qualifying_mails() -> None:
    """Only accepted mails get the queue label; the search excludes the done label."""
    imap = FakeImap(mails={'1': _mail(body=YT_URL), '2': _mail(body='hello\nthere'),
                           '3': _mail(body=FB_URL, sender='x@y.com')})
    results = scan_mailbox(imap=imap, senders=SENDERS, queue_label='yt-queue',  # type: ignore[arg-type]
                           done_label='yt-done', apply_labels=True)
    assert [r.urls for r in results] == [[YT_URL], [], []]
    assert imap.stores == [('1', '+X-GM-LABELS', '("yt-queue")')]
    assert imap.search_query == '"(from:main@gmail.com OR from:me@gmail.com) -label:yt-done"'


def test_scan_dry_run_changes_no_labels() -> None:
    """A dry run classifies but stores nothing."""
    imap = FakeImap(mails={'1': _mail(body=YT_URL)})
    results = scan_mailbox(imap=imap, senders=SENDERS, queue_label='yt-queue',  # type: ignore[arg-type]
                           done_label='yt-done', apply_labels=False)
    assert results[0].urls == [YT_URL]
    assert not imap.stores


def test_mark_done_moves_label() -> None:
    """A success adds the done label and removes the queue label."""
    imap = FakeImap(mails={})
    mark_done(imap=imap, uid='7', queue_label='yt-queue', done_label='yt-done')  # type: ignore[arg-type]
    assert imap.stores == [('7', '+X-GM-LABELS', '("yt-done")'), ('7', '-X-GM-LABELS', '("yt-queue")')]
