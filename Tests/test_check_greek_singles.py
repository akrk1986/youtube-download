"""Unit tests for funcs_check_greek_singles/ package."""
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from funcs_check_greek_singles.audio_reader import (  # noqa: E402
    MONTH_FOLDER_RE, iter_month_folders, parse_month_arg,
)
from funcs_check_greek_singles.database import (  # noqa: E402
    SCHEMA_DDL,
    archive_previous_db, insert_song,
    query_in_multiple_months, query_only_in_all,
    query_only_in_months, query_untagged,
)
from funcs_check_greek_singles.models import Song, SongKey  # noqa: E402
from funcs_check_greek_singles.normalize import (  # noqa: E402
    extract_year, format_duration, normalize,
)


class TestNormalize:
    """normalize() should be case/diacritic/punctuation/whitespace-insensitive."""

    def test_collapses_whitespace_and_strips_diacritics(self):
        assert normalize(text='  Γιάννης Πάριος  ') == 'γιαννης παριος'

    def test_lowercases_latin_and_strips_diacritics(self):
        assert normalize(text='Café  AU LAIT') == 'cafe au lait'

    def test_strips_punctuation_but_keeps_digits(self):
        assert normalize(text='Best of, Vol. 2') == 'best of vol 2'

    def test_strips_pipe_and_emoji(self):
        assert normalize(text='Track | Live 🎵') == 'track live'

    def test_strips_apostrophe_inside_greek(self):
        assert normalize(text="Σ' αγαπώ") == 'σ αγαπω'

    def test_empty_input_returns_empty(self):
        assert normalize(text='') == ''

    def test_only_punctuation_returns_empty(self):
        assert normalize(text='!!!  ---  ###') == ''


class TestSongKey:
    """SongKey equality must collapse all the normalization classes."""

    def test_identical_keys_for_variants(self):
        k1 = SongKey(title='σ αγαπω', artist='γιαννης παριος')
        k2 = SongKey(title='σ αγαπω', artist='γιαννης παριος')
        assert k1 == k2
        assert hash(k1) == hash(k2)

    def test_album_irrelevance(self):
        # Two songs with same title+artist but different albums must yield the same key
        # (album never enters the matching key).
        song_a = _make_song(
            file_path=Path('/tmp/a.mp3'),
            title="Σ' αγαπώ", artist='Γιάννης Πάριος', album='Best of',
        )
        song_b = _make_song(
            file_path=Path('/tmp/b.mp3'),
            title="Σ' αγαπώ", artist='Γιάννης Πάριος', album='Live 2024',
        )
        assert song_a.key == song_b.key
        assert song_a.raw_album != song_b.raw_album


class TestUntaggedRouting:
    """Title and artist are mandatory; album alone is not."""

    def test_missing_title_routes_to_untagged(self):
        song = _make_song(file_path=Path('/tmp/x.mp3'), title='', artist='Artist', album='Album')
        assert song.key is None

    def test_missing_artist_routes_to_untagged(self):
        song = _make_song(file_path=Path('/tmp/x.mp3'), title='Title', artist='', album='Album')
        assert song.key is None

    def test_album_alone_missing_is_tagged(self):
        song = _make_song(file_path=Path('/tmp/x.mp3'), title='Title', artist='Artist', album='')
        assert song.key is not None

    def test_whitespace_only_tags_count_as_missing(self):
        song = _make_song(file_path=Path('/tmp/x.mp3'), title='   ', artist='Artist', album='Album')
        # raw_title preserves as supplied; the key check uses the normalized form.
        assert song.key is None


class TestExtractYear:
    """extract_year picks the first 4-digit run."""

    def test_iso_date(self):
        assert extract_year(date_tag_value='2023-07-15') == '2023'

    def test_yyyymmdd(self):
        assert extract_year(date_tag_value='20230715') == '2023'

    def test_year_only(self):
        assert extract_year(date_tag_value='2023') == '2023'

    def test_empty(self):
        assert extract_year(date_tag_value='') == ''

    def test_no_digits(self):
        assert extract_year(date_tag_value='unknown') == ''


