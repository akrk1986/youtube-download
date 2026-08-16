"""NiceGUI page assembly and server entry.

Registers the single ``/`` page (built fresh per user, so all run state is page-local), applies the
config-driven theme through validated CSS, wires Launch/Cancel to the UI-free runner, shows a live
command preview, and streams the selected script's output into a wrapped, scrollable colour log.
"""

import argparse
import asyncio
import importlib.util
import logging
import shlex
from collections import deque
from collections.abc import Callable
from pathlib import Path

from nicegui import app, background_tasks, ui

from webapp import VERSION
from webapp.ansi import AnsiPalette, lines_to_html, palette_for
from webapp.config import (CONFIG_FILENAME, DEFAULT_FONT_FAMILY, DEFAULT_MONO_FAMILY, AppConfig,
                           ThemeConfig, default_theme_colors, is_wsl, load_config,
                           resolve_host_port)
from webapp.form import FormView
from webapp.runner import DRIVER_SCRIPT, DriverProcess, build_command
from webapp.services.clipboard_watcher import ClipboardWatcher
from webapp.validate import (is_safe_color, is_safe_font_family, is_safe_font_size, is_safe_url)

logger = logging.getLogger(__name__)

_DEFAULT_SECRET: str = 'yt-dlp-webapp-dev-secret'
# How often queued output lines are rendered. Also the worst-case delay before a line appears, so it
# stays well under the ~150 ms at which a live log stops feeling live.
_LOG_FLUSH_INTERVAL: float = 0.1
# How often the clipboard is read while watching is on.
_CLIPBOARD_POLL_INTERVAL: float = 1.0
# How often the command preview is rebuilt from the live form values.
_PREVIEW_REFRESH_INTERVAL: float = 0.4


class _AnsiLog:
    """A scrollable output log that renders ANSI SGR colour codes as HTML.

    Covers the slice of ``ui.log`` the page relies on — a ``push(line)`` method with max-line
    trimming and auto-scroll to the newest line — but converts each line from ANSI to safe HTML, so
    the linter's coloured rich tables and New/Stable badges render as colour rather than raw escapes.

    Pushed lines are **buffered and flushed on a timer** rather than rendered one at a time. yt-dlp
    and the linters emit output in bursts, and rendering per line cost one element creation plus one
    ``scroll_to`` round-trip *each* — so a fast burst queued two websocket messages per line and left
    one Vue component per line on the page. A flush instead renders the whole batch as a single
    element and scrolls once, which bounds the traffic by the flush rate instead of the output rate.
    """

    def __init__(self, *, max_lines: int, css_class: str, palette: AnsiPalette,
                 flush_interval: float) -> None:
        """Build the scroll area, the inner column hosting rendered batches, and the flush timer.

        Args:
            max_lines: Oldest lines beyond this count are dropped (to the nearest whole batch).
            css_class: Extra CSS class on the scroll area (the theme font-size/monospace hook).
            palette: The ANSI palette matching the configured log background.
            flush_interval: Seconds between flushes; also the worst-case latency of a new line.
        """
        self._max_lines = max_lines
        self._palette = palette
        self._pending: list[str] = []
        # One entry per rendered batch element, oldest first: how many lines that element holds.
        self._batch_sizes: deque[int] = deque()
        self._rendered_lines = 0
        # No height class here: .driver-log sizes the log to the leftover viewport height (see
        # _apply_theme), so a tall monitor gets a tall log instead of a fixed 384px one.
        self._scroll = ui.scroll_area().classes(f'w-full {css_class}')
        with self._scroll:
            self._col = ui.column().classes('w-full gap-0')
        ui.timer(flush_interval, self.flush)

    def push(self, line: str) -> None:
        """Queue one line for the next flush.

        Args:
            line: The raw output line (may contain ANSI SGR escape codes).
        """
        self._pending.append(line)
        # A producer faster than the flush rate can't grow the queue without bound: anything beyond
        # max_lines would be trimmed on render anyway, so drop it before paying to convert it.
        if len(self._pending) > self._max_lines:
            del self._pending[:-self._max_lines]

    def flush(self) -> None:
        """Render every queued line as one batch element, trim to ``max_lines``, then scroll once."""
        if not self._pending:
            return
        lines, self._pending = self._pending, []
        with self._col:
            ui.html(lines_to_html(lines=lines, css_class='driver-log-line', palette=self._palette))
        self._batch_sizes.append(len(lines))
        self._rendered_lines += len(lines)
        # Trim whole batches (never the last one, so the newest output always survives).
        while self._rendered_lines > self._max_lines and len(self._batch_sizes) > 1:
            self._col.remove(0)
            self._rendered_lines -= self._batch_sizes.popleft()
        self._scroll.scroll_to(percent=1.0)

    def clear(self) -> None:
        """Drop every queued and rendered line from the log."""
        self._pending.clear()
        self._batch_sizes.clear()
        self._rendered_lines = 0
        self._col.clear()


