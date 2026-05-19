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
class InFolderDupRow:
    """Cluster of >=2 files in the same folder sharing the matching key.

    'Same folder' means same (side, month_folder); for singles-all rows
    month_folder is None. file_paths holds every member of the cluster
    (sorted, full paths).
    """
    side: str               # 'singles_all' | 'month'
    month_folder: str | None
    raw_title: str
    raw_artist: str
    raw_album: str
    duration_seconds: float
    dup_count: int
    file_paths: tuple[str, ...]
