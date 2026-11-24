"""Episode DOM scraping and debug DOM dump for ERTFlix series pages."""
# PEP 810: lazy on Python 3.15+, ignored (eager) on older versions; Page is used in annotations only.
__lazy_modules__ = ['playwright.sync_api']

import logging
import re
import time
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

import arrow
from playwright.sync_api import Page

from common_av.text import plural_noun, plural_verb
from funcs_ertflix_automation.api_metadata import ApiMetadataStore
from funcs_ertflix_automation.errors import NoSeasonsOrEpisodesFound
from funcs_ertflix_automation.season_scraper import (ASSET_CARD_SELECTOR,
                                                     PLAY_BUTTON_IN_CARD_SELECTOR,
                                                     SEASON_BUTTON_SELECTORS)


# A generic episode title carrying its number, e.g. 'Episode 4' or 'Επεισόδιο 4'.
NUMBERED_EPISODE_TITLE_RE = re.compile(r'^(?:episode|επεισόδιο|επεισοδιο)\s+(\d+)\b', re.IGNORECASE)

# Episode-table order labels (see describe_episode_order).
ORDER_NEWEST_FIRST = 'Newest first'
ORDER_OLDEST_FIRST = 'Oldest first'
ORDER_UNKNOWN = 'Episode dates unknown, order same as on the site'

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Episode:
    """One episode card scraped from the currently-visible DOM.

    Identified by its play-button ``aria-label`` (which is the episode title
    as shown in the UI) — this is stable across naming-scheme changes that
    might affect internal ID formats.
    """

    index: int
    title: str
    episode_id: str = ''
    duration: str = ''
    description: str = ''
    broadcast: str = ''


_BROWSER_SCRAPE_SCRIPT = r'''
() => {
    const out = [];
    const seen = new Set();
    document.querySelectorAll('.asset-card').forEach(card => {
        const btn = card.querySelector('button[aria-label]');
        if (!btn) return;
        const title = (btn.getAttribute('aria-label') || '').trim();
        if (!title) return;
        const img = card.querySelector('img[data-src]');
        const imgSrc = img ? img.getAttribute('data-src') || '' : '';
        const idMatch = imgSrc.match(/tvshow\/(ERT_[A-Z0-9_-]+)\//);
        const episodeId = idMatch ? idMatch[1] : '';
        const key = episodeId || title;
        if (seen.has(key)) return;
        seen.add(key);
        const row = card.closest('.row');
        let duration = '';
        let description = '';
        if (row) {
            const durEl = row.querySelector('h4.clr-pri-text-f');
            if (durEl && durEl.childNodes[0]) {
                duration = (durEl.childNodes[0].textContent || '').trim();
            }
            const descEl = row.querySelector('p[aria-label]');
            description = descEl ? (descEl.getAttribute('aria-label') || '').trim() : '';
        }
        out.push({ title, episodeId, duration, description });
    });
    return out;
}
'''


def _poll_episodes_until_stable(page: Page, stable_rounds_needed: int = 6,
                                poll_ms: int = 600, max_wait_s: float = 30.0,
                                min_wait_s: float = 4.0) -> list[dict[str, str]]:
    """Poll DOM until the scraped episode title set stabilizes for several rounds.

    Args:
        page: Active Playwright page.
        stable_rounds_needed: Consecutive polls with identical title sets to exit.
        poll_ms: Milliseconds between polls.
        max_wait_s: Hard timeout cap.
        min_wait_s: Minimum elapsed time before an early-stable exit is allowed.

    Returns:
        list[dict[str, str]]: Raw scrape results from the final stable poll.
    """
    start = time.monotonic()
    deadline = start + max_wait_s
    previous_titles: set[str] = set()
    stable = 0
    raw: list[dict[str, str]] = []
    elapsed = 0.0
    while time.monotonic() < deadline:
        raw = page.evaluate(_BROWSER_SCRAPE_SCRIPT)
        current_titles = {item['title'] for item in raw}
        elapsed = time.monotonic() - start
        if current_titles and current_titles == previous_titles and elapsed >= min_wait_s:
            stable += 1
            if stable >= stable_rounds_needed:
                break
        else:
            stable = 0
        previous_titles = current_titles
        page.wait_for_timeout(poll_ms)
    logger.info(f'Scraped {len(raw)} unique episodes from DOM (waited {elapsed:.1f}s)')
    return raw