class _WatchControls:
    """The clipboard Start/Stop-watching buttons, the watcher they drive, and their poll timer.

    Grouped into one object because the concern was otherwise smeared across five closures in the
    page builder, all of which had to agree about the same two buttons: which is enabled, whether
    either is visible for the selected preset, and what happens when a URL arrives.
    """

    def __init__(self, *, form: FormView, supported: bool, poll_interval: float) -> None:
        """Create both buttons and, where supported, the clipboard poll timer.

        Args:
            form: The form whose URL field receives a picked-up clipboard URL.
            supported: False under WSL, where the clipboard bridge is unreliable — the buttons stay
                hidden and no poll timer is created.
            poll_interval: Seconds between clipboard reads while watching.
        """
        self._form = form
        self._supported = supported
        self._watcher = ClipboardWatcher(on_media_url=self._on_media_url)
        # Flat and uncoloured (see the button-row comment in _build_page for why color=None): these
        # are secondary to Launch, and only one of the pair is ever enabled, so the enabled/disabled
        # contrast already says which is the meaningful action.
        self._start_btn = ui.button('Start watching', icon='content_paste',
                                    on_click=self._start, color=None).props('flat')
        self._stop_btn = ui.button('Stop watching', icon='content_paste_off',
                                   on_click=self._stop, color=None).props('flat')
        self._stop_btn.set_enabled(False)  # not watching yet
        self.sync_visibility()
        # poll() no-ops until 'Start watching', so the timer is cheap while idle.
        if supported:
            ui.timer(poll_interval, self._watcher.poll)

    def sync_visibility(self) -> None:
        """Show both buttons only for a URL-prompting preset on a platform that supports watching."""
        visible = self._supported and self._form.current_is_prompt()
        self._start_btn.set_visibility(visible)
        self._stop_btn.set_visibility(visible)

    def on_preset_changed(self) -> None:
        """React to a preset switch: a preset with no URL field can't be watched for, so stop."""
        if not self._form.current_is_prompt() and self._watcher.is_enabled():
            self._stop()
        self.sync_visibility()

    def _on_media_url(self, url: str) -> None:
        """Fill the URL field with a URL picked up from the clipboard and say so.

        Args:
            url: The media URL found on the clipboard.
        """
        self._form.set_url(url=url)
        # Persist until dismissed (timeout=0) with an OK button. Its text is forced black via CSS
        # (.q-notification__actions .q-btn in _apply_theme) — the default is blue-on-green.
        ui.notify('Picked up URL from the clipboard', type='positive', close_button='OK', timeout=0)

    def _start(self) -> None:
        """Begin watching the clipboard."""
        self._watcher.start()
        self._sync_enabled()

    def _stop(self) -> None:
        """Stop watching the clipboard."""
        self._watcher.stop()
        self._sync_enabled()

    def _sync_enabled(self) -> None:
        """Enable whichever of the two buttons is the meaningful next action."""
        watching = self._watcher.is_enabled()
        self._start_btn.set_enabled(not watching)
        self._stop_btn.set_enabled(watching)


def run_app() -> None:
    """Load config (with env/CLI host/port overrides), register the page, and start the server."""
    repo_root = Path(__file__).resolve().parent.parent
    config = load_config(config_path=Path(__file__).resolve().parent / CONFIG_FILENAME)
    cli_host, cli_port, cli_native = _parse_cli()
    config = resolve_host_port(config=config, cli_host=cli_host, cli_port=cli_port)
    secret = _load_storage_secret(repo_root=repo_root)
    # --native forces the desktop window on; config.json `native` still works as a fallback.
    native = cli_native or config.native

    # Register the single page; built fresh per user/page-load so all run state stays page-local.
    ui.page('/')(lambda: _build_page(config=config, repo_root=repo_root))

    # reload (file-watch hot reload) is opt-in via config; default off is the safe deployment stance.
    ui.run(host=config.host, port=config.port, native=native, reload=config.reload,
           storage_secret=secret, title='yt-dlp', show=False)


