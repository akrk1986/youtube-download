"""Data classes for the Greek singles cross-checker."""
from dataclasses import dataclass, replace
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
    auto_original flags the sole 01-Singles-All keeper in a --scope all group, so
    staging writes its 'original' verdict (the one scoped exception to the rule
    that only the user writes a verdict); every other path leaves it False.
    """
    file_path: str
    month_folder: str | None
    raw_album: str
    duration_seconds: float
    auto_original: bool = False


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


@dataclass(frozen=True)
class AllScopeDupRow:
    """Cluster pooling 01-Singles-All and month copies of one song (--scope all).

    Members span both sides: all_members are the 01-Singles-All copies
    (month_folder is None), month_members the month-folder copies. Only kept when
    a >= 1 and (a >= 2 or m >= 2) -- a normal song (one All/ copy + one month copy)
    is filtered out by query_all_scope_duplicates.
    """
    raw_title: str
    raw_artist: str
    members: tuple[InFolderDupMember, ...]

    @property
    def all_members(self) -> tuple[InFolderDupMember, ...]:
        """The 01-Singles-All copies in the cluster (those with no month folder)."""
        return tuple(member for member in self.members if member.month_folder is None)

    @property
    def month_members(self) -> tuple[InFolderDupMember, ...]:
        """The month-folder copies in the cluster."""
        return tuple(member for member in self.members if member.month_folder is not None)

    def staging_members(self) -> tuple[InFolderDupMember, ...]:
        """Members for staging, auto-flagging the sole All/ copy 'original' when a == 1.

        When exactly one 01-Singles-All copy is present it is the unambiguous master
        keeper, so it is returned with auto_original=True (the user inspects the month
        copies). With two or more All/ copies the keeper is ambiguous, so nothing is
        flagged and the members are returned unchanged.
        """
        if len(self.all_members) != 1:
            return self.members
        return tuple(
            replace(member, auto_original=True) if member.month_folder is None else member
            for member in self.members
        )


@dataclass(frozen=True)
class StagingGroup:
    """A dupe group destined for one Staging-Dupes/grp-NNNN subfolder.

    Built for staging by concatenating cross-month clusters (all month copies of a
    song) with 01-Singles-All in-folder clusters; the two never share files.
    `number` is assigned at staging time and drives the 4-digit folder name.
    """
    number: int
    raw_title: str
    raw_artist: str
    members: tuple[InFolderDupMember, ...]

    @property
    def folder_name(self) -> str:
        """Staging subfolder name for this group, e.g. 'grp-0007'."""
        return f'grp-{self.number:04d}'