class TestFormatDuration:
    """format_duration is m:ss for <1h, h:mm:ss for >=1h."""

    def test_zero_returns_empty(self):
        assert format_duration(seconds=0) == ''

    def test_none_returns_empty(self):
        assert format_duration(seconds=None) == ''

    def test_negative_returns_empty(self):
        assert format_duration(seconds=-1.0) == ''

    def test_short_track(self):
        assert format_duration(seconds=65.4) == '1:05'

    def test_typical_pop_song(self):
        assert format_duration(seconds=222) == '3:42'

    def test_just_under_one_hour(self):
        assert format_duration(seconds=3599) == '59:59'

    def test_over_one_hour(self):
        assert format_duration(seconds=3725) == '1:02:05'


class TestMonthFolderRegex:
    """MONTH_FOLDER_RE matches 'yyyy-mm' with optional ' <suffix>' tail."""

    @pytest.mark.parametrize('name', ['2024-03', '2024-12', '2024-03 holiday', '2024-05 spring break'])
    def test_accepts(self, name):
        assert MONTH_FOLDER_RE.match(name)

    @pytest.mark.parametrize('name', ['2024-3', '2024-13', 'random', '24-03', '', '2024-03-extra'])
    def test_rejects(self, name):
        assert not MONTH_FOLDER_RE.match(name)


class TestTitlePrefixFilter:
    """Title prefix matching uses the same normalization as title keys."""

    def test_diacritic_insensitive_prefix(self):
        # User supplies prefix without diacritics; song title has diacritics.
        prefix_norm = normalize(text='Σε μαγικά')
        song_title_norm = normalize(text='Σε  μαγικά νησιά')   # double space
        assert song_title_norm.startswith(prefix_norm)

    def test_case_insensitive_prefix(self):
        prefix_norm = normalize(text='Σε ΜΑΓΙΚΑ')
        song_title_norm = normalize(text='Σε  μαγικά νησιά')
        assert song_title_norm.startswith(prefix_norm)

    def test_non_matching_prefix(self):
        prefix_norm = normalize(text='Σε άλλα')
        song_title_norm = normalize(text='Σε  μαγικά νησιά')
        assert not song_title_norm.startswith(prefix_norm)


class TestParseMonthArg:
    """parse_month_arg validates and expands the CLI value."""

    def test_yyyy_mm_passes_through(self):
        assert parse_month_arg(value='2024-03', is_end=False) == '2024-03'
        assert parse_month_arg(value='2024-03', is_end=True) == '2024-03'

    def test_yyyy_expands_to_january_for_start(self):
        assert parse_month_arg(value='2024', is_end=False) == '2024-01'

    def test_yyyy_expands_to_december_for_end(self):
        assert parse_month_arg(value='2024', is_end=True) == '2024-12'

    @pytest.mark.parametrize('bad', ['24-03', '2024-13', '2024-00', '2024-3', 'random', '', '2024-03-01'])
    def test_rejects_malformed(self, bad):
        with pytest.raises(ValueError):
            parse_month_arg(value=bad, is_end=False)


