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
from funcs_check_greek_singles.config import DURATION_MATCH_MARGIN_SECONDS  # noqa: E402
from funcs_check_greek_singles.database import (  # noqa: E402
    SCHEMA_DDL,
    archive_previous_db, insert_song,
    query_in_folder_duplicates, query_in_multiple_months, query_only_in_all,
    query_only_in_months, query_untagged,
)
from funcs_check_greek_singles.file_actions import (  # noqa: E402
    apply_missing_action, prompt_action_limit,
)
from funcs_check_greek_singles.models import MatchedRow, Song, SongKey  # noqa: E402
from funcs_check_greek_singles.normalize import (  # noqa: E402
    extract_year, format_duration, normalize,
)
from funcs_check_greek_singles.report import _format_size  # noqa: E402


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
            file_path=Path('/test/a.mp3'),
            title="Σ' αγαπώ", artist='Γιάννης Πάριος', album='Best of',
        )
        song_b = _make_song(
            file_path=Path('/test/b.mp3'),
            title="Σ' αγαπώ", artist='Γιάννης Πάριος', album='Live 2024',
        )
        assert song_a.key == song_b.key
        assert song_a.raw_album != song_b.raw_album


class TestUntaggedRouting:
    """Title and artist are mandatory; album alone is not."""

    def test_missing_title_routes_to_untagged(self):
        song = _make_song(file_path=Path('/test/x.mp3'), title='', artist='Artist', album='Album')
        assert song.key is None

    def test_missing_artist_routes_to_untagged(self):
        song = _make_song(file_path=Path('/test/x.mp3'), title='Title', artist='', album='Album')
        assert song.key is None

    def test_album_alone_missing_is_tagged(self):
        song = _make_song(file_path=Path('/test/x.mp3'), title='Title', artist='Artist', album='')
        assert song.key is not None

    def test_whitespace_only_tags_count_as_missing(self):
        song = _make_song(file_path=Path('/test/x.mp3'), title='   ', artist='Artist', album='Album')
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

    @pytest.mark.parametrize('name', [
        '2024-03', '2024-12', '2024-03 holiday', '2024-05 spring break',
        '2024-03-extra', '2025-11-Nykhta Stasou',
    ])
    def test_accepts(self, name):
        assert MONTH_FOLDER_RE.match(name)

    @pytest.mark.parametrize('name', ['2024-3', '2024-13', 'random', '24-03', '', '2024-03foo'])
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


class TestFormatSize:
    """_format_size renders MB up to 1 GB, GB above."""

    def test_zero(self):
        assert _format_size(size_bytes=0) == '0 MB'

    def test_negative(self):
        assert _format_size(size_bytes=-1) == '0 MB'

    def test_under_one_gb(self):
        assert _format_size(size_bytes=5 * 1024 * 1024) == '5.00 MB'

    def test_just_under_one_gb(self):
        # 1023 MB stays in MB.
        assert _format_size(size_bytes=1023 * 1024 * 1024) == '1023.00 MB'

    def test_one_gb_and_change(self):
        assert _format_size(size_bytes=int(1.5 * 1024 * 1024 * 1024)) == '1.50 GB'


