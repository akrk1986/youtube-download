"""DOM scraping and click helpers for ERTFlix series pages."""
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import arrow
from playwright.sync_api import ElementHandle, Page

from funcs_ertflix_automation.errors import (NoSeasonsOrEpisodesFound,
                                             TokenCaptureTimeout)


SEASON_BUTTON_SELECTORS: list[str] = [
    '[role="tablist"] button',
    '[class*="season" i]',
    '[aria-label*="Σεζόν" i]',
    '[aria-label*="Κύκλος" i]',
    'nav button',
]

ASSET_CARD_SELECTOR = '.asset-card'
PLAY_BUTTON_IN_CARD_SELECTOR = '.asset-card button[aria-label]'

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Season:
    """One season tab scraped from the series page."""

    index: int
    label: str
    selector: str


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


def discover_seasons(page: Page, debug_dom: bool = False) -> list[Season]:
    """Probe candidate selectors and return any visible season tabs/buttons.

    Args:
        page: Active Playwright page already navigated to the series URL.
        debug_dom: If True, log every candidate selector's match count.

    Returns:
        list[Season]: Seasons in DOM order. Empty when the page has no seasons.
    """
    seen_labels: set[str] = set()
    raw: list[tuple[str, str]] = []

    for selector in SEASON_BUTTON_SELECTORS:
        try:
            handles = page.query_selector_all(selector)
        except Exception as exc:
            logger.debug(f'Selector {selector!r} raised: {exc}')
            continue
        if debug_dom:
            logger.info(f'Selector {selector!r} matched {len(handles)} element(s)')
        for handle in handles:
            label = _label_for_button(handle=handle)
            if not label or label in seen_labels:
                continue
            if not _looks_like_season_label(label=label):
                continue
            seen_labels.add(label)
            raw.append((label, selector))

    total = len(raw)
    return [
        Season(index=total - offset, label=label, selector=selector)
        for offset, (label, selector) in enumerate(raw)
    ]


def select_season(page: Page, season: Season, wait_ms: int = 15000) -> None:
    """Click the button whose text/aria-label matches the given season.

    After the click, wait for the visible episode-title set to both (a) differ
    from the pre-click set and (b) stop changing, so that ``discover_episodes``
    reads the fully-hydrated new season.

    Args:
        page: Active Playwright page.
        season: The season to click.
        wait_ms: Max time to wait for the episode list to re-render + settle.
    """
    logger.info(f'Selecting season {season.index}: {season.label}')
    handles = page.query_selector_all(season.selector)
    target: ElementHandle | None = None
    for handle in handles:
        if _label_for_button(handle=handle) == season.label:
            target = handle
            break
    if target is None:
        raise NoSeasonsOrEpisodesFound(
            f'Could not re-locate season button {season.label!r}'
        )

    pre_click_titles = set(_current_episode_titles(page=page))
    logger.debug(f'Pre-click episode titles: {len(pre_click_titles)} found')
    target.click()

    try:
        page.wait_for_load_state('networkidle', timeout=wait_ms)
    except Exception as exc:
        logger.debug(f'networkidle after season click timed out: {exc}')


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


