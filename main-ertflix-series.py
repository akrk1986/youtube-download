#!/usr/bin/env python3
"""Interactive ERTFlix series browser: pick season + episode, then download.

Without a URL, the script first asks which known program to open (Parea,
To Alati tis Gis, Nykhta Stasou). It then drives Chromium (via Playwright) to
the series page, scrapes available seasons and episodes, lets you pick one
via an arrow-key TUI, captures the token API URL that ERTFlix generates when
you click Play, and hands it off to ``main-yt-dlp.py --ertflix-program`` for the actual download.

Unknown flags are forwarded verbatim to ``main-yt-dlp.py``, so you can still
use ``--only-audio``, ``--audio-format mp3``, etc.

Setup (one time):
    pip install -r requirements.txt   # installs playwright, questionary, rich
    python -m playwright install chromium

Examples:
    ./main-ertflix-series.py --only-audio --audio-format mp3
    ./main-ertflix-series.py --program Parea --only-audio
    ./main-ertflix-series.py https://www.ertflix.gr/#/details/ERT_PS054741_E0 \\
        --program Parea --only-audio --audio-format mp3
"""
# PEP 810: lazy on Python 3.15+, ignored (eager) on older versions; Page is used in annotations only.
__lazy_modules__ = ['playwright.sync_api']

import argparse
import logging
import re
import shlex
import sys
import textwrap
from pathlib import Path
from urllib.parse import urlparse

import arrow
from playwright.sync_api import Page

from common_av.text import count_noun

from funcs_ertflix_automation import (DEFAULT_PROFILE_DIR, KNOWN_PROGRAMS,
                                      BrowserSession, Episode,
                                      ErtflixAutomationError, Season,
                                      dump_debug_dom, hand_off_to_ytdlp,
                                      pick_episode, pick_program, pick_season,
                                      render_episodes_table,
                                      render_seasons_table, resolve_program)
from funcs_ertflix_automation.api_metadata import ApiMetadataStore
from funcs_ertflix_automation.errors import BackToSeasons
from funcs_ertflix_automation.episode_scraper import discover_episodes
from funcs_ertflix_automation.player_scraper import (click_episode_play,
                                                     extract_player_info)
from funcs_ertflix_automation.season_scraper import discover_seasons, select_season
from funcs_ertflix_automation.handoff import build_ytdlp_argv
from funcs_utils import setup_logging
from project_defs import VALID_OTHER_DOMAINS

VERSION = '2026-11-24-1810'
DEBUG_DOM_DIR = Path('Logs')
URL_PREFIX_RE = re.compile(r'https?://', re.IGNORECASE)

logger = logging.getLogger(__name__)


