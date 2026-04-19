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


EPISODE_ID_REGEX = re.compile(r'ERT_[A-Z0-9_]+')

PLAY_BUTTON_SELECTOR = (
    'button[aria-label*="play" i], '
    'button[aria-label*="Αναπαραγωγή" i], '
    'button[class*="play" i], '
    '.asset-card button'
)

SEASON_BUTTON_SELECTORS: list[str] = [
    '[role="tablist"] button',
    '[class*="season" i]',
    'button[aria-label*="season" i]',
    'button[aria-label*="Σεζόν" i]',
    'button[aria-label*="Κύκλος" i]',
    'nav button',
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Season:
    """One season tab scraped from the series page."""

    index: int
    label: str
    selector: str


@dataclass(frozen=True)
class Episode:
    """One episode card scraped from the currently-visible DOM."""

    index: int
    title: str
    episode_id: str


def extract_episode_id(img_src: str | None) -> str | None:
    """Return the first ERT_ID pattern found in an image src, or None.

    Args:
        img_src: The `src` or `data-src` attribute of a card image.

    Returns:
        str | None: The matched episode ID, or None if not present.
    """
    if not img_src:
        return None
    match = EPISODE_ID_REGEX.search(img_src)
    return match.group(0) if match else None


def discover_seasons(page: Page, debug_dom: bool = False) -> list[Season]:
    """Probe candidate selectors and return any visible season tabs/buttons.

    Args:
        page: Active Playwright page already navigated to the series URL.
        debug_dom: If True, log every candidate selector's match count.

    Returns:
        list[Season]: Seasons in DOM order. Empty when the page has no seasons.
    """
    seen_labels: set[str] = set()
    seasons: list[Season] = []

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
            seasons.append(Season(index=len(seasons) + 1, label=label, selector=selector))

    return seasons


def select_season(page: Page, season: Season, wait_ms: int = 15000) -> None:
    """Click the button whose text/aria-label matches the given season.

    Args:
        page: Active Playwright page.
        season: The season to click.
        wait_ms: Max time to wait for .asset-card elements to re-render.
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

    pre_click_ids = _current_card_ids(page=page)
    logger.debug(f'Pre-click episode IDs: {len(pre_click_ids)} found')
    target.click()

    deadline = time.monotonic() + (wait_ms / 1000.0)
    while time.monotonic() < deadline:
        current_ids = _current_card_ids(page=page)
        if current_ids and current_ids != pre_click_ids:
            logger.debug(f'Season DOM swapped (ids: {len(pre_click_ids)} -> {len(current_ids)})')
            break
        page.wait_for_timeout(250)
    else:
        logger.debug('Season DOM did not visibly change within timeout; proceeding anyway')

    try:
        page.wait_for_load_state('networkidle', timeout=wait_ms)
    except Exception as exc:
        logger.debug(f'networkidle after season click timed out: {exc}')


_BROWSER_SCRAPE_SCRIPT = r'''
async ({ maxRounds, settleMs, stepPx }) => {
    const collected = new Map();
    const seenOrder = [];
    const EPISODE_RE = /ERT_[A-Z0-9_]+/;

    const scrape = () => {
        document.querySelectorAll('.asset-card').forEach(card => {
            const img = card.querySelector('img');
            const src = img ? (img.getAttribute('src') || img.getAttribute('data-src') || '') : '';
            const match = EPISODE_RE.exec(src);
            if (!match) return;
            const id = match[0];
            if (collected.has(id)) return;
            const btn = card.querySelector('button[aria-label]');
            const aria = btn ? btn.getAttribute('aria-label') : '';
            const text = card.innerText ? card.innerText.split('\n')[0].trim() : '';
            const title = (aria && aria.trim()) || text || id;
            collected.set(id, title);
            seenOrder.push(id);
        });
    };

    const scrollAncestors = () => {
        const cards = document.querySelectorAll('.asset-card');
        if (cards.length === 0) return;
        const last = cards[cards.length - 1];
        last.scrollIntoView({ block: 'end', inline: 'end', behavior: 'instant' });
        let el = last.parentElement;
        while (el && el !== document.body) {
            if (el.scrollHeight > el.clientHeight) el.scrollTop = el.scrollHeight;
            if (el.scrollWidth > el.clientWidth) el.scrollLeft = el.scrollWidth;
            el = el.parentElement;
        }
        window.scrollBy(0, stepPx);
    };

    window.scrollTo(0, 0);
    await new Promise(r => setTimeout(r, settleMs));

    let prev = -1;
    let stable = 0;
    for (let i = 0; i < maxRounds; i++) {
        scrape();
        if (collected.size === prev) {
            stable++;
            if (stable >= 4) break;
        } else {
            stable = 0;
        }
        prev = collected.size;
        scrollAncestors();
        await new Promise(r => setTimeout(r, settleMs));
    }
    scrape();
    return seenOrder.map(id => ({ id, title: collected.get(id) }));
}
'''


def discover_episodes(page: Page, max_scroll_rounds: int = 80,
                      settle_ms: int = 300, step_px: int = 600) -> list[Episode]:
    """Scroll inside the browser and collect every `.asset-card`.

    The whole scroll+scrape loop runs in the browser via ``page.evaluate`` to
    avoid the per-round Python↔Chromium round-trip latency. Works with both
    window-level scroll and inner scrollable containers.

    Args:
        page: Active Playwright page.
        max_scroll_rounds: Safety cap on scroll iterations.
        settle_ms: Wait between scroll steps so new cards can render.
        step_px: Window scroll step per round.

    Returns:
        list[Episode]: Episodes in first-seen DOM order.
    """
    raw = page.evaluate(
        _BROWSER_SCRAPE_SCRIPT,
        {'maxRounds': max_scroll_rounds, 'settleMs': settle_ms, 'stepPx': step_px},
    )
    logger.info(f'Collected {len(raw)} unique episodes from browser-side scroll')
    episodes: list[Episode] = [
        Episode(index=idx, title=item['title'], episode_id=item['id'])
        for idx, item in enumerate(raw, start=1)
    ]
    if not episodes:
        raise NoSeasonsOrEpisodesFound(
            'No .asset-card elements with ERT_ IDs were found. '
            'Re-run with --debug-dom to inspect the page structure.'
        )
    return episodes


def click_episode_play(page: Page, episode: Episode, token_urls: list[str],
                       timeout_s: float = 10.0) -> str:
    """Click the Play button of the given episode and wait for the token URL.

    Args:
        page: Active Playwright page.
        episode: The episode whose Play button to click.
        token_urls: Shared list populated by install_token_interceptor().
        timeout_s: Max seconds to wait for a matching network request.

    Returns:
        str: The captured token API URL.
    """
    card = _card_for_episode_id(page=page, episode_id=episode.episode_id)
    if card is None:
        raise NoSeasonsOrEpisodesFound(
            f'Could not re-locate card for episode {episode.episode_id}'
        )
    play_button = card.query_selector(PLAY_BUTTON_SELECTOR)
    if play_button is None:
        raise NoSeasonsOrEpisodesFound(
            f'No Play button inside card for episode {episode.episode_id}'
        )
    logger.info(f'Clicking Play for {episode.episode_id} ({episode.title})')
    play_button.click()

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
    return bool(re.fullmatch(r'(?:[ΑΒΓΔΕΖΗΘΙΚΛ]\'?|\d{1,2})', label.strip()))


def _episode_id_from_card(card: ElementHandle) -> str | None:
    """Extract the ERT_ID from the first image inside a card."""
    img = card.query_selector('img')
    if img is None:
        return None
    src = img.get_attribute('src') or img.get_attribute('data-src')
    return extract_episode_id(img_src=src)


def _title_from_card(card: ElementHandle) -> str | None:
    """Best-effort scrape of a human-readable title from a card."""
    button = card.query_selector('button[aria-label]')
    if button is not None:
        aria = button.get_attribute('aria-label')
        if aria:
            return aria.strip()
    try:
        text = card.inner_text().strip()
    except Exception:  # noqa: BLE001
        return None
    return text.splitlines()[0].strip() if text else None


def _current_card_ids(page: Page) -> list[str]:
    """Return the ordered list of episode IDs currently in the DOM."""
    ids: list[str] = []
    for card in page.query_selector_all('.asset-card'):
        episode_id = _episode_id_from_card(card=card)
        if episode_id:
            ids.append(episode_id)
    return ids


def _card_for_episode_id(page: Page, episode_id: str) -> ElementHandle | None:
    """Return the .asset-card whose image src contains the episode id."""
    cards = page.query_selector_all('.asset-card')
    for card in cards:
        if _episode_id_from_card(card=card) == episode_id:
            return card
    return None


def flatten_selector_list(selectors: Sequence[str]) -> str:
    """Join selectors with commas for a single query_selector_all call."""
    return ', '.join(selectors)
