"""Staged measure -> prompt -> boost -> copy flow for FFMPEG_OPTS=prompt mode.

Invoked from main-yt-dlp.py after audio has been extracted to staging/staging-m4a/.
For each newly-staged m4a file:
  1. Measure its integrated LUFS + true peak.
  2. Compute a suggested boost multiplier vs. the user-supplied baseline LUFS,
     applying a clipping safeguard.
  3. Prompt the user (Enter accepts the suggestion, '1.0' means copy as-is).
  4. Print a summary table.
  5. Copy (multiplier == 1.0) or ffmpeg-re-encode (else) the staged file into
     the final yt-audio-m4a/ directory.
  6. Delete the staged source on success.
"""
import logging
import shutil
import subprocess  # nosec B404
from pathlib import Path

from funcs_for_audio_utils import (
    TARGET_PEAK_DB_DEFAULT,
    LoudnessStats,
    Suggestion,
    compute_suggestion,
    measure_lufs,
)
from project_defs import DEFAULT_AUDIO_QUALITY


logger = logging.getLogger(__name__)

TITLE_MAX_LEN: int = 64


def _truncate_title(title: str, max_len: int = TITLE_MAX_LEN) -> str:
    """Truncate to max_len chars, appending '…' when cut."""
    if len(title) <= max_len:
        return title
    return title[:max_len - 1] + '…'


def _prompt_user_for_multiplier(idx: int, total: int, title: str,
                                measured: LoudnessStats, suggestion: Suggestion) -> float:
    """Show the per-file prompt and parse the response.

    Returns the chosen multiplier. Empty input accepts the suggestion. '1.0' means no boost.
    Re-prompts on invalid input.
    """
    short_title = _truncate_title(title=title)
    print(f'\n[{idx}/{total}] {short_title}')
    print(f'      Current: {measured.integrated_lufs:.1f} LUFS, '
          f'TP={measured.true_peak_db:.1f} dBTP, '
          f'suggested boost = {suggestion.multiplier:.2f}'
          + (f'  ({suggestion.text.split("(", 1)[1].rstrip(")")})'
             if '(' in suggestion.text else ''))

    while True:
        response = input(f'      Boost (Enter = accept {suggestion.multiplier:.2f}): ').strip()
        if not response:
            return suggestion.multiplier
        try:
            value = float(response)
        except ValueError:
            print(f"      Invalid input '{response}': enter a positive number or just press Enter.")
            continue
        if value <= 0:
            print('      Boost must be > 0.')
            continue
        return value


def _apply_one(staging_file: Path, final_dir: Path, multiplier: float,
               ffmpeg_exe: str) -> Path:
    """Copy (multiplier == 1.0) or ffmpeg-boost (else) the staged m4a to final_dir.

    Returns the final output path.
    """
    final_dir.mkdir(parents=True, exist_ok=True)
    output = final_dir / staging_file.name

    if multiplier == 1.0:
        shutil.copy2(staging_file, output)
        logger.info(f"Copied '{staging_file.name}' to '{final_dir}' (no boost)")
        return output

    cmd = [
        ffmpeg_exe, '-hide_banner', '-nostats', '-y',
        '-i', str(staging_file),
        '-map', '0',
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', DEFAULT_AUDIO_QUALITY,
        '-af', f'volume={multiplier}',
        '-movflags', '+faststart',
        str(output),
    ]
    logger.debug(f'Boost command: {cmd}')
    try:
        subprocess.run(  # nosec B603
            cmd, capture_output=True, text=True,
            encoding='utf-8', errors='replace', check=True,
        )
    except subprocess.CalledProcessError as e:
        stderr_tail = (e.stderr or '')[-500:]
        raise RuntimeError(
            f"ffmpeg boost failed for '{staging_file.name}' (exit {e.returncode}): {stderr_tail}"
        ) from e
    logger.info(f"Boosted '{staging_file.name}' by volume={multiplier:.2f} -> '{final_dir}'")
    return output