def discover_episodes(page: Page, debug_dump_dir: Path | None = None,
                      metadata: ApiMetadataStore | None = None,
                      season_number: int | None = None,
                      oldest_first: bool | None = None) -> list[Episode]:
    """Poll the DOM until the set of visible episode titles stabilizes.

    Each episode is identified by its play-button ``aria-label`` (the title
    displayed in the UI). Scrapes via ``page.evaluate`` on every tick so the
    stability check tracks *hydrated cards* (those that already have their
    aria-label set), not raw placeholder divs.

    Args:
        page: Active Playwright page.
        debug_dump_dir: If provided and placeholder cards remain after settling,
            write a DOM dump here for diagnosis.
        metadata: ERTFlix API data; matched episodes take its official number and
            broadcast date (see ``_apply_metadata``).
        season_number: The selected season's official number, to narrow matching.
        oldest_first: Whether the page lists episodes oldest first (from the program
            list); None = guess from 'Episode N' titles.

    Episodes found in ``metadata`` get their official number and broadcast date.
    The rest are numbered newest-to-oldest by DOM position (the Parea page order),
    unless ``oldest_first`` says the page lists them oldest first (then the first card
    is episode 1). When ``oldest_first`` is None, the generic ``Episode N`` titles decide
    (see ``_listed_oldest_first``).

    Returns:
        list[Episode]: Episodes in DOM order.

    Raises:
        NoSeasonsOrEpisodesFound: If no episodes are found after polling.
    """
    raw = _poll_episodes_until_stable(page=page)

    placeholder_count = _placeholder_card_count(page=page)
    if placeholder_count > 0 and debug_dump_dir is not None:
        logger.warning(
            f'{placeholder_count} placeholder {plural_noun("card", placeholder_count)} '
            f'{plural_verb("remains", placeholder_count)} un-hydrated '
            'after settle window — dumping DOM for diagnosis'
        )
        try:
            dump_path = dump_debug_dom(page=page, out_dir=debug_dump_dir)
            logger.warning(f'Post-season-click DOM dumped to {dump_path}')
        except Exception as exc:  # noqa: BLE001
            logger.debug(f'Post-season-click dump failed: {exc}')

    total = len(raw)
    if oldest_first is None:
        oldest_first = _listed_oldest_first(titles=[item['title'] for item in raw])
        if oldest_first:
            logger.info('Episodes are listed oldest first on this page; numbering from the top.')
    episodes: list[Episode] = [
        Episode(
            index=offset + 1 if oldest_first else total - offset,
            title=item['title'],
            episode_id=item.get('episodeId', ''),
            duration=item.get('duration', ''),
            description=item.get('description', ''),
        )
        for offset, item in enumerate(raw)
    ]
    if not episodes:
        raise NoSeasonsOrEpisodesFound(
            'No episode cards with aria-label titles were found. '
            'Re-run with --debug-dom to inspect the page structure.'
        )
    if metadata is not None:
        episodes = _apply_metadata(episodes=episodes, metadata=metadata, season_number=season_number)
    return episodes


def describe_episode_order(episodes: list[Episode]) -> str:
    """Say which order the episodes are listed in, judged by their broadcast dates.

    The list is the site's order; this only describes it. Episodes without a date are
    skipped. With fewer than two dates, or dates that go both up and down, the order
    is reported as unknown.

    Args:
        episodes: Episodes in the order shown.

    Returns:
        str: ``ORDER_NEWEST_FIRST``, ``ORDER_OLDEST_FIRST`` or ``ORDER_UNKNOWN``.
    """
    dates = [episode.broadcast for episode in episodes if episode.broadcast]
    if len(dates) < 2 or dates[0] == dates[-1]:
        return ORDER_UNKNOWN
    pairs = list(zip(dates, dates[1:]))
    if all(earlier >= later for earlier, later in pairs):
        return ORDER_NEWEST_FIRST
    if all(earlier <= later for earlier, later in pairs):
        return ORDER_OLDEST_FIRST
    return ORDER_UNKNOWN