def _build_page(config: AppConfig, repo_root: Path) -> None:
    """Assemble the whole UI: theme, form, command preview, controls, output log.

    The Launch / Cancel / Exit-web-app controls sit above the output log. The controls are capped to
    a readable width; only the output log spans the full browser width (useful on desktop).

    Args:
        config: The app configuration.
        repo_root: Repository root (the driver and linter scripts live here).
    """
    _apply_theme(theme=config.theme)
    state: dict[str, DriverProcess | None] = {'proc': None}
    # Clipboard watching is unreliable from the running server under WSL (the Windows clipboard bridge
    # doesn't deliver reliably); disable it there — the buttons are hidden and the poll timer is not
    # created. Native Linux keeps it active but is UNTESTED — see webapp/README.md "Known issues".
    watching_supported = not is_wsl()

    def _refresh_preview() -> None:
        argv, env = build_command(params=form.collect(), repo_root=repo_root)
        env_str = ' '.join(f'{key}={value}' for key, value in env.items())
        cmd = 'python ' + shlex.join(argv[1:])
        preview.set_text(f'{env_str} {cmd}'.strip())

    def _finish(code: int) -> None:
        # Render whatever is still queued first, so the outcome never appears above the last lines
        # of output that produced it.
        log.flush()
        state['proc'] = None
        launch_btn.set_enabled(True)
        cancel_btn.set_enabled(False)
        ok = code == 0
        banner.set_text(f'Done — exit {code}' if ok else f'Failed — exit {code}')
        banner.classes(replace='text-lg font-bold ' + ('text-positive' if ok else 'text-negative'))

    async def _run(proc: DriverProcess) -> None:
        async for line in proc.stream():
            log.push(line)
        _finish(code=await proc.wait())

    async def _launch() -> None:
        # Enter in a text field reaches this too, and the keyboard has no disabled state to respect
        # the way the Launch button does — so refuse a second run explicitly.
        if state['proc'] is not None:
            ui.notify('A run is already in progress — cancel it first.', type='warning')
            return
        params = form.collect()
        if params.script == DRIVER_SCRIPT:
            if params.url and not is_safe_url(url=params.url):
                ui.notify('URL must start with http:// or https://', type='negative')
                return
            if not params.url and not params.rerun:
                ui.notify('Enter a URL (or choose a --rerun preset).', type='warning')
                return
        argv, env = build_command(params=params, repo_root=repo_root)
        proc = DriverProcess(argv=argv, env_overrides=env, cwd=repo_root)
        state['proc'] = proc
        launch_btn.set_enabled(False)
        cancel_btn.set_enabled(True)
        banner.set_text('Running…')
        banner.classes(replace='text-lg font-bold text-warning')
        log.push('$ ' + shlex.join(argv))
        background_tasks.create(_run(proc=proc), name='driver-run')

    def _cancel() -> None:
        proc = state['proc']
        if proc is not None:
            proc.cancel()
            log.push('— cancelled —')

    def _clear_log() -> None:
        log.clear()
        banner.set_text('')

    def _stop_webapp() -> None:
        page.clear()
        with page:
            # Colours come from .driver-stopped (theme-derived) rather than an inline literal, so the
            # final page can't flash a fixed bright yellow out of a dark UI.
            ui.label('Web application was stopped').classes(
                'w-full text-center text-xl font-bold p-4 driver-stopped')
        # Shut down on a background task (no UI slot needed, unlike ui.timer) after a short delay,
        # so the cleared/replacement page reaches the client before the websocket closes.
        background_tasks.create(_delayed_shutdown(), name='exit-webapp')

    def _on_preset_changed() -> None:
        watch.on_preset_changed()

    # flex-1/min-h-0 make this column fill the viewport-height wrapper and let the log inside it
    # shrink; the p-4 the column used to carry is dropped because .nicegui-content already pads 1rem,
    # and the doubled padding was costing the log vertical space for nothing.
    page = ui.column().classes('w-full flex-1 min-h-0 gap-3')
    with page:
        # Controls are capped to a readable width; only the output log spans the full window.
        # shrink-0 keeps them at their natural height so the log absorbs the leftover space.
        with ui.column().classes('w-full max-w-3xl shrink-0 gap-3'):
            # Title, version and the Exit control share one row: the version no longer needs the
            # -mt-3 negative-margin hack to sit under the title, and Exit — destructive but rarely
            # wanted — is parked in the corner at the lowest weight on the page, well away from the
            # Launch button it used to sit beside wearing a louder colour.
            with ui.row().classes('w-full items-center gap-2'):
                ui.label('yt-dlp — download driver').classes('text-2xl font-bold')
                ui.label(f'webapp v{VERSION}').classes('text-xs text-grey')
                ui.space()
                ui.button('Exit web app', icon='dangerous', on_click=_stop_webapp,
                          color=None).props('flat dense').classes('driver-exit')
            form = FormView(config=config, on_change=_on_preset_changed, on_submit=_launch)
            # break-words, not break-all: the preview is a command line, so wrapping between its
            # tokens keeps flags and URLs readable instead of splitting them mid-word.
            preview = ui.label().classes('w-full font-mono text-sm break-words driver-preview')
            # Rank by weight, not by hue. Launch is the only filled button on the page; Cancel is an
            # outline (and stays disabled until there is something to cancel); everything else is
            # flat. `unelevated` drops Material's drop shadow, which reads as decoration on a
            # control surface. color=None is deliberate: NiceGUI otherwise defaults every button to
            # 'primary', and a flat primary button is blue text — only 3.6:1 on the dark background.
            # Unset, a flat button inherits the theme foreground and follows whatever theme is set.
            with ui.row().classes('items-center gap-2'):
                launch_btn = ui.button('Launch', icon='play_arrow',
                                       on_click=_launch).props('unelevated')
                cancel_btn = ui.button('Cancel', icon='stop',
                                       on_click=_cancel).props('outline color=negative')
                ui.button('Clear log', icon='delete_sweep', on_click=_clear_log,
                          color=None).props('flat')
                watch = _WatchControls(form=form, supported=watching_supported,
                                       poll_interval=_CLIPBOARD_POLL_INTERVAL)
            # The run outcome belongs next to the button that caused it. It used to sit below the
            # log, where a tall log pushed the one answer you wait for off the bottom of the window.
            banner = ui.label().classes('text-lg font-bold')
        log = _AnsiLog(max_lines=5000, css_class='driver-log',
                       palette=palette_for(dark=config.theme.dark),
                       flush_interval=_LOG_FLUSH_INTERVAL)
    cancel_btn.set_enabled(False)
    ui.timer(_PREVIEW_REFRESH_INTERVAL, _refresh_preview)


