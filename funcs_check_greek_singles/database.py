"""SQLite persistence layer: schema, archive, insert, diff queries."""
import itertools
import logging
import sqlite3
from pathlib import Path

import arrow

from funcs_check_greek_singles.models import (
    InFolderDupRow, MatchedRow, MultiMonthRow, Song, UntaggedRow,
)
from funcs_check_greek_singles.normalize import normalize

SIDE_SINGLES_ALL = 'singles_all'
SIDE_MONTH = 'month'

# Two songs match if their normalized tags (title, artist) align AND their durations
# differ by at most this many seconds. ABS-based tolerance (no X.5 boundary
# issue). Sub-second encoder jitter is well within 1.0s; distinct recordings of
# the same song (studio vs live) typically differ by 10s+.
DURATION_MATCH_MARGIN_SECONDS = 3.0

SCHEMA_DDL = """
PRAGMA journal_mode = MEMORY;
CREATE TABLE songs (
    side             TEXT NOT NULL,
    month_folder     TEXT,
    file_path        TEXT NOT NULL,
    raw_title        TEXT,
    raw_artist       TEXT,
    raw_album        TEXT,
    year             TEXT,
    duration_seconds REAL,
    size_bytes       INTEGER NOT NULL DEFAULT 0,
    norm_title       TEXT,
    norm_artist      TEXT,
    norm_album       TEXT,
    has_key          INTEGER NOT NULL,
    PRIMARY KEY (side, file_path)
);
CREATE INDEX idx_songs_key ON songs(norm_title, norm_artist) WHERE has_key = 1;
"""

# Matching predicate: (norm_title, norm_artist, ABS(dur_a - dur_b) <= margin).
# The duration margin is DURATION_MATCH_MARGIN_SECONDS (default 1.0s) and
# disambiguates same-tagged-but-different recordings (e.g. 'BandaLaika' studio
# vs 'BandaLaika' live). Inlined into the SQL via f-string at module load — the
# constant is project-controlled, no injection risk.
#
# Note: GROUP BY clauses (in _QUERY_IN_MULTIPLE_MONTHS and _QUERY_IN_FOLDER_DUPS)
# still use ROUND(duration_seconds) for bucketing. SQL can't do fuzzy GROUP BY;
# for the 1.0s default margin this only affects durations that straddle X.5.
_QUERY_ONLY_IN_ALL = f"""
SELECT *
FROM songs s
WHERE s.side = 'singles_all'
  AND s.has_key = 1
  AND NOT EXISTS (
    SELECT 1 FROM songs m
    WHERE m.side = 'month' AND m.has_key = 1
      AND m.norm_title = s.norm_title
      AND m.norm_artist = s.norm_artist
      AND ABS(m.duration_seconds - s.duration_seconds) <= {DURATION_MATCH_MARGIN_SECONDS}
  )
ORDER BY s.norm_title, s.norm_artist, s.norm_album, s.file_path
"""

_QUERY_ONLY_IN_MONTHS = f"""
SELECT *
FROM songs m
WHERE m.side = 'month'
  AND m.has_key = 1
  AND NOT EXISTS (
    SELECT 1 FROM songs s
    WHERE s.side = 'singles_all' AND s.has_key = 1
      AND s.norm_title = m.norm_title
      AND s.norm_artist = m.norm_artist
      AND ABS(s.duration_seconds - m.duration_seconds) <= {DURATION_MATCH_MARGIN_SECONDS}
  )
ORDER BY m.norm_title, m.norm_artist, m.norm_album, m.month_folder, m.file_path
"""