class TestSizeBytesPropagates:
    """size_bytes flows from Song -> DB -> query result."""

    def test_only_in_months_carries_size(self, conn):
        _insert(conn=conn, side='month', month_folder='2024-01',
                title='Big', artist='Y', size_bytes=10 * 1024 * 1024)
        rows = query_only_in_months(conn=conn)
        assert len(rows) == 1
        assert rows[0].size_bytes == 10 * 1024 * 1024


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
        assert rows[0].raw_title == 'Solo A'
        assert query_only_in_months(conn=conn) == []

    def test_only_in_months(self, conn):
        _insert(conn=conn, side='month', month_folder='2024-01', title='Other', artist='Y')

        rows = query_only_in_months(conn=conn)
        assert len(rows) == 1
        assert rows[0].raw_title == 'Other'
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
        assert rows[0].folder_count == 2
        assert '2024-01' in rows[0].folders
        assert '2024-03 spring' in rows[0].folders

    def test_single_month_not_in_multi_result(self, conn):
        _insert(conn=conn, side='singles_all', month_folder=None, title='Hit', artist='Y')
        _insert(conn=conn, side='month', month_folder='2024-01', title='Hit', artist='Y')

        assert query_in_multiple_months(conn=conn) == []

    def test_untagged(self, conn):
        _insert(conn=conn, side='singles_all', month_folder=None, title='', artist='', album='Stray')
        _insert(conn=conn, side='month', month_folder='2024-01', title='OK', artist='OK')

        rows = query_untagged(conn=conn)
        assert len(rows) == 1
        assert rows[0].raw_album == 'Stray'

    def test_multiple_entries_per_side_all_returned(self, conn):
        # Same (title, artist) appears twice in singles-all with different albums.
        # All entries must surface in the only-in result (not just the first).
        _insert(conn=conn, side='singles_all', month_folder=None,
                title='Sagapo', artist='Parios', album='Best of', file_path='/x/a.mp3')
        _insert(conn=conn, side='singles_all', month_folder=None,
                title='Sagapo', artist='Parios', album='Live 2024', file_path='/x/b.mp3')

        rows = query_only_in_all(conn=conn)
        assert len(rows) == 2
        albums = {row.raw_album for row in rows}
        assert albums == {'Best of', 'Live 2024'}


class TestDurationDisambiguation:
    """Matching key includes ROUND(duration_seconds): same tags + different
    durations -> treated as different songs across all queries."""

    def test_different_durations_not_matched(self, conn):
        # Same title + artist, durations 200s vs 250s.
        # Each must surface as "missing from the other side".
        _insert(conn=conn, side='singles_all', month_folder=None,
                title='Same', artist='Band', duration_seconds=200.0)
        _insert(conn=conn, side='month', month_folder='2024-01',
                title='Same', artist='Band', duration_seconds=250.0)

        assert len(query_only_in_all(conn=conn)) == 1
        assert len(query_only_in_months(conn=conn)) == 1

    def test_identical_durations_match(self, conn):
        # Same title, artist, and duration -> matches across sides.
        _insert(conn=conn, side='singles_all', month_folder=None,
                title='Same', artist='Band', duration_seconds=222.5)
        _insert(conn=conn, side='month', month_folder='2024-01',
                title='Same', artist='Band', duration_seconds=222.5)

        assert query_only_in_all(conn=conn) == []
        assert query_only_in_months(conn=conn) == []

    def test_durations_within_margin_match(self, conn):
        # Durations half a margin apart match (ABS tolerance, no ROUND X.5 quirk).
        # Computed relative to the module constant so the test is margin-agnostic.
        delta = DURATION_MATCH_MARGIN_SECONDS / 2
        _insert(conn=conn, side='singles_all', month_folder=None,
                title='Jitter', artist='Band', duration_seconds=222.0)
        _insert(conn=conn, side='month', month_folder='2024-01',
                title='Jitter', artist='Band', duration_seconds=222.0 + delta)

        assert query_only_in_all(conn=conn) == []
        assert query_only_in_months(conn=conn) == []

    def test_duration_at_margin_boundary_matches(self, conn):
        # ABS(diff) == DURATION_MATCH_MARGIN_SECONDS uses '<=' so the boundary
        # is inclusive.
        _insert(conn=conn, side='singles_all', month_folder=None,
                title='Edge', artist='Band', duration_seconds=200.0)
        _insert(conn=conn, side='month', month_folder='2024-01',
                title='Edge', artist='Band',
                duration_seconds=200.0 + DURATION_MATCH_MARGIN_SECONDS)

        assert query_only_in_all(conn=conn) == []
        assert query_only_in_months(conn=conn) == []

    def test_duration_just_beyond_margin_does_not_match(self, conn):
        # One second past the margin -> treated as distinct recordings.
        _insert(conn=conn, side='singles_all', month_folder=None,
                title='Past', artist='Band', duration_seconds=200.0)
        _insert(conn=conn, side='month', month_folder='2024-01',
                title='Past', artist='Band',
                duration_seconds=200.0 + DURATION_MATCH_MARGIN_SECONDS + 1.0)

        assert len(query_only_in_all(conn=conn)) == 1
        assert len(query_only_in_months(conn=conn)) == 1

    def test_in_multiple_months_respects_duration(self, conn):
        # singles_all has ONE entry (duration 200). Two month folders each have a
        # 'Hit' by 'Y' but with different durations: one matches (200), one not (300).
        # The matched pair must NOT appear in in_multiple_months (folder_count would be 1).
        _insert(conn=conn, side='singles_all', month_folder=None,
                title='Hit', artist='Y', duration_seconds=200.0)
        _insert(conn=conn, side='month', month_folder='2024-01',
                title='Hit', artist='Y', duration_seconds=200.0)
        _insert(conn=conn, side='month', month_folder='2024-03',
                title='Hit', artist='Y', duration_seconds=300.0)

        assert query_in_multiple_months(conn=conn) == []

    def test_in_multiple_months_matches_when_all_durations_align(self, conn):
        # All three sides agree on duration -> in_multiple_months sees folder_count=2.
        _insert(conn=conn, side='singles_all', month_folder=None,
                title='Hit', artist='Y', duration_seconds=200.0)
        _insert(conn=conn, side='month', month_folder='2024-01',
                title='Hit', artist='Y', duration_seconds=200.0)
        _insert(conn=conn, side='month', month_folder='2024-03',
                title='Hit', artist='Y', duration_seconds=200.0)

        rows = query_in_multiple_months(conn=conn)
        assert len(rows) == 1
        assert rows[0].folder_count == 2


