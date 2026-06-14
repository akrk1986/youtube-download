#!/usr/bin/env python3
"""Tests for extract_composer_from_description (Greek composer credit parsing)."""
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from funcs_video_info import extract_composer_from_description  # noqa: E402


class TestExtractComposerFromDescription:
    """Verify composer extraction from Greek video descriptions."""

    def test_simple_label(self):
        """The plain 'Μουσική:' label yields the composer name."""
        assert extract_composer_from_description(
            description='Μουσική: Σταύρος Ξαρχάκος') == 'Σταύρος Ξαρχάκος'

    def test_space_before_colon(self):
        """Whitespace before the colon is tolerated."""
        assert extract_composer_from_description(
            description='Μουσική : Σταύρος Ξαρχάκος') == 'Σταύρος Ξαρχάκος'

    def test_combined_music_lyrics_label(self):
        """The 'Μουσική/Στίχοι:' combined label yields the composer name."""
        assert extract_composer_from_description(
            description='Μουσική/Στίχοι: Νίκος Γκάτσος') == 'Νίκος Γκάτσος'

    def test_combined_label_with_whitespace(self):
        """Whitespace around the slash and colon in the combined label is tolerated."""
        assert extract_composer_from_description(
            description='Μουσική / Στίχοι : Νίκος Γκάτσος') == 'Νίκος Γκάτσος'

    def test_lyrics_music_order(self):
        """The reversed 'Στίχοι/Μουσική:' combined label is also accepted."""
        assert extract_composer_from_description(
            description='Στίχοι/Μουσική: Νίκος Γκάτσος') == 'Νίκος Γκάτσος'

    def test_label_case_insensitive(self):
        """The label matches regardless of letter case."""
        assert extract_composer_from_description(
            description='ΜΟΥΣΙΚΗ: Σταύρος Ξαρχάκος') == 'Σταύρος Ξαρχάκος'

    def test_label_diacritics_insensitive(self):
        """The label matches whether or not it carries diacritics."""
        assert extract_composer_from_description(
            description='Μουσικη: Σταύρος Ξαρχάκος') == 'Σταύρος Ξαρχάκος'

    def test_name_diacritics_preserved(self):
        """The captured composer name keeps its original diacritics."""
        assert extract_composer_from_description(
            description='μουσικη: Μάνος Χατζιδάκις') == 'Μάνος Χατζιδάκις'

    def test_lyrics_only_label_ignored(self):
        """A 'Στίχοι:' (lyrics-only) credit does not set the composer."""
        assert extract_composer_from_description(
            description='Στίχοι: Νίκος Γκάτσος') is None

    def test_trailing_whitespace_trimmed_internal_spaces_kept(self):
        """Trailing whitespace to EOL is trimmed; internal name spaces are preserved."""
        assert extract_composer_from_description(
            description='Μουσική: Μάνος Χατζιδάκις   ') == 'Μάνος Χατζιδάκις'

    def test_multiline_only_music_line_captured(self):
        """Only the 'Μουσική' line is captured; later credit lines are ignored."""
        description = 'Μουσική: Σταύρος Ξαρχάκος\nΣτίχοι: Νίκος Γκάτσος\n'
        assert extract_composer_from_description(description=description) == 'Σταύρος Ξαρχάκος'

    def test_label_amid_other_text(self):
        """The label is found even when surrounded by other description lines."""
        description = 'Από τη συναυλία.\nΜουσική: Μίκης Θεοδωράκης\nΤραγούδι: ...'
        assert extract_composer_from_description(description=description) == 'Μίκης Θεοδωράκης'

    def test_no_label_returns_none(self):
        """A description without the label returns None."""
        assert extract_composer_from_description(
            description='Just a normal description, no credits here.') is None

    def test_empty_description_returns_none(self):
        """An empty description returns None."""
        assert extract_composer_from_description(description='') is None

    def test_blank_name_returns_none(self):
        """A label with no name (only whitespace to EOL) returns None."""
        assert extract_composer_from_description(description='Μουσική:   \n') is None


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
