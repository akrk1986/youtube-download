"""Unit tests for funcs_check_greek_singles/ package."""
import csv
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from mutagen.flac import FLAC
from mutagen.id3 import APIC, COMM, ID3, ID3NoHeaderError, TALB, TCOM, TDRC, TIT2, TPE1, TRCK
from mutagen.mp4 import MP4

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from funcs_check_greek_singles.audio_reader import (  # noqa: E402
    MONTH_FOLDER_RE, iter_month_folders, parse_month_arg,
)
from funcs_check_greek_singles.config import (  # noqa: E402
    DURATION_MATCH_MARGIN_SECONDS, VERDICT_DUPLICATE, VERDICT_ORIGINAL,
)
from funcs_check_greek_singles.database import (  # noqa: E402
    SCHEMA_DDL,
    insert_song,
    query_cross_month_duplicates, query_in_folder_duplicates,
    query_in_multiple_months, query_only_in_all,
    query_only_in_months, query_untagged,
)
from funcs_check_greek_singles.file_actions import (  # noqa: E402
    apply_missing_action, cluster_is_fully_judged, next_group_number, parse_group_range,
    process_inspected, prompt_action_limit, stage_duplicates, unstage_all,
)
from funcs_check_greek_singles.models import (  # noqa: E402
    InFolderDupMember, MatchedRow, Song, SongKey, StagingGroup,
)
from funcs_check_greek_singles.normalize import (  # noqa: E402
    extract_year, format_duration, normalize,
)
from funcs_check_greek_singles.report import _format_size  # noqa: E402
from funcs_check_greek_singles.state_tag import (  # noqa: E402
    VERDICT_AMBIGUOUS, VERDICT_PENDING,
    build_origin_marker, classify_verdict, clear_state, parse_origin,
    read_deletion_tags, read_state, write_state,
)
from funcs_check_greek_singles.verify_groups import (  # noqa: E402
    STATUS_EMPTY, STATUS_MISGROUPED, STATUS_OK, STATUS_SINGLETON, STATUS_UNTAGGED,
    classify_group, verify_staging_dir,
)
from funcs_check_greek_singles.inspect_groups import (  # noqa: E402
    InspectFile, InspectGroup, _group_letter, build_collage, iter_files,
    load_groups, read_cover_art, set_verdict,
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


class TestCrossMonthDuplicates:
    """Pool month folders across a range; cluster by (title, artist, dur-within-margin)."""

    def test_same_song_two_months_clusters(self, conn):
        _insert(conn=conn, side='month', month_folder='2021-03',
                title='Recur', artist='Band', duration_seconds=200.0,
                file_path='/Months/2021-03/x.mp3')
        _insert(conn=conn, side='month', month_folder='2021-07',
                title='Recur', artist='Band', duration_seconds=200.0,
                file_path='/Months/2021-07/y.mp3')

        rows = query_cross_month_duplicates(conn=conn)
        assert len(rows) == 1
        assert rows[0].dup_count == 2
        assert rows[0].distinct_months == 2

    def test_within_and_across_months_merge(self, conn):
        _insert(conn=conn, side='month', month_folder='2021-03',
                title='Recur', artist='Band', duration_seconds=200.0,
                file_path='/Months/2021-03/a.mp3')
        _insert(conn=conn, side='month', month_folder='2021-03',
                title='Recur', artist='Band', duration_seconds=200.0,
                file_path='/Months/2021-03/b.mp3')
        _insert(conn=conn, side='month', month_folder='2021-07',
                title='Recur', artist='Band', duration_seconds=200.0,
                file_path='/Months/2021-07/c.mp3')

        rows = query_cross_month_duplicates(conn=conn)
        assert len(rows) == 1
        assert rows[0].dup_count == 3
        assert rows[0].distinct_months == 2

    def test_singleton_not_clustered(self, conn):
        _insert(conn=conn, side='month', month_folder='2021-03',
                title='Lone', artist='Band', duration_seconds=200.0)

        assert query_cross_month_duplicates(conn=conn) == []

    def test_durations_beyond_margin_not_clustered(self, conn):
        _insert(conn=conn, side='month', month_folder='2021-03',
                title='Same', artist='Band', duration_seconds=200.0,
                file_path='/Months/2021-03/x.mp3')
        _insert(conn=conn, side='month', month_folder='2021-07',
                title='Same', artist='Band',
                duration_seconds=200.0 + DURATION_MATCH_MARGIN_SECONDS + 1.0,
                file_path='/Months/2021-07/y.mp3')

        assert query_cross_month_duplicates(conn=conn) == []

    def test_durations_within_margin_cluster(self, conn):
        delta = DURATION_MATCH_MARGIN_SECONDS / 2
        _insert(conn=conn, side='month', month_folder='2021-03',
                title='Same', artist='Band', duration_seconds=200.0,
                file_path='/Months/2021-03/x.mp3')
        _insert(conn=conn, side='month', month_folder='2021-07',
                title='Same', artist='Band', duration_seconds=200.0 + delta,
                file_path='/Months/2021-07/y.mp3')

        rows = query_cross_month_duplicates(conn=conn)
        assert len(rows) == 1
        assert rows[0].dup_count == 2

    def test_singles_all_excluded(self, conn):
        # A singles-all copy + one month copy of the same key -> no cross-month cluster
        # (cross-month pools the month side only).
        _insert(conn=conn, side='singles_all', month_folder=None,
                title='Same', artist='Band', duration_seconds=200.0,
                file_path='/All/x.mp3')
        _insert(conn=conn, side='month', month_folder='2021-03',
                title='Same', artist='Band', duration_seconds=200.0,
                file_path='/Months/2021-03/y.mp3')

        assert query_cross_month_duplicates(conn=conn) == []


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


class TestStateTagParsing:
    """parse_origin() / classify_verdict() / build_origin_marker() — pure, no audio files."""

    def test_origin_marker_roundtrips(self):
        rel = '03-Singles-by-Month/2021-03/Song.mp3'
        assert parse_origin(value=build_origin_marker(origin_relpath=rel)) == rel

    def test_origin_path_with_spaces(self):
        value = 'DUPE-ORIGIN[03-Singles-by-Month/2025-11-Nykhta Stasou/My Song.flac]'
        assert parse_origin(value=value) == '03-Singles-by-Month/2025-11-Nykhta Stasou/My Song.flac'

    def test_origin_none_without_marker(self):
        assert parse_origin(value='Some Artist') is None
        assert parse_origin(value='') is None

    def test_verdict_pending_when_empty(self):
        assert classify_verdict(value='') == VERDICT_PENDING

    def test_verdict_duplicate(self):
        assert classify_verdict(value='duplicate') == VERDICT_DUPLICATE

    def test_verdict_original_case_insensitive(self):
        assert classify_verdict(value='original') == VERDICT_ORIGINAL
        assert classify_verdict(value='  ORIGINAL ') == VERDICT_ORIGINAL

    def test_verdict_duplicate_abbreviations(self):
        for token in ('d', 'dup', 'dupe', 'duplicate', 'DUP', 'D', ' Dupe '):
            assert classify_verdict(value=token) == VERDICT_DUPLICATE

    def test_verdict_original_abbreviations(self):
        for token in ('o', 'orig', 'original', 'ORIG', 'O', ' Orig '):
            assert classify_verdict(value=token) == VERDICT_ORIGINAL

    def test_verdict_free_text_is_ambiguous(self):
        # 'not a duplicate' contains 'duplicate' but is not an exact token;
        # partial stems ('dupl', 'origi') are not accepted either.
        assert classify_verdict(value='not a duplicate') == VERDICT_AMBIGUOUS
        assert classify_verdict(value='maybe') == VERDICT_AMBIGUOUS
        assert classify_verdict(value='dupl') == VERDICT_AMBIGUOUS
        assert classify_verdict(value='origi') == VERDICT_AMBIGUOUS


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg not available')
class TestStateTagIO:
    """Origin (Album Artist) and verdict (Copyright) round-trip independently; mtime preserved."""

    @staticmethod
    def _make_audio(path: Path) -> None:
        """Generate a tiny silent audio file via ffmpeg (codec inferred from suffix)."""
        subprocess.run(
            ['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono',
             '-t', '0.3', '-y', str(path)],
            check=True, capture_output=True, encoding='utf-8', errors='replace',
        )

    @pytest.mark.parametrize('ext', ['mp3', 'm4a', 'flac'])
    def test_origin_and_verdict_are_independent(self, tmp_path, ext):
        audio = tmp_path / f'song.{ext}'
        self._make_audio(path=audio)
        assert read_state(file_path=audio, field='origin') == ''
        assert read_state(file_path=audio, field='verdict') == ''

        marker = build_origin_marker(origin_relpath=f'03-Singles-by-Month/2021-03/song.{ext}')
        write_state(file_path=audio, value=marker, field='origin')
        write_state(file_path=audio, value='original', field='verdict')

        assert parse_origin(value=read_state(file_path=audio, field='origin')) == \
            f'03-Singles-by-Month/2021-03/song.{ext}'
        assert classify_verdict(value=read_state(file_path=audio, field='verdict')) == VERDICT_ORIGINAL

        # Clearing one field leaves the other intact.
        clear_state(file_path=audio, field='origin')
        assert read_state(file_path=audio, field='origin') == ''
        assert classify_verdict(value=read_state(file_path=audio, field='verdict')) == VERDICT_ORIGINAL
        clear_state(file_path=audio, field='verdict')
        assert read_state(file_path=audio, field='verdict') == ''

    @pytest.mark.parametrize('ext', ['mp3', 'm4a', 'flac'])
    def test_writes_and_clears_preserve_mtime(self, tmp_path, ext):
        audio = tmp_path / f'song.{ext}'
        self._make_audio(path=audio)
        old = _make_known_epoch()
        os.utime(audio, (old, old))

        write_state(file_path=audio, value=build_origin_marker(origin_relpath=f'x/y.{ext}'), field='origin')
        write_state(file_path=audio, value='duplicate', field='verdict')
        assert audio.stat().st_mtime == pytest.approx(old, abs=2)

        clear_state(file_path=audio, field='origin')
        clear_state(file_path=audio, field='verdict')
        assert audio.stat().st_mtime == pytest.approx(old, abs=2)


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg not available')
class TestStageAndInspect:
    """stage_duplicates / process_inspected file moves + tag state (real files)."""

    @staticmethod
    def _audio(path: Path) -> None:
        """Generate a tiny silent audio file via ffmpeg under path (parents created)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono',
             '-t', '0.3', '-y', str(path)],
            check=True, capture_output=True, encoding='utf-8', errors='replace',
        )

    def test_staging_creates_group_folder_and_preserves_verdict(self, tmp_path):
        root = tmp_path / 'Music'
        first = root / '03-Singles-by-Month' / '2021-03' / 'song.mp3'
        second = root / '03-Singles-by-Month' / '2021-07' / 'song.mp3'
        self._audio(path=first)
        self._audio(path=second)
        write_state(file_path=first, value='original', field='verdict')  # user-set, must survive
        members = (
            InFolderDupMember(file_path=str(first), month_folder='2021-03',
                              raw_album='', duration_seconds=1.0),
            InFolderDupMember(file_path=str(second), month_folder='2021-07',
                              raw_album='', duration_seconds=1.0),
        )
        group = StagingGroup(number=1, raw_title='Song', raw_artist='Artist', members=members)
        staging = root / 'Staging-Dupes'

        summary = stage_duplicates(groups=[group], root=root, staging_dir=staging, dry_run=False)

        assert summary.staged == 2
        grp_dir = staging / 'grp-0001'
        staged = sorted(grp_dir.iterdir())
        assert len(staged) == 2
        for path in staged:
            assert parse_origin(value=read_state(file_path=path, field='origin')) is not None
        # the script never touches the verdict -- the pre-set 'original' survives.
        verdicts = {classify_verdict(value=read_state(file_path=p, field='verdict')) for p in staged}
        assert VERDICT_ORIGINAL in verdicts

    def test_next_group_number(self, tmp_path):
        staging = tmp_path / 'Staging-Dupes'
        assert next_group_number(staging_dir=staging) == 1   # missing dir
        staging.mkdir()
        (staging / 'grp-0003').mkdir()
        (staging / 'grp-0007').mkdir()
        (staging / 'not-a-group').mkdir()
        assert next_group_number(staging_dir=staging) == 8

    def test_cluster_is_fully_judged(self, tmp_path):
        first = tmp_path / 'a.mp3'
        second = tmp_path / 'b.mp3'
        self._audio(path=first)
        self._audio(path=second)
        write_state(file_path=first, value='original', field='verdict')
        write_state(file_path=second, value='original', field='verdict')
        members = (
            InFolderDupMember(file_path=str(first), month_folder='2021-03',
                              raw_album='', duration_seconds=1.0),
            InFolderDupMember(file_path=str(second), month_folder='2021-07',
                              raw_album='', duration_seconds=1.0),
        )
        assert cluster_is_fully_judged(members=members) is True
        # One member left unmarked -> the cluster is not fully judged -> staged.
        clear_state(file_path=second, field='verdict')
        assert cluster_is_fully_judged(members=members) is False

    def test_post_inspection_by_group_range(self, tmp_path):
        root = tmp_path / 'Music'
        staging = root / 'Staging-Dupes'
        dupes = root / 'Dupes'
        dup = staging / 'grp-0001' / '2021-03 — x.mp3'
        keeper = staging / 'grp-0002' / '2021-07 — y.mp3'
        self._audio(path=dup)
        self._audio(path=keeper)
        write_state(file_path=dup, field='origin',
                    value=build_origin_marker(origin_relpath='03-Singles-by-Month/2021-03/x.mp3'))
        write_state(file_path=dup, value='duplicate', field='verdict')
        write_state(file_path=keeper, field='origin',
                    value=build_origin_marker(origin_relpath='03-Singles-by-Month/2021-07/y.mp3'))
        write_state(file_path=keeper, value='original', field='verdict')

        # Process only grp-0002.
        summary = process_inspected(staging_dir=staging, root=root, dupes_dir=dupes,
                                    group_range=(2, 2), dry_run=False)
        assert summary.restored == 1 and summary.moved_to_dupes == 0
        assert (root / '03-Singles-by-Month' / '2021-07' / 'y.mp3').is_file()
        assert not (staging / 'grp-0002').exists()           # emptied -> removed
        assert (staging / 'grp-0001').exists() and dup.exists()  # out of range -> untouched

        # Now process the rest (no range).
        summary2 = process_inspected(staging_dir=staging, root=root, dupes_dir=dupes,
                                     group_range=None, dry_run=False)
        assert summary2.moved_to_dupes == 1
        assert (dupes / '2021-03 — x.mp3').is_file()
        assert not (staging / 'grp-0001').exists()

    def test_unstage_by_group_range(self, tmp_path):
        root = tmp_path / 'Music'
        staging = root / 'Staging-Dupes'
        in_range = staging / 'grp-0001' / '2021-03 — a.mp3'
        out_range = staging / 'grp-0002' / '2021-07 — b.mp3'
        self._audio(path=in_range)
        self._audio(path=out_range)
        write_state(file_path=in_range, field='origin',
                    value=build_origin_marker(origin_relpath='03-Singles-by-Month/2021-03/a.mp3'))
        write_state(file_path=out_range, field='origin',
                    value=build_origin_marker(origin_relpath='03-Singles-by-Month/2021-07/b.mp3'))

        summary = unstage_all(staging_dir=staging, root=root, group_range=(1, 1), dry_run=False)

        assert summary.restored == 1
        assert (root / '03-Singles-by-Month' / '2021-03' / 'a.mp3').is_file()
        assert not (staging / 'grp-0001').exists()
        assert (staging / 'grp-0002').exists() and out_range.exists()  # out of range -> untouched


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg not available')
class TestDeletionLog:
    """read_deletion_tags round-trip + the deletion log appended on duplicate milk-runs."""

    @staticmethod
    def _audio(path: Path) -> None:
        """Generate a tiny silent audio file via ffmpeg under path (parents created)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono',
             '-t', '0.3', '-y', str(path)],
            check=True, capture_output=True, encoding='utf-8', errors='replace',
        )

    @staticmethod
    def _write_descriptive_tags(path: Path, *, title: str, artist: str, album: str,
                                year: str, track: str, composer: str, comment: str) -> None:
        """Write the 7 deletion-log tags to a real audio file (per format)."""
        suffix = path.suffix.lower()
        if suffix == '.mp3':
            try:
                id3 = ID3(path)
            except ID3NoHeaderError:
                id3 = ID3()
            id3.setall('TIT2', [TIT2(encoding=3, text=[title])])
            id3.setall('TPE1', [TPE1(encoding=3, text=[artist])])
            id3.setall('TALB', [TALB(encoding=3, text=[album])])
            id3.setall('TDRC', [TDRC(encoding=3, text=[year])])
            id3.setall('TRCK', [TRCK(encoding=3, text=[track])])
            id3.setall('TCOM', [TCOM(encoding=3, text=[composer])])
            id3.setall('COMM', [COMM(encoding=3, lang='eng', desc='', text=[comment])])
            id3.save(path, v2_version=3)
            return
        if suffix == '.m4a':
            mp4 = MP4(path)
            mp4['\xa9nam'] = [title]
            mp4['\xa9ART'] = [artist]
            mp4['\xa9alb'] = [album]
            mp4['\xa9day'] = [year]
            mp4['trkn'] = [(int(track), 0)]
            mp4['\xa9wrt'] = [composer]
            mp4['\xa9cmt'] = [comment]
            mp4.save()
            return
        flac = FLAC(path)
        flac['title'] = [title]
        flac['artist'] = [artist]
        flac['album'] = [album]
        flac['date'] = [year]
        flac['tracknumber'] = [track]
        flac['composer'] = [composer]
        flac['comment'] = [comment]
        flac.save()

    def _stage_dupe(self, *, staging: Path, grp: str, name: str,
                    url: str, verdict: str) -> Path:
        """Create a staged file with descriptive tags, an origin marker, and a verdict."""
        path = staging / grp / name
        self._audio(path=path)
        self._write_descriptive_tags(
            path=path, title='T', artist='A', album='Al', year='2021',
            track='1', composer='C', comment=url)
        write_state(file_path=path, field='origin',
                    value=build_origin_marker(origin_relpath=f'03-Singles-by-Month/2021-03/{name}'))
        write_state(file_path=path, value=verdict, field='verdict')
        return path

    @pytest.mark.parametrize('ext', ['mp3', 'm4a', 'flac'])
    def test_read_deletion_tags_roundtrip(self, tmp_path, ext):
        audio = tmp_path / f'song.{ext}'
        self._audio(path=audio)
        self._write_descriptive_tags(
            path=audio, title='Τίτλος', artist='Καλλιτέχνης', album='Άλμπουμ',
            year='2021', track='5', composer='Συνθέτης', comment='https://youtu.be/xyz')
        tags = read_deletion_tags(file_path=audio)
        assert tags == {
            'title': 'Τίτλος', 'artist': 'Καλλιτέχνης', 'album': 'Άλμπουμ',
            'year': '2021', 'track': '5', 'composer': 'Συνθέτης',
            'comment': 'https://youtu.be/xyz',
        }

    @pytest.mark.parametrize('ext', ['mp3', 'm4a', 'flac'])
    def test_read_deletion_tags_blank_when_absent(self, tmp_path, ext):
        audio = tmp_path / f'bare.{ext}'
        self._audio(path=audio)
        tags = read_deletion_tags(file_path=audio)
        assert set(tags) == {'title', 'artist', 'album', 'year', 'track', 'composer', 'comment'}
        assert all(value == '' for value in tags.values())

    def test_duplicate_milkrun_appends_row_with_url(self, tmp_path):
        root = tmp_path / 'Music'
        staging = root / 'Staging-Dupes'
        log = tmp_path / 'Logs' / 'dupes-deleted-log.csv'
        self._stage_dupe(staging=staging, grp='grp-0001', name='x.mp3',
                         url='https://youtu.be/abc123', verdict='duplicate')

        summary = process_inspected(staging_dir=staging, root=root, dupes_dir=root / 'Dupes',
                                    group_range=None, dry_run=False, dupes_log=log)

        assert summary.moved_to_dupes == 1
        assert log.is_file()
        rows = list(csv.DictReader(log.open(encoding='utf-8')))
        assert len(rows) == 1
        assert rows[0]['comment'] == 'https://youtu.be/abc123'
        assert rows[0]['title'] == 'T'
        assert rows[0]['track'] == '1'
        assert rows[0]['logged_at']                      # timestamp present

    def test_dry_run_writes_no_row(self, tmp_path):
        root = tmp_path / 'Music'
        staging = root / 'Staging-Dupes'
        log = tmp_path / 'Logs' / 'dupes-deleted-log.csv'
        dup = self._stage_dupe(staging=staging, grp='grp-0001', name='x.mp3',
                               url='https://youtu.be/abc123', verdict='duplicate')

        summary = process_inspected(staging_dir=staging, root=root, dupes_dir=root / 'Dupes',
                                    group_range=None, dry_run=True, dupes_log=log)

        assert summary.moved_to_dupes == 1
        assert not log.exists()                          # preview only
        assert dup.exists()                              # not moved

    def test_original_writes_no_row(self, tmp_path):
        root = tmp_path / 'Music'
        staging = root / 'Staging-Dupes'
        log = tmp_path / 'Logs' / 'dupes-deleted-log.csv'
        self._stage_dupe(staging=staging, grp='grp-0001', name='x.mp3',
                         url='https://youtu.be/abc123', verdict='original')

        summary = process_inspected(staging_dir=staging, root=root, dupes_dir=root / 'Dupes',
                                    group_range=None, dry_run=False, dupes_log=log)

        assert summary.restored == 1 and summary.moved_to_dupes == 0
        assert not log.exists()

    def test_log_appends_across_runs_with_single_header(self, tmp_path):
        root = tmp_path / 'Music'
        staging = root / 'Staging-Dupes'
        dupes = root / 'Dupes'
        log = tmp_path / 'Logs' / 'dupes-deleted-log.csv'

        self._stage_dupe(staging=staging, grp='grp-0001', name='x.mp3',
                         url='https://youtu.be/one', verdict='duplicate')
        process_inspected(staging_dir=staging, root=root, dupes_dir=dupes,
                          group_range=(1, 1), dry_run=False, dupes_log=log)
        self._stage_dupe(staging=staging, grp='grp-0002', name='y.mp3',
                         url='https://youtu.be/two', verdict='duplicate')
        process_inspected(staging_dir=staging, root=root, dupes_dir=dupes,
                          group_range=(2, 2), dry_run=False, dupes_log=log)

        header_lines = [ln for ln in log.read_text(encoding='utf-8').splitlines()
                        if ln.startswith('logged_at')]
        assert len(header_lines) == 1
        rows = list(csv.DictReader(log.open(encoding='utf-8')))
        assert len(rows) == 2
        assert {r['comment'] for r in rows} == {'https://youtu.be/one', 'https://youtu.be/two'}