class TestInFolderDuplicates:
    """Clusters of >=2 files in the SAME folder sharing (title, artist, ROUND(duration))."""

    def test_two_files_in_singles_all_same_key_cluster(self, conn):
        _insert(conn=conn, side='singles_all', month_folder=None,
                title='Dup', artist='Band', duration_seconds=200.0,
                file_path='/All/a.mp3')
        _insert(conn=conn, side='singles_all', month_folder=None,
                title='Dup', artist='Band', duration_seconds=200.0,
                file_path='/All/b.mp3')

        rows = query_in_folder_duplicates(conn=conn)
        assert len(rows) == 1
        assert rows[0].dup_count == 2
        assert rows[0].month_folder is None
        assert rows[0].side == 'singles_all'
        assert rows[0].file_paths == ('/All/a.mp3', '/All/b.mp3')

    def test_two_files_in_same_month_cluster(self, conn):
        _insert(conn=conn, side='month', month_folder='2024-06',
                title='Dup', artist='Band', duration_seconds=200.0,
                file_path='/Months/2024-06/a.mp3')
        _insert(conn=conn, side='month', month_folder='2024-06',
                title='Dup', artist='Band', duration_seconds=200.0,
                file_path='/Months/2024-06/b.mp3')

        rows = query_in_folder_duplicates(conn=conn)
        assert len(rows) == 1
        assert rows[0].month_folder == '2024-06'
        assert rows[0].side == 'month'
        assert rows[0].dup_count == 2

    def test_different_months_not_clustered(self, conn):
        _insert(conn=conn, side='month', month_folder='2024-01',
                title='Same', artist='Band', duration_seconds=200.0)
        _insert(conn=conn, side='month', month_folder='2024-02',
                title='Same', artist='Band', duration_seconds=200.0)

        assert query_in_folder_duplicates(conn=conn) == []

    def test_singleton_not_clustered(self, conn):
        _insert(conn=conn, side='singles_all', month_folder=None,
                title='Lone', artist='Band', duration_seconds=200.0)

        assert query_in_folder_duplicates(conn=conn) == []

    def test_different_durations_not_clustered(self, conn):
        _insert(conn=conn, side='month', month_folder='2024-06',
                title='Same', artist='Band', duration_seconds=200.0,
                file_path='/Months/2024-06/x.mp3')
        _insert(conn=conn, side='month', month_folder='2024-06',
                title='Same', artist='Band', duration_seconds=300.0,
                file_path='/Months/2024-06/y.mp3')

        assert query_in_folder_duplicates(conn=conn) == []

    def test_three_in_one_folder_cluster_n_equals_3(self, conn):
        for letter in ('a', 'b', 'c'):
            _insert(conn=conn, side='singles_all', month_folder=None,
                    title='Triple', artist='Band', duration_seconds=200.0,
                    file_path=f'/All/{letter}.mp3')

        rows = query_in_folder_duplicates(conn=conn)
        assert len(rows) == 1
        assert rows[0].dup_count == 3
        assert len(rows[0].file_paths) == 3
        assert rows[0].file_paths == ('/All/a.mp3', '/All/b.mp3', '/All/c.mp3')

    def test_margin_clusters_spread_durations(self, conn):
        # Real-world case: 3 files, same (title, artist), durations 2:48 / 2:51 / 2:51
        # (168 / 171 / 171). ROUND-bucketing split 168 from 171; the duration-sweep
        # with margin>=3 clusters all three.
        for letter, dur in (('a', 168.0), ('b', 171.0), ('c', 171.0)):
            _insert(conn=conn, side='month', month_folder='2023-06',
                    title='Thelo na ta spaso', artist='Band', duration_seconds=dur,
                    file_path=f'/Months/2023-06/{letter}.mp3')

        rows = query_in_folder_duplicates(conn=conn, margin=3.0)
        assert len(rows) == 1
        assert rows[0].dup_count == 3

    def test_margin_too_small_splits_cluster(self, conn):
        # Same three files, margin=1.0: 168 sits alone (gap to 171 is 3 > 1),
        # the two 171s cluster. One reported cluster of 2.
        for letter, dur in (('a', 168.0), ('b', 171.0), ('c', 171.0)):
            _insert(conn=conn, side='month', month_folder='2023-06',
                    title='Thelo na ta spaso', artist='Band', duration_seconds=dur,
                    file_path=f'/Months/2023-06/{letter}.mp3')

        rows = query_in_folder_duplicates(conn=conn, margin=1.0)
        assert len(rows) == 1
        assert rows[0].dup_count == 2
        assert rows[0].file_paths == ('/Months/2023-06/b.mp3', '/Months/2023-06/c.mp3')


