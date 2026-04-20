"""Interactive ERTFlix series browser: pick season + episode, then download.

This script drives Chromium (via Playwright) to the series URL, scrapes
available seasons and episodes, lets you pick one via an arrow-key TUI,
captures the token API URL that ERTFlix generates when you click Play, and
hands it off to ``main-yt-dlp.py --ertflix-program`` for the actual download.

Unknown flags are forwarded verbatim to ``main-yt-dlp.py``, so you can still
use ``--only-audio``, ``--audio-format mp3``, ``--split-chapters``, etc.

Setup (one time):
    uv add playwright questionary rich
    python -m playwright install chromium

Example:
    python main-ertflix-series.py https://www.ertflix.gr/vod/vod.345646-parea \\
        --only-audio --audio-format mp3
"""
import argparse
import logging
import shlex
import sys
import textwrap
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Page

from funcs_ertflix_automation import (DEFAULT_PROFILE_DIR, BrowserSession,
                                      Episode, ErtflixAutomationError, Season,
                                      dump_debug_dom, hand_off_to_ytdlp,
                                      pick_episode, pick_season,
                                      render_episodes_table,
                                      render_seasons_table)
from funcs_ertflix_automation.errors import BackToSeasons
from funcs_ertflix_automation.dom_scraper import (click_episode_play,
                                                  discover_episodes,
                                                  discover_seasons,
                                                  extract_player_info,
                                                  select_season)
from funcs_utils import setup_logging
from project_defs import VALID_OTHER_DOMAINS

VERSION = '2026-04-20-1257'
DEBUG_DOM_DIR = Path('Logs')

logger = logging.getLogger(__name__)


def parse_arguments(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    """Parse known args and collect unknown args for pass-through.

    Args:
        argv: Arguments to parse (defaults to sys.argv[1:]).

    Returns:
        tuple[argparse.Namespace, list[str]]: Parsed args and unknown args
        to forward to main-yt-dlp.py.
    """
    parser = argparse.ArgumentParser(
        description='Interactive ERTFlix series browser. Unknown flags are '
                    'forwarded to main-yt-dlp.py.',
        epilog='One-time setup: uv add playwright questionary rich && '
               'python -m playwright install chromium',
    )
    parser.add_argument('series_url', help='ERTFlix series/Parea page URL')
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
                        help='Program name (e.g. "Parea"). When provided, the hand-off '
                             'sets --title "<program> S<NN>E<NN>" and NOTIF_MSG to the '
                             'same string.')
    parser.add_argument('--get-info', action='store_true',
                        help='Click Play, mute video, extract episode info popup to '
                             'Logs/episode-info.txt and print it to the console')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print the hand-off command instead of invoking main-yt-dlp.py')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable DEBUG logging')
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    return parser.parse_known_args(argv)


def _pick_season_and_episode(
        page: Page, seasons: list[Season],
) -> tuple[Season | None, Episode]:
    """Loop season + episode selection, allowing back-navigation to seasons.

    Args:
        page: Active Playwright page.
        seasons: Discovered seasons (may be empty when page has no selector).

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
        episodes = discover_episodes(page=page, debug_dump_dir=DEBUG_DOM_DIR)
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


def main() -> int:
    """Script entry point.

    Returns:
        int: Process exit code.
    """
    args, passthrough = parse_arguments()
    setup_logging(verbose=args.verbose)
    _validate_series_url(url=args.series_url)

    try:
        with BrowserSession(profile_dir=args.profile_dir, headless=args.headless) as session:
            session.open_series(series_url=args.series_url)
            token_urls = session.install_token_interceptor()
            session.ensure_authenticated()

            print('\n>>> The page is loaded in Chromium.')
            print('>>> If you want to change the page language, do so now in the browser.')
            input('>>> Press Enter when ready... ')

            if args.debug_dom:
                dump_path = dump_debug_dom(page=session.page, out_dir=DEBUG_DOM_DIR)
                logger.info(f'Debug dump written to {dump_path}. Exiting.')
                return 0

            seasons = discover_seasons(page=session.page)
            chosen_season, chosen_episode = _pick_season_and_episode(
                page=session.page, seasons=seasons,
            )

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
                except Exception:  # noqa: BLE001
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

    logger.info(f'Captured token URL: {token_url[:120]}...')

    env_overrides: dict[str, str] = {'NOTIFICATIONS': 'ALL'}
    if args.program:
        season_num = chosen_season.index if chosen_season is not None else 1
        title_str = f'{args.program} S{season_num:02d}E{chosen_episode.index:02d}'
        passthrough = ['--title', title_str, *passthrough]
        env_overrides['NOTIF_MSG'] = title_str
        logger.info(f'Using title and NOTIF_MSG: {title_str!r}')

    if args.dry_run:
        from funcs_ertflix_automation.handoff import build_ytdlp_argv
        argv = build_ytdlp_argv(token_url=token_url, passthrough_args=passthrough)
        logger.info('Dry run — would execute:')
        logger.info(shlex.join(argv))
        if env_overrides:
            logger.info(f'With env overrides: {env_overrides}')
        return 0

    return hand_off_to_ytdlp(
        token_url=token_url,
        passthrough_args=passthrough,
        env_overrides=env_overrides,
    )


if __name__ == '__main__':
    sys.exit(main())