async def _delayed_shutdown() -> None:
    """Stop the NiceGUI server after a short delay so the client renders the final page first."""
    await asyncio.sleep(0.5)
    app.shutdown()


def _parse_cli() -> tuple[str | None, int | None, bool]:
    """Parse the optional ``--host`` / ``--port`` / ``--native`` overrides from the command line.

    Returns:
        tuple[str | None, int | None, bool]: The CLI host, port (None when not given), and the
        ``--native`` flag (launch as a desktop window instead of a browser tab).
    """
    parser = argparse.ArgumentParser(description='yt-dlp download web app.')
    parser.add_argument('--host', help='Override the listen host (else WEBAPP_HOST, else config.json)')
    parser.add_argument('--port', type=int,
                        help='Override the listen port (else WEBAPP_PORT, else config.json)')
    parser.add_argument('--native', action='store_true',
                        help='Launch as a standalone desktop window (needs pywebview) instead of a '
                             'browser tab')
    args, _ = parser.parse_known_args()
    return args.host, args.port, args.native


def _apply_theme(theme: ThemeConfig) -> None:
    """Inject validated theme colours and fonts as CSS.

    Every value is regex-validated first; an unsafe value falls back to a built-in default so no raw
    string reaches ``ui.add_css``.

    Args:
        theme: The theme block from config.json.
    """
    ui.dark_mode(value=theme.dark)
    default_fg, default_bg = default_theme_colors(dark=theme.dark)
    bg = _validated(key='bg_color', value=theme.bg_color, is_valid=is_safe_color,
                    fallback=default_bg)
    fg = _validated(key='fg_color', value=theme.fg_color, is_valid=is_safe_color,
                    fallback=default_fg)
    family = _validated(key='font_family', value=theme.font_family, is_valid=is_safe_font_family,
                        fallback=DEFAULT_FONT_FAMILY)
    size = _validated(key='font_size', value=theme.font_size, is_valid=is_safe_font_size,
                      fallback='16px')
    mono = _validated(key='output_font_family', value=theme.output_font_family,
                      is_valid=is_safe_font_family, fallback=DEFAULT_MONO_FAMILY)
    out_size = _validated(key='output_font_size', value=theme.output_font_size,
                          is_valid=is_safe_font_size, fallback='13px')
    ui.add_css('\n'.join([
        # tabular-nums keeps the panel's figures (timeout, retries, boost factor, exit codes) on a
        # fixed advance width, so a changing value never nudges the text beside it.
        _css_rule(selector='body', declarations={
            'background-color': bg, 'color': fg, 'font-family': family, 'font-size': size,
            'font-variant-numeric': 'tabular-nums'}),
        # Anchor the page to the viewport so the log below can claim the leftover height. The
        # wrapper still scrolls when the window is too short for the controls plus the log's floor.
        _css_rule(selector='.nicegui-content', declarations={
            'height': '100vh', 'overflow-y': 'auto'}),
        # Monospace so the linter's rich box-drawing tables line up; font-size from the theme.
        # The compound selector outranks NiceGUI's own `.nicegui-scroll-area { height: 16rem }`,
        # which would otherwise pin the log's height and defeat the flex sizing.
        _css_rule(selector='.nicegui-scroll-area.driver-log', declarations={
            'font-size': out_size, 'font-family': mono,
            'border': '1px solid rgba(128,128,128,0.4)', 'border-radius': '4px',
            'flex': '1 1 0', 'height': 'auto', 'min-height': '12rem'}),
        # Each rendered log line wraps rather than overflowing the log's width.
        _css_rule(selector='.driver-log-line', declarations={
            'white-space': 'pre-wrap', 'word-break': 'break-word'}),
        # Exit sits below every other control in the visual order without dropping out of reach:
        # 0.7 of the theme foreground still measures above 4.5:1 on both the dark and light
        # backgrounds, where Quasar's 'grey' would have failed on light (2.6:1).
        _css_rule(selector='.driver-exit', declarations={'opacity': '0.7'}),
        # The post-shutdown page: theme foreground, boxed by a full border. A full border rather
        # than a colour fill keeps it legible whichever theme is configured.
        _css_rule(selector='.driver-stopped', declarations={
            'color': fg, 'border': f'2px solid {fg}', 'border-radius': '4px'}),
        # Quasar's touch-pan scroll directive tags the scroll-area content with .q-touch, whose
        # user-select:none makes the log text unselectable; re-enable selection for copy/paste.
        _css_rule(selector='.driver-log .q-touch, .driver-log .q-scrollarea__content', declarations={
            '-webkit-user-select': 'text', 'user-select': 'text'}),
        # Force the notification close button ('OK') text black — the Quasar default is a hard-to-read
        # blue on the green positive-notification background.
        _css_rule(selector='.q-notification__actions .q-btn', declarations={'color': '#000 !important'}),
    ]))


