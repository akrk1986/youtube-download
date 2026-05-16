"""EBU R128 loudness measurement + boost-suggestion helpers.

Single source of truth used by both `Utils/main-suggest-boost.py` (network-stream
diagnostic) and `funcs_for_main_yt_dlp/prompt_boost.py` (FFMPEG_OPTS=prompt staged flow).
"""
import logging
import re
import subprocess  # nosec B404
from dataclasses import dataclass
from pathlib import Path


logger = logging.getLogger(__name__)

TARGET_PEAK_DB_DEFAULT: float = -0.5


@dataclass
class LoudnessStats:
    """ebur128 measurement: integrated LUFS + true peak in dBFS."""
    integrated_lufs: float
    true_peak_db: float


@dataclass
class Suggestion:
    """Boost suggestion derived from a measured stat vs. a baseline LUFS."""
    gain_db: float
    capped_gain_db: float
    multiplier: float
    text: str  # 'volume=N', 'volume=N (CAPPED ...)', or 'no boost'


def _parse_ebur128(stderr_text: str) -> LoudnessStats:
    """Extract integrated LUFS + true peak from the final ebur128 Summary block."""
    summary_idx = stderr_text.rfind('Summary:')
    if summary_idx == -1:
        raise RuntimeError('ffmpeg ebur128 produced no Summary block')
    summary = stderr_text[summary_idx:]

    i_match = re.search(r'I:\s+(-?\d+(?:\.\d+)?)\s+LUFS', summary)
    peak_match = re.search(r'Peak:\s+(-?\d+(?:\.\d+)?)\s+dBFS', summary)
    if not i_match or not peak_match:
        raise RuntimeError(f'Failed to parse ebur128 summary block: {summary[:200]!r}')

    return LoudnessStats(
        integrated_lufs=float(i_match.group(1)),
        true_peak_db=float(peak_match.group(1)),
    )


def measure_lufs(input_source: str | Path, ffmpeg_exe: str) -> LoudnessStats:
    """Run ffmpeg ebur128 on a file path or URL and return loudness stats."""
    source_str = str(input_source)
    cmd = [
        ffmpeg_exe, '-hide_banner', '-nostats',
        '-i', source_str, '-vn',
        '-af', 'ebur128=peak=true',
        '-f', 'null', '-',
    ]
    logger.debug(f'Measuring loudness: {cmd}')
    try:
        # encoding='utf-8' + errors='replace' required on Windows where the default
        # cp1252 decoder dies on UTF-8 metadata (e.g. Greek tags) and leaves
        # result.stderr as None.
        result = subprocess.run(  # nosec B603
            cmd, capture_output=True, text=True,
            encoding='utf-8', errors='replace', check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f"ffmpeg failed to launch for '{source_str}': {e}") from e

    if result.returncode != 0:
        tail = result.stderr[-500:] if result.stderr else '<no stderr>'
        raise RuntimeError(
            f"ffmpeg ebur128 exited with code {result.returncode} for '{source_str}': {tail}"
        )
    return _parse_ebur128(stderr_text=result.stderr)


def compute_suggestion(measured: LoudnessStats, baseline_lufs: float,
                       target_peak_db: float = TARGET_PEAK_DB_DEFAULT) -> Suggestion:
    """Compute the boost factor that lifts measured -> baseline, applying clipping cap.

    Returns 'no boost' (multiplier 1.0) when gain_db <= 0. Caps the gain to keep the
    predicted true peak at or below target_peak_db.
    """
    gain_db = baseline_lufs - measured.integrated_lufs
    if gain_db <= 0:
        return Suggestion(gain_db=gain_db, capped_gain_db=0.0,
                          multiplier=1.0, text='no boost')

    predicted_peak = measured.true_peak_db + gain_db
    if predicted_peak > target_peak_db:
        capped_gain = max(target_peak_db - measured.true_peak_db, 0.0)
        multiplier = 10 ** (capped_gain / 20)
        text = (f'volume={multiplier:.2f} '
                f'(CAPPED from +{gain_db:.1f} to +{capped_gain:.1f} dB)')
        return Suggestion(gain_db=gain_db, capped_gain_db=capped_gain,
                          multiplier=multiplier, text=text)

    multiplier = 10 ** (gain_db / 20)
    return Suggestion(gain_db=gain_db, capped_gain_db=gain_db,
                      multiplier=multiplier, text=f'volume={multiplier:.2f}')