def discover_episodes(page: Page, stable_rounds_needed: int = 6,
                      poll_ms: int = 600, max_wait_s: float = 30.0,
                      min_wait_s: float = 4.0,
                      debug_dump_dir: Path | None = None) -> list[Episode]:
    """Poll the DOM until the set of visible episode titles stabilizes.

    Each episode is identified by its play-button ``aria-label`` (the title
    displayed in the UI). Scrapes via ``page.evaluate`` on every tick so the
    stability check tracks *hydrated cards* (those that already have their
    aria-label set), not raw placeholder divs. A minimum wait floor prevents
    exit during Angular's early-burst render.

    Args:
        page: Active Playwright page.
        stable_rounds_needed: Consecutive polls with no new titles to exit.
        poll_ms: Poll interval.
        max_wait_s: Hard cap.
        min_wait_s: Minimum time before an early exit is allowed.
        debug_dump_dir: If provided and the final list looks suspiciously
            short, write a DOM dump here for diagnosis.

    Returns:
        list[Episode]: Episodes in DOM order.
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


def click_episode_play(page: Page, episode: Episode, token_urls: list[str],
                       timeout_s: float = 10.0) -> str:
    """Click the Play button of the given episode and wait for the token URL.

    Locates the play button by matching its ``aria-label`` against the episode
    title. Falls back to positional Nth-card if the exact-title match misses
    (in case the title includes characters that need escaping).

    Args:
        page: Active Playwright page.
        episode: The episode whose Play button to click.
        token_urls: Shared list populated by install_token_interceptor().
        timeout_s: Max seconds to wait for a matching network request.

    Returns:
        str: The captured token API URL.
    """
    button = _find_play_button(page=page, episode=episode)
    if button is None:
        raise NoSeasonsOrEpisodesFound(
            f'Could not locate Play button for episode #{episode.index} '
            f'({episode.title!r})'
        )
    logger.info(f'Clicking Play for #{episode.index}: {episode.title}')
    button.click()

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if token_urls:
            return token_urls[0]
        page.wait_for_timeout(200)

    raise TokenCaptureTimeout(
        f'No token URL captured within {timeout_s:.1f}s. If ERTFlix requires '
        'login, rerun headed (without --headless) and sign in inside the browser window.'
    )


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


def _label_for_button(handle: ElementHandle) -> str:
    """Return a normalized label for a button element."""
    aria = handle.get_attribute('aria-label')
    if aria:
        return aria.strip()
    try:
        text = handle.inner_text()
    except Exception:  # noqa: BLE001
        text = ''
    return text.strip()


def _looks_like_season_label(label: str) -> bool:
    """Heuristic: reject obviously non-season button labels."""
    if not label:
        return False
    lowered = label.lower()
    if any(word in lowered for word in ('season', 'κύκλος', 'σεζόν', 'κυκλος', 'σεζον')):
        return True
    return bool(re.fullmatch(r"(?:[ΑΒΓΔΕΖΗΘΙΚΛ]\'?|\d{1,2})", label.strip()))


def _current_episode_titles(page: Page) -> list[str]:
    """Return ordered list of episode titles (aria-labels) currently in DOM."""
    titles: list[str] = []
    for card in page.query_selector_all(ASSET_CARD_SELECTOR):
        btn = card.query_selector('button[aria-label]')
        if btn is None:
            continue
        aria = btn.get_attribute('aria-label')
        if aria:
            titles.append(aria.strip())
    return titles


def _placeholder_card_count(page: Page) -> int:
    """Return the number of ``.asset-card`` divs that have no aria-label yet."""
    total = len(page.query_selector_all(ASSET_CARD_SELECTOR))
    hydrated = len(page.query_selector_all(PLAY_BUTTON_IN_CARD_SELECTOR))
    return max(0, total - hydrated)


def _find_play_button(page: Page, episode: Episode) -> ElementHandle | None:
    """Resolve the play button for ``episode`` by aria-label, with a positional fallback."""
    escaped = episode.title.replace('\\', '\\\\').replace('"', '\\"')
    selector = f'.asset-card button[aria-label="{escaped}"]'
    try:
        button = page.query_selector(selector)
    except Exception as exc:  # noqa: BLE001
        logger.debug(f'Exact-title selector failed ({exc}); falling back to index lookup')
        button = None
    if button is not None:
        return button
    cards = page.query_selector_all(ASSET_CARD_SELECTOR)
    dom_position = len(cards) - episode.index
    if 0 <= dom_position < len(cards):
        return cards[dom_position].query_selector('button[aria-label]')
    return None


def flatten_selector_list(selectors: Sequence[str]) -> str:
    """Join selectors with commas for a single query_selector_all call."""
    return ', '.join(selectors)
