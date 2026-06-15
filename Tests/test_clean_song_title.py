#!/usr/bin/env python3
"""Tests for _clean_song_title (chapter/song title cleanup for the CSV)."""
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from funcs_video_info.chapters import _clean_song_title  # noqa: E402


class TestCleanSongTitle:
    """Verify leading-sequence and trailing-period cleanup."""

    def test_plain_title_unchanged(self):
        """A plain title with no sequence or trailing period is unchanged."""
        assert _clean_song_title(title='Song Title') == 'Song Title'

    def test_trailing_period_removed(self):
        """A single trailing period is removed."""
        assert _clean_song_title(title='Song Title.') == 'Song Title'

    def test_multiple_trailing_periods_removed(self):
        """All trailing periods (e.g. an ellipsis) are removed."""
        assert _clean_song_title(title='Song Title...') == 'Song Title'

    def test_leading_sequence_with_space(self):
        """A 'NN. ' leading sequence is stripped."""
        assert _clean_song_title(title='01. Song Title') == 'Song Title'

    def test_leading_sequence_no_space(self):
        """A 'N.' leading sequence without a space is stripped."""
        assert _clean_song_title(title='1.Song Title') == 'Song Title'

    def test_leading_sequence_multiple_spaces(self):
        """Extra whitespace after the sequence dot is consumed."""
        assert _clean_song_title(title='12.  Song Title') == 'Song Title'

    def test_sequence_and_trailing_period(self):
        """Both the leading sequence and the trailing period are removed."""
        assert _clean_song_title(title='01. Song Title.') == 'Song Title'

    def test_leading_whitespace_before_sequence(self):
        """Leading whitespace before the sequence number is tolerated."""
        assert _clean_song_title(title='  03. Song Title') == 'Song Title'

    def test_internal_period_kept(self):
        """A non-trailing period (e.g. a version number) is preserved."""
        assert _clean_song_title(title='Song 2.0') == 'Song 2.0'

    def test_non_leading_number_kept(self):
        """A number that is not a leading track sequence is preserved."""
        assert _clean_song_title(title='Track 1 of 5') == 'Track 1 of 5'


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