class TestRowMappers:
    """Query mappers tolerate NULL columns and substitute sensible defaults."""

    def test_matched_row_handles_null_columns(self, conn):
        conn.execute(
            "INSERT INTO songs (side, file_path, raw_title, raw_artist, "
            "raw_album, year, duration_seconds, "
            "norm_title, norm_artist, norm_album, has_key) VALUES "
            "('singles_all', '/x/a.mp3', 'T', 'A', NULL, NULL, NULL, "
            "'t', 'a', '', 1)"
        )
        rows = query_only_in_all(conn=conn)
        assert len(rows) == 1
        row = rows[0]
        assert row.file_path == '/x/a.mp3'
        assert row.raw_album == ''
        assert row.year == ''
        assert row.duration_seconds == 0.0
        assert row.size_bytes == 0    # column is NOT NULL DEFAULT 0; mapper just round-trips
        assert row.month_folder is None


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


def _make_song(file_path: Path, title: str, artist: str, album: str,
               size_bytes: int = 0, duration_seconds: float = 0.0) -> Any:
    """Build a Song the same way the production code does, but bypass tag-reading."""
    norm_title = normalize(text=title)
    norm_artist = normalize(text=artist)
    key = SongKey(title=norm_title, artist=norm_artist) if norm_title and norm_artist else None
    return Song(
        file_path=file_path, raw_title=title, raw_artist=artist, raw_album=album,
        year='', duration_seconds=duration_seconds, size_bytes=size_bytes, key=key,
    )


def _insert(conn: sqlite3.Connection, side: str, month_folder: str | None,
            title: str, artist: str, album: str = '',
            file_path: str | None = None, size_bytes: int = 0,
            duration_seconds: float = 0.0) -> None:
    """Helper to insert a synthetic row directly via the production insert_song()."""
    if file_path is None:
        # Include month_folder so the same (title, artist) inserted in different
        # months produces distinct file paths (PRIMARY KEY is (side, file_path)).
        slot = month_folder or 'singles'
        file_path = f'/test/{side}/{slot}/{title}_{artist}.mp3'
    song = _make_song(file_path=Path(file_path), title=title, artist=artist, album=album,
                      size_bytes=size_bytes, duration_seconds=duration_seconds)
    insert_song(conn=conn, song=song, side=side, month_folder=month_folder)


