"""The preset registry (UI-free).

Each preset is a curated PyCharm run configuration, expressed as a fully-formed
:class:`~webapp.runner.DriverParams`. Selecting a preset in the UI pre-fills the form with these
values (which remain editable before launch). Console-prompt sentinels from the original configs
(``--title prompt`` etc.) are intentionally dropped — they become empty, editable form fields.
"""

from dataclasses import dataclass

from webapp.runner import DRIVER_SCRIPT, LINTER_SCRIPT, DriverParams


@dataclass(frozen=True)
class Preset:
    """A named, folder-grouped set of default driver parameters."""

    key: str
    folder: str
    label: str
    params: DriverParams


PRESETS: tuple[Preset, ...] = (
    # ---- Folder: YT-DLP-presets (main-yt-dlp.py) ----
    Preset(key='presets/av-m4a-boost', folder='YT-DLP-presets', label='audio+video M4A boost',
           params=DriverParams(script=DRIVER_SCRIPT, mode='with-audio', audio_format='m4a',
                               subs=True, boost=True, boost_volume=2.0, cookies='firefox',
                               notifications='NO')),
    Preset(key='presets/av-m4a', folder='YT-DLP-presets', label='audio+video M4A',
           params=DriverParams(script=DRIVER_SCRIPT, mode='with-audio', audio_format='m4a',
                               subs=True, cookies='firefox', notifications='NO')),
    Preset(key='presets/audio-m4a-boost', folder='YT-DLP-presets', label='audio-only M4A boost',
           params=DriverParams(script=DRIVER_SCRIPT, mode='only-audio', audio_format='m4a',
                               verbose=True, boost=True, boost_volume=2.0, cookies='firefox',
                               notifications='NO')),
    Preset(key='presets/audio-m4a', folder='YT-DLP-presets', label='audio-only M4A',
           params=DriverParams(script=DRIVER_SCRIPT, mode='only-audio', audio_format='m4a',
                               verbose=True, cookies='firefox', notifications='NO')),
    # ---- Folder: YT-DLP-prompt (main-yt-dlp.py) ----
    Preset(key='prompt/all', folder='YT-DLP-prompt', label='prompt-all',
           params=DriverParams(script=DRIVER_SCRIPT, mode='with-audio', subs=True,
                               cookies='firefox', notifications='NO')),
    Preset(key='prompt/both', folder='YT-DLP-prompt', label='prompt-both',
           params=DriverParams(script=DRIVER_SCRIPT, mode='with-audio', cookies='firefox',
                               notifications='NO')),
    Preset(key='prompt/both-boost', folder='YT-DLP-prompt', label='prompt-both-boost',
           params=DriverParams(script=DRIVER_SCRIPT, mode='with-audio', boost=True,
                               boost_volume=2.0, cookies='firefox', notifications='NO')),
    Preset(key='prompt/audio-only', folder='YT-DLP-prompt', label='prompt-audio-only',
           params=DriverParams(script=DRIVER_SCRIPT, mode='only-audio', cookies='firefox',
                               notifications='NO')),
    Preset(key='prompt/chapters', folder='YT-DLP-prompt', label='chapters list+download',
           params=DriverParams(script=DRIVER_SCRIPT, mode='video-only', list_chapters='manual',
                               progress=True, cookies='firefox', retries=50, notifications='ALL')),
    Preset(key='prompt/ertflix', folder='YT-DLP-prompt', label='ertflix-program',
           params=DriverParams(script=DRIVER_SCRIPT, mode='ertflix-program', verbose=True,
                               cookies='none', notifications='ALL')),
    Preset(key='prompt/video-only-rerun', folder='YT-DLP-prompt', label='video-only rerun',
           params=DriverParams(script=DRIVER_SCRIPT, mode='video-only', subs=True,
                               video_timeout=1800, rerun=True, cookies='firefox',
                               notifications='NO')),
    # ---- Folder: Run Linters (run-linters.py) ----
    Preset(key='linters/all', folder='Run Linters', label='run-linters all',
           params=DriverParams(script=LINTER_SCRIPT, extra_argv=())),
    Preset(key='linters/pip-audit', folder='Run Linters', label='run-linters pip-audit',
           params=DriverParams(script=LINTER_SCRIPT, extra_argv=('--tool', 'pip-audit'))),
    Preset(key='linters/freshness', folder='Run Linters', label='run-linters freshness',
           params=DriverParams(script=LINTER_SCRIPT, extra_argv=('--tool', 'freshness'))),
)

PRESETS_BY_KEY: dict[str, Preset] = {preset.key: preset for preset in PRESETS}


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