def _validated(key: str, value: str, is_valid: Callable[[str], bool], fallback: str) -> str:
    """Return a theme value if it passes its validator, else log what was rejected and substitute.

    Every theme string is regex-checked before it reaches ``ui.add_css``, so an unsupported value is
    dropped rather than injected. Dropping it silently, though, looks identical to the setting having
    no effect — hence the warning naming the key, the rejected value and what is used instead.

    Args:
        key: The config.json theme key the value came from.
        value: The configured value.
        is_valid: The validator for this kind of value.
        fallback: The value used when validation fails.

    Returns:
        str: ``value`` when valid, otherwise ``fallback``.
    """
    if is_valid(value):  # positional: Callable[[str], bool] carries no parameter name to bind to
        return value
    logger.warning('config.json theme.%s: %r is not a supported value — using %r instead',
                   key, value, fallback)
    return fallback


def _css_rule(selector: str, declarations: dict[str, str]) -> str:
    """Render one CSS rule from a selector and a declarations mapping.

    Args:
        selector: The CSS selector.
        declarations: Property-to-value mapping.

    Returns:
        str: A single ``selector { prop: value; ... }`` rule.
    """
    body = ' '.join(f'{prop}: {value};' for prop, value in declarations.items())
    return selector + ' { ' + body + ' }'


def _load_storage_secret(repo_root: Path) -> str:
    """Load the NiceGUI storage secret from the gitignored top-level ``git_excluded.py``.

    Args:
        repo_root: Repository root that may hold ``git_excluded.py``.

    Returns:
        str: The ``STORAGE_SECRET`` value, or a built-in development fallback when absent.
    """
    path = repo_root / 'git_excluded.py'
    if not path.is_file():
        return _DEFAULT_SECRET
    spec = importlib.util.spec_from_file_location('git_excluded', path)
    if spec is None or spec.loader is None:
        return _DEFAULT_SECRET
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, 'STORAGE_SECRET', _DEFAULT_SECRET)