_QUERY_IN_MULTIPLE_MONTHS = f"""
SELECT s.norm_title, s.norm_artist,
       s.raw_title, s.raw_artist, s.raw_album,
       s.year, s.duration_seconds, s.file_path,
       COUNT(DISTINCT m.month_folder) AS folder_count,
       GROUP_CONCAT(DISTINCT m.month_folder) AS folders
FROM songs s
JOIN songs m
  ON s.side = 'singles_all' AND m.side = 'month'
 AND s.has_key = 1 AND m.has_key = 1
 AND s.norm_title = m.norm_title
 AND s.norm_artist = m.norm_artist
 AND ABS(s.duration_seconds - m.duration_seconds) <= {DURATION_MATCH_MARGIN_SECONDS}
GROUP BY s.norm_title, s.norm_artist, ROUND(s.duration_seconds)
HAVING folder_count >= 2
ORDER BY s.norm_title, s.norm_artist
"""

_QUERY_UNTAGGED = """
SELECT side, month_folder, file_path, raw_title, raw_artist, raw_album
FROM songs
WHERE has_key = 0
ORDER BY side, COALESCE(month_folder, ''), file_path
"""

# Candidate rows for in-folder duplicate clustering: every tagged song, ordered
# so itertools.groupby can partition by (side, month_folder, norm_title,
# norm_artist) and a duration sweep can cluster within each partition. Duration
# clustering is done in Python (query_in_folder_duplicates) because SQL GROUP BY
# can't honor the ABS-based margin -- ROUND-bucketing would split e.g. 168s and
# 171s into different buckets even when the margin (3.0s) says they're the same.
_QUERY_IN_FOLDER_CANDIDATES = """
SELECT side, month_folder, norm_title, norm_artist,
       raw_title, raw_artist, raw_album,
       duration_seconds, file_path
FROM songs
WHERE has_key = 1
ORDER BY side, COALESCE(month_folder, ''), norm_title, norm_artist, duration_seconds
"""

_QUERY_TOTAL_MONTH_SONGS = """
SELECT COUNT(*) FROM songs WHERE side = 'month' AND has_key = 1
"""

logger = logging.getLogger(__name__)


def archive_previous_db(db_path: Path) -> None:
    """Rename an existing DB to 'songs-<mtime>.sqlite', with -1/-2/... on name collision."""
    if not db_path.exists():
        return
    mtime_ts = arrow.get(db_path.stat().st_mtime).format('YYYY-MM-DD-HHmm')
    target = db_path.with_name(f'songs-{mtime_ts}.sqlite')
    seq = 0
    while target.exists():
        seq += 1
        target = db_path.with_name(f'songs-{mtime_ts}-{seq}.sqlite')
    db_path.rename(target)
    logger.info(f'Archived previous DB to {target.name}')


def init_db(db_path: Path) -> sqlite3.Connection:
    """Open a fresh DB at db_path and create the schema. Caller must close()."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_DDL)
    return conn


def insert_song(conn: sqlite3.Connection, song: Song,
                side: str, month_folder: str | None) -> None:
    """Insert (or replace on PK collision) one Song row."""
    has_key = 1 if song.key is not None else 0
    norm_title = song.key.title if song.key is not None else ''
    norm_artist = song.key.artist if song.key is not None else ''
    norm_album = normalize(text=song.raw_album)
    conn.execute(
        """
        INSERT OR REPLACE INTO songs (
            side, month_folder, file_path,
            raw_title, raw_artist, raw_album,
            year, duration_seconds, size_bytes,
            norm_title, norm_artist, norm_album,
            has_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            side, month_folder, str(song.file_path),
            song.raw_title, song.raw_artist, song.raw_album,
            song.year, song.duration_seconds, song.size_bytes,
            norm_title, norm_artist, norm_album,
            has_key,
        ),
    )


def _row_to_matched(row: sqlite3.Row) -> MatchedRow:
    return MatchedRow(
        file_path=row['file_path'],
        raw_title=row['raw_title'] or '',
        raw_artist=row['raw_artist'] or '',
        raw_album=row['raw_album'] or '',
        year=row['year'] or '',
        duration_seconds=float(row['duration_seconds'] or 0.0),
        size_bytes=int(row['size_bytes'] or 0),
        month_folder=row['month_folder'],
    )


