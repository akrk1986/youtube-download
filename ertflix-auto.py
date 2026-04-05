"""ERTFlix automated downloader.

Opens the ERTFlix episode page with your Firefox profile, drives playback automatically (Shaka /
video / keyboard fallbacks; manual Play still works), intercepts the token API URL, then calls
main-yt-dlp.py to download.

Usage:
    python ertflix-auto.py "https://www.ertflix.gr/#/details/ERT_PS054741_E0"
    python ertflix-auto.py --only-audio "https://www.ertflix.gr/#/details/..."
    python ertflix-auto.py --only-audio --audio-format m4a "https://..."
    python ertflix-auto.py --headless "https://..."

Requirements:
    pip install playwright
    playwright install firefox   # required: Playwright drives its own Firefox build by default

System /usr/bin/firefox is optional via --system-firefox but often breaks automation (blank tab,
hang after “Launching Firefox…”) because the browser build does not match Playwright’s driver.

Playwright’s Firefox often shows “Nightly” in the window title — that is normal (it is not your distro Firefox).

By default the script uses a **fixed automation profile** under your user data directory (e.g.
``~/.local/share/ertflix-auto/firefox-profile`` on Linux), not ``~/.mozilla/firefox/…``, so
Playwright’s Firefox does not keep spawning sibling profiles next to your daily driver. Use
``--use-mozilla-default-profile`` only if you want the same tree as normal Firefox (can create
extra profile folders). Close normal Firefox when using a profile under ``~/.mozilla/firefox``.

For the yt-dlp download step, match the ERTFlix README and set cookies (same browser you use on the site):
    export YTDLP_USE_COOKIES=firefox
If this is unset, main-yt-dlp.py runs without --cookies-from-browser and ERTFlix CDN requests may fail.
"""
import argparse
import asyncio
import configparser
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

_TOKEN_API_PATTERN = 'api.ertflix.opentv.com/urlbuilder/v1/playout/content/token'

# Playback UI: Shaka / Video.js / generic overlays / ERTFlix cards (order: likely controls first).
_PLAY_SELECTORS = [
    '.shaka-play-button',
    'button.shaka-play-button',
    '[class*="shaka-play-button" i]',
    '[class*="ShakaPlayButton" i]',
    '[class*="shaka-big-play-button" i]',
    '.video-js .vjs-big-play-button',
    '[class*="vjs-big-play-button" i]',
    '[class*="big-play-button" i]',
    '[class*="bigPlayButton" i]',
    '[class*="BigPlay" i]',
    '[class*="play-button" i]',
    '[class*="PlayButton" i]',
    'div[role="button"][class*="play" i]',
    'button[aria-label*="play" i]',
    'button[aria-label*="Αναπαραγωγή" i]',
    'button[class*="play" i]',
    '.asset-card button',
    '[data-testid*="play" i]',
    'button[title*="play" i]',
    'button[title*="Αναπαραγωγή" i]',
    'button:has(svg[aria-label*="play" i])',
]

_PAGE_LOAD_TIMEOUT_MS = 60_000
_PLAY_BUTTON_TIMEOUT_MS = 15_000
# Manual Play is allowed: user may click before our selectors match; poll this long for the token.
_PLAY_OR_TOKEN_DEADLINE_S = 180.0
# Re-run overlay / Shaka / video strategies on this interval until the token request fires.
_PLAYBACK_RETRY_INTERVAL_S = 2.5

# ERTFlix switches to a minimal / “use the app” layout below ~1024px width (see README).
_ERTFLIX_VIEWPORT = {'width': 1920, 'height': 1080}

# Greek site: helps translation bundles and APIs; reduces “gen_error” / raw i18n keys on some setups.
_ERTFLIX_LOCALE = 'el-GR'
_ERTFLIX_TIMEZONE = 'Europe/Athens'
_ERTFLIX_ACCEPT_LANGUAGE = 'el-GR,el;q=0.9,en-GB;q=0.8,en;q=0.7'

