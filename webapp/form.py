"""The input form view.

Builds a preset selector plus every ``main-yt-dlp.py`` parameter as a widget (all presented
uniformly, so the env-backed options — boost, cookies, notifications, retries — are
indistinguishable from the CLI flags) and collects the live values into a
:class:`~webapp.runner.DriverParams`. Selecting a preset pre-fills the widgets; selecting a linter
preset hides the download form (its command is fixed). Holds no module-level state: one instance is
created per page load.
"""

from nicegui import ui

from webapp.config import AppConfig
from webapp.presets import PRESETS, PRESETS_BY_KEY, Preset
from webapp.runner import DRIVER_SCRIPT, LINTER_SCRIPT, DriverParams

_MODES = {
    'with-audio': 'Video + audio',
    'only-audio': 'Audio only',
    'ertflix-program': 'ERTFlix program (token URL)',
    'video-only': 'Video only',
}
_AUDIO_FORMATS = {
    'm4a': 'M4A',
    'mp3': 'MP3',
    'flac': 'FLAC',
    'mp3,m4a': 'MP3 + M4A',
    'mp3,m4a,flac': 'MP3 + M4A + FLAC',
}
_CHAPTERS = {'none': 'No', 'json': 'json (native)', 'manual': 'manual (tracklist)'}
_COOKIES = {'none': 'None', 'firefox': 'Firefox', 'chrome': 'Chrome'}
_NOTIF = {'NO': 'None', 'S': 'Slack', 'G': 'Gmail', 'ALL': 'Slack + Gmail'}


class FormView:  # pylint: disable=too-many-instance-attributes
    """Builds the preset + parameter form and collects a :class:`DriverParams` from the widgets."""

    def __init__(self, config: AppConfig) -> None:
        """Build the preset selector and all download-parameter controls.

        Args:
            config: The app configuration (boost default).
        """
        self._config = config
        first_key = PRESETS[0].key

        preset_options = {preset.key: f'{preset.folder}  /  {preset.label}' for preset in PRESETS}
        self._preset = ui.select(preset_options, value=first_key, label='Preset',
                                 on_change=self._on_preset_change).props('outlined').classes('w-full')

        self._card = ui.card().classes('w-full gap-2')
        with self._card:
            _section('URL')
            self._url = ui.input('Playlist / video / token URL').props(
                'outlined stack-label dense').classes('w-full')

            ui.separator()
            _section('Mode')
            self._mode = ui.radio(_MODES, value='with-audio').props('inline')
            self._fmt = ui.select(_AUDIO_FORMATS, value='m4a', label='Audio format').props(
                'outlined dense').classes('w-72')

            ui.separator()
            _section('Metadata (single videos only)')
            self._title = ui.input('Title').props('outlined stack-label dense').classes('w-full')
            self._artist = ui.input('Artist').props('outlined stack-label dense').classes('w-full')
            self._album = ui.input('Album').props('outlined stack-label dense').classes('w-full')

            ui.separator()
            _section('Options')
            with ui.row().classes('gap-4'):
                self._subs = ui.checkbox('Subtitles')
                self._json = ui.checkbox('Write JSON')
                self._progress = ui.checkbox('Progress bar')
                self._verbose = ui.checkbox('Verbose')
                self._rerun = ui.checkbox('Re-run last URL')
            with ui.row().classes('items-center gap-2'):
                self._chapters = ui.select(_CHAPTERS, value='none', label='List chapters').props(
                    'outlined dense').classes('w-56')
                self._timeout = ui.number('Video timeout (s, 0=auto)', value=0, min=0,
                                          format='%d').props('outlined dense').classes('w-56')

            ui.separator()
            _section('Boost')
            with ui.row().classes('items-center gap-2'):
                self._boost = ui.checkbox('Boost volume')
                self._boost_vol = ui.number('factor', value=config.boost_default, min=0.1, max=10,
                                            step=0.1).props('outlined dense').classes('w-28')
                self._boost_vol.bind_visibility_from(self._boost, 'value')

            ui.separator()
            _section('Environment')
            with ui.row().classes('items-center gap-6'):
                with ui.column().classes('gap-1'):
                    ui.label('Cookies').classes('text-sm text-grey')
                    self._cookies = ui.select(_COOKIES, value='none').props('outlined dense').classes('w-40')
                with ui.column().classes('gap-1'):
                    ui.label('Notifications').classes('text-sm text-grey')
                    self._notif = ui.radio(_NOTIF, value='NO').props('inline')
            with ui.row().classes('items-center gap-2'):
                self._notif_msg = ui.input('NOTIF_MSG suffix').props(
                    'outlined stack-label dense').classes('w-72')
                self._retries = ui.number('Retries (0=default)', value=0, min=0,
                                          format='%d').props('outlined dense').classes('w-56')

        self.apply_preset(preset=PRESETS_BY_KEY[first_key])

    def apply_preset(self, preset: Preset) -> None:
        """Pre-fill every widget from a preset's default params (or hide the form for linters).

        Args:
            preset: The selected preset whose params seed the widgets.
        """
        params = preset.params
        is_driver = params.script == DRIVER_SCRIPT
        self._card.set_visibility(is_driver)
        if not is_driver:
            return
        self._url.value = params.url
        self._mode.value = params.mode
        self._fmt.value = params.audio_format
        self._title.value = params.title
        self._artist.value = params.artist
        self._album.value = params.album
        self._subs.value = params.subs
        self._json.value = params.write_json
        self._progress.value = params.progress
        self._verbose.value = params.verbose
        self._rerun.value = params.rerun
        self._chapters.value = params.list_chapters
        self._timeout.value = params.video_timeout
        self._boost.value = params.boost
        self._boost_vol.value = params.boost_volume
        self._cookies.value = params.cookies
        self._notif.value = params.notifications
        self._notif_msg.value = params.notif_msg
        self._retries.value = params.retries

    def collect(self) -> DriverParams:
        """Read the live widget values (or the fixed linter command) into a :class:`DriverParams`.

        Returns:
            DriverParams: The collected parameters for the selected preset.
        """
        preset = PRESETS_BY_KEY[str(self._preset.value)]
        if preset.params.script == LINTER_SCRIPT:
            return preset.params
        return DriverParams(
            script=DRIVER_SCRIPT,
            url=str(self._url.value).strip(),
            mode=str(self._mode.value),
            audio_format=str(self._fmt.value),
            subs=bool(self._subs.value),
            write_json=bool(self._json.value),
            progress=bool(self._progress.value),
            verbose=bool(self._verbose.value),
            rerun=bool(self._rerun.value),
            title=str(self._title.value).strip(),
            artist=str(self._artist.value).strip(),
            album=str(self._album.value).strip(),
            list_chapters=str(self._chapters.value),
            video_timeout=int(self._timeout.value or 0),
            boost=bool(self._boost.value),
            boost_volume=float(self._boost_vol.value or 0),
            cookies=str(self._cookies.value),
            notifications=str(self._notif.value),
            notif_msg=str(self._notif_msg.value).strip(),
            retries=int(self._retries.value or 0),
        )

    def _on_preset_change(self) -> None:
        """Apply the newly selected preset to the form widgets."""
        self.apply_preset(preset=PRESETS_BY_KEY[str(self._preset.value)])


def _section(title: str) -> None:
    """Render a bold section header inside the form card.

    Args:
        title: The section title text.
    """
    ui.label(title).classes('text-base font-bold')
