"""NiceGUI page assembly and server entry.

Registers the single ``/`` page (built fresh per user, so all run state is page-local), applies the
config-driven theme through validated CSS, wires Launch/Cancel to the UI-free runner, shows a live
command preview, and streams the selected script's output into a wrapped, scrollable ``ui.log``.
"""

import argparse
import asyncio
import importlib.util
import shlex
from pathlib import Path

from nicegui import app, background_tasks, ui

from webapp import VERSION
from webapp.config import CONFIG_FILENAME, AppConfig, ThemeConfig, load_config, resolve_host_port
from webapp.form import FormView
from webapp.runner import DRIVER_SCRIPT, DriverProcess, build_command
from webapp.services.clipboard_watcher import ClipboardWatcher
from webapp.validate import (is_safe_color, is_safe_font_family, is_safe_font_size, is_safe_url)

_DEFAULT_SECRET: str = 'yt-dlp-webapp-dev-secret'


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

    def _refresh_preview() -> None:
        argv, env = build_command(params=form.collect(), repo_root=repo_root)
        env_str = ' '.join(f'{key}={value}' for key, value in env.items())
        cmd = 'python ' + shlex.join(argv[1:])
        preview.set_text(f'{env_str} {cmd}'.strip())

    def _finish(code: int) -> None:
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

    def _stop_webapp() -> None:
        page.clear()
        with page:
            ui.label('Web application was stopped').classes(
                'w-full text-center text-xl font-bold p-4'
            ).style('background-color: #ffeb3b; color: #000')
        # Shut down on a background task (no UI slot needed, unlike ui.timer) after a short delay,
        # so the cleared/replacement page reaches the client before the websocket closes.
        background_tasks.create(_delayed_shutdown(), name='exit-webapp')

    def _on_clip_url(url: str) -> None:
        form.set_url(url=url)
        # Persist until dismissed (timeout=0) with an OK button. Its text is forced black via CSS
        # (.q-notification__actions .q-btn in _apply_theme) — the default is blue-on-green.
        ui.notify('Picked up URL from the clipboard', type='positive', close_button='OK', timeout=0)

    watcher = ClipboardWatcher(on_youtube_url=_on_clip_url)

    def _sync_watch_btns() -> None:
        on = watcher.is_enabled()
        start_watch_btn.set_enabled(not on)
        stop_watch_btn.set_enabled(on)

    def _start_watch() -> None:
        watcher.start()
        _sync_watch_btns()

    def _stop_watch() -> None:
        watcher.stop()
        _sync_watch_btns()

    page = ui.column().classes('w-full p-4 gap-3')
    with page:
        # Controls are capped to a readable width; only the output log spans the full window.
        with ui.column().classes('w-full max-w-3xl gap-3'):
            ui.label('yt-dlp — download driver').classes('text-2xl font-bold')
            ui.label(f'webapp v{VERSION}').classes('text-xs text-grey -mt-3')
            form = FormView(config=config)
            preview = ui.label().classes('w-full font-mono text-sm break-all driver-preview')
            with ui.row():
                launch_btn = ui.button('Launch', icon='play_arrow', on_click=_launch)
                cancel_btn = ui.button('Cancel', icon='stop', on_click=_cancel).props('color=negative')
                ui.button('Exit web app', icon='dangerous',
                          on_click=_stop_webapp).props('color=orange')
                start_watch_btn = ui.button('Start watching', icon='content_paste',
                                            on_click=_start_watch).props('color=positive')
                stop_watch_btn = ui.button('Stop watching', icon='content_paste_off',
                                           on_click=_stop_watch).props('color=grey')
        log = ui.log(max_lines=5000).classes('w-full h-96 driver-log')
        banner = ui.label().classes('text-lg font-bold')
    cancel_btn.set_enabled(False)
    stop_watch_btn.set_enabled(False)  # not watching yet
    ui.timer(0.4, _refresh_preview)
    # Clipboard poll: always ticks, but watcher.poll() no-ops until 'Start watching' enables it.
    ui.timer(1.0, watcher.poll)


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
    bg = theme.bg_color if is_safe_color(value=theme.bg_color) else '#1e1e1e'
    fg = theme.fg_color if is_safe_color(value=theme.fg_color) else '#e8e8e8'
    family = theme.font_family if is_safe_font_family(value=theme.font_family) else 'Roboto, sans-serif'
    size = theme.font_size if is_safe_font_size(value=theme.font_size) else '16px'
    out_size = theme.output_font_size if is_safe_font_size(value=theme.output_font_size) else '13px'
    ui.add_css('\n'.join([
        _css_rule(selector='body', declarations={
            'background-color': bg, 'color': fg, 'font-family': family, 'font-size': size}),
        _css_rule(selector='.driver-log', declarations={
            'font-size': out_size, 'white-space': 'pre-wrap', 'word-break': 'break-word'}),
        # Force the notification close button ('OK') text black — the Quasar default is a hard-to-read
        # blue on the green positive-notification background.
        _css_rule(selector='.q-notification__actions .q-btn', declarations={'color': '#000 !important'}),
    ]))


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