def _print_summary_table(rows: list[dict]) -> None:
    """Print the suggested-vs-chosen summary table."""
    print()
    print('Summary')
    header = f'{"#":>3} | {"Title":<64} | {"LUFS":>7} | {"Suggested":>10} | {"Chosen":>6}'
    print(header)
    print('-' * len(header))
    any_capped = False
    for row in rows:
        capped_marker = '*' if row.get('capped') else ' '
        print(f'{row["idx"]:>3} | {row["title"]:<64} | {row["lufs"]:>7.1f} | '
              f'{row["suggested"]:>9.2f}{capped_marker} | {row["chosen"]:>6.2f}')
        if row.get('capped'):
            any_capped = True
    if any_capped:
        print('  * = capped from raw suggestion to keep true peak <= -0.5 dBTP')


def run_prompt_boost_flow(staging_dir: Path, final_dir: Path,
                          baseline_lufs: float, ffmpeg_exe: str,
                          target_peak_db: float = TARGET_PEAK_DB_DEFAULT,
                          new_files: list[Path] | None = None) -> None:
    """Drive the prompt mode for files in staging_dir, writing results to final_dir.

    Args:
        staging_dir: Directory containing freshly-extracted m4a files (typically
            staging/staging-m4a/).
        final_dir: Where boosted/copied output should land (typically yt-audio-m4a/).
        baseline_lufs: Pre-measured baseline integrated LUFS.
        ffmpeg_exe: Resolved ffmpeg executable path.
        target_peak_db: True-peak ceiling for the clipping safeguard.
        new_files: Subset of files in staging_dir to process. If None, processes
            every *.m4a in staging_dir (which may include stale files left over from
            other workflows -- the caller is expected to snapshot before extraction).
    """
    if new_files is None:
        candidates = sorted(staging_dir.glob('*.m4a'))
    else:
        candidates = sorted(new_files)

    if not candidates:
        logger.warning(f"No m4a files to process in '{staging_dir}'")
        return

    print(f'\nMeasuring {len(candidates)} downloaded file(s)...')

    # Phase 1: measure + suggest + prompt, one at a time.
    rows: list[dict] = []
    for idx, staged in enumerate(candidates, start=1):
        try:
            measured = measure_lufs(input_source=staged, ffmpeg_exe=ffmpeg_exe)
        except RuntimeError as e:
            logger.error(f"Skipping '{staged.name}': measurement failed: {e}")
            continue
        suggestion = compute_suggestion(measured=measured,
                                        baseline_lufs=baseline_lufs,
                                        target_peak_db=target_peak_db)
        chosen = _prompt_user_for_multiplier(idx=idx, total=len(candidates),
                                             title=staged.stem, measured=measured,
                                             suggestion=suggestion)
        rows.append({
            'idx': idx,
            'staged': staged,
            'title': _truncate_title(title=staged.stem),
            'lufs': measured.integrated_lufs,
            'suggested': suggestion.multiplier,
            'capped': '(CAPPED' in suggestion.text,
            'chosen': chosen,
        })

    if not rows:
        logger.warning('No files processed in prompt mode.')
        return

    _print_summary_table(rows=rows)

    # Phase 2: apply the chosen multipliers and clean up staging.
    print('\nApplying boost values...')
    for row in rows:
        staged: Path = row['staged']
        chosen: float = row['chosen']
        action = 'copy as-is' if chosen == 1.0 else f'volume={chosen:.2f}'
        print(f"  [{row['idx']}/{len(rows)}] {row['title']}  -> {action}  ...", end=' ', flush=True)
        try:
            _apply_one(staging_file=staged, final_dir=final_dir,
                       multiplier=chosen, ffmpeg_exe=ffmpeg_exe)
        except RuntimeError as e:
            print(f'FAILED: {e}')
            continue
        try:
            staged.unlink()
        except OSError as e:
            logger.warning(f"Could not delete staged file '{staged}': {e}")
        print('DONE')

    print(f'\nAll m4a files written to {final_dir}.')
