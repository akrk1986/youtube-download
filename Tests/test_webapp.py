"""Unit tests for the web app's UI-free logic (runner command mapping + presets + validators).

These verify the highest-value behaviour — that each form value is routed to the correct script
argv flag or environment variable, that every preset targets a script that exists, and that the
URL validator works — without launching yt-dlp or the NiceGUI runtime.
"""

import sys
from pathlib import Path

from webapp.ansi import ansi_to_html
from webapp.config import load_config
from webapp.presets import COOKIES_FROM_CONFIG, PRESETS, PRESETS_BY_KEY, folders
from webapp.runner import DRIVER_SCRIPT, LINTER_SCRIPT, DriverParams, build_command
from webapp.validate import is_safe_color, is_safe_url

REPO_ROOT = Path(__file__).resolve().parent.parent


def _download(**overrides: object) -> DriverParams:
    """Build a download DriverParams with sensible defaults, overriding selected fields.

    Args:
        **overrides: Field values to override on the default params.

    Returns:
        DriverParams: The constructed params for the download script.
    """
    return DriverParams(script=DRIVER_SCRIPT, **overrides)  # type: ignore[arg-type]


def test_minimal_command_has_url_and_no_env() -> None:
    """A bare video-only run passes just the URL, with no env overrides beyond the gate flag."""
    argv, env = build_command(params=_download(url='https://x'), repo_root=REPO_ROOT)
    assert argv[-1] == 'https://x'
    assert str(REPO_ROOT / DRIVER_SCRIPT) in argv
    assert env == {'LINTER_GATE': 'off'}


def test_mode_flags_are_mutually_exclusive() -> None:
    """Each mode maps to its single flag; video-only emits none of the three."""
    assert '--with-audio' in build_command(params=_download(mode='with-audio'), repo_root=REPO_ROOT)[0]
    assert '--only-audio' in build_command(params=_download(mode='only-audio'), repo_root=REPO_ROOT)[0]
    assert '--ertflix-program' in build_command(
        params=_download(mode='ertflix-program'), repo_root=REPO_ROOT)[0]
    video_argv, _ = build_command(params=_download(mode='video-only'), repo_root=REPO_ROOT)
    assert not ({'--with-audio', '--only-audio', '--ertflix-program'} & set(video_argv))


def test_audio_format_only_for_audio_modes() -> None:
    """--audio-format is emitted for audio modes, not for video-only/ertflix."""
    wa_argv, _ = build_command(
        params=_download(mode='with-audio', audio_format='mp3,m4a'), repo_root=REPO_ROOT)
    assert wa_argv[wa_argv.index('--audio-format') + 1] == 'mp3,m4a'
    vo_argv, _ = build_command(params=_download(mode='video-only'), repo_root=REPO_ROOT)
    assert '--audio-format' not in vo_argv


def test_env_backed_options_go_to_env_not_argv() -> None:
    """Boost / cookies / notifications / retries are delivered as env vars, never as CLI flags."""
    argv, env = build_command(
        params=_download(mode='only-audio', boost=True, boost_volume=3.0, cookies='firefox',
                         notifications='ALL', notif_msg='PROD', retries=50),
        repo_root=REPO_ROOT)
    assert env['FFMPEG_OPTS'] == 'volume=3.0'
    assert env['YTDLP_USE_COOKIES'] == 'firefox'
    assert env['NOTIFICATIONS'] == 'ALL'
    assert env['NOTIF_MSG'] == 'PROD'
    assert env['YTDLP_RETRIES'] == '50'
    assert not any(token.startswith('--boost') or token.startswith('--cookies') for token in argv)


def test_notifications_no_and_cookies_none_omit_env() -> None:
    """NOTIFICATIONS=NO and cookies=none add nothing to the environment."""
    _, env = build_command(
        params=_download(mode='with-audio', notifications='NO', cookies='none'), repo_root=REPO_ROOT)
    assert 'NOTIFICATIONS' not in env
    assert 'YTDLP_USE_COOKIES' not in env


def test_empty_metadata_fields_are_omitted() -> None:
    """Empty Title/Artist/Album produce no flags; non-empty ones are passed through."""
    bare_argv, _ = build_command(params=_download(mode='with-audio'), repo_root=REPO_ROOT)
    assert not ({'--title', '--artist', '--album'} & set(bare_argv))
    filled_argv, _ = build_command(
        params=_download(mode='with-audio', title='T', artist='A', album='B'), repo_root=REPO_ROOT)
    assert filled_argv[filled_argv.index('--title') + 1] == 'T'
    assert filled_argv[filled_argv.index('--artist') + 1] == 'A'
    assert filled_argv[filled_argv.index('--album') + 1] == 'B'


def test_video_only_rerun_uses_current_timeout_flag() -> None:
    """The rerun preset emits --video-download-timeout (not the removed --video flag)."""
    argv, _ = build_command(
        params=_download(mode='video-only', subs=True, video_timeout=1800, rerun=True),
        repo_root=REPO_ROOT)
    assert argv[argv.index('--video-download-timeout') + 1] == '1800'
    assert '--video' not in argv
    assert '--rerun' in argv and '--subs' in argv


