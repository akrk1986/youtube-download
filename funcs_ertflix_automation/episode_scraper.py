"""Episode DOM scraping and debug DOM dump for ERTFlix series pages."""
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import arrow
from playwright.sync_api import Page

from funcs_ertflix_automation.errors import NoSeasonsOrEpisodesFound
from funcs_ertflix_automation.season_scraper import (ASSET_CARD_SELECTOR,
                                                     PLAY_BUTTON_IN_CARD_SELECTOR,
                                                     SEASON_BUTTON_SELECTORS)


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


_BROWSER_SCRAPE_SCRIPT = r'''
() => {
    const out = [];
    const seen = new Set();
    document.querySelectorAll('.asset-card').forEach(card => {
        const btn = card.querySelector('button[aria-label]');
        if (!btn) return;
        const title = (btn.getAttribute('aria-label') || '').trim();
        if (!title || seen.has(title)) return;
        seen.add(title);
        const img = card.querySelector('img[data-src]');
        const imgSrc = img ? img.getAttribute('data-src') || '' : '';
        const idMatch = imgSrc.match(/tvshow\/(ERT_[A-Z0-9_-]+)\//);
        const episodeId = idMatch ? idMatch[1] : '';
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


def discover_episodes(page: Page, debug_dump_dir: Path | None = None) -> list[Episode]:
    """Poll the DOM until the set of visible episode titles stabilizes.

    Each episode is identified by its play-button ``aria-label`` (the title
    displayed in the UI). Scrapes via ``page.evaluate`` on every tick so the
    stability check tracks *hydrated cards* (those that already have their
    aria-label set), not raw placeholder divs.

    Args:
        page: Active Playwright page.
        debug_dump_dir: If provided and placeholder cards remain after settling,
            write a DOM dump here for diagnosis.

    Returns:
        list[Episode]: Episodes in DOM order.
    """
    raw = _poll_episodes_until_stable(page=page)

    placeholder_count = _placeholder_card_count(page=page)
    if placeholder_count > 0 and debug_dump_dir is not None:
        logger.warning(
            f'{placeholder_count} placeholder card(s) remain un-hydrated '
            'after settle window — dumping DOM for diagnosis'
        )
        try:
            dump_path = dump_debug_dom(page=page, out_dir=debug_dump_dir)
            logger.warning(f'Post-season-click DOM dumped to {dump_path}')
        except Exception as exc:  # noqa: BLE001
            logger.debug(f'Post-season-click dump failed: {exc}')

    total = len(raw)
    episodes: list[Episode] = [
        Episode(
            index=total - offset,
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
    return episodes


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


def _placeholder_card_count(page: Page) -> int:
    """Return the number of ``.asset-card`` divs that have no aria-label yet."""
    total = len(page.query_selector_all(ASSET_CARD_SELECTOR))
    hydrated = len(page.query_selector_all(PLAY_BUTTON_IN_CARD_SELECTOR))
    return max(0, total - hydrated)
