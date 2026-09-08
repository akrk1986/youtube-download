"""Regression tests for custom-metadata / faststart ffmpeg postprocessor-args merging.

yt-dlp keeps only the *last* ``--postprocessor-args`` for a given postprocessor key, so emitting a
separate ``ffmpeg:-movflags +faststart`` for M4A used to silently drop the custom artist/album
(``ffmpeg:-metadata …``) — the tags landed in the MP4 but not the M4A. `_append_common_flags` now
merges everything into a single ``ffmpeg:`` entry; these tests guard that.
"""

import re
from pathlib import Path

from funcs_for_main_yt_dlp._download_common import DownloadOptions, _append_common_flags
from project_defs import ENGAGEMENT_PREFIX_PATTERN


def test_m4a_faststart_merges_with_custom_metadata() -> None:
    """For M4A, faststart and custom artist/album share ONE ffmpeg pp-args entry (no overwrite)."""
    opts = DownloadOptions(ytdlp_exe='yt-dlp', url='U', is_it_playlist=False,
                           custom_artist='Some Artist', custom_album='My Album')
    cmd: list[str | Path] = [Path('yt-dlp'), 'U']
    _append_common_flags(cmd=cmd, opts=opts, extra_ffmpeg_args=['-movflags', '+faststart'])
    assert cmd.count('--postprocessor-args') == 1
    value = cmd[cmd.index('--postprocessor-args') + 1]
    assert value == ('ffmpeg:-metadata artist="Some Artist" -metadata album="My Album" '
                     '-movflags +faststart')


def test_metadata_only_without_extra_args() -> None:
    """Without extra args (the MP4/video path), the ffmpeg pp-args holds just the custom metadata."""
    opts = DownloadOptions(ytdlp_exe='yt-dlp', url='U', is_it_playlist=False,
                           custom_artist='A', custom_album='B')
    cmd: list[str | Path] = [Path('yt-dlp'), 'U']
    _append_common_flags(cmd=cmd, opts=opts)
    value = cmd[cmd.index('--postprocessor-args') + 1]
    assert value == 'ffmpeg:-metadata artist=A -metadata album=B'


def test_faststart_only_when_no_custom_metadata() -> None:
    """M4A with no custom metadata still gets a faststart-only ffmpeg pp-args entry."""
    opts = DownloadOptions(ytdlp_exe='yt-dlp', url='U', is_it_playlist=False)
    cmd: list[str | Path] = [Path('yt-dlp'), 'U']
    _append_common_flags(cmd=cmd, opts=opts, extra_ffmpeg_args=['-movflags', '+faststart'])
    assert cmd[cmd.index('--postprocessor-args') + 1] == 'ffmpeg:-movflags +faststart'


def test_no_pp_args_without_metadata_or_extras() -> None:
    """A plain video-only command (no custom metadata, no extras) has no ffmpeg pp-args at all."""
    opts = DownloadOptions(ytdlp_exe='yt-dlp', url='U', is_it_playlist=False)
    cmd: list[str | Path] = [Path('yt-dlp'), 'U']
    _append_common_flags(cmd=cmd, opts=opts)
    assert '--postprocessor-args' not in cmd


def test_engagement_prefix_rule_present_without_custom_title() -> None:
    """With no custom title, the title tag gets the Facebook engagement-prefix strip rule."""
    opts = DownloadOptions(ytdlp_exe='yt-dlp', url='U', is_it_playlist=False)
    cmd: list[str | Path] = [Path('yt-dlp'), 'U']
    _append_common_flags(cmd=cmd, opts=opts)
    index = cmd.index('--replace-in-metadata')
    assert cmd[index:index + 4] == ['--replace-in-metadata', 'title', ENGAGEMENT_PREFIX_PATTERN, '']


def test_engagement_prefix_rule_present_for_audio_path() -> None:
    """The rule is not coupled to the video path: the M4A call (extra ffmpeg args) gets it too."""
    opts = DownloadOptions(ytdlp_exe='yt-dlp', url='U', is_it_playlist=False)
    cmd: list[str | Path] = [Path('yt-dlp'), 'U']
    _append_common_flags(cmd=cmd, opts=opts, extra_ffmpeg_args=['-movflags', '+faststart'])
    assert ENGAGEMENT_PREFIX_PATTERN in cmd


def test_custom_title_suppresses_engagement_rule() -> None:
    """A custom title emits only the '.+' overwrite -- the prefix rule would be a no-op there."""
    opts = DownloadOptions(ytdlp_exe='yt-dlp', url='U', is_it_playlist=False, custom_title='My Song')
    cmd: list[str | Path] = [Path('yt-dlp'), 'U']
    _append_common_flags(cmd=cmd, opts=opts, sanitized_title='My Song')
    assert cmd.count('--replace-in-metadata') == 1
    index = cmd.index('--replace-in-metadata')
    assert cmd[index:index + 4] == ['--replace-in-metadata', 'title', '.+', 'My Song']


def test_engagement_rule_present_for_playlists() -> None:
    """Playlists name files from %(title)s, which yt-dlp resolves after this pre_process rule."""
    opts = DownloadOptions(ytdlp_exe='yt-dlp', url='U', is_it_playlist=True)
    cmd: list[str | Path] = [Path('yt-dlp'), 'U']
    _append_common_flags(cmd=cmd, opts=opts)
    assert ENGAGEMENT_PREFIX_PATTERN in cmd


def test_engagement_pattern_compiles() -> None:
    """The pattern must be a valid regex -- yt-dlp would otherwise fail at download start."""
    re.compile(ENGAGEMENT_PREFIX_PATTERN)
