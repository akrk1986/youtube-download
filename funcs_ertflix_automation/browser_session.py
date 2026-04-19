"""Playwright browser lifecycle and token-URL network interception for ERTFlix."""
import logging
from pathlib import Path
from types import TracebackType

from playwright.sync_api import (BrowserContext, Page, Playwright, Request,
                                 sync_playwright)

from funcs_ertflix_automation.errors import BrowserLaunchFailed


DEFAULT_PROFILE_DIR: Path = Path('.ertflix-profile')
TOKEN_URL_FRAGMENT: str = 'api.ertflix.opentv.com/urlbuilder/v1/playout/content/token'

logger = logging.getLogger(__name__)


class BrowserSession:
    """Manage a persistent Chromium context and observe ERTFlix token requests."""

    def __init__(self, profile_dir: Path = DEFAULT_PROFILE_DIR,
                 headless: bool = False) -> None:
        """Initialize session configuration.

        Args:
            profile_dir: Persistent user-data directory for Chromium. Login
                cookies are stored here across runs.
            headless: If True, run Chromium without a visible window.
        """
        self._profile_dir = profile_dir
        self._headless = headless
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._original_url: str | None = None

    def __enter__(self) -> 'BrowserSession':
        """Start Playwright and launch the persistent Chromium context."""
        try:
            self._profile_dir.mkdir(parents=True, exist_ok=True)
            playwright = sync_playwright().start()
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(self._profile_dir.resolve()),
                headless=self._headless,
            )
            page = context.pages[0] if context.pages else context.new_page()
            self._playwright = playwright
            self._context = context
            self._page = page
        except Exception as exc:
            self._cleanup_after_failure()
            raise BrowserLaunchFailed(
                f'Could not launch Chromium (headless={self._headless}). '
                f'On WSL use WSLg or run from native Windows Python. Cause: {exc}'
            ) from exc
        return self

    def __exit__(self, _exc_type: type[BaseException] | None,
                 _exc_val: BaseException | None,
                 _exc_tb: TracebackType | None) -> None:
        """Close the browser context and stop Playwright."""
        if self._context is not None:
            try:
                self._context.close()
            except Exception as exc:
                logger.debug(f'Context close failed: {exc}')
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception as exc:
                logger.debug(f'Playwright stop failed: {exc}')
        self._context = None
        self._page = None
        self._playwright = None

    @property
    def page(self) -> Page:
        """Return the active Playwright page (session must be entered first)."""
        if self._page is None:
            raise RuntimeError('BrowserSession used outside of its context manager')
        return self._page

    def open_series(self, series_url: str, nav_timeout_ms: int = 30000) -> None:
        """Navigate to the series URL and wait for the SPA to render.

        Args:
            series_url: Series / Parea page URL on www.ertflix.gr.
            nav_timeout_ms: Navigation timeout in milliseconds.
        """
        logger.info(f'Navigating to {series_url}')
        self._original_url = series_url
        self.page.goto(series_url, timeout=nav_timeout_ms)
        try:
            self.page.wait_for_load_state('networkidle', timeout=nav_timeout_ms)
        except Exception as exc:
            logger.debug(f'networkidle wait timed out, proceeding anyway: {exc}')

    def ensure_authenticated(self, settle_timeout_ms: int = 15000) -> None:
        """Pause for interactive login if ERTFlix redirected away from the series URL.

        ERTFlix redirects unauthenticated users to ``/#/landing`` (or similar).
        When that happens, prompt the user to log in inside the open Chromium
        window, then re-navigate to the originally requested series URL.

        Args:
            settle_timeout_ms: How long to wait for ``.asset-card`` to appear
                before declaring the page ready.
        """
        current_url = self.page.url
        landing_markers = ('#/landing', '#/login', '/landing', '/login')
        if any(marker in current_url for marker in landing_markers):
            logger.warning(
                f'Redirected to {current_url} — ERTFlix requires login. '
                'Please sign in inside the open Chromium window.'
            )
            print('\n>>> Please log in to ERTFlix in the browser window that just opened.')
            print('>>> Once you are logged in and can see the series page, come back here.')
            input('>>> Press Enter to continue... ')
            if self._original_url is not None:
                logger.info(f'Re-navigating to {self._original_url} after login')
                self.page.goto(self._original_url, timeout=settle_timeout_ms * 2)
                try:
                    self.page.wait_for_load_state('networkidle', timeout=settle_timeout_ms)
                except Exception as exc:
                    logger.debug(f'networkidle after login timed out: {exc}')
        try:
            self.page.wait_for_selector('.asset-card', timeout=settle_timeout_ms)
        except Exception as exc:
            logger.debug(f'.asset-card wait timed out, proceeding anyway: {exc}')

    def install_token_interceptor(self) -> list[str]:
        """Observe requests and collect ERTFlix token URLs into a shared list.

        Returns:
            list[str]: Mutable list populated as matching requests are seen.
        """
        token_urls: list[str] = []

        def _on_request(request: Request) -> None:
            url = request.url
            if TOKEN_URL_FRAGMENT in url and url not in token_urls:
                logger.debug(f'Captured token URL: {url[:120]}...')
                token_urls.append(url)

        self.page.on('request', _on_request)
        return token_urls

    def _cleanup_after_failure(self) -> None:
        """Best-effort teardown after a failed launch."""
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:  # noqa: BLE001  # nosec B110
                pass
        self._context = None
        self._page = None
        self._playwright = None