def test_chapters_and_flags() -> None:
    """list_chapters and the boolean flags appear only when set."""
    argv, _ = build_command(
        params=_download(mode='video-only', list_chapters='manual', progress=True,
                         write_json=True, verbose=True),
        repo_root=REPO_ROOT)
    assert argv[argv.index('--list-chapters') + 1] == 'manual'
    assert {'--progress', '--json', '--verbose'} <= set(argv)


def test_linter_preset_targets_run_linters() -> None:
    """A linter preset shells run-linters.py with its --tool args and colour-forcing env."""
    params = DriverParams(script=LINTER_SCRIPT, extra_argv=('--tool', 'pip-audit'))
    argv, env = build_command(params=params, repo_root=REPO_ROOT)
    assert str(REPO_ROOT / LINTER_SCRIPT) in argv
    assert argv[-2:] == ['--tool', 'pip-audit']
    assert env == {'FORCE_COLOR': '1', 'COLUMNS': '120'}


def test_every_preset_script_exists() -> None:
    """Each preset targets a script file that exists in the repo, and keys are unique."""
    assert len(PRESETS_BY_KEY) == len(PRESETS)
    for preset in PRESETS:
        assert (REPO_ROOT / preset.params.script).is_file(), preset.key


def test_preset_default_rules() -> None:
    """Cookies follow the config default except ertflix (none); notif=ALL only for the two configs."""
    by_key = PRESETS_BY_KEY
    assert by_key['prompt/ertflix'].params.cookies == 'none'
    assert all(by_key[k].params.cookies == COOKIES_FROM_CONFIG
               for k in by_key if by_key[k].params.script == DRIVER_SCRIPT and k != 'prompt/ertflix')
    all_notif = {k for k in by_key if by_key[k].params.notifications == 'ALL'}
    assert all_notif == {'prompt/ertflix', 'prompt/chapters'}
    assert folders() == ['YT-DLP-presets', 'YT-DLP-prompt', 'Run Linters']


def test_default_cookies_resolution(tmp_path: Path) -> None:
    """config.json 'cookies' overrides the platform default; blank/invalid falls back to platform."""
    cfg = tmp_path / 'config.json'
    cfg.write_text('{"cookies": "chrome"}', encoding='utf-8')
    assert load_config(config_path=cfg).default_cookies == 'chrome'

    cfg.write_text('{"cookies": ""}', encoding='utf-8')
    platform_default = 'firefox' if sys.platform == 'win32' else 'none'
    assert load_config(config_path=cfg).default_cookies == platform_default

    cfg.write_text('{"cookies": "bogus"}', encoding='utf-8')
    assert load_config(config_path=cfg).default_cookies == platform_default


def test_validators() -> None:
    """The security validators accept safe values and reject unsafe ones."""
    assert is_safe_url('https://example.com')
    assert is_safe_url('')
    assert not is_safe_url('javascript:alert(1)')
    assert is_safe_color('#1e1e1e')
    assert not is_safe_color('red; } body { display:none')


def test_ansi_plain_text_is_escaped_and_unwrapped() -> None:
    """Text with no escapes is HTML-escaped and never wrapped in a span."""
    assert ansi_to_html(text='a < b & "c"') == 'a &lt; b &amp; &quot;c&quot;'
    assert ansi_to_html(text='plain') == 'plain'


def test_ansi_basic_colours_become_spans() -> None:
    """The red/green badges rich emits map to coloured spans around the escaped run."""
    assert ansi_to_html(text='\x1b[31mNew\x1b[0m') == '<span style="color:#cd3131">New</span>'
    assert ansi_to_html(text='\x1b[32mStable\x1b[0m') == '<span style="color:#0dbc79">Stable</span>'


def test_ansi_bold_italic_and_reset() -> None:
    """Bold and italic map to CSS; a reset closes the styled run so trailing text is plain."""
    assert ansi_to_html(text='\x1b[1mB\x1b[0m x') == '<span style="font-weight:bold">B</span> x'
    assert ansi_to_html(text='\x1b[3mI\x1b[0m') == '<span style="font-style:italic">I</span>'


def test_ansi_truecolor_and_other_escapes_stripped() -> None:
    """24-bit colour maps exactly; non-SGR escapes (cursor moves) are dropped entirely."""
    assert ansi_to_html(text='\x1b[38;2;255;0;0mR\x1b[0m') == '<span style="color:#ff0000">R</span>'
    assert ansi_to_html(text='a\x1b[2Kb') == 'ab'


def test_ansi_emoji_pinned_to_rich_cell_width() -> None:
    """Table emoji are wrapped in an inline-block of the cell width rich reserved (⛔=2ch, ⚠=1ch)."""
    red_stop = ansi_to_html(text='\x1b[31m⛔ held by pylint\x1b[0m')
    assert 'display:inline-block;width:2ch;text-align:center">⛔</span>' in red_stop
    assert 'held by pylint' in red_stop
    warn = ansi_to_html(text='⚠ build')
    assert 'width:1ch;text-align:center">⚠</span>' in warn
    # Box-drawing characters are left as plain monospace text (already one cell wide).
    assert ansi_to_html(text='│ x │') == '│ x │'


def test_ansi_content_cannot_inject_markup() -> None:
    """A colour code around HTML-looking text still escapes the text (no tag injection)."""
    assert ansi_to_html(text='\x1b[31m<b>hi</b>\x1b[0m') == (
        '<span style="color:#cd3131">&lt;b&gt;hi&lt;/b&gt;</span>')
