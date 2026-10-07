#!/usr/bin/env python3
"""Download the FB/YouTube videos linked in mails you sent yourself, or every URL in a file.

Two input modes:

- ``--from-mail``: scans the Gmail inbox (IMAP, with the App Password from ``GMAIL_PARAMS`` in
  ``git_excluded.py``) for mails from the allowed senders whose body — signature excluded — is a
  single FB/YT video link. Forwarded mails (inline or as attachments) are supported. Each
  qualifying mail gets the queue label and its URL is written to
  ``yt-queue/dl-candidates-<timestamp>.txt``. With ``--download`` each URL is then downloaded, and
  a mail whose download succeeded moves from the queue label to the done label. Mails that don't
  qualify are never labelled; mails with the done label are not scanned again.
- ``--url-file``: downloads every URL found in a .txt/.odt file (e.g. a dl-candidates file).

Unknown flags (``--only-audio``, ``--audio-format mp3``, ...) are forwarded to ``main-yt-dlp.py``,
which is run once per URL.
"""
import argparse
import logging
import os
import subprocess  # nosec B404
import sys
from pathlib import Path

import arrow

# Allow imports of project packages when this script is invoked directly from Utils/.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# pylint: disable=wrong-import-position
from common_av.text import count_noun  # noqa: E402
from funcs_utils import sanitize_url_for_subprocess, setup_logging  # noqa: E402
from funcs_utils.mail_urls import (MAILBOX, MailCandidate, connect, ensure_labels,  # noqa: E402
                                   mark_done, scan_mailbox)
from funcs_video_info.url_extraction import extract_urls_from_file  # noqa: E402

GMAIL_PARAMS: dict[str, str] | None = None
try:
    from git_excluded import GMAIL_PARAMS  # type: ignore[assignment,no-redef,attr-defined]  # noqa: E402
except ImportError:
    pass

VERSION = '2026-10-07-1808'
DRIVER_SCRIPT = _PROJECT_ROOT / 'main-yt-dlp.py'
CANDIDATES_DIR = _PROJECT_ROOT / 'yt-queue'

logger = logging.getLogger(__name__)


