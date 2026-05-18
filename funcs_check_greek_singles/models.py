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
    key: SongKey | None     # None iff title or artist is missing -> 'untagged'
