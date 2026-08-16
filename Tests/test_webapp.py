"""Unit tests for the web app's UI-free logic (runner command mapping + presets + validators).

These verify the highest-value behaviour — that each form value is routed to the correct script
argv flag or environment variable, that every preset targets a script that exists, and that the
URL validator works — without launching yt-dlp or the NiceGUI runtime.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from webapp import config
from webapp.ansi import DARK_PALETTE, LIGHT_PALETTE, ansi_to_html, lines_to_html, palette_for
from webapp.config import (DEFAULT_FONT_FAMILY, DEFAULT_MONO_FAMILY, default_theme_colors, is_wsl,
                           load_config)
from webapp.presets import COOKIES_FROM_CONFIG, PRESETS, PRESETS_BY_KEY, folders, is_prompt_preset
from webapp.runner import DRIVER_SCRIPT, LINTER_SCRIPT, DriverParams, build_command
from webapp.validate import is_safe_color, is_safe_font_family, is_safe_font_size, is_safe_url

REPO_ROOT = Path(__file__).resolve().parent.parent


def _relative_luminance(color: str) -> float:
    """Return the WCAG relative luminance of a ``#rrggbb`` colour.

    Args:
        color: A six-digit hex colour string.

    Returns:
        float: Relative luminance in the range 0.0-1.0, per WCAG 2.1.
    """
    channels = [int(color.lstrip('#')[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
              for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(first: float, second: float) -> float:
    """Return the WCAG contrast ratio between two relative luminances.

    Args:
        first: One relative luminance.
        second: The other relative luminance.

    Returns:
        float: The contrast ratio (1.0-21.0), lighter over darker.
    """
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def _blend(fg: str, bg: str, alpha: float) -> str:
    """Composite a foreground colour over a background at a given opacity.

    Mirrors what the browser does for the ``opacity`` the dim (SGR 2) style applies.

    Args:
        fg: Foreground ``#rrggbb`` colour.
        bg: Background ``#rrggbb`` colour.
        alpha: Foreground opacity in the range 0.0-1.0.

    Returns:
        str: The resulting ``#rrggbb`` colour.
    """
    parts = []
    for index in (0, 2, 4):
        top = int(fg.lstrip('#')[index:index + 2], 16)
        bottom = int(bg.lstrip('#')[index:index + 2], 16)
        parts.append(round(alpha * top + (1 - alpha) * bottom))
    return '#' + ''.join(f'{value:02x}' for value in parts)


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


def test_is_prompt_preset() -> None:
    """Only the YT-DLP-prompt presets are URL-prompting; quick presets and linters are not."""
    for preset in PRESETS:
        expected = preset.key.startswith('prompt/')
        assert is_prompt_preset(preset=preset) is expected, preset.key
    # Sanity: every folder is represented so the assertion above is non-trivial.
    assert {preset.folder for preset in PRESETS if is_prompt_preset(preset=preset)} == {'YT-DLP-prompt'}


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


def test_font_size_accepts_fractional_values() -> None:
    """Fractional sizes are valid CSS and must not be silently dropped; units stay a closed set."""
    assert is_safe_font_size('13px')
    assert is_safe_font_size('12.5px')
    assert is_safe_font_size('0.8rem')
    assert not is_safe_font_size('13')
    assert not is_safe_font_size('13pxx')
    assert not is_safe_font_size('12px; background: url(x)')


def test_default_font_stacks_survive_validation() -> None:
    """The shipped stacks must pass the CSS-injection guard, or they'd silently fall back to it."""
    assert is_safe_font_family(DEFAULT_FONT_FAMILY)
    assert is_safe_font_family(DEFAULT_MONO_FAMILY)
    # Neither the UI face nor the log face may be the framework default or a bare generic.
    assert 'Roboto' not in DEFAULT_FONT_FAMILY
    assert DEFAULT_MONO_FAMILY != 'monospace'
    # The guard still rejects anything that could close the declaration.
    assert not is_safe_font_family('Consolas; } body { display: none')


def test_blank_font_settings_fall_back_to_the_stacks(tmp_path: Path) -> None:
    """An empty font entry in config.json means 'use the default', not an empty CSS value."""
    cfg = tmp_path / 'config.json'
    cfg.write_text('{"theme": {"font_family": "", "output_font_family": ""}}', encoding='utf-8')
    theme = load_config(config_path=cfg).theme
    assert theme.font_family == DEFAULT_FONT_FAMILY
    assert theme.output_font_family == DEFAULT_MONO_FAMILY


def test_default_theme_colors_pair_with_the_flag() -> None:
    """The derived colour pair is exposed so the CSS fallbacks match the configured theme."""
    assert default_theme_colors(dark=True) == ('#e8e8e8', '#1e1e1e')
    assert default_theme_colors(dark=False) == ('#1f1f1f', '#fafafa')


