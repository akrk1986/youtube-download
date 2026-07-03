"""The preset registry (UI-free).

Each preset is a curated PyCharm run configuration, expressed as a fully-formed
:class:`~webapp.runner.DriverParams`. Selecting a preset in the UI pre-fills the form with these
values (which remain editable before launch). Console-prompt sentinels from the original configs
(``--title prompt`` etc.) are intentionally dropped — they become empty, editable form fields.
"""

from dataclasses import dataclass

from webapp.runner import DRIVER_SCRIPT, LINTER_SCRIPT, DriverParams

# Sentinel cookies value on a preset meaning "use AppConfig.default_cookies" (platform-aware:
# firefox on native Windows, none on WSL/Linux/macOS, overridable in config.json). Resolved by
# FormView.apply_preset; it is never a selectable widget value and never reaches build_command.
COOKIES_FROM_CONFIG: str = 'default'


@dataclass(frozen=True)
class Preset:
    """A named, folder-grouped set of default driver parameters."""

    key: str
    folder: str
    label: str
    params: DriverParams


PRESETS: tuple[Preset, ...] = (
    # ---- Folder: YT-DLP-presets (main-yt-dlp.py) ----
    # These four carry the playlist URL hardcoded in the original PyCharm run configs, so selecting
    # one pre-fills the URL field (no clipboard watcher needed — hence they show no watch buttons).
    Preset(key='presets/av-m4a-boost', folder='YT-DLP-presets', label='audio+video M4A boost',
           params=DriverParams(script=DRIVER_SCRIPT,
                               url='https://www.youtube.com/playlist?list=PLRXnwzqAlx1MCOsyZ-5uMCeZTDclK_2SC',
                               mode='with-audio', audio_format='m4a',
                               subs=True, boost=True, boost_volume=2.0, cookies=COOKIES_FROM_CONFIG,
                               notifications='NO')),
    Preset(key='presets/av-m4a', folder='YT-DLP-presets', label='audio+video M4A',
           params=DriverParams(script=DRIVER_SCRIPT,
                               url='https://www.youtube.com/playlist?list=PLRXnwzqAlx1NehOIsFdwtVbsZ0Orf71cE',
                               mode='with-audio', audio_format='m4a',
                               subs=True, cookies=COOKIES_FROM_CONFIG, notifications='NO')),
    Preset(key='presets/audio-m4a-boost', folder='YT-DLP-presets', label='audio-only M4A boost',
           params=DriverParams(script=DRIVER_SCRIPT,
                               url='https://www.youtube.com/playlist?list=PLRXnwzqAlx1NRqFohqBVngXZyAB1M-oML',
                               mode='only-audio', audio_format='m4a',
                               verbose=True, boost=True, boost_volume=2.0, cookies=COOKIES_FROM_CONFIG,
                               notifications='NO')),
    Preset(key='presets/audio-m4a', folder='YT-DLP-presets', label='audio-only M4A',
           params=DriverParams(script=DRIVER_SCRIPT,
                               url='https://www.youtube.com/playlist?list=PLRXnwzqAlx1OjuERxW0S7XEdJCgl_lf_L',
                               mode='only-audio', audio_format='m4a',
                               verbose=True, cookies=COOKIES_FROM_CONFIG, notifications='NO')),
    # ---- Folder: YT-DLP-prompt (main-yt-dlp.py) ----
    Preset(key='prompt/all', folder='YT-DLP-prompt', label='prompt-all',
           params=DriverParams(script=DRIVER_SCRIPT, mode='with-audio', subs=True,
                               cookies=COOKIES_FROM_CONFIG, notifications='NO')),
    Preset(key='prompt/both', folder='YT-DLP-prompt', label='prompt-both',
           params=DriverParams(script=DRIVER_SCRIPT, mode='with-audio', cookies=COOKIES_FROM_CONFIG,
                               notifications='NO')),
    Preset(key='prompt/both-boost', folder='YT-DLP-prompt', label='prompt-both-boost',
           params=DriverParams(script=DRIVER_SCRIPT, mode='with-audio', boost=True,
                               boost_volume=2.0, cookies=COOKIES_FROM_CONFIG, notifications='NO')),
    Preset(key='prompt/audio-only', folder='YT-DLP-prompt', label='prompt-audio-only',
           params=DriverParams(script=DRIVER_SCRIPT, mode='only-audio', cookies=COOKIES_FROM_CONFIG,
                               notifications='NO')),
    Preset(key='prompt/chapters', folder='YT-DLP-prompt', label='chapters list+download',
           params=DriverParams(script=DRIVER_SCRIPT, mode='video-only', list_chapters='manual',
                               progress=True, cookies=COOKIES_FROM_CONFIG, retries=50, notifications='ALL')),
    Preset(key='prompt/ertflix', folder='YT-DLP-prompt', label='ertflix-program',
           params=DriverParams(script=DRIVER_SCRIPT, mode='ertflix-program', verbose=True,
                               cookies='none', notifications='ALL')),
    Preset(key='prompt/video-only-rerun', folder='YT-DLP-prompt', label='video-only rerun',
           params=DriverParams(script=DRIVER_SCRIPT, mode='video-only', subs=True,
                               video_timeout=1800, rerun=True, cookies=COOKIES_FROM_CONFIG,
                               notifications='NO')),
    # ---- Folder: Run Linters (run-linters.py) ----
    # --batch on every linter preset: the web app streams output but cannot forward keystrokes, so
    # the freshness upgrade-script prompt (its only interactive step) must be skipped.
    Preset(key='linters/all', folder='Run Linters', label='run-linters all',
           params=DriverParams(script=LINTER_SCRIPT, extra_argv=('--batch',))),
    Preset(key='linters/pip-audit', folder='Run Linters', label='run-linters pip-audit',
           params=DriverParams(script=LINTER_SCRIPT, extra_argv=('--batch', '--tool', 'pip-audit'))),
    Preset(key='linters/freshness', folder='Run Linters', label='run-linters freshness',
           params=DriverParams(script=LINTER_SCRIPT, extra_argv=('--batch', '--tool', 'freshness'))),
)

PRESETS_BY_KEY: dict[str, Preset] = {preset.key: preset for preset in PRESETS}


def is_prompt_preset(preset: Preset) -> bool:
    """Return True when a preset expects a user-supplied URL (the YT-DLP-prompt folder).

    Args:
        preset: The preset to classify.

    Returns:
        bool: True for ``prompt/*`` presets, False for the quick presets and the linters.
    """
    return preset.folder == 'YT-DLP-prompt'


def folders() -> list[str]:
    """Return the distinct preset folder names in registry order.

    Returns:
        list[str]: Folder names, first-seen order preserved.
    """
    seen: list[str] = []
    for preset in PRESETS:
        if preset.folder not in seen:
            seen.append(preset.folder)
    return seen