def dump_debug_dom(page: Page, out_dir: Path) -> Path:
    """Write an HTML snapshot and selector-probe summary to Logs/.

    Args:
        page: Active Playwright page.
        out_dir: Directory to write the dump file into.

    Returns:
        Path: Path to the written HTML file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = arrow.now().format('YYYY-MM-DD-HHmmss')
    out_path = out_dir / f'ertflix-debug-{stamp}.html'

    lines: list[str] = ['<!-- ERTFlix DOM debug dump -->', f'<!-- URL: {page.url} -->']
    for selector in SEASON_BUTTON_SELECTORS:
        try:
            handles = page.query_selector_all(selector)
        except Exception as exc:
            lines.append(f'<!-- selector {selector!r} raised {exc} -->')
            continue
        lines.append(f'<!-- selector {selector!r}: {len(handles)} match(es) -->')
        for handle in handles[:10]:
            try:
                outer = handle.evaluate('el => el.outerHTML')
            except Exception as exc:
                outer = f'<!-- outerHTML failed: {exc} -->'
            lines.append(str(outer))
    try:
        body_html = page.content()
    except Exception as exc:
        body_html = f'<!-- page.content() failed: {exc} -->'
    lines.append('<!-- FULL PAGE -->')
    lines.append(body_html)

    out_path.write_text('\n'.join(lines), encoding='utf-8')
    logger.info(f'Wrote debug DOM dump to {out_path}')
    return out_path


def _apply_metadata(episodes: list[Episode], metadata: ApiMetadataStore,
                    season_number: int | None) -> list[Episode]:
    """Give each episode found in the ERTFlix data its official number and broadcast date.

    Episodes not found keep their position-based number. Duplicate numbers are reported,
    not renumbered.

    Args:
        episodes: Episodes as scraped, with position-based numbers.
        metadata: ERTFlix API data collected so far.
        season_number: The selected season's official number (None = any season).

    Returns:
        list[Episode]: The episodes, in the same order.
    """
    if not metadata.has_episodes:
        logger.info('No ERTFlix episode data captured; numbering episodes from the page order.')
        return episodes
    updated: list[Episode] = []
    for episode in episodes:
        found = metadata.match(season_number=season_number, title=episode.title,
                               episode_id=episode.episode_id)
        if found is None:
            logger.debug(f'Episode {episode.title!r} not found in ERTFlix data')
            updated.append(episode)
            continue
        updated.append(replace(episode, index=found.episode_number, broadcast=found.broadcast_date))
    matched = sum(1 for old, new in zip(episodes, updated) if new is not old)
    logger.info(f'Matched {matched} of {len(episodes)} episodes to ERTFlix data '
                '(official numbers and broadcast dates)')
    duplicates = sorted(n for n, count in Counter(e.index for e in updated).items() if count > 1)
    if duplicates:
        logger.warning(f'Episode numbers used more than once: {duplicates}; check the titles '
                       'before picking.')
    return updated


def _listed_oldest_first(titles: list[str]) -> bool:
    """Tell whether the page lists episodes oldest first.

    Uses the generic ``Episode N`` titles some pages give untitled episodes: when at
    least two exist and their numbers rise down the list, the list is oldest first.
    Without such titles, returns False (newest first, as on the Parea page).

    Args:
        titles: Episode titles in DOM order.

    Returns:
        bool: True when the numbered titles rise down the list.
    """
    numbers = [int(match.group(1)) for title in titles
               if (match := NUMBERED_EPISODE_TITLE_RE.match(title.strip()))]
    if len(numbers) < 2:
        return False
    return all(earlier < later for earlier, later in zip(numbers, numbers[1:]))


def _placeholder_card_count(page: Page) -> int:
    """Return the number of ``.asset-card`` divs that have no aria-label yet."""
    total = len(page.query_selector_all(ASSET_CARD_SELECTOR))
    hydrated = len(page.query_selector_all(PLAY_BUTTON_IN_CARD_SELECTOR))
    return max(0, total - hydrated)
