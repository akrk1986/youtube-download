"""Dolby Vision profile-5 detection for downloaded video content.

DoVi profile 5 cannot be played by Plex on some devices, so such files are
flagged as "bad". Detection uses ffprobe to read the DOVI configuration record
side-data of each video stream.
"""
import json
import subprocess  # nosec B404
import sys
from pathlib import Path

from common_av.ffmpeg import get_ffmpeg_paths

VIDEO_EXTENSIONS: frozenset[str] = frozenset({'.mp4', '.mkv', '.m4v', '.mov', '.ts', '.webm'})
PROBE_TIMEOUT_SECONDS: int = 30
BAD_DOVI_PROFILE: int = 5


def _get_ffprobe_path() -> str:
    """Return the path to the ffprobe executable (Windows or Linux/WSL/macOS).

    Returns:
        str: Path to ffprobe.
    """
    return get_ffmpeg_paths()[1]


def _video_dovi_profile(file_path: Path) -> int | None:
    """Return the Dolby Vision profile of a file's first DoVi video stream.

    Args:
        file_path: Path to the video file to probe.

    Returns:
        int | None: The dv_profile value, or None when the file has no DoVi
            side-data (or no video stream).
    """
    ffprobe = _get_ffprobe_path()
    result = subprocess.run(  # nosec B603
        [ffprobe, '-v', 'quiet', '-print_format', 'json', '-show_streams', str(file_path)],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=PROBE_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        return None

    data = json.loads(result.stdout)
    for stream in data.get('streams', []):
        if stream.get('codec_type') != 'video':
            continue
        for side_data in stream.get('side_data_list', []):
            profile = side_data.get('dv_profile')
            if profile is not None:
                return int(profile)
    return None


def file_is_dovi_profile5(file_path: Path) -> bool:
    """Return True if the video file is Dolby Vision profile 5.

    Args:
        file_path: Path to the video file.

    Returns:
        bool: True iff the file's DoVi profile is 5.
    """
    return _video_dovi_profile(file_path=file_path) == BAD_DOVI_PROFILE


def path_is_bad(path: Path) -> bool:
    """Return True if the path is (or contains) a DoVi profile-5 video file.

    When path is a file it is probed directly; when it is a directory it is
    scanned recursively and the result is True if any video file is profile 5.
    Probe failures are treated as good (False) so a glitch never raises a false
    alarm or blocks the notification hook.

    Args:
        path: A video file or a directory containing video files.

    Returns:
        bool: True if any examined video file is DoVi profile 5.
    """
    if path.is_file():
        candidates = [path]
    else:
        candidates = sorted(p for p in path.rglob('*')
                            if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS)

    for candidate in candidates:
        try:
            if file_is_dovi_profile5(file_path=candidate):
                return True
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            print(f'Warning: could not probe {candidate}: {exc}', file=sys.stderr)
    return False
