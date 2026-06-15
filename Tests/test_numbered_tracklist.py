#!/usr/bin/env python3
"""Tests for the numbered-tracklist description parser and CSV chapter resolver."""
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from funcs_video_info.chapters import (  # noqa: E402
    _parse_numbered_tracklist,
    _resolve_csv_chapters,
    create_chapters_csv,
)

# Representative numbered tracklist: includes the no-space '9.Κάνε' form, an overlapping
# start (#2 before #1's end), a corrupt end range (#27), and trailing-period titles.
_TRACKLIST_DESC = (
    '1. Εισαγωγή 00:00 - 05:37\n'
    '2. Έρημα κορμιά 05:28 - 09:46\n'
    '9.Κάνε κάτι να χάσω το τρένο 24:53 - 28:49\n'
    '27. Συνέντευξη 01:09:56 - 01:10 32\n'
    '33. Δικαιώματα. 01:27:49 - 01:32:44\n'
)


class TestParseNumberedTracklist:
    """Verify title-first numbered tracklist parsing."""

    def test_row_count(self):
        """Every numbered line becomes a chapter, including the overlapping/corrupt ones."""
        rows = _parse_numbered_tracklist(description=_TRACKLIST_DESC, video_duration=6000)
        assert len(rows) == 5

    def test_titles_and_starts(self):
        """Titles drop the leading number and start times use the first timestamp."""
        rows = _parse_numbered_tracklist(description=_TRACKLIST_DESC, video_duration=6000)
        assert rows[0] == {'start_time': 0, 'title': 'Εισαγωγή', 'end_time': 328}
        assert rows[1]['title'] == 'Έρημα κορμιά'      # the song YouTube dropped
        assert rows[2]['title'] == 'Κάνε κάτι να χάσω το τρένο'  # no space after '9.'

    def test_corrupt_end_line_uses_start(self):
        """A malformed end range still yields the correct start time."""
        rows = _parse_numbered_tracklist(description=_TRACKLIST_DESC, video_duration=6000)
        assert rows[3] == {'start_time': 4196, 'title': 'Συνέντευξη', 'end_time': 5269}

    def test_trailing_period_stripped_and_last_end_is_duration(self):
        """The last row's title is cleaned and its end time is the video duration."""
        rows = _parse_numbered_tracklist(description=_TRACKLIST_DESC, video_duration=6000)
        assert rows[-1] == {'start_time': 5269, 'title': 'Δικαιώματα', 'end_time': 6000}

    def test_timestamp_first_description_not_parsed(self):
        """A normal timestamp-first description yields no tracklist rows."""
        desc = '00:00 Intro\n05:37 - Chapter Two\n'
        assert _parse_numbered_tracklist(description=desc, video_duration=600) == []


class TestResolveCsvChapters:
    """Verify the CSV chapter-source resolver."""

    @staticmethod
    def _video_info():
        """Build a video_info with native chapters plus a numbered-tracklist description."""
        return {
            'chapters': [{'start_time': 0, 'end_time': 6000, 'title': 'Native'}],
            'description': _TRACKLIST_DESC,
            'duration': 6000,
        }

    def test_json_uses_native(self):
        """'json' source always returns the native chapters."""
        chapters = _resolve_csv_chapters(video_info=self._video_info(), chapter_source='json')
        assert len(chapters) == 1
        assert chapters[0]['title'] == 'Native'

    def test_manual_uses_parsed(self):
        """'manual' source returns the description-parsed tracklist when present."""
        chapters = _resolve_csv_chapters(video_info=self._video_info(), chapter_source='manual')
        assert len(chapters) == 5
        assert chapters[1]['title'] == 'Έρημα κορμιά'

    def test_manual_falls_back_to_native(self, caplog):
        """'manual' falls back to native chapters (with a warning) when no tracklist is found."""
        info = {
            'chapters': [{'start_time': 0, 'end_time': 600, 'title': 'Native'}],
            'description': '00:00 Intro\n05:37 Outro\n',
            'duration': 600,
        }
        chapters = _resolve_csv_chapters(video_info=info, chapter_source='manual')
        assert len(chapters) == 1
        assert chapters[0]['title'] == 'Native'
        assert any('no numbered tracklist' in r.message for r in caplog.records)


class TestCsvDuplicateNames:
    """Verify duplicate song names are made unique and marked SKIP in the CSV."""

    @staticmethod
    def _csv_rows(tmp_path, titles):
        """Write a CSV from chapters with the given titles; return (song_name, comment) pairs."""
        chapters = [{'start_time': i * 60, 'end_time': (i + 1) * 60, 'title': t}
                    for i, t in enumerate(titles)]
        create_chapters_csv(video_info={'chapters': chapters}, output_dir=tmp_path, video_title='T')
        lines = [ln for ln in (tmp_path / 'segments-hms-full.txt').read_text(encoding='utf-8').splitlines()
                 if ln and not ln.startswith('#')]
        cells = [ln.split(',') for ln in lines[1:]]  # skip header
        return [(c[3], c[9]) for c in cells]  # column 3 = song name, column 9 = comment

    def test_repeated_name_suffixed_and_skipped(self, tmp_path):
        """Repeated names get a numbered suffix and SKIP in every occurrence (incl. the 1st)."""
        rows = self._csv_rows(tmp_path, ['Συνέντευξη', 'Βαβέλ', 'Συνέντευξη', 'Συνέντευξη'])
        assert rows == [
            ('Συνέντευξη', 'SKIP'),
            ('Βαβέλ', ''),
            ('Συνέντευξη(01)', 'SKIP'),
            ('Συνέντευξη(02)', 'SKIP'),
        ]

    def test_unique_names_unchanged(self, tmp_path):
        """Distinct names are left as-is with an empty comment."""
        rows = self._csv_rows(tmp_path, ['One', 'Two', 'Three'])
        assert rows == [('One', ''), ('Two', ''), ('Three', '')]

    def test_year_only_on_first_row(self, tmp_path):
        """The year appears only in the first row; later rows use '-'."""
        chapters = [{'start_time': i * 60, 'end_time': (i + 1) * 60, 'title': n}
                    for i, n in enumerate(['One', 'Two', 'Three'])]
        create_chapters_csv(video_info={'chapters': chapters, 'upload_date': '20240115'},
                            output_dir=tmp_path, video_title='T')
        lines = [ln for ln in (tmp_path / 'segments-hms-full.txt').read_text(encoding='utf-8').splitlines()
                 if ln and not ln.startswith('#')]
        years = [ln.split(',')[7] for ln in lines[1:]]  # column 7 = year
        assert years == ['2024', '-', '-']


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
