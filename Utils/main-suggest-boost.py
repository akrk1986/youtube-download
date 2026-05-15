#!/usr/bin/env python3
"""Suggest an FFMPEG_OPTS volume= factor by comparing a URL's loudness to a baseline file.

Measures integrated loudness (EBU R128) via ffmpeg's ebur128 filter.

- Cases 1 & 2 (single YouTube video, with or without chapters) and any non-YouTube URL
  (ertflix, facebook, ...): prints a 3-line baseline / measured / suggestion block.
- Case 3 (YouTube playlist): iterates entries and prints one table row per entry as soon
  as each measurement completes. The baseline is measured exactly once per invocation.

If the target is already at/above the baseline, the suggestion is the literal 'no boost'.
"""
import argparse
import logging
import re
import subprocess  # nosec B404
import sys
from dataclasses import dataclass
from pathlib import Path

# Allow imports of project packages when this script is invoked directly from Utils/.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# pylint: disable=wrong-import-position
from funcs_for_main_yt_dlp import get_ffmpeg_path, get_ytdlp_path  # noqa: E402
from funcs_video_info import get_playlist_entries, is_playlist  # noqa: E402


logger = logging.getLogger(__name__)

TARGET_PEAK_DB_DEFAULT: float = -0.5
TITLE_MAX_LEN: int = 64


@dataclass
class LoudnessStats:
    """Loudness measurement from ebur128: integrated LUFS + true peak in dBFS."""
    integrated_lufs: float
    true_peak_db: float


@dataclass
class Suggestion:
    """A computed boost suggestion for one source."""
    gain_db: float
    capped_gain_db: float
    multiplier: float
    text: str


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


def measure_lufs(input_source: str, ffmpeg_exe: str) -> LoudnessStats:
    """Run ffmpeg ebur128 on a file path or URL and return loudness stats."""
    cmd = [
        ffmpeg_exe, '-hide_banner', '-nostats',
        '-i', input_source, '-vn',
        '-af', 'ebur128=peak=true',
        '-f', 'null', '-',
    ]
    logger.debug(f'Measuring loudness: {cmd}')
    try:
        # encoding='utf-8' + errors='replace' is required on Windows: the default cp1252
        # decoder dies in subprocess's reader thread when ffmpeg prints UTF-8 metadata
        # (e.g. Greek tags) -> result.stderr ends up None.
        result = subprocess.run(  # nosec B603
            cmd, capture_output=True, text=True,
            encoding='utf-8', errors='replace', check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f"ffmpeg failed to launch for '{input_source}': {e}") from e

    if result.returncode != 0:
        tail = result.stderr[-500:] if result.stderr else '<no stderr>'
        raise RuntimeError(
            f"ffmpeg ebur128 exited with code {result.returncode} for '{input_source}': {tail}"
        )
    return _parse_ebur128(stderr_text=result.stderr)


def resolve_url_to_media(url: str, ytdlp_exe: str) -> str:
    """yt-dlp -g -f bestaudio URL -> direct audio CDN/manifest URL (first line if multiple)."""
    cmd = [ytdlp_exe, '--no-warnings', '-g', '-f', 'bestaudio/best', url]
    logger.debug(f'Resolving URL: {cmd}')
    try:
        result = subprocess.run(  # nosec B603
            cmd, capture_output=True, text=True,
            encoding='utf-8', errors='replace', check=True,
        )
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or '').strip()
        raise RuntimeError(f"yt-dlp could not resolve '{url}': {stderr or e}") from e
    lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError(f"yt-dlp returned no media URL for '{url}'")
    return lines[0]


def compute_suggestion(measured: LoudnessStats, baseline_lufs: float,
                       target_peak_db: float = TARGET_PEAK_DB_DEFAULT) -> Suggestion:
    """Compute the boost factor that lifts measured -> baseline, applying clipping cap."""
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


def _truncate_title(title: str, max_len: int = TITLE_MAX_LEN) -> str:
    """Truncate title to max_len chars, appending an ellipsis if it was cut."""
    if len(title) <= max_len:
        return title
    return title[:max_len - 1] + '…'


def _format_suggestion_line(gain_db: float, text: str) -> str:
    """Format the 'Gain needed' single-video output line."""
    if text == 'no boost':
        return f'Gain needed: {gain_db:+.1f} dB   ->   no boost'
    return f"Gain needed: +{gain_db:.1f} dB   ->   FFMPEG_OPTS='{text}'"


