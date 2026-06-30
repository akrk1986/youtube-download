"""Regression tests for custom-metadata / faststart ffmpeg postprocessor-args merging.

yt-dlp keeps only the *last* ``--postprocessor-args`` for a given postprocessor key, so emitting a
separate ``ffmpeg:-movflags +faststart`` for M4A used to silently drop the custom artist/album
(``ffmpeg:-metadata …``) — the tags landed in the MP4 but not the M4A. `_append_common_flags` now
merges everything into a single ``ffmpeg:`` entry; these tests guard that.
"""

from pathlib import Path

from funcs_for_main_yt_dlp._download_common import DownloadOptions, _append_common_flags


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
