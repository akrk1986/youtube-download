"""SQLite persistence layer: schema, archive, insert, diff queries."""
import logging
import sqlite3
from pathlib import Path

import arrow

from funcs_check_greek_singles.models import Song
from funcs_check_greek_singles.normalize import normalize

SIDE_SINGLES_ALL = 'singles_all'
SIDE_MONTH = 'month'

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
    norm_title       TEXT,
    norm_artist      TEXT,
    norm_album       TEXT,
    has_key          INTEGER NOT NULL,
    PRIMARY KEY (side, file_path)
);
CREATE INDEX idx_songs_key ON songs(norm_title, norm_artist) WHERE has_key = 1;
"""

_QUERY_ONLY_IN_ALL = """
SELECT *
FROM songs s
WHERE s.side = 'singles_all'
  AND s.has_key = 1
  AND NOT EXISTS (
    SELECT 1 FROM songs m
    WHERE m.side = 'month' AND m.has_key = 1
      AND m.norm_title = s.norm_title
      AND m.norm_artist = s.norm_artist
  )
ORDER BY s.norm_title, s.norm_artist, s.norm_album, s.file_path
"""

_QUERY_ONLY_IN_MONTHS = """
SELECT *
FROM songs m
WHERE m.side = 'month'
  AND m.has_key = 1
  AND NOT EXISTS (
    SELECT 1 FROM songs s
    WHERE s.side = 'singles_all' AND s.has_key = 1
      AND s.norm_title = m.norm_title
      AND s.norm_artist = m.norm_artist
  )
ORDER BY m.norm_title, m.norm_artist, m.norm_album, m.month_folder, m.file_path
"""

_QUERY_IN_MULTIPLE_MONTHS = """
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
GROUP BY s.norm_title, s.norm_artist
HAVING folder_count >= 2
ORDER BY s.norm_title, s.norm_artist
"""

_QUERY_UNTAGGED = """
SELECT side, month_folder, file_path, raw_title, raw_artist, raw_album
FROM songs
WHERE has_key = 0
ORDER BY side, COALESCE(month_folder, ''), file_path
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
            year, duration_seconds,
            norm_title, norm_artist, norm_album,
            has_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            side, month_folder, str(song.file_path),
            song.raw_title, song.raw_artist, song.raw_album,
            song.year, song.duration_seconds,
            norm_title, norm_artist, norm_album,
            has_key,
        ),
    )


def query_only_in_all(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Songs in 01-Singles-All with no (title, artist) match in any month folder."""
    return list(conn.execute(_QUERY_ONLY_IN_ALL))


def query_only_in_months(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Songs in any month folder with no (title, artist) match in 01-Singles-All."""
    return list(conn.execute(_QUERY_ONLY_IN_MONTHS))


def query_in_multiple_months(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Singles-all songs whose (title, artist) appears in >=2 distinct month folders."""
    return list(conn.execute(_QUERY_IN_MULTIPLE_MONTHS))


def query_untagged(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Files missing title and/or artist (album alone missing does not qualify)."""
    return list(conn.execute(_QUERY_UNTAGGED))