class TestIterMonthFolders:
    """iter_month_folders honours start_yyyymm and end_yyyymm bounds (inclusive)."""

    @staticmethod
    def _build_tree(tmp_path: Path) -> Path:
        by_month = tmp_path / '03-Singles-by-Month'
        by_month.mkdir()
        for name in ['2023-12', '2024-01', '2024-06 holiday', '2024-12', '2025-01', 'README']:
            (by_month / name).mkdir()
        return by_month

    def test_both_bounds(self, tmp_path):
        by_month = self._build_tree(tmp_path=tmp_path)
        names = [p.name for p in iter_month_folders(
            by_month_root=by_month, start_yyyymm='2024-01', end_yyyymm='2024-12')]
        assert names == ['2024-01', '2024-06 holiday', '2024-12']

    def test_only_start_bound(self, tmp_path):
        by_month = self._build_tree(tmp_path=tmp_path)
        names = [p.name for p in iter_month_folders(
            by_month_root=by_month, start_yyyymm='2024-06', end_yyyymm='')]
        assert names == ['2024-06 holiday', '2024-12', '2025-01']

    def test_only_end_bound(self, tmp_path):
        by_month = self._build_tree(tmp_path=tmp_path)
        names = [p.name for p in iter_month_folders(
            by_month_root=by_month, start_yyyymm='', end_yyyymm='2024-01')]
        assert names == ['2023-12', '2024-01']

    def test_no_bounds_yields_all_matching(self, tmp_path):
        by_month = self._build_tree(tmp_path=tmp_path)
        names = [p.name for p in iter_month_folders(by_month_root=by_month)]
        # 'README' is filtered out by MONTH_FOLDER_RE.
        assert names == ['2023-12', '2024-01', '2024-06 holiday', '2024-12', '2025-01']

    def test_range_excluding_everything(self, tmp_path):
        by_month = self._build_tree(tmp_path=tmp_path)
        names = [p.name for p in iter_month_folders(
            by_month_root=by_month, start_yyyymm='2030-01', end_yyyymm='2030-12')]
        assert names == []


class TestDiffQueries:
    """Insert synthetic Songs into an in-memory DB and verify each diff query."""

    def test_only_in_all(self, conn):
        _insert(conn=conn, side='singles_all', month_folder=None, title='Solo A', artist='X')

        rows = query_only_in_all(conn=conn)
        assert len(rows) == 1
        assert rows[0]['raw_title'] == 'Solo A'
        assert query_only_in_months(conn=conn) == []

    def test_only_in_months(self, conn):
        _insert(conn=conn, side='month', month_folder='2024-01', title='Other', artist='Y')

        rows = query_only_in_months(conn=conn)
        assert len(rows) == 1
        assert rows[0]['raw_title'] == 'Other'
        assert query_only_in_all(conn=conn) == []

    def test_match_is_not_reported(self, conn):
        _insert(conn=conn, side='singles_all', month_folder=None, title='Shared', artist='Z')
        _insert(conn=conn, side='month', month_folder='2024-01', title='Shared', artist='Z')

        assert query_only_in_all(conn=conn) == []
        assert query_only_in_months(conn=conn) == []

    def test_in_multiple_months(self, conn):
        _insert(conn=conn, side='singles_all', month_folder=None, title='Hit', artist='Y')
        _insert(conn=conn, side='month', month_folder='2024-01', title='Hit', artist='Y')
        _insert(conn=conn, side='month', month_folder='2024-03 spring', title='Hit', artist='Y')

        rows = query_in_multiple_months(conn=conn)
        assert len(rows) == 1
        assert rows[0]['folder_count'] == 2
        assert '2024-01' in rows[0]['folders']
        assert '2024-03 spring' in rows[0]['folders']

    def test_single_month_not_in_multi_result(self, conn):
        _insert(conn=conn, side='singles_all', month_folder=None, title='Hit', artist='Y')
        _insert(conn=conn, side='month', month_folder='2024-01', title='Hit', artist='Y')

        assert query_in_multiple_months(conn=conn) == []

    def test_untagged(self, conn):
        _insert(conn=conn, side='singles_all', month_folder=None, title='', artist='', album='Stray')
        _insert(conn=conn, side='month', month_folder='2024-01', title='OK', artist='OK')

        rows = query_untagged(conn=conn)
        assert len(rows) == 1
        assert rows[0]['raw_album'] == 'Stray'

    def test_multiple_entries_per_side_all_returned(self, conn):
        # Same (title, artist) appears twice in singles-all with different albums.
        # All entries must surface in the only-in result (not just the first).
        _insert(conn=conn, side='singles_all', month_folder=None,
                title='Sagapo', artist='Parios', album='Best of', file_path='/x/a.mp3')
        _insert(conn=conn, side='singles_all', month_folder=None,
                title='Sagapo', artist='Parios', album='Live 2024', file_path='/x/b.mp3')

        rows = query_only_in_all(conn=conn)
        assert len(rows) == 2
        albums = {row['raw_album'] for row in rows}
        assert albums == {'Best of', 'Live 2024'}