# Run before each document loads (new navigations only).
_HIDE_WEBDRIVER_INIT = """
(() => {
  try {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });
  } catch (e) {}
})();
"""


def _attach_page_debug(page: object, verbose: bool) -> None:
    """Log browser console, uncaught errors, and failed requests when --verbose."""
    if not verbose:
        return

    def _on_console(msg: object) -> None:
        text = getattr(msg, 'text', str(msg))
        logger.debug('browser console: %s', text)

    def _on_page_error(exc: BaseException) -> None:
        logger.debug('browser pageerror: %s', exc)

    def _on_request_failed(request: object) -> None:
        url = getattr(request, 'url', '')
        # Ads / telemetry often abort when the player tears down; not useful for debugging.
        if any(
            noise in url
            for noise in (
                'csi.gstatic.com',
                'pagead2.googlesyndication.com',
                'doubleclick.net',
                'googleads.g.doubleclick.net',
            )
        ):
            return
        fail = getattr(request, 'failure', None)
        logger.debug('request failed: %s (%s)', url, fail)

    page.on('console', _on_console)
    page.on('pageerror', _on_page_error)
    page.on('requestfailed', _on_request_failed)


async def _try_playback_strategies(page: object, verbose: bool) -> None:
    """Try Shaka / overlay buttons, ``<video>`` interaction, and keyboard — one round per call."""
    for selector in _PLAY_SELECTORS:
        loc = page.locator(selector).first
        try:
            if await loc.is_visible():
                await loc.click(timeout=_PLAY_BUTTON_TIMEOUT_MS)
                logger.info('Clicked playback control (%s)', selector)
                break
        except PlaywrightTimeoutError:
            if verbose:
                logger.debug('Playback control not visible: %s', selector)
        except Exception as exc:
            if verbose:
                logger.debug('Playback skip %s: %s', selector, exc)

    vloc = page.locator('video').first
    try:
        if await vloc.count() > 0 and await vloc.is_visible():
            await vloc.click(timeout=_PLAY_BUTTON_TIMEOUT_MS, force=True)
            logger.info('Clicked <video> element')
    except Exception as exc:
        if verbose:
            logger.debug('Video click: %s', exc)

    try:
        played = await page.evaluate(
            """async () => {
            const v = document.querySelector('video');
            if (!v) return false;
            try {
                await v.play();
                return true;
            } catch (e) {
                return false;
            }
        }"""
        )
        if played:
            logger.info('Called HTMLVideoElement.play()')
    except Exception as exc:
        if verbose:
            logger.debug('video.play(): %s', exc)

    try:
        if await vloc.count() > 0:
            await vloc.focus(timeout=1_000)
        await page.keyboard.press('Space')
        if verbose:
            logger.debug('Sent Space (keyboard play toggle)')
    except Exception as exc:
        if verbose:
            logger.debug('Keyboard Space: %s', exc)


async def _wait_for_play_or_token(page: object, captured: asyncio.Event, *, verbose: bool) -> bool:
    """Poll until token is captured (automation or manual Play) or deadline."""
    if captured.is_set():
        return True

    logger.info(
        'Waiting for token URL — playback automation every %.1fs (manual Play still works).',
        _PLAYBACK_RETRY_INTERVAL_S,
    )
    deadline = time.monotonic() + _PLAY_OR_TOKEN_DEADLINE_S
    next_attempt = time.monotonic()

    while time.monotonic() < deadline:
        if captured.is_set():
            return True
        if time.monotonic() >= next_attempt:
            await _try_playback_strategies(page, verbose)
            next_attempt = time.monotonic() + _PLAYBACK_RETRY_INTERVAL_S
        try:
            await asyncio.wait_for(captured.wait(), timeout=0.35)
            return True
        except asyncio.TimeoutError:
            continue

    return captured.is_set()


