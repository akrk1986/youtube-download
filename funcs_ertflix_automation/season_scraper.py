"""Season discovery and selection for ERTFlix series pages."""
# PEP 810: lazy on Python 3.15+, ignored (eager) on older versions; used in annotations only.
__lazy_modules__ = ['playwright.sync_api']

import logging
import re
from dataclasses import dataclass

from playwright.sync_api import ElementHandle, Page

from common_av.text import count_noun
from funcs_ertflix_automation.errors import NoSeasonsOrEpisodesFound


SEASON_BUTTON_SELECTORS: list[str] = [
    '[role="tablist"] button',
    '[class*="season" i]',
    '[aria-label*="Σεζόν" i]',
    '[aria-label*="Κύκλος" i]',
    'nav button',
]

# A word repeated back to back, e.g. 'Season Season 10' (aria-label prefix + visible text).
REPEATED_WORD_RE = re.compile(r'\b(\w+)(\s+\1\b)+', re.IGNORECASE)
SEASON_NUMBER_RE = re.compile(r'\d+')
# Label numbers at or above this are years ('Season 2026 - 2027'), not season numbers.
MIN_YEAR_IN_LABEL = 1900

ASSET_CARD_SELECTOR = '.asset-card'
PLAY_BUTTON_IN_CARD_SELECTOR = '.asset-card button[aria-label]'

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Season:
    """One season tab scraped from the series page."""

    index: int
    label: str
    selector: str


def discover_seasons(page: Page, debug_dom: bool = False) -> list[Season]:
    """Probe candidate selectors and return any visible season tabs/buttons.

    The same season often matches twice (e.g. ``Season 10`` and ``Season Season 10``),
    so labels are normalized with ``_normalize_label`` before de-duplication.

    When every label carries a number, the list is sorted by it, newest first. A small
    number ('Season 10') is the season index; a year ('Season 2026 - 2027') is not, so
    year-labelled seasons are numbered by rank, oldest = 1. Labels without numbers
    are numbered by DOM position (newest first).

    Args:
        page: Active Playwright page already navigated to the series URL.
        debug_dom: If True, log every candidate selector's match count.

    Returns:
        list[Season]: Seasons, newest first. Empty when the page has no seasons.
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
            logger.info(f'Selector {selector!r} matched {count_noun(len(handles), "element")}')
        for handle in handles:
            label = _normalize_label(label=_label_for_button(handle=handle))
            if not label or label in seen_labels:
                continue
            if not _looks_like_season_label(label=label):
                continue
            seen_labels.add(label)
            raw.append((label, selector))

    matches = [SEASON_NUMBER_RE.search(label) for label, _ in raw]
    if raw and all(matches):
        numbered = sorted(
            ((int(match.group()), label, selector)
             for (label, selector), match in zip(raw, matches) if match is not None),
            reverse=True,
        )
        are_years = any(number >= MIN_YEAR_IN_LABEL for number, _, _ in numbered)
        total = len(numbered)
        return [
            Season(index=total - rank if are_years else number, label=label, selector=selector)
            for rank, (number, label, selector) in enumerate(numbered)
        ]

    total = len(raw)
    return [
        Season(index=total - offset, label=label, selector=selector)
        for offset, (label, selector) in enumerate(raw)
    ]


def select_season(page: Page, season: Season, wait_ms: int = 15000) -> None:
    """Click the button whose text/aria-label matches the given season.

    After the click, wait for the episode list to re-render so that
    ``discover_episodes`` reads the fully-hydrated new season.

    Args:
        page: Active Playwright page.
        season: The season to click.
        wait_ms: Max time to wait for the episode list to re-render + settle.

    Raises:
        NoSeasonsOrEpisodesFound: If the season button cannot be found on the page.
    """
    logger.info(f"Selected season {season.index}: '{season.label}'")
    logger.info('Retrieving list of episodes (will take a few seconds)...')
    handles = page.query_selector_all(season.selector)
    target: ElementHandle | None = None
    for handle in handles:
        if _normalize_label(label=_label_for_button(handle=handle)) == season.label:
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


def _normalize_label(label: str) -> str:
    """Collapse a word repeated back to back ('Season Season 10' -> 'Season 10')."""
    return REPEATED_WORD_RE.sub(r'\1', label).strip()


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