def test_theme_colors_follow_the_dark_flag(tmp_path: Path) -> None:
    """Omitted fg/bg colours are derived from 'dark', so the two can't silently disagree."""
    cfg = tmp_path / 'config.json'

    cfg.write_text('{"theme": {"dark": true}}', encoding='utf-8')
    dark_theme = load_config(config_path=cfg).theme
    assert (dark_theme.fg_color, dark_theme.bg_color) == ('#e8e8e8', '#1e1e1e')

    # Flipping only 'dark' must carry the background with it — the bug was a light component theme
    # left sitting on the dark #1e1e1e body.
    cfg.write_text('{"theme": {"dark": false}}', encoding='utf-8')
    light_theme = load_config(config_path=cfg).theme
    assert (light_theme.fg_color, light_theme.bg_color) == ('#1f1f1f', '#fafafa')

    # An explicit colour still wins over the derived default.
    cfg.write_text('{"theme": {"dark": true, "bg_color": "#101010"}}', encoding='utf-8')
    assert load_config(config_path=cfg).theme.bg_color == '#101010'


def test_is_wsl(monkeypatch: pytest.MonkeyPatch) -> None:
    """WSL is detected via the WSL env vars or the microsoft kernel marker; Windows/Linux are not."""
    monkeypatch.delenv('WSL_DISTRO_NAME', raising=False)
    monkeypatch.delenv('WSL_INTEROP', raising=False)

    # Windows: never WSL (short-circuits before the Linux-only checks).
    monkeypatch.setattr(config.sys, 'platform', 'win32')
    assert is_wsl() is False

    # Native Linux: linux platform, no WSL env vars, plain kernel release.
    monkeypatch.setattr(config.sys, 'platform', 'linux')
    monkeypatch.setattr(config.platform, 'uname', lambda: SimpleNamespace(release='6.1.0-generic'))
    assert is_wsl() is False

    # WSL via env var (even with a plain kernel release).
    monkeypatch.setenv('WSL_DISTRO_NAME', 'Ubuntu')
    assert is_wsl() is True
    monkeypatch.delenv('WSL_DISTRO_NAME')

    # WSL via the kernel-release marker.
    monkeypatch.setattr(config.platform, 'uname',
                        lambda: SimpleNamespace(release='5.15.167.4-microsoft-standard-WSL2'))
    assert is_wsl() is True


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
    assert ansi_to_html(text='\x1b[31mNew\x1b[0m') == '<span style="color:#ff7b72">New</span>'
    assert ansi_to_html(text='\x1b[32mStable\x1b[0m') == '<span style="color:#23d18b">Stable</span>'


def test_palette_follows_the_theme() -> None:
    """The dark/light flag selects the palette, and the two disagree where it matters."""
    assert palette_for(dark=True) is DARK_PALETTE
    assert palette_for(dark=False) is LIGHT_PALETTE
    # Black and bright-white are the two entries that must invert with the background.
    assert DARK_PALETTE.fg[30] != LIGHT_PALETTE.fg[30]
    assert DARK_PALETTE.fg[97] != LIGHT_PALETTE.fg[97]
    assert ansi_to_html(text='\x1b[31mNew\x1b[0m', palette=LIGHT_PALETTE) == (
        '<span style="color:#cd3131">New</span>')


def test_dark_palette_is_readable_on_the_dark_background() -> None:
    """Every dark-palette colour clears WCAG AA (4.5:1) against the dark theme background.

    This is the defect the palette split fixes: the light-tuned table rendered SGR 30/37/97 at
    1.1-1.5:1 on #1e1e1e, i.e. invisible, and four more colours below the 4.5:1 AA threshold.
    """
    background = _relative_luminance(color='#1e1e1e')
    for code, color in DARK_PALETTE.fg.items():
        ratio = _contrast_ratio(_relative_luminance(color=color), background)
        assert ratio >= 4.5, f'SGR {code} ({color}) is {ratio:.2f}:1 on #1e1e1e'


def test_dimmed_dark_palette_stays_legible() -> None:
    """Dim (SGR 2) composites toward the background; at 0.85 it must not wash colours out.

    The previous 0.7 opacity dropped dimmed grey to ~2.5:1, which is why the value is palette-owned.
    """
    assert DARK_PALETTE.dim_opacity == 0.85
    background = _relative_luminance(color='#1e1e1e')
    for code, color in DARK_PALETTE.fg.items():
        blended = _blend(fg=color, bg='#1e1e1e', alpha=DARK_PALETTE.dim_opacity)
        ratio = _contrast_ratio(_relative_luminance(color=blended), background)
        assert ratio >= 4.0, f'dimmed SGR {code} ({color}) is {ratio:.2f}:1 on #1e1e1e'


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


def test_lines_to_html_batches_one_div_per_line() -> None:
    """A burst renders as one fragment with a wrapped div per line, escaping preserved."""
    markup = lines_to_html(lines=['plain', '\x1b[32mok\x1b[0m', '<b>x</b>'],
                           css_class='driver-log-line')
    assert markup == (
        '<div class="driver-log-line">plain</div>'
        '<div class="driver-log-line"><span style="color:#23d18b">ok</span></div>'
        '<div class="driver-log-line">&lt;b&gt;x&lt;/b&gt;</div>')
    # An empty batch must not emit a stray empty line.
    assert lines_to_html(lines=[], css_class='driver-log-line') == ''


def test_ansi_content_cannot_inject_markup() -> None:
    """A colour code around HTML-looking text still escapes the text (no tag injection)."""
    assert ansi_to_html(text='\x1b[31m<b>hi</b>\x1b[0m') == (
        '<span style="color:#ff7b72">&lt;b&gt;hi&lt;/b&gt;</span>')
