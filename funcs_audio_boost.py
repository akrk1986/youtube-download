"""Audio volume boosting functions using ffmpeg."""
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path

from funcs_for_main_yt_dlp import get_ffmpeg_path


FFMPEG_EXE = get_ffmpeg_path()
TARGET_PEAK_DB = -0.5  # Target peak level (with safety margin to avoid clipping)


def detect_audio_levels(input_file: Path) -> tuple[float, float]:
    """
    Detect audio levels using ffmpeg volumedetect filter.

    Args:
        input_file: Path to the input audio/video file.

    Returns:
        tuple: (mean_volume_db, max_volume_db)

    Raises:
        RuntimeError: If unable to detect audio levels.
    """
    cmd = [
        FFMPEG_EXE,
        '-i', str(input_file),
        '-af', 'volumedetect',
        '-f', 'null',
        '/dev/null' if sys.platform != 'win32' else 'NUL'
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stderr

        # Parse mean_volume and max_volume from output
        mean_match = re.search(r'mean_volume:\s*([-\d.]+)\s*dB', output)
        max_match = re.search(r'max_volume:\s*([-\d.]+)\s*dB', output)

        if not mean_match or not max_match:
            raise RuntimeError('Failed to parse volume information')

        mean_volume = float(mean_match.group(1))
        max_volume = float(max_match.group(1))

        return mean_volume, max_volume

    except Exception as e:
        raise RuntimeError(f'Error detecting audio levels: {e}')


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


class AudioBooster(ABC):
    """Abstract base class for audio volume boosting."""

    def __init__(self, ffmpeg_exe: str = FFMPEG_EXE):
        """
        Initialize the audio booster.

        Args:
            ffmpeg_exe: Path to ffmpeg executable.
        """
        self.ffmpeg_exe = ffmpeg_exe

    @abstractmethod
    def _build_ffmpeg_command(self, input_file: Path, output_file: Path,
                              use_loudnorm: bool, boost_value: float) -> list[str]:
        """
        Build the ffmpeg command for this audio format.

        Args:
            input_file: Path to the input file.
            output_file: Path to the output file.
            use_loudnorm: Whether to use loudnorm filter.
            boost_value: Volume multiplier value.

        Returns:
            list: ffmpeg command as list of strings.
        """
        pass

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


class MP3Booster(AudioBooster):
    """Audio booster for MP3 files."""

    def _build_ffmpeg_command(self, input_file: Path, output_file: Path,
                              use_loudnorm: bool, boost_value: float) -> list[str]:
        """Build the ffmpeg command for MP3 files."""
        # Build audio filter based on mode
        if use_loudnorm:
            audio_filter = 'loudnorm=I=-16:TP=-1.5:LRA=11'
        else:
            audio_filter = f'volume={boost_value}'

        cmd = [
            self.ffmpeg_exe,
            '-y',
            '-i', str(input_file),
            '-af', audio_filter,
            str(output_file)
        ]

        return cmd


class MP4Booster(AudioBooster):
    """Audio booster for MP4/M4A files."""

    def _build_ffmpeg_command(self, input_file: Path, output_file: Path,
                              use_loudnorm: bool, boost_value: float) -> list[str]:
        """Build the ffmpeg command for MP4/M4A files."""
        # Build audio filter based on mode
        if use_loudnorm:
            audio_filter = 'loudnorm=I=-16:TP=-1.5:LRA=11'
        else:
            audio_filter = f'volume={boost_value}'

        cmd = [
            self.ffmpeg_exe,
            '-y',
            '-i', str(input_file),
            '-af', audio_filter,
            '-c:v', 'copy',  # Copy video stream without re-encoding
            str(output_file)
        ]

        return cmd