class TestArchivePreviousDb:
    """archive_previous_db renames the existing file by mtime, with -N collisions."""

    def test_noop_when_absent(self, tmp_path):
        db_path = tmp_path / 'songs.sqlite'
        archive_previous_db(db_path=db_path)
        assert not db_path.exists()

    def test_renames_using_mtime(self, tmp_path):
        db_path = tmp_path / 'songs.sqlite'
        db_path.write_bytes(b'fake db')
        fixed_epoch = _make_known_epoch()
        os.utime(db_path, (fixed_epoch, fixed_epoch))

        archive_previous_db(db_path=db_path)

        archived = list(tmp_path.glob('songs-*.sqlite'))
        assert len(archived) == 1
        assert not db_path.exists()
        import re as _re
        assert _re.match(r'^songs-\d{4}-\d{2}-\d{2}-\d{4}\.sqlite$', archived[0].name)

    def test_collision_appends_sequence(self, tmp_path):
        db_path = tmp_path / 'songs.sqlite'
        db_path.write_bytes(b'fake db')
        fixed_epoch = _make_known_epoch()
        os.utime(db_path, (fixed_epoch, fixed_epoch))

        import arrow as _arrow
        mtime_ts = _arrow.get(fixed_epoch).format('YYYY-MM-DD-HHmm')
        # Pre-create the would-be target and one sequence collision.
        (tmp_path / f'songs-{mtime_ts}.sqlite').write_bytes(b'prev1')
        (tmp_path / f'songs-{mtime_ts}-1.sqlite').write_bytes(b'prev2')

        archive_previous_db(db_path=db_path)

        # New archive should land at the next free slot: songs-<mtime>-2.sqlite
        expected = tmp_path / f'songs-{mtime_ts}-2.sqlite'
        assert expected.exists()
        assert not db_path.exists()


@pytest.fixture
def conn():
    """In-memory DB initialised with the production schema."""
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_DDL)
    yield connection
    connection.close()


def _make_song(file_path: Path, title: str, artist: str, album: str) -> Any:
    """Build a Song the same way the production code does, but bypass tag-reading."""
    norm_title = normalize(text=title)
    norm_artist = normalize(text=artist)
    key = SongKey(title=norm_title, artist=norm_artist) if norm_title and norm_artist else None
    return Song(
        file_path=file_path, raw_title=title, raw_artist=artist, raw_album=album,
        year='', duration_seconds=0.0, key=key,
    )


def _insert(conn: sqlite3.Connection, side: str, month_folder: str | None,
            title: str, artist: str, album: str = '',
            file_path: str | None = None) -> None:
    """Helper to insert a synthetic row directly via the production insert_song()."""
    if file_path is None:
        # Include month_folder so the same (title, artist) inserted in different
        # months produces distinct file paths (PRIMARY KEY is (side, file_path)).
        slot = month_folder or 'singles'
        file_path = f'/test/{side}/{slot}/{title}_{artist}.mp3'
    song = _make_song(file_path=Path(file_path), title=title, artist=artist, album=album)
    insert_song(conn=conn, song=song, side=side, month_folder=month_folder)


def _make_known_epoch() -> float:
    """Return a stable epoch (well in the past so it never collides with 'now')."""
    return time.mktime((2024, 6, 15, 12, 34, 0, 0, 0, -1))
