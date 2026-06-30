"""NiceGUI page assembly and server entry.

Registers the single ``/`` page (built fresh per user, so all run state is page-local), applies the
config-driven theme through validated CSS, wires Launch/Cancel to the UI-free runner, shows a live
command preview, and streams the selected script's output into a wrapped, scrollable ``ui.log``.
"""

import argparse
import importlib.util
import shlex
from pathlib import Path

from nicegui import background_tasks, ui

from webapp.config import CONFIG_FILENAME, AppConfig, ThemeConfig, load_config, resolve_host_port
from webapp.form import FormView
from webapp.runner import DRIVER_SCRIPT, DriverProcess, build_command
from webapp.validate import (is_safe_color, is_safe_font_family, is_safe_font_size, is_safe_url)

_DEFAULT_SECRET: str = 'yt-dlp-webapp-dev-secret'


def run_app() -> None:
    """Load config (with env/CLI host/port overrides), register the page, and start the server."""
    repo_root = Path(__file__).resolve().parent.parent
    config = load_config(config_path=Path(__file__).resolve().parent / CONFIG_FILENAME)
    cli_host, cli_port = _parse_cli()
    config = resolve_host_port(config=config, cli_host=cli_host, cli_port=cli_port)
    secret = _load_storage_secret(repo_root=repo_root)

    # Register the single page; built fresh per user/page-load so all run state stays page-local.
    ui.page('/')(lambda: _build_page(config=config, repo_root=repo_root))

    # reload (file-watch hot reload) is opt-in via config; default off is the safe deployment stance.
    ui.run(host=config.host, port=config.port, native=config.native, reload=config.reload,
           storage_secret=secret, title='yt-dlp', show=False)


def _build_page(config: AppConfig, repo_root: Path) -> None:
    """Assemble the whole UI: theme, form, command preview, output log, Launch/Cancel.

    Args:
        config: The app configuration.
        repo_root: Repository root (the driver and linter scripts live here).
    """
    _apply_theme(theme=config.theme)
    page = ui.column().classes('w-full max-w-3xl mx-auto p-4 gap-3')
    with page:
        ui.label('yt-dlp — download driver').classes('text-2xl font-bold')

    state: dict[str, DriverProcess | None] = {'proc': None}
    with page:
        form = FormView(config=config)
        preview = ui.label().classes('w-full font-mono text-sm break-all driver-preview')
        log = ui.log(max_lines=5000).classes('w-full h-96 driver-log')
        banner = ui.label().classes('text-lg font-bold')

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

    with page, ui.row():
        launch_btn = ui.button('Launch', icon='play_arrow', on_click=_launch)
        cancel_btn = ui.button('Cancel', icon='stop', on_click=_cancel).props('color=negative')
    cancel_btn.set_enabled(False)
    ui.timer(0.4, _refresh_preview)


def _parse_cli() -> tuple[str | None, int | None]:
    """Parse the optional ``--host`` / ``--port`` overrides from the command line.

    Returns:
        tuple[str | None, int | None]: The CLI host and port (None when not given).
    """
    parser = argparse.ArgumentParser(description='yt-dlp download web app.')
    parser.add_argument('--host', help='Override the listen host (else WEBAPP_HOST, else config.json)')
    parser.add_argument('--port', type=int,
                        help='Override the listen port (else WEBAPP_PORT, else config.json)')
    args, _ = parser.parse_known_args()
    return args.host, args.port


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