def parse_arguments(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    """Parse known args and collect unknown args for pass-through.

    Args:
        argv: Arguments to parse (defaults to sys.argv[1:]).

    The optional series URL is taken out of ``argv`` (first ``http(s)://`` token)
    before argparse runs. An optional positional would otherwise swallow the value
    of a forwarded flag, e.g. ``mp3`` in ``--audio-format mp3``.

    Returns:
        tuple[argparse.Namespace, list[str]]: Parsed args (``series_url`` is None
        when no URL was given) and unknown args to forward to main-yt-dlp.py.
    """
    raw = list(sys.argv[1:] if argv is None else argv)
    series_url = next((a for a in raw if URL_PREFIX_RE.match(a)), None)
    if series_url is not None:
        raw.remove(series_url)

    parser = argparse.ArgumentParser(
        usage='%(prog)s [series_url] [options] [main-yt-dlp.py options]',
        description='Interactive ERTFlix series browser. series_url is the ERTFlix series '
                    'page URL; omit it to choose from the program menu. Unknown flags are '
                    'forwarded to main-yt-dlp.py.',
        epilog='One-time setup: pip install -r requirements.txt && '
               'python -m playwright install chromium',
    )
    parser.add_argument('--profile-dir', type=Path, default=DEFAULT_PROFILE_DIR,
                        help='Chromium persistent user-data directory (default: %(default)s)')
    parser.add_argument('--headless', action='store_true',
                        help='Run Chromium without a visible window')
    parser.add_argument('--debug-dom', action='store_true',
                        help='Dump the rendered DOM + selector probes to Logs/ and exit')
    parser.add_argument('--debug-dom-player', action='store_true',
                        help='Pick season + episode, click Play, dump the player DOM to '
                             'Logs/ and exit (used to discover player info-button selectors)')
    parser.add_argument('--token-timeout', type=float, default=10.0,
                        help='Seconds to wait for the token URL after clicking Play '
                             '(default: %(default)s)')
    parser.add_argument('--program',
                        help='Program name (e.g. "Parea"). Without a URL, a known name '
                             'opens that program and skips the program menu. The hand-off '
                             'sets --title "<program> S<NN>E<NN>" and NOTIF_MSG to the '
                             'same string; a program picked from the menu supplies its own name.')
    parser.add_argument('--get-info', action='store_true',
                        help='Click Play, mute video, extract episode info popup to '
                             'Logs/episode-info.txt and print it to the console')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print the hand-off command instead of invoking main-yt-dlp.py')
    parser.add_argument('--log-api', action='store_true',
                        help='Save every JSON response the ERTFlix page receives to '
                             'Logs/ertflix-api-<timestamp>.jsonl (to look for metadata such '
                             'as dates)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable DEBUG logging')
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    args, unknown = parser.parse_known_args(raw)
    args.series_url = series_url
    return args, unknown


def _pick_season_and_episode(
        page: Page, seasons: list[Season], metadata: ApiMetadataStore,
        oldest_first: bool | None,
) -> tuple[Season | None, Episode]:
    """Loop season + episode selection, allowing back-navigation to seasons.

    Args:
        page: Active Playwright page.
        seasons: Discovered seasons (may be empty when page has no selector).
        metadata: ERTFlix API data collected so far (official numbers, broadcast dates).
        oldest_first: Whether the program's page lists episodes oldest first (None = guess).

    Returns:
        tuple[Season | None, Episode]: Chosen season (None if no seasons) and episode.
    """
    chosen_season: Season | None = None
    while True:
        if seasons:
            render_seasons_table(seasons=seasons)
            chosen_season = pick_season(seasons=seasons)
            select_season(page=page, season=chosen_season)
        else:
            logger.info('No season selector detected; reading episodes directly.')
        episodes = discover_episodes(
            page=page, debug_dump_dir=DEBUG_DOM_DIR, metadata=metadata,
            season_number=chosen_season.index if chosen_season is not None else None,
            oldest_first=oldest_first,
        )
        render_episodes_table(episodes=episodes)
        try:
            chosen_episode = pick_episode(episodes=episodes, has_seasons=bool(seasons))
            return chosen_season, chosen_episode
        except BackToSeasons:
            continue


def _print_info_file(path: Path, width: int = 80) -> None:
    """Print the contents of the episode-info file with line wrapping.

    Args:
        path: Path to the info text file.
        width: Maximum line width before wrapping.
    """
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return
    print()
    for line in text.splitlines():
        if line:
            print(textwrap.fill(line, width=width))
        else:
            print()
    print()


def _wait_for_enter(message: str) -> None:
    """Keep the terminal window open until Enter, so the run's output can be read.

    Args:
        message: Prompt text (without the trailing space).
    """
    try:
        input(f'{message} ')
    except (EOFError, KeyboardInterrupt):
        pass


def _validate_series_url(url: str) -> None:
    """Abort unless the URL points at an ERTFlix domain.

    Args:
        url: The URL to validate.
    """
    try:
        host = (urlparse(url).hostname or '').lower()
    except ValueError:
        host = ''
    if host not in VALID_OTHER_DOMAINS:
        logger.error(
            f'Series URL host {host!r} is not an ERTFlix domain. '
            f'Expected one of: {", ".join(VALID_OTHER_DOMAINS)}'
        )
        sys.exit(1)


def _execute_handoff(  # pylint: disable=too-many-arguments
        args: argparse.Namespace, program_label: str | None, token_url: str,
        chosen_season: Season | None, chosen_episode: Episode,
        passthrough: list[str]) -> int:
    """Build env overrides + title, then hand off to main-yt-dlp.py.

    Args:
        args: Parsed CLI arguments.
        program_label: Program name for the title / NOTIF_MSG (None = no title).
        token_url: Captured ERTFlix token API URL.
        chosen_season: Selected season (None when page has no season selector).
        chosen_episode: Selected episode.
        passthrough: Extra args forwarded to main-yt-dlp.py.

    Returns:
        int: Process exit code.
    """
    env_overrides: dict[str, str] = {'NOTIFICATIONS': 'ALL'}
    if chosen_episode.broadcast and '--date' not in passthrough:
        passthrough = ['--date', chosen_episode.broadcast, *passthrough]
        logger.info(f'Using date tag: {chosen_episode.broadcast}')
    if program_label:
        season_num = chosen_season.index if chosen_season is not None else 1
        title_str = f'{program_label} S{season_num:02d}E{chosen_episode.index:02d}'
        passthrough = ['--title', title_str, *passthrough]
        env_overrides['NOTIF_MSG'] = title_str
        logger.info(f'Using title and NOTIF_MSG: {title_str!r}')

    if args.dry_run:
        argv = build_ytdlp_argv(token_url=token_url, passthrough_args=passthrough)
        logger.info('Dry run — would execute:')
        logger.info(shlex.join(argv))
        if env_overrides:
            logger.info(f'With env overrides: {env_overrides}')
        _wait_for_enter(message='Dry-run mode, press Enter to exit')
        return 0

    exit_code = hand_off_to_ytdlp(
        token_url=token_url,
        passthrough_args=passthrough,
        env_overrides=env_overrides,
    )
    outcome = 'Download finished' if exit_code == 0 else f'Download failed (exit code {exit_code})'
    _wait_for_enter(message=f'{outcome}, press Enter to exit')
    return exit_code


def main() -> int:
    """Script entry point.

    Returns:
        int: Process exit code.
    """
    args, passthrough = parse_arguments()
    setup_logging(verbose=args.verbose)

    try:
        series_url, program_label, oldest_first = resolve_program(
            series_url=args.series_url, program_label=args.program,
            picker=lambda programs: pick_program(programs=programs),
            programs=KNOWN_PROGRAMS,
        )
    except KeyboardInterrupt:
        logger.info('Cancelled by user.')
        return 130
    _validate_series_url(url=series_url)

    session = BrowserSession(profile_dir=args.profile_dir, headless=args.headless)
    api_log: Path | None = None
    try:
        with session:
            if args.log_api:
                stamp = arrow.now().format('YYYY-MM-DD-HHmmss')
                api_log = DEBUG_DOM_DIR / f'ertflix-api-{stamp}.jsonl'
            session.install_response_hook(api_log=api_log)
            session.open_series(series_url=series_url)
            token_urls = session.install_token_interceptor()
            session.ensure_authenticated()

            print('\n>>> The page is loaded in Chromium.')
            print('>>> If you want to change the page language, do so now in the browser.')
            input('>>> Press Enter when ready... ')

            if args.debug_dom:
                dump_path = dump_debug_dom(page=session.page, out_dir=DEBUG_DOM_DIR)
                logger.info(f'Debug dump written to {dump_path}. Exiting.')
                return 0

            seasons = discover_seasons(page=session.page, metadata=session.metadata)
            chosen_season, chosen_episode = _pick_season_and_episode(
                page=session.page, seasons=seasons, metadata=session.metadata,
                oldest_first=oldest_first,
            )
            season_num = chosen_season.index if chosen_season is not None else 1
            logger.info(f'Selected S{season_num:02d}E{chosen_episode.index:02d}: '
                        f'{chosen_episode.title}')

            token_url = click_episode_play(
                page=session.page,
                episode=chosen_episode,
                token_urls=token_urls,
                timeout_s=args.token_timeout,
            )

            if args.get_info or args.debug_dom_player:
                try:
                    session.page.evaluate('''() => {
                        document.querySelectorAll("video").forEach(v => v.muted = true);
                        new MutationObserver(() => {
                            document.querySelectorAll("video").forEach(v => v.muted = true);
                        }).observe(document.body, { childList: true, subtree: true });
                    }'''
                    )
                except Exception:  # noqa: BLE001  # nosec B110
                    pass

            if args.debug_dom_player:
                dump_path = dump_debug_dom(page=session.page, out_dir=DEBUG_DOM_DIR)
                logger.info(f'Player DOM dump written to {dump_path}. Exiting.')
                return 0

            if args.get_info:
                print('Note: episode video will play for ~30 seconds and then '
                      'the browser window will be closed. Then the script will resume.')
                info_file = DEBUG_DOM_DIR / 'episode-info.txt'
                extract_player_info(page=session.page, out_file=info_file)
                print('─' * 60)
                print('Episode info from player:')
                _print_info_file(info_file)
                print('─' * 60)
    except KeyboardInterrupt:
        logger.info('Cancelled by user.')
        return 130
    except ErtflixAutomationError as exc:
        logger.error(str(exc))
        return 1
    finally:
        if api_log is not None:
            logger.info(f'Saved {count_noun(session.api_responses_logged, "JSON response")} '
                        f'to {api_log}')
    logger.info(f'Captured token URL: {token_url[:120]}...')
    return _execute_handoff(
        args=args,
        program_label=program_label,
        token_url=token_url,
        chosen_season=chosen_season,
        chosen_episode=chosen_episode,
        passthrough=passthrough,
    )


if __name__ == '__main__':
    sys.exit(main())
