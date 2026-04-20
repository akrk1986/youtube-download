"""Play-button click and episode info extraction for ERTFlix."""
import logging
import time
from pathlib import Path

from playwright.sync_api import ElementHandle, Page

from funcs_ertflix_automation.errors import (NoSeasonsOrEpisodesFound,
                                             TokenCaptureTimeout)
from funcs_ertflix_automation.episode_scraper import Episode
from funcs_ertflix_automation.season_scraper import ASSET_CARD_SELECTOR


INFO_BUTTON_SELECTOR = 'button#more'
INFO_DIALOG_SELECTOR = 'mat-dialog-container'
INFO_DIALOG_CLOSE_SELECTOR = 'mat-dialog-container button'

logger = logging.getLogger(__name__)


_INFO_EXTRACT_SCRIPT = '''
() => {
    const d = document.querySelector('mat-dialog-container');
    if (!d) return null;
    const headings = Array.from(d.querySelectorAll('h1,h2,h3,h4'))
        .map(el => el.textContent.trim()).filter(Boolean);
    const paras = Array.from(d.querySelectorAll('p'))
        .map(el => el.textContent.trim()).filter(Boolean);
    return { headings, paras };
}
'''


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
    logger.info(f'Selected episode #{episode.index}: {episode.title}')
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


def extract_player_info(page: Page, out_file: Path,
                        timeout_s: float = 10.0) -> bool:
    """Click the player info button, extract popup text, save to file, close popup.

    Args:
        page: Active Playwright page on the episode details/player page.
        out_file: File to write the extracted text to (created or overwritten).
        timeout_s: Max seconds to wait for the info button and dialog to appear.

    Returns:
        bool: True if text was extracted and saved; False if info button not found.
    """
    timeout_ms = int(timeout_s * 1000)
    try:
        page.wait_for_selector(INFO_BUTTON_SELECTOR, timeout=timeout_ms)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f'Info button not found: {exc}')
        return False
    try:
        page.click(INFO_BUTTON_SELECTOR)
        page.wait_for_selector(INFO_DIALOG_SELECTOR, timeout=timeout_ms)
        result = page.evaluate(_INFO_EXTRACT_SCRIPT)
        if not result:
            logger.warning('Info dialog appeared but contained no extractable text')
            return False
        lines: list[str] = []
        for heading in result.get('headings') or []:
            lines.append(heading)
        if lines:
            lines.append('')
        for para in result.get('paras') or []:
            lines.append(para)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text('\n'.join(lines), encoding='utf-8')
        logger.info(f'Episode info saved to {out_file}')
    except Exception as exc:  # noqa: BLE001
        logger.warning(f'Failed to extract info dialog text: {exc}')
        return False
    finally:
        try:
            close_btn = page.query_selector(INFO_DIALOG_CLOSE_SELECTOR)
            if close_btn:
                close_btn.click()
            else:
                page.keyboard.press('Escape')
        except Exception:  # noqa: BLE001
            pass
    return True


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
