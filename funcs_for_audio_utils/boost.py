"""Audio volume boosting functions using ffmpeg."""
import re
import subprocess
import sys
from pathlib import Path

from funcs_for_main_yt_dlp import get_ffmpeg_path

TARGET_PEAK_DB = -0.5  # Target peak level (with safety margin to avoid clipping)


def detect_audio_levels(
        input_file: Path,
        ffmpeg_exe: str | None = None
) -> tuple[float, float]:
    """
    Detect audio levels using ffmpeg volumedetect filter.

    Args:
        input_file: Path to the input audio/video file.
        ffmpeg_exe: Path to ffmpeg executable.
            If None, auto-detected via get_ffmpeg_path().

    Returns:
        tuple: (mean_volume_db, max_volume_db)

    Raises:
        RuntimeError: If unable to detect audio levels.
    """
    if ffmpeg_exe is None:
        ffmpeg_exe = get_ffmpeg_path()

    cmd = [
        ffmpeg_exe,
        '-i', str(input_file),
        '-af', 'volumedetect',
        '-f', 'null',
        '/dev/null' if sys.platform != 'win32' else 'NUL'
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f'Error running ffmpeg: {e}')

    output = result.stderr

    # Parse mean_volume and max_volume from output
    mean_match = re.search(r'mean_volume:\s*([-\d.]+)\s*dB', output)
    max_match = re.search(r'max_volume:\s*([-\d.]+)\s*dB', output)

    if not mean_match or not max_match:
        raise RuntimeError('Failed to parse volume information')

    mean_volume = float(mean_match.group(1))
    max_volume = float(max_match.group(1))

    return mean_volume, max_volume


def calculate_boost_value(max_volume_db: float, target_db: float = TARGET_PEAK_DB) -> float:
    """
    Calculate the boost value needed to reach target peak level.

    Args:
        max_volume_db: Current maximum volume in dB.
        target_db: Target peak level in dB (default: TARGET_PEAK_DB).

    Returns:
        float: Linear gain multiplier needed.
    """
    # Calculate the dB difference
    gain_db = target_db - max_volume_db

    # Convert dB to linear gain: gain = 10^(dB/20)
    linear_gain = 10 ** (gain_db / 20)

    return linear_gain


class AudioBooster:
    """Audio volume booster using ffmpeg."""

    def __init__(self, ffmpeg_exe: str | None = None,
                 preserve_video: bool = False) -> None:
        """
        Initialize the audio booster.

        Args:
            ffmpeg_exe: Path to ffmpeg executable.
                If None, auto-detected via get_ffmpeg_path().
            preserve_video: If True, copy video stream
                without re-encoding (for MP4/M4A with cover art).
        """
        if ffmpeg_exe is None:
            ffmpeg_exe = get_ffmpeg_path()
        self.ffmpeg_exe = ffmpeg_exe
        self.preserve_video = preserve_video

    def _build_ffmpeg_command(self, input_file: Path, output_file: Path,
                              use_loudnorm: bool, boost_value: float) -> list[str]:
        """
        Build the ffmpeg command.

        Args:
            input_file: Path to the input file.
            output_file: Path to the output file.
            use_loudnorm: Whether to use loudnorm filter.
            boost_value: Volume multiplier value.

        Returns:
            list: ffmpeg command as list of strings.
        """
        if use_loudnorm:
            audio_filter = 'loudnorm=I=-16:TP=-1.5:LRA=11'
        else:
            audio_filter = f'volume={boost_value}'

        cmd = [
            self.ffmpeg_exe,
            '-y',
            '-i', str(input_file),
            '-af', audio_filter,
        ]

        if self.preserve_video:
            cmd.extend(['-c:v', 'copy'])

        cmd.append(str(output_file))
        return cmd

    def boost_volume(self, input_file: Path, use_loudnorm: bool = False,
                     boost_value: float = 3.0) -> Path:
        """
        Boost audio volume using ffmpeg loudnorm filter or volume multiplier.

        Args:
            input_file: Path to the input file.
            use_loudnorm: If True, use loudnorm filter. If False, use volume multiplier.
            boost_value: Volume multiplier value (only used when use_loudnorm is False).

        Returns:
            Path: Path to the output file with boosted volume.

        Raises:
            subprocess.CalledProcessError: If ffmpeg command fails.
            FileNotFoundError: If input file does not exist.
        """
        if not input_file.exists():
            raise FileNotFoundError(f'Input file {input_file!r} does not exist')

        # Create output filename with '-boost' suffix
        output_file = input_file.parent / f'{input_file.stem}-boost{input_file.suffix}'

        # Build ffmpeg command
        cmd = self._build_ffmpeg_command(
            input_file=input_file,
            output_file=output_file,
            use_loudnorm=use_loudnorm,
            boost_value=boost_value
        )

        print(f'Running ffmpeg command: {cmd}')
        print(f'Input: {input_file}')
        print(f'Output: {output_file}')
        print(f'Mode: {"loudnorm" if use_loudnorm else f"volume boost ({boost_value}x)"}')

        try:
            subprocess.run(cmd, check=True)
            print(f'Successfully created {output_file}')
            return output_file
        except subprocess.CalledProcessError as e:
            print(f'Error running ffmpeg: {e}')
            raise