def _process_single(url: str, baseline_stats: LoudnessStats,
                    ffmpeg_exe: str, ytdlp_exe: str,
                    target_peak_db: float) -> None:
    """Measure one URL, print a 3-line baseline / video / suggestion block."""
    try:
        media_url = resolve_url_to_media(url=url, ytdlp_exe=ytdlp_exe)
        measured = measure_lufs(input_source=media_url, ffmpeg_exe=ffmpeg_exe)
    except RuntimeError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)

    print(f"Video    '{url}':     I={measured.integrated_lufs:.1f} LUFS, "
          f'TP={measured.true_peak_db:.1f} dBTP')
    suggestion = compute_suggestion(measured=measured,
                                    baseline_lufs=baseline_stats.integrated_lufs,
                                    target_peak_db=target_peak_db)
    print(_format_suggestion_line(gain_db=suggestion.gain_db, text=suggestion.text))


def _process_playlist(url: str, baseline_stats: LoudnessStats,
                      ffmpeg_exe: str, ytdlp_exe: str,
                      target_peak_db: float) -> None:
    """Iterate playlist entries, measure each, print a streaming table row per entry."""
    try:
        entries = get_playlist_entries(url=url)
    except RuntimeError as e:
        print(f'ERROR enumerating playlist: {e}', file=sys.stderr)
        sys.exit(1)

    header = f'{"#":>3} | {"Title":<64} | {"LUFS":>7} | Suggestion'
    print(header)
    print('-' * len(header))

    for idx, (title, entry_url) in enumerate(entries, start=1):
        short_title = _truncate_title(title=title)
        try:
            media_url = resolve_url_to_media(url=entry_url, ytdlp_exe=ytdlp_exe)
            measured = measure_lufs(input_source=media_url, ffmpeg_exe=ffmpeg_exe)
        except RuntimeError as e:
            logger.debug(f"Failed to measure entry {idx} ({entry_url}): {e}")
            print(f'{idx:>3} | {short_title:<64} | {"ERROR":>7} | -')
            continue
        suggestion = compute_suggestion(measured=measured,
                                        baseline_lufs=baseline_stats.integrated_lufs,
                                        target_peak_db=target_peak_db)
        print(f'{idx:>3} | {short_title:<64} | {measured.integrated_lufs:>7.1f} | '
              f'{suggestion.text}')


def main() -> None:
    """Entry point: parse args, measure baseline once, dispatch by URL type."""
    parser = argparse.ArgumentParser(
        description=("Measure a URL's loudness via EBU R128 and suggest an FFMPEG_OPTS "
                     "volume= factor that matches a baseline file."))
    parser.add_argument('url',
                        help='YouTube/Facebook/ERTFlix URL (single video or YouTube playlist)')
    parser.add_argument('--baseline', required=True, type=Path,
                        help='Local audio/video file whose loudness the suggested boost should target')
    parser.add_argument('--target-peak-db', type=float, default=TARGET_PEAK_DB_DEFAULT,
                        help='True-peak ceiling for the clipping safeguard (default: %(default)s)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable DEBUG logging to stderr')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING,
                        format='%(levelname)s %(message)s')

    if not args.baseline.is_file():
        print(f"baseline file does not exist: '{args.baseline}'", file=sys.stderr)
        sys.exit(1)

    ffmpeg_exe = get_ffmpeg_path()
    ytdlp_exe = get_ytdlp_path()

    try:
        baseline_stats = measure_lufs(input_source=str(args.baseline), ffmpeg_exe=ffmpeg_exe)
    except RuntimeError as e:
        print(f'ERROR measuring baseline: {e}', file=sys.stderr)
        sys.exit(1)

    print(f"Baseline '{args.baseline.name}': I={baseline_stats.integrated_lufs:.1f} LUFS, "
          f'TP={baseline_stats.true_peak_db:.1f} dBTP')

    if is_playlist(url=args.url):
        _process_playlist(url=args.url, baseline_stats=baseline_stats,
                          ffmpeg_exe=ffmpeg_exe, ytdlp_exe=ytdlp_exe,
                          target_peak_db=args.target_peak_db)
    else:
        _process_single(url=args.url, baseline_stats=baseline_stats,
                        ffmpeg_exe=ffmpeg_exe, ytdlp_exe=ytdlp_exe,
                        target_peak_db=args.target_peak_db)


if __name__ == '__main__':
    main()
