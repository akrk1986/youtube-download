"""Data classes for the Greek singles cross-checker."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SongKey:
    """Matching key for cross-folder song comparison.

    Both fields hold normalized values (lowercase, diacritics-stripped,
    non-alphanumeric stripped, whitespace-collapsed). Album is intentionally
    excluded: two files with the same title+artist but different albums match
    on the same key, and are surfaced as adjacent rows for manual review.
    """
    title: str
    artist: str


@dataclass
class Song:
    """Parsed audio file with raw display fields and a derived matching key."""
    file_path: Path
    raw_title: str
    raw_artist: str
    raw_album: str
    year: str
    duration_seconds: float
    size_bytes: int
    key: SongKey | None     # None iff title or artist is missing -> 'untagged'


@dataclass(frozen=True)
class MatchedRow:
    """Query result for only_in_all / only_in_months.

    month_folder is None for singles-all rows, set to the folder name for
    month-side rows. file_path is the stored TEXT (full filesystem path).
    """
    file_path: str
    raw_title: str
    raw_artist: str
    raw_album: str
    year: str
    duration_seconds: float
    size_bytes: int
    month_folder: str | None


@dataclass(frozen=True)
class MultiMonthRow:
    """Query result for in_multiple_months.

    file_path is always from the singles-all side of the self-join, so the
    display path renders as 'All/<name>'. folders is the comma-joined list
    of month folders this (title, artist) key appears in.
    """
    file_path: str
    raw_title: str
    raw_artist: str
    raw_album: str
    year: str
    duration_seconds: float
    folders: str
    folder_count: int


@dataclass(frozen=True)
class UntaggedRow:
    """Query result for untagged."""
    side: str               # 'singles_all' | 'month'
    month_folder: str | None
    file_path: str
    raw_title: str
    raw_artist: str
    raw_album: str


@dataclass(frozen=True)
class InFolderDupMember:
    """One file within a duplicate cluster (per-file folder/album/duration).

    month_folder is the file's own month folder (None for singles-all). In a
    per-folder cluster every member shares it; in a cross-month cluster it varies.
    """
    file_path: str
    month_folder: str | None
    raw_album: str
    duration_seconds: float


@dataclass(frozen=True)
class InFolderDupRow:
    """Cluster of >=2 files in the same folder sharing the matching key.

    'Same folder' means same (side, month_folder); for singles-all rows
    month_folder is None. raw_title / raw_artist are cluster-level (same
    normalized key); album and duration vary per file, so they live on
    `members` (sorted by file_path).
    """
    side: str               # 'singles_all' | 'month'
    month_folder: str | None
    raw_title: str
    raw_artist: str
    members: tuple[InFolderDupMember, ...]

    @property
    def dup_count(self) -> int:
        """Number of files in the cluster."""
        return len(self.members)

    @property
    def file_paths(self) -> tuple[str, ...]:
        """Full paths of every file in the cluster, in member order."""
        return tuple(member.file_path for member in self.members)


@dataclass(frozen=True)
class CrossMonthDupRow:
    """Cluster of >=2 month-folder files sharing (title, artist, dur-within-margin),
    pooled across the scanned month range. members may span multiple months."""
    raw_title: str
    raw_artist: str
    members: tuple[InFolderDupMember, ...]

    @property
    def dup_count(self) -> int:
        """Number of files in the cluster."""
        return len(self.members)

    @property
    def distinct_months(self) -> int:
        """How many distinct month folders the cluster spans."""
        return len({member.month_folder for member in self.members})