class TestStagingGroupHelpers:
    """parse_group_range() validation + StagingGroup.folder_name (pure)."""

    def test_parse_group_range_ok(self):
        assert parse_group_range(value='7,10') == (7, 10)
        assert parse_group_range(value='7,7') == (7, 7)

    @pytest.mark.parametrize('value', ['10,7', '5', 'a,b', '1,2,3', '0,3', ''])
    def test_parse_group_range_rejects(self, value):
        with pytest.raises(ValueError):
            parse_group_range(value=value)

    def test_staging_group_folder_name(self):
        group = StagingGroup(number=7, raw_title='t', raw_artist='a', members=())
        assert group.folder_name == 'grp-0007'


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


class TestVerifyGroups:
    """classify_group() status precedence + verify_staging_dir() folder scan."""

    @staticmethod
    def _song(title: str, artist: str, name: str = 'x.mp3', dur: float = 180.0) -> Song:
        """Build a Song with a normalized key (None when title or artist is blank)."""
        norm_title, norm_artist = normalize(text=title), normalize(text=artist)
        key = SongKey(title=norm_title, artist=norm_artist) if norm_title and norm_artist else None
        return Song(file_path=Path(name), raw_title=title, raw_artist=artist, raw_album='',
                    year='', duration_seconds=dur, size_bytes=0, key=key)

    @staticmethod
    def _audio_with_tags(path: Path, *, title: str, artist: str) -> None:
        """Create a tiny silent mp3 under path and set its title/artist tags."""
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono',
             '-t', '0.3', '-y', str(path)],
            check=True, capture_output=True, encoding='utf-8', errors='replace',
        )
        try:
            id3 = ID3(path)
        except ID3NoHeaderError:
            id3 = ID3()
        id3.setall('TIT2', [TIT2(encoding=3, text=[title])])
        id3.setall('TPE1', [TPE1(encoding=3, text=[artist])])
        id3.save(path, v2_version=3)

    def test_ok_single_song_two_copies(self):
        songs = [self._song(title='Καημός', artist='Χάρις Αλεξίου', name='a.mp3'),
                 self._song(title='καημος', artist='χαρις αλεξιου', name='b.mp3')]
        report = classify_group(name='grp-0001', songs=songs)
        assert report.status == STATUS_OK
        assert report.is_ok
        assert len(report.distinct_keys) == 1

    def test_misgrouped_two_different_songs(self):
        songs = [self._song(title='Κυριακή σε είχα βρει', artist='Ρία Ελληνίδου', name='a.mp3'),
                 self._song(title='Λες και κράταγες μαχαίρια', artist='Ρία Ελληνίδου', name='b.mp3')]
        report = classify_group(name='grp-0002', songs=songs)
        assert report.status == STATUS_MISGROUPED
        assert not report.is_ok
        assert len(report.distinct_keys) == 2

    def test_singleton(self):
        report = classify_group(name='grp-0003', songs=[self._song(title='Solo', artist='X')])
        assert report.status == STATUS_SINGLETON

    def test_empty(self):
        report = classify_group(name='grp-0004', songs=[])
        assert report.status == STATUS_EMPTY
        assert report.distinct_keys == ()

    def test_untagged_when_key_missing(self):
        songs = [self._song(title='Tagged', artist='X', name='a.mp3'),
                 self._song(title='', artist='', name='b.mp3')]
        report = classify_group(name='grp-0005', songs=songs)
        assert report.status == STATUS_UNTAGGED

    def test_misgrouped_takes_precedence_over_untagged(self):
        songs = [self._song(title='Song A', artist='X', name='a.mp3'),
                 self._song(title='Song B', artist='X', name='b.mp3'),
                 self._song(title='', artist='', name='c.mp3')]
        report = classify_group(name='grp-0006', songs=songs)
        assert report.status == STATUS_MISGROUPED

    @pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg not available')
    def test_verify_staging_dir_flags_misgrouped(self, tmp_path):
        staging = tmp_path / 'Staging-Dupes'
        self._audio_with_tags(staging / 'grp-0001' / '2021-03 — a.mp3',
                              title='Same Song', artist='Artist')
        self._audio_with_tags(staging / 'grp-0001' / '2021-06 — b.mp3',
                              title='same song', artist='artist')
        self._audio_with_tags(staging / 'grp-0002' / '2021-03 — c.mp3',
                              title='Song One', artist='Artist')
        self._audio_with_tags(staging / 'grp-0002' / '2021-06 — d.mp3',
                              title='Song Two', artist='Artist')

        reports = verify_staging_dir(staging_dir=staging)

        assert [report.name for report in reports] == ['grp-0001', 'grp-0002']  # number-sorted
        by_name = {report.name: report for report in reports}
        assert by_name['grp-0001'].status == STATUS_OK
        assert by_name['grp-0002'].status == STATUS_MISGROUPED
        assert len(by_name['grp-0002'].distinct_keys) == 2