def _row_to_multi_month(row: sqlite3.Row) -> MultiMonthRow:
    return MultiMonthRow(
        file_path=row['file_path'],
        raw_title=row['raw_title'] or '',
        raw_artist=row['raw_artist'] or '',
        raw_album=row['raw_album'] or '',
        year=row['year'] or '',
        duration_seconds=float(row['duration_seconds'] or 0.0),
        folders=row['folders'] or '',
        folder_count=int(row['folder_count'] or 0),
    )


def _row_to_untagged(row: sqlite3.Row) -> UntaggedRow:
    return UntaggedRow(
        side=row['side'],
        month_folder=row['month_folder'],
        file_path=row['file_path'],
        raw_title=row['raw_title'] or '',
        raw_artist=row['raw_artist'] or '',
        raw_album=row['raw_album'] or '',
    )


def _in_folder_group_key(row: sqlite3.Row) -> tuple[str, str | None, str, str]:
    return (row['side'], row['month_folder'], row['norm_title'], row['norm_artist'])


def _build_in_folder_cluster(rows: list[sqlite3.Row]) -> InFolderDupRow:
    first = rows[0]
    paths = tuple(sorted(r['file_path'] for r in rows))
    return InFolderDupRow(
        side=first['side'],
        month_folder=first['month_folder'],
        raw_title=first['raw_title'] or '',
        raw_artist=first['raw_artist'] or '',
        raw_album=first['raw_album'] or '',
        duration_seconds=float(min(r['duration_seconds'] or 0.0 for r in rows)),
        dup_count=len(rows),
        file_paths=paths,
    )


def query_only_in_all(conn: sqlite3.Connection) -> list[MatchedRow]:
    """Songs in 01-Singles-All with no (title, artist) match in any month folder."""
    return [_row_to_matched(row=r) for r in conn.execute(_QUERY_ONLY_IN_ALL)]


def query_only_in_months(conn: sqlite3.Connection) -> list[MatchedRow]:
    """Songs in any month folder with no (title, artist) match in 01-Singles-All."""
    return [_row_to_matched(row=r) for r in conn.execute(_QUERY_ONLY_IN_MONTHS)]


def query_in_multiple_months(conn: sqlite3.Connection) -> list[MultiMonthRow]:
    """Singles-all songs whose (title, artist) appears in >=2 distinct month folders."""
    return [_row_to_multi_month(row=r) for r in conn.execute(_QUERY_IN_MULTIPLE_MONTHS)]


def query_untagged(conn: sqlite3.Connection) -> list[UntaggedRow]:
    """Files missing title and/or artist (album alone missing does not qualify)."""
    return [_row_to_untagged(row=r) for r in conn.execute(_QUERY_UNTAGGED)]


def query_in_folder_duplicates(
        conn: sqlite3.Connection,
        margin: float = DURATION_MATCH_MARGIN_SECONDS,
) -> list[InFolderDupRow]:
    """Clusters of >=2 files in the same folder sharing (title, artist), durations
    within `margin` seconds.

    Within each (side, month_folder, norm_title, norm_artist) partition, rows are
    swept in ascending duration order and split wherever the gap to the previous
    row exceeds `margin` (single-linkage clustering). A cluster is reported only
    when it holds >=2 files.
    """
    rows = conn.execute(_QUERY_IN_FOLDER_CANDIDATES).fetchall()
    clusters: list[InFolderDupRow] = []
    for _key, group_iter in itertools.groupby(rows, key=_in_folder_group_key):
        group = list(group_iter)
        current = [group[0]]
        for row in group[1:]:
            if row['duration_seconds'] - current[-1]['duration_seconds'] <= margin:
                current.append(row)
            else:
                if len(current) >= 2:
                    clusters.append(_build_in_folder_cluster(rows=current))
                current = [row]
        if len(current) >= 2:
            clusters.append(_build_in_folder_cluster(rows=current))
    return clusters


def query_total_month_songs(conn: sqlite3.Connection) -> int:
    """Count tagged songs across all scanned month folders (within the active range)."""
    row = conn.execute(_QUERY_TOTAL_MONTH_SONGS).fetchone()
    return int(row[0]) if row else 0
