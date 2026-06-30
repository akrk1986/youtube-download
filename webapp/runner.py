"""Driver invocation for the web app (UI-free).

Turns a validated :class:`DriverParams` into the target script's ``argv`` plus the
environment-variable overrides (boost / cookies / notifications / retries), and runs it via
``asyncio.create_subprocess_exec`` — an argument list, never a shell — so the live output can be
streamed line by line. Two target scripts are supported: ``main-yt-dlp.py`` (the download driver)
and ``run-linters.py`` (the linter presets).
"""

import asyncio
import os
import sys
from asyncio.subprocess import Process
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

DRIVER_SCRIPT: str = 'main-yt-dlp.py'
LINTER_SCRIPT: str = 'run-linters.py'


@dataclass(frozen=True)
class DriverParams:  # pylint: disable=too-many-instance-attributes
    """Every form value, framework-agnostic. The runner alone routes each to argv or env."""

    script: str
    # Download fields (used only when script == DRIVER_SCRIPT):
    url: str = ''
    mode: str = 'video-only'  # 'with-audio' | 'only-audio' | 'ertflix-program' | 'video-only'
    audio_format: str = 'm4a'
    subs: bool = False
    write_json: bool = False
    progress: bool = False
    verbose: bool = False
    rerun: bool = False
    title: str = ''
    artist: str = ''
    album: str = ''
    list_chapters: str = 'none'  # 'none' | 'json' | 'manual'
    video_timeout: int = 0  # 0 = unset
    boost: bool = False
    boost_volume: float = 2.0
    cookies: str = 'none'  # 'none' | 'firefox' | 'chrome'
    notifications: str = 'NO'  # 'NO' | 'S' | 'G' | 'ALL'
    notif_msg: str = ''
    retries: int = 0  # 0 = unset
    # Linter field (used only when script == LINTER_SCRIPT):
    extra_argv: tuple[str, ...] = field(default_factory=tuple)


def build_command(params: DriverParams, repo_root: Path) -> tuple[list[str], dict[str, str]]:
    """Build the target-script argv and the environment overrides from the form values.

    Args:
        params: The collected form values.
        repo_root: Repository root holding the driver and linter scripts.

    Returns:
        tuple[list[str], dict[str, str]]: The argv list and the extra environment variables.
    """
    argv = [sys.executable, str(repo_root / params.script)]
    if params.script == LINTER_SCRIPT:
        return argv + list(params.extra_argv), {}
    return argv + _download_argv(params=params), _download_env(params=params)


def _download_argv(params: DriverParams) -> list[str]:
    """Build the ``main-yt-dlp.py`` flag list (and trailing URL) from the form values.

    Args:
        params: The collected download form values.

    Returns:
        list[str]: The download flags, with the positional URL last when present.
    """
    argv: list[str] = []
    mode_flag = {'with-audio': '--with-audio', 'only-audio': '--only-audio',
                 'ertflix-program': '--ertflix-program'}.get(params.mode)
    if mode_flag:
        argv.append(mode_flag)
    if params.mode in ('with-audio', 'only-audio'):
        argv += ['--audio-format', params.audio_format]
    for flag, enabled in (('--subs', params.subs), ('--json', params.write_json),
                          ('--progress', params.progress), ('--verbose', params.verbose),
                          ('--rerun', params.rerun)):
        if enabled:
            argv.append(flag)
    for flag, value in (('--title', params.title), ('--artist', params.artist),
                        ('--album', params.album)):
        if value:
            argv += [flag, value]
    if params.list_chapters != 'none':
        argv += ['--list-chapters', params.list_chapters]
    if params.video_timeout:
        argv += ['--video-download-timeout', str(params.video_timeout)]
    if params.url:
        argv.append(params.url)
    return argv


def _download_env(params: DriverParams) -> dict[str, str]:
    """Build the environment overrides for a ``main-yt-dlp.py`` run.

    Args:
        params: The collected download form values.

    Returns:
        dict[str, str]: The env vars to layer onto the process environment.
    """
    # LINTER_GATE=off so the driver's freshness-gate prompt can't block the stdin=DEVNULL subprocess.
    env: dict[str, str] = {'LINTER_GATE': 'off'}
    if params.boost:
        env['FFMPEG_OPTS'] = f'volume={params.boost_volume}'
    if params.cookies != 'none':
        env['YTDLP_USE_COOKIES'] = params.cookies
    if params.notifications != 'NO':
        env['NOTIFICATIONS'] = params.notifications
    if params.notif_msg:
        env['NOTIF_MSG'] = params.notif_msg
    if params.retries:
        env['YTDLP_RETRIES'] = str(params.retries)
    return env


class DriverProcess:
    """A single running subprocess whose merged output can be streamed and cancelled."""

    def __init__(self, argv: list[str], env_overrides: dict[str, str], cwd: Path) -> None:
        """Capture the command, env overrides and working directory for a later start.

        Args:
            argv: The command (interpreter + script + flags).
            env_overrides: Extra environment variables layered onto the current environment.
            cwd: Working directory (repo root) so the script's imports resolve.
        """
        self._argv = argv
        self._cwd = cwd
        self._env = {**os.environ, 'PYTHONUNBUFFERED': '1', **env_overrides}
        self._proc: Process | None = None

    async def stream(self) -> AsyncIterator[str]:
        """Start the process and yield its merged stdout/stderr line by line.

        Decodes as UTF-8 with ``errors='replace'`` so non-Latin filenames/tags never crash the
        reader. ``stdin`` is closed so any interactive prompt never blocks.

        Yields:
            str: One output line (without the trailing newline).
        """
        self._proc = await asyncio.create_subprocess_exec(
            *self._argv,
            cwd=str(self._cwd),
            env=self._env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert self._proc.stdout is not None
        while True:
            raw = await self._proc.stdout.readline()
            if not raw:
                break
            yield raw.decode('utf-8', errors='replace').rstrip('\n')

    async def wait(self) -> int:
        """Wait for the process to finish and return its exit code.

        Returns:
            int: The process exit code (-1 if it was never started).
        """
        if self._proc is None:
            return -1
        return await self._proc.wait()

    def cancel(self) -> None:
        """Terminate the running process if it has not already exited."""
        if self._proc is not None and self._proc.returncode is None:
            self._proc.terminate()
