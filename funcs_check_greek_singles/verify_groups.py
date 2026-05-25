"""Verify that each Staging-Dupes/grp-NNNN folder holds exactly one song.

After a staging run every grp-NNNN subfolder should hold the copies of a single
song -- all files sharing one normalized (title, artist) key, just gathered from
different months/folders. This module re-reads the staged files' tags from disk
(via the same audio_reader the staging used), so a post-run rearrangement that
mixed different songs into one folder is detected even though the run DB would not
reflect it. The thin CLI wrapper lives in Utils/main-verify-dupe-groups.py.
"""
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from funcs_check_greek_singles.audio_reader import collect_songs
from funcs_check_greek_singles.models import Song, SongKey

# Per-folder verification outcomes (see classify_group).
STATUS_OK = 'ok'                  # >=2 files, all one (title, artist) key
STATUS_MISGROUPED = 'misgrouped'  # >=2 distinct keys -> different songs together
STATUS_UNTAGGED = 'untagged'      # a file missing title/artist -> can't verify
STATUS_SINGLETON = 'singleton'    # exactly 1 file (a group should have >=2)
STATUS_EMPTY = 'empty'            # no audio files

# grp-NNNN subfolder name (mirrors file_actions._GROUP_DIR_RE).
_GROUP_DIR_RE = re.compile(r'grp-(\d+)$')

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GroupReport:
    """Verification result for one grp-NNNN staging folder."""
    name: str
    status: str
    songs: tuple[Song, ...]

    @property
    def distinct_keys(self) -> tuple[SongKey, ...]:
        """The distinct non-None song keys in the folder, title/artist-sorted."""
        keys = {song.key for song in self.songs if song.key is not None}
        return tuple(sorted(keys, key=lambda key: (key.title, key.artist)))

    @property
    def is_ok(self) -> bool:
        """True iff the folder holds exactly one song (status OK)."""
        return self.status == STATUS_OK


def classify_group(name: str, songs: list[Song]) -> GroupReport:
    """Classify one group folder's songs into a GroupReport.

    Precedence: empty -> misgrouped (>=2 distinct keys) -> untagged (any song
    without a key) -> singleton (exactly one file) -> ok.

    Args:
        name: The group folder name (e.g. 'grp-0007').
        songs: The Songs parsed from the folder, in any order.

    Returns:
        GroupReport: The folder's status and its songs.
    """
    ordered = tuple(songs)
    distinct = {song.key for song in ordered if song.key is not None}
    if not ordered:
        status = STATUS_EMPTY
    elif len(distinct) >= 2:
        status = STATUS_MISGROUPED
    elif any(song.key is None for song in ordered):
        status = STATUS_UNTAGGED
    elif len(ordered) == 1:
        status = STATUS_SINGLETON
    else:
        status = STATUS_OK
    return GroupReport(name=name, status=status, songs=ordered)


def iter_group_dirs(staging_dir: Path) -> list[Path]:
    """Return staging_dir's grp-NNNN subfolders, ascending by group number."""
    if not staging_dir.is_dir():
        return []
    numbered: list[tuple[int, Path]] = []
    for entry in staging_dir.iterdir():
        match = _GROUP_DIR_RE.fullmatch(entry.name) if entry.is_dir() else None
        if match is not None:
            numbered.append((int(match.group(1)), entry))
    return [path for _, path in sorted(numbered)]


def verify_staging_dir(staging_dir: Path) -> list[GroupReport]:
    """Scan every grp-NNNN folder under staging_dir and classify each.

    Reads each file's tags from disk via collect_songs, so a song mixed into the
    wrong group after the run is caught.

    Args:
        staging_dir: The Staging-Dupes directory holding the grp-NNNN subfolders.

    Returns:
        list[GroupReport]: One report per group folder, ascending by group number.
    """
    reports: list[GroupReport] = []
    for group_dir in iter_group_dirs(staging_dir=staging_dir):
        songs = collect_songs(directory=group_dir)
        reports.append(classify_group(name=group_dir.name, songs=songs))
    return reports