def _find_firefox_profile() -> Path | None:
    """Find the default Firefox profile directory by parsing profiles.ini.

    Priority:
    1. [Install*] section Default= — the most recently launched profile
    2. A [Profile*] section with Default=1
    3. The first [Profile*] section found

    Returns:
        Path to the profile directory, or None if not found.
    """
    candidates = [
        Path.home() / '.mozilla' / 'firefox' / 'profiles.ini',           # Linux/macOS
        Path.home() / 'AppData' / 'Roaming' / 'Mozilla' / 'Firefox' / 'profiles.ini',  # Windows
    ]
    profiles_ini = next((p for p in candidates if p.exists()), None)
    if not profiles_ini:
        return None

    config = configparser.ConfigParser()
    config.read(profiles_ini)
    firefox_dir = profiles_ini.parent

    def _resolve(path_str: str, is_relative: bool) -> Path:
        return (firefox_dir / path_str) if is_relative else Path(path_str)

    # Priority 1: [Install*] section — most recently active profile
    for section in config.sections():
        if section.lower().startswith('install'):
            default_path = config.get(section, 'Default', fallback=None)
            if default_path:
                profile = firefox_dir / default_path
                if profile.exists():
                    return profile

    # Priority 2: Profile with Default=1
    for section in config.sections():
        if section.lower().startswith('profile'):
            if config.getboolean(section, 'Default', fallback=False):
                path_str = config.get(section, 'Path', fallback=None)
                if path_str:
                    is_relative = config.getboolean(section, 'IsRelative', fallback=True)
                    profile = _resolve(path_str, is_relative)
                    if profile.exists():
                        return profile

    # Priority 3: First [Profile*] section
    for section in config.sections():
        if section.lower().startswith('profile'):
            path_str = config.get(section, 'Path', fallback=None)
            if path_str:
                is_relative = config.getboolean(section, 'IsRelative', fallback=True)
                profile = _resolve(path_str, is_relative)
                if profile.exists():
                    return profile

    return None


def _automation_firefox_profile_dir() -> Path:
    """Return a stable directory for Playwright-only data (not registered in profiles.ini).

    Keeping automation separate from ``~/.mozilla/firefox/`` avoids Gecko migration creating
    new random profile folders when Playwright’s Firefox opens a retail profile.
    """
    if sys.platform == 'win32':
        local = os.getenv('LOCALAPPDATA', '').strip()
        base = Path(local) if local else Path.home() / 'AppData' / 'Local'
        return (base / 'ertflix-auto' / 'firefox-profile').resolve()
    if sys.platform == 'darwin':
        return (
            Path.home() / 'Library' / 'Application Support' / 'ertflix-auto' / 'firefox-profile'
        ).resolve()
    xdg = os.getenv('XDG_DATA_HOME', '').strip()
    data_home = Path(xdg) if xdg else Path.home() / '.local' / 'share'
    return (data_home / 'ertflix-auto' / 'firefox-profile').resolve()


def _profile_under_mozilla_install(profile_path: Path) -> bool:
    """True if ``profile_path`` lives under the same tree desktop Firefox uses."""
    resolved = profile_path.resolve()
    candidates = [
        Path.home() / '.mozilla' / 'firefox',
        Path.home() / 'AppData' / 'Roaming' / 'Mozilla' / 'Firefox',
        Path.home() / 'Library' / 'Application Support' / 'Firefox',
    ]
    for root in candidates:
        try:
            root_r = root.resolve()
        except OSError:
            continue
        if not root_r.is_dir():
            continue
        try:
            if resolved.is_relative_to(root_r):
                return True
        except ValueError:
            continue
    return False