class TestInspectGroups:
    """inspect_groups: cover-art read, group loading/labelling, collage, verdict write."""

    @staticmethod
    def _png_bytes() -> bytes:
        """Return a tiny valid PNG image as bytes (for embedded cover art / collage cells)."""
        from io import BytesIO

        from PIL import Image
        buffer = BytesIO()
        Image.new('RGB', (4, 4), color=(10, 120, 200)).save(buffer, format='PNG')
        return buffer.getvalue()

    @staticmethod
    def _audio(path: Path, *, title: str, artist: str, art: bytes | None = None,
               composer: str = '') -> None:
        """Create a tiny silent mp3 with title/artist (+ optional composer/art) tags."""
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono',
             '-t', '0.3', '-y', str(path)],
            check=True, capture_output=True, encoding='utf-8', errors='replace',
        )
        try:
            id3 = ID3(path)
        except ID3NoHeaderError:
            id3 = ID3()
        id3.setall('TIT2', [TIT2(encoding=3, text=[title])])
        id3.setall('TPE1', [TPE1(encoding=3, text=[artist])])
        if composer:
            id3.setall('TCOM', [TCOM(encoding=3, text=[composer])])
        if art is not None:
            id3.setall('APIC', [APIC(encoding=3, mime='image/png', type=3, desc='', data=art)])
        id3.save(path, v2_version=3)

    @staticmethod
    def _song(name: str) -> Song:
        """Build a minimal tagged Song for constructing InspectFiles directly."""
        return Song(file_path=Path(name), raw_title='T', raw_artist='A', raw_album='',
                    year='', duration_seconds=180.0, size_bytes=0,
                    key=SongKey(title='t', artist='a'))

    def test_group_letter(self):
        assert _group_letter(index=0) == 'A'
        assert _group_letter(index=25) == 'Z'
        assert _group_letter(index=26) == 'AA'

    @pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg not available')
    def test_read_cover_art_present_and_absent(self, tmp_path):
        with_art, without = tmp_path / 'a.mp3', tmp_path / 'b.mp3'
        self._audio(with_art, title='T', artist='A', art=self._png_bytes())
        self._audio(without, title='T', artist='A')
        assert read_cover_art(path=with_art) is not None
        assert read_cover_art(path=without) is None

    @pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg not available')
    def test_load_groups_labels_art_and_verdict(self, tmp_path):
        staging = tmp_path / 'Staging-Dupes'
        png = self._png_bytes()
        self._audio(staging / 'grp-0008' / 'a1.mp3', title='Song A', artist='X', art=png,
                    composer='Composer X')
        self._audio(staging / 'grp-0008' / 'a2.mp3', title='Song A', artist='X')
        self._audio(staging / 'grp-0009' / 'b1.mp3', title='Song B', artist='Y', art=png)
        self._audio(staging / 'grp-0009' / 'b2.mp3', title='Song B', artist='Y', art=png)
        self._audio(staging / 'grp-0009' / 'b3.mp3', title='Song B', artist='Y')
        write_state(file_path=staging / 'grp-0008' / 'a2.mp3', value='d', field='verdict')

        groups = load_groups(staging_dir=staging, group_range=(8, 9))

        assert [group.name for group in groups] == ['grp-0008', 'grp-0009']
        assert [group.letter for group in groups] == ['A', 'B']
        files = iter_files(groups=groups)
        assert [file.label for file in files] == ['A1', 'A2', 'B1', 'B2', 'B3']
        by_label = {file.label: file for file in files}
        assert by_label['A1'].has_art and not by_label['A2'].has_art
        assert by_label['A1'].composer == 'Composer X' and by_label['A2'].composer == ''
        assert by_label['A2'].current_verdict == VERDICT_DUPLICATE
        assert by_label['A1'].current_verdict == VERDICT_PENDING

    def test_build_collage_writes_png(self, tmp_path):
        png = self._png_bytes()
        group = InspectGroup(name='grp-0008', letter='A', files=(
            InspectFile(path=Path('a1.mp3'), label='A1', group_name='grp-0008',
                        song=self._song(name='a1.mp3'), composer='', comment='', art=png,
                        current_verdict=VERDICT_PENDING),
            InspectFile(path=Path('a2.mp3'), label='A2', group_name='grp-0008',
                        song=self._song(name='a2.mp3'), composer='', comment='', art=None,
                        current_verdict=VERDICT_PENDING),
        ))
        out = tmp_path / 'collage.png'
        result = build_collage(groups=[group], out_path=out)
        assert result == out
        assert out.is_file() and out.stat().st_size > 0

    @pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg not available')
    def test_set_verdict_roundtrip(self, tmp_path):
        path = tmp_path / 'x.mp3'
        self._audio(path, title='T', artist='A')
        set_verdict(file_path=path, verdict=VERDICT_DUPLICATE)
        assert classify_verdict(value=read_state(file_path=path, field='verdict')) == VERDICT_DUPLICATE
        clear_state(file_path=path, field='verdict')
        assert classify_verdict(value=read_state(file_path=path, field='verdict')) == VERDICT_PENDING