def _make_known_epoch() -> float:
    """Return a stable epoch (well in the past so it never collides with 'now')."""
    return time.mktime((2024, 6, 15, 12, 34, 0, 0, 0, -1))


def _write_source(*, root: Path, month_folder: str, name: str, content: bytes = b'src') -> Path:
    """Create a fake month-folder source file and return its full path."""
    folder = root / month_folder
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(content)
    return path


def _matched_row(*, file_path: Path, month_folder: str, raw_title: str = 't',
                 raw_artist: str = 'a', size_bytes: int = 0) -> MatchedRow:
    """Build a MatchedRow with the same shape query_only_in_months produces."""
    return MatchedRow(
        file_path=str(file_path), raw_title=raw_title, raw_artist=raw_artist,
        raw_album='', year='', duration_seconds=0.0, size_bytes=size_bytes,
        month_folder=month_folder,
    )


class TestApplyMissingAction:
    """File-actions module: copy/move semantics + limit + prompt parsing."""

    def test_copy_creates_month_subfolders(self, tmp_path):
        by_month = tmp_path / 'by-month'
        singles_all = tmp_path / 'All'
        src1 = _write_source(root=by_month, month_folder='2024-03', name='song1.mp3')
        src2 = _write_source(root=by_month, month_folder='2024-06 holiday', name='song2.mp3')
        rows = [
            _matched_row(file_path=src1, month_folder='2024-03'),
            _matched_row(file_path=src2, month_folder='2024-06 holiday'),
        ]
        summary = apply_missing_action(
            rows=rows, singles_all_root=singles_all,
            action='copy', target_is_year=False, limit=2,
        )
        assert summary.succeeded == 2
        assert summary.failed == 0
        assert summary.skipped == 0
        assert (singles_all / '2024-03' / 'song1.mp3').exists()
        assert (singles_all / '2024-06 holiday' / 'song2.mp3').exists()
        # Copy preserves sources.
        assert src1.exists()
        assert src2.exists()

    def test_copy_with_target_is_year_groups_by_year(self, tmp_path):
        by_month = tmp_path / 'by-month'
        singles_all = tmp_path / 'All'
        src1 = _write_source(root=by_month, month_folder='2024-03', name='song1.mp3')
        src2 = _write_source(root=by_month, month_folder='2024-06 holiday', name='song2.mp3')
        rows = [
            _matched_row(file_path=src1, month_folder='2024-03'),
            _matched_row(file_path=src2, month_folder='2024-06 holiday'),
        ]
        summary = apply_missing_action(
            rows=rows, singles_all_root=singles_all,
            action='copy', target_is_year=True, limit=2,
        )
        assert summary.succeeded == 2
        # Both files land under All/2024/ (year-only folder).
        assert (singles_all / '2024' / 'song1.mp3').exists()
        assert (singles_all / '2024' / 'song2.mp3').exists()
        assert not (singles_all / '2024-03').exists()

    def test_move_removes_source(self, tmp_path):
        by_month = tmp_path / 'by-month'
        singles_all = tmp_path / 'All'
        src = _write_source(root=by_month, month_folder='2024-03', name='song.mp3')
        rows = [_matched_row(file_path=src, month_folder='2024-03')]
        summary = apply_missing_action(
            rows=rows, singles_all_root=singles_all,
            action='move', target_is_year=False, limit=1,
        )
        assert summary.succeeded == 1
        assert (singles_all / '2024-03' / 'song.mp3').exists()
        assert not src.exists()

    def test_overwrite_replaces_existing_target(self, tmp_path):
        by_month = tmp_path / 'by-month'
        singles_all = tmp_path / 'All'
        src = _write_source(root=by_month, month_folder='2024-03',
                            name='song.mp3', content=b'new')
        target_dir = singles_all / '2024-03'
        target_dir.mkdir(parents=True)
        target_file = target_dir / 'song.mp3'
        target_file.write_bytes(b'old')
        rows = [_matched_row(file_path=src, month_folder='2024-03')]
        summary = apply_missing_action(
            rows=rows, singles_all_root=singles_all,
            action='copy', target_is_year=False, limit=1,
        )
        assert summary.succeeded == 1
        assert target_file.read_bytes() == b'new'

    def test_skips_missing_source(self, tmp_path):
        singles_all = tmp_path / 'All'
        rows = [_matched_row(
            file_path=tmp_path / 'nope' / 'gone.mp3', month_folder='2024-03',
        )]
        summary = apply_missing_action(
            rows=rows, singles_all_root=singles_all,
            action='copy', target_is_year=False, limit=1,
        )
        assert summary.attempted == 1
        assert summary.skipped == 1
        assert summary.succeeded == 0
        assert summary.failed == 0

    def test_limit_picks_alphabetical_first_n(self, tmp_path):
        # Rows passed in shuffled order; sort-by-filename should pick the
        # alphabetically-lowest names regardless of input order.
        by_month = tmp_path / 'by-month'
        singles_all = tmp_path / 'All'
        names = ['zebra.mp3', 'apple.mp3', 'mango.mp3']
        sources = {
            n: _write_source(root=by_month, month_folder='2024-03', name=n)
            for n in names
        }
        rows = [_matched_row(file_path=sources[n], month_folder='2024-03') for n in names]
        summary = apply_missing_action(
            rows=rows, singles_all_root=singles_all,
            action='copy', target_is_year=False, limit=2,
        )
        assert summary.succeeded == 2
        copied = sorted(p.name for p in (singles_all / '2024-03').iterdir())
        assert copied == ['apple.mp3', 'mango.mp3']

    def test_limit_truncates_processing(self, tmp_path):
        by_month = tmp_path / 'by-month'
        singles_all = tmp_path / 'All'
        sources = [
            _write_source(root=by_month, month_folder='2024-03', name=f'song{i}.mp3')
            for i in range(5)
        ]
        rows = [_matched_row(file_path=p, month_folder='2024-03') for p in sources]
        summary = apply_missing_action(
            rows=rows, singles_all_root=singles_all,
            action='copy', target_is_year=False, limit=3,
        )
        assert summary.attempted == 3
        assert summary.succeeded == 3
        copied = sorted((singles_all / '2024-03').iterdir())
        assert [p.name for p in copied] == ['song0.mp3', 'song1.mp3', 'song2.mp3']

    def test_prompt_returns_none_for_n(self, monkeypatch):
        monkeypatch.setattr('builtins.input', lambda *_: 'n')
        result = prompt_action_limit(
            action='copy', row_count=10, total_bytes=0, target_is_year=False)
        assert result is None

    def test_prompt_returns_none_for_empty_input(self, monkeypatch):
        monkeypatch.setattr('builtins.input', lambda *_: '')
        result = prompt_action_limit(
            action='copy', row_count=10, total_bytes=0, target_is_year=False)
        assert result is None

    def test_prompt_returns_row_count_for_all(self, monkeypatch):
        for reply in ('all', 'ALL', '  All  '):
            monkeypatch.setattr('builtins.input', lambda *_, r=reply: r)
            result = prompt_action_limit(
                action='copy', row_count=486, total_bytes=0, target_is_year=False)
            assert result == 486

    def test_prompt_returns_int_for_valid_number(self, monkeypatch):
        monkeypatch.setattr('builtins.input', lambda *_: '10')
        assert prompt_action_limit(
            action='copy', row_count=486, total_bytes=0, target_is_year=False) == 10
        # Above row_count clamps down.
        monkeypatch.setattr('builtins.input', lambda *_: '500')
        assert prompt_action_limit(
            action='copy', row_count=486, total_bytes=0, target_is_year=False) == 486

    def test_prompt_reprompts_on_invalid_input(self, monkeypatch):
        replies = iter(['asdf', '-3', '0', '5'])
        monkeypatch.setattr('builtins.input', lambda *_: next(replies))
        result = prompt_action_limit(
            action='copy', row_count=100, total_bytes=0, target_is_year=False)
        assert result == 5

    def test_prompt_returns_none_on_eof(self, monkeypatch):
        def _raise_eof(*_):
            raise EOFError
        monkeypatch.setattr('builtins.input', _raise_eof)
        result = prompt_action_limit(
            action='copy', row_count=10, total_bytes=0, target_is_year=False)
        assert result is None