def parse_arguments(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    """Parse known args and collect unknown args for pass-through to main-yt-dlp.py.

    Args:
        argv: Arguments to parse (defaults to sys.argv[1:]).

    Returns:
        tuple[argparse.Namespace, list[str]]: Parsed args and the unknown args to forward.
    """
    parser = argparse.ArgumentParser(
        description='Download FB/YouTube links from self-sent Gmail mails, or every URL in a file. '
                    'Unknown flags are forwarded to main-yt-dlp.py.')
    parser.add_argument('--download', action='store_true',
                        help='With --from-mail: download the found URLs and label the mails done')
    parser.add_argument('--dry-run', action='store_true',
                        help='With --from-mail: write the dl-candidates file, but download nothing '
                             'and change no labels')
    parser.add_argument('--out-file', type=Path,
                        help='With --from-mail: where to write the found URLs '
                             '(default: yt-queue/dl-candidates-<timestamp>.txt)')
    parser.add_argument('--sender', action='append',
                        help='Accept mails from this address (repeatable; default: the recipient_email '
                             'and sender_email of GMAIL_PARAMS)')
    parser.add_argument('--queue-label', default='yt-queue',
                        help='Gmail label for qualifying mails not yet downloaded (default: %(default)s)')
    parser.add_argument('--done-label', default='yt-done',
                        help='Gmail label for mails whose download succeeded (default: %(default)s)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable DEBUG logging')
    # --version is listed last, just before the mutually-exclusive groups.
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')

    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument('--from-mail', action='store_true',
                              help='Scan the Gmail inbox for self-sent single-link mails')
    source_group.add_argument('--url-file', type=Path,
                              help='Download every URL in this .txt/.odt file')
    return parser.parse_known_args(argv)


def _log_scan_results(results: list[MailCandidate]) -> None:
    """Log one line per scanned mail: accepted with its URL, or skipped with the reason.

    Args:
        results: The scanned mails.
    """
    accepted = [r for r in results if r.urls]
    logger.info(f'Scanned {count_noun(len(results), "mail")}, {len(accepted)} accepted')
    for r in results:
        status = 'ACCEPT' if r.urls else 'SKIP  '
        detail = ' '.join(r.urls) if r.urls else r.skip_reason
        logger.info(f'  {status} uid={r.uid:<6} {r.subject[:50]:<50}  {detail}')


def _write_candidates(urls: list[str], out_file: Path) -> None:
    """Write the URLs, one per line, creating the parent directory when needed.

    Args:
        urls: The URLs to write.
        out_file: The target file.
    """
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(''.join(f'{url}\n' for url in urls), encoding='utf-8')
    logger.info(f"Wrote {count_noun(len(urls), 'URL')} to '{out_file}'")


def _download(url: str, passthrough_args: list[str], gate: bool) -> bool:
    """Run main-yt-dlp.py for one URL.

    Args:
        url: The video URL.
        passthrough_args: Extra flags forwarded to main-yt-dlp.py.
        gate: False sets LINTER_GATE=off, so the linter-freshness prompt shows only once per batch.

    Returns:
        bool: True when the download exited with code 0.
    """
    argv = [sys.executable, str(DRIVER_SCRIPT), *passthrough_args, sanitize_url_for_subprocess(url=url)]
    env = None if gate else {**os.environ, 'LINTER_GATE': 'off'}
    logger.info(f'Downloading {url}')
    logger.debug(f'Subprocess argv: {argv}')
    completed = subprocess.run(argv, check=False, cwd=_PROJECT_ROOT, env=env)  # nosec B603
    if completed.returncode != 0:
        logger.error(f'Download failed (exit code {completed.returncode}): {url}')
    return completed.returncode == 0


def _run_from_mail(args: argparse.Namespace, passthrough_args: list[str]) -> int:
    """Scan the inbox, write the candidates file, and optionally download + relabel.

    Args:
        args: The parsed arguments.
        passthrough_args: Extra flags forwarded to main-yt-dlp.py.

    Returns:
        int: The process exit code (1 when any download failed or the mail settings are missing).
    """
    if not GMAIL_PARAMS:
        logger.error('GMAIL_PARAMS not found in git_excluded.py')
        return 1
    address = GMAIL_PARAMS['sender_email']
    password = GMAIL_PARAMS['sender_app_password']
    sender_list = args.sender or [GMAIL_PARAMS.get('recipient_email', ''), address]
    senders = {s.strip().lower() for s in sender_list if s and s.strip()}
    logger.info(f"Scanning {address}'s inbox for mails from: {', '.join(sorted(senders))}")
    labels = {'queue_label': args.queue_label, 'done_label': args.done_label}

    imap = connect(address=address, app_password=password)
    try:
        if not args.dry_run:
            ensure_labels(imap=imap, labels=[args.queue_label, args.done_label])
        imap.select(MAILBOX, readonly=args.dry_run)
        results = scan_mailbox(imap=imap, senders=senders, apply_labels=not args.dry_run, **labels)
    finally:
        imap.logout()

    _log_scan_results(results=results)
    urls_by_uid = {r.uid: r.urls for r in results if r.urls}
    all_urls = list(dict.fromkeys(url for urls in urls_by_uid.values() for url in urls))
    if not all_urls:
        logger.info('No qualifying mails found')
        return 0

    timestamp = arrow.now().format('YYYY-MM-DD-HHmm')
    out_file = args.out_file or CANDIDATES_DIR / f'dl-candidates-{timestamp}.txt'
    _write_candidates(urls=all_urls, out_file=out_file)

    if args.dry_run:
        if args.download:
            logger.info('--dry-run: skipping the downloads')
        return 0
    if not args.download:
        return 0

    succeeded: set[str] = set()
    for idx, url in enumerate(all_urls):
        if not _download(url=url, passthrough_args=passthrough_args, gate=idx == 0):
            continue
        succeeded.add(url)
        # Relabel each mail as soon as all of its URLs are downloaded. A fresh connection per
        # relabel: a long download can outlive an idle IMAP session.
        done_uids = [uid for uid, urls in urls_by_uid.items() if set(urls) <= succeeded]
        if not done_uids:
            continue
        imap = connect(address=address, app_password=password)
        try:
            imap.select(MAILBOX)
            for uid in done_uids:
                mark_done(imap=imap, uid=uid, **labels)
                del urls_by_uid[uid]
        finally:
            imap.logout()
    logger.info(f'Downloaded {len(succeeded)} of {count_noun(len(all_urls), "URL")}')
    return 0 if len(succeeded) == len(all_urls) else 1


def _run_from_file(url_file: Path, passthrough_args: list[str]) -> int:
    """Download every URL found in a .txt/.odt file.

    Args:
        url_file: The file holding the URLs.
        passthrough_args: Extra flags forwarded to main-yt-dlp.py.

    Returns:
        int: The process exit code (1 when any download failed or the file can't be read).
    """
    try:
        urls = list(dict.fromkeys(extract_urls_from_file(file_path=url_file)))
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        return 1
    if not urls:
        logger.info(f"No URLs found in '{url_file}'")
        return 0
    logger.info(f"Found {count_noun(len(urls), 'URL')} in '{url_file}'")
    failed = sum(not _download(url=url, passthrough_args=passthrough_args, gate=idx == 0)
                 for idx, url in enumerate(urls))
    logger.info(f'Downloaded {len(urls) - failed} of {count_noun(len(urls), "URL")}')
    return 1 if failed else 0


def main() -> int:
    """Entry point: dispatch to the mail or file mode.

    Returns:
        int: The process exit code.
    """
    args, passthrough_args = parse_arguments()
    setup_logging(verbose=args.verbose, log_dir=_PROJECT_ROOT / 'Logs')
    if passthrough_args:
        logger.info(f'Forwarding to main-yt-dlp.py: {" ".join(passthrough_args)}')
    if args.url_file is not None:
        return _run_from_file(url_file=args.url_file, passthrough_args=passthrough_args)
    return _run_from_mail(args=args, passthrough_args=passthrough_args)


if __name__ == '__main__':
    sys.exit(main())