def _find_system_firefox() -> Path | None:
    """Return the path to the system-installed Firefox binary, if present.

    Checks common locations in order: PATH lookup first, then explicit paths
    for Linux, macOS, and Windows.

    Returns:
        Path to the Firefox binary, or None if not found.
    """
    # Try PATH first (covers most Linux distros and macOS with Homebrew)
    found = shutil.which('firefox')
    if found:
        return Path(found)

    # Explicit fallback locations
    candidates = [
        Path('/usr/bin/firefox'),
        Path('/usr/lib/firefox/firefox'),
        Path('/snap/bin/firefox'),
        Path('/opt/firefox/firefox'),
        Path('/Applications/Firefox.app/Contents/MacOS/firefox'),           # macOS
        Path.home() / 'AppData/Local/Mozilla Firefox/firefox.exe',         # Windows user
        Path('C:/Program Files/Mozilla Firefox/firefox.exe'),              # Windows system
        Path('C:/Program Files (x86)/Mozilla Firefox/firefox.exe'),
    ]
    return next((p for p in candidates if p.exists()), None)


def _check_firefox_running() -> bool:
    """Return True if a Firefox process is currently running."""
    result = subprocess.run(
        ['pgrep', '-x', 'firefox'],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


async def _capture_token_url(
    page_url: str,
    profile_path: Path,
    headless: bool,
    *,
    use_system_firefox: bool,
    verbose: bool,
) -> str:
    """Launch Firefox with the user profile, navigate to the ERTFlix page,
    start playback when possible, and return the captured token API URL.

    Args:
        page_url: The ERTFlix episode page URL.
        profile_path: Path to the Firefox profile directory.
        headless: Whether to run the browser without a visible window.
        use_system_firefox: If True, use PATH /usr/bin/firefox (often incompatible); if False,
            use Playwright’s bundled Firefox (matches the Marionette driver).
        verbose: Log browser console, page errors, and failed network requests.

    Returns:
        The captured token API URL string.
    """
    token_url: str | None = None
    captured = asyncio.Event()

    firefox_bin: Path | None = None
    if use_system_firefox:
        firefox_bin = _find_system_firefox()
        if firefox_bin:
            logger.info(f'Using system Firefox (--system-firefox): {firefox_bin}')
        else:
            logger.warning('System Firefox not found; using Playwright bundled Firefox instead.')
    else:
        logger.info(
            'Using Playwright bundled Firefox with your profile (recommended). '
            'If launch fails, run: playwright install firefox'
        )

    async with async_playwright() as pw:
        logger.info(f'Launching Firefox with profile: {profile_path}')
        launch_kwargs: dict[str, object] = {
            'user_data_dir': str(profile_path),
            'headless': headless,
            'viewport': _ERTFLIX_VIEWPORT,
            'locale': _ERTFLIX_LOCALE,
            'timezone_id': _ERTFLIX_TIMEZONE,
            'extra_http_headers': {'Accept-Language': _ERTFLIX_ACCEPT_LANGUAGE},
            'firefox_user_prefs': {
                # Gecko language negotiation (in addition to Accept-Language on requests).
                'intl.accept_languages': 'el-GR, el, en-US, en',
            },
        }
        if firefox_bin is not None:
            launch_kwargs['executable_path'] = str(firefox_bin)

        logger.info('Starting browser (waiting for automation handshake — can take a few seconds)…')
        context = await pw.firefox.launch_persistent_context(**launch_kwargs)  # type: ignore[arg-type]
        logger.info('Browser connected; initial tab count=%d', len(context.pages))

        await context.add_init_script(_HIDE_WEBDRIVER_INIT)

        # Session restore opens tabs asynchronously after launch.
        # Wait briefly so all restored tabs appear in context.pages before we collect them.
        await asyncio.sleep(2)

        # Open a fresh tab for our navigation, then close every session-restored tab.
        # Firefox often leaves an about:blank or new-tab page *focused* while our real tab
        # loads in the background — users see an “empty” tab. bring_to_front fixes that.
        page = await context.new_page()
        _attach_page_debug(page, verbose)
        await page.bring_to_front()
        for restored in list(context.pages):
            if restored != page:
                await restored.close()
        await page.bring_to_front()

        def _on_request(request: object) -> None:
            nonlocal token_url
            url = getattr(request, 'url', '')
            if _TOKEN_API_PATTERN in url and not captured.is_set():
                token_url = url
                logger.info('Token API URL captured.')
                captured.set()

        page.on('request', _on_request)

        logger.info(f'Navigating to: {page_url}')
        try:
            # SPAs (ERTFlix) rarely reach networkidle; domcontentloaded is enough to mount the app.
            await page.goto(page_url, wait_until='domcontentloaded', timeout=_PAGE_LOAD_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            logger.warning('Page load timed out (domcontentloaded); continuing anyway.')
        await page.bring_to_front()
        final_url = page.url
        logger.info(f'After navigation, page.url is: {final_url}')
        if not final_url or final_url == 'about:blank' or 'ertflix' not in final_url.lower():
            logger.warning(
                'URL bar does not look like ERTFlix — page may be wrong tab, blocked, or still loading. '
                'Try --verbose and confirm Firefox is not showing a different tab in front.'
            )

        # Give the client router time to render (hash routes after domcontentloaded).
        try:
            await page.wait_for_load_state('load', timeout=15_000)
        except PlaywrightTimeoutError:
            logger.debug('wait_for_load_state(load) timed out; continuing.')

        try:
            body_text = await page.inner_text('body', timeout=5_000)
        except PlaywrightTimeoutError:
            body_text = ''
        if 'gen_error' in body_text or 'gen_ok' in body_text:
            logger.warning(
                'ERTFlix rendered the generic error screen (raw keys like gen_error / gen_ok). '
                'The app often does this when bootstrap or translations fail. '
                'Run with --verbose to see failed network requests and console errors. '
                'If it keeps happening, capture the token URL manually in normal Firefox (README JS script).'
            )

        got_token = await _wait_for_play_or_token(page, captured, verbose=verbose)
        if not got_token:
            logger.error(
                'Timed out waiting for the token API URL (%.0fs).\n'
                'Click Play on the episode if you have not, or run without --headless to inspect the page.',
                _PLAY_OR_TOKEN_DEADLINE_S,
            )
            await context.close()
            sys.exit(1)

        logger.info('Closing browser (can take a few seconds while the player stops)…')
        await context.close()
        logger.info('Browser closed; starting main-yt-dlp.py download.')

    assert token_url is not None  # satisfied by captured.set() before this point
    return token_url


def _build_download_command(
    token_url: str,
    args: argparse.Namespace,
    extra_args: list[str],
) -> list[str]:
    """Build the main-yt-dlp.py command for the captured token URL.

    Args:
        token_url: The resolved playback token URL.
        args: Parsed CLI arguments from this script.
        extra_args: Any unrecognised args to pass through verbatim.

    Returns:
        List of command parts (suitable for subprocess.run).
    """
    script = Path(__file__).parent / 'main-yt-dlp.py'
    cmd: list[str] = [sys.executable, str(script)]

    if args.only_audio:
        cmd.append('--only-audio')
        cmd += ['--audio-format', args.audio_format]
    else:
        cmd.append('--ertflix-program')

    if args.verbose:
        cmd.append('--verbose')

    cmd += extra_args
    cmd.append(token_url)
    return cmd


def _parse_args() -> tuple[argparse.Namespace, list[str]]:
    """Parse CLI arguments for this script.

    Returns:
        Tuple of (known args namespace, list of unrecognised extra args).
    """
    parser = argparse.ArgumentParser(
        description='ERTFlix auto-downloader: opens page, clicks Play, downloads.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Any unrecognised flags are passed through to main-yt-dlp.py.\n\n'
            'Examples:\n'
            '  python ertflix-auto.py "https://www.ertflix.gr/#/details/ERT_PS054741_E0"\n'
            '  python ertflix-auto.py --only-audio --audio-format m4a "https://..."\n'
            '  python ertflix-auto.py --headless "https://..."'
        ),
    )
    parser.add_argument('page_url', help='ERTFlix episode page URL')
    parser.add_argument(
        '--profile',
        metavar='PATH',
        help=(
            'Firefox user-data directory for Playwright (overrides default). '
            'Default is a fixed path under XDG data / AppData / Library (see module docstring).'
        ),
    )
    parser.add_argument(
        '--use-mozilla-default-profile',
        action='store_true',
        help=(
            'Use profiles.ini default under ~/.mozilla/firefox (or Windows/macOS equivalent) '
            'instead of the dedicated ertflix-auto profile. May create extra profile folders; '
            'close normal Firefox before running.'
        ),
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run Firefox headlessly (no visible window)',
    )
    parser.add_argument(
        '--system-firefox',
        action='store_true',
        help=(
            'Use /usr/bin/firefox (or PATH) instead of Playwright’s Firefox. '
            'Often hangs or shows a blank tab; only try if bundled Firefox fails.'
        ),
    )
    parser.add_argument(
        '--only-audio',
        action='store_true',
        help='Download audio only (default: video via --ertflix-program)',
    )
    parser.add_argument(
        '--audio-format',
        default='mp3',
        metavar='FMT',
        help='Audio format when using --only-audio: mp3, m4a, or flac (default: mp3)',
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable DEBUG logging',
    )
    return parser.parse_known_args()


def main() -> None:
    """Entry point."""
    args, extra_args = _parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
    )
    # Verbose mode sets root to DEBUG; keep asyncio/playwright quiet unless diagnosing them.
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('playwright').setLevel(logging.WARNING)

    # Resolve Firefox user-data dir for Playwright (dedicated path by default).
    if args.profile:
        profile_path = Path(args.profile).expanduser().resolve()
        if not profile_path.is_dir():
            logger.error('Profile path is not a directory: %s', profile_path)
            sys.exit(1)
    elif args.use_mozilla_default_profile:
        found = _find_firefox_profile()
        if not found:
            logger.error(
                'Could not auto-detect Firefox profile.\n'
                'Use --profile /path/to/your/firefox/profile or omit both flags for the '
                'dedicated automation profile under ~/.local/share/ertflix-auto/...'
            )
            sys.exit(1)
        profile_path = found.resolve()
        logger.info('Using Mozilla default profile: %s', profile_path)
    else:
        profile_path = _automation_firefox_profile_dir()
        profile_path.mkdir(parents=True, exist_ok=True)
        logger.info(
            'Using dedicated automation profile (stable path): %s\n'
            'Log in to ERTFlix here once if needed; cookies persist for later runs.',
            profile_path,
        )

    if _profile_under_mozilla_install(profile_path) and _check_firefox_running():
        logger.warning(
            'Firefox is running and this profile is under your Mozilla install — close Firefox '
            'and retry (or use the default dedicated profile without --use-mozilla-default-profile).'
        )
        sys.exit(1)

    # Capture the token URL by automating the browser
    token_url = asyncio.run(
        _capture_token_url(
            args.page_url,
            profile_path,
            args.headless,
            use_system_firefox=args.system_firefox,
            verbose=args.verbose,
        )
    )
    logger.info(f'Token URL: {token_url[:100]}...')

    # Hand off to main-yt-dlp.py
    if not os.getenv('YTDLP_USE_COOKIES', '').strip():
        logger.warning(
            'YTDLP_USE_COOKIES is not set. For ERTFlix, export YTDLP_USE_COOKIES=firefox '
            'before running (see README ERTFlix section).'
        )

    cmd = _build_download_command(token_url, args, extra_args)
    logger.info(f'Starting download: {" ".join(cmd[:4])} ... {cmd[-1][:60]}...')
    subprocess.run(cmd, check=False)


if __name__ == '__main__':
    main()
