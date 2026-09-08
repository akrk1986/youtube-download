#!/usr/bin/env python3
"""Tests for _strip_engagement_prefix (Facebook's '<n> views <m> reactions ' title prefix)."""
import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from funcs_for_main_yt_dlp._download_common import _strip_engagement_prefix  # noqa: E402

FB_TITLE_VASILIKI = ('17K views · 376 reactions | Vasiliki Stefanou / Βασιλική Στεφάνου ~ '
                     'Στην υγειά μας ρε παιδιά - 12/06/2021 | World Greek Radio')
FB_TITLE_MARIANNA = ('40K views · 1.4K reactions | Μαριάννα Παπαμακαρίου/Marianna Papamakariou - '
                     'Το καυγαδάκι | World Greek Radio')


class TestStripEngagementPrefix:
    """Verify the '<count> views<sep><count> reactions<sep>' prefix is removed, and only that."""

    def test_real_facebook_title(self):
        """The prefix goes and the real title survives from its first character."""
        assert _strip_engagement_prefix(title=FB_TITLE_VASILIKI).startswith('Vasiliki Stefanou /')

    def test_real_facebook_title_greek(self):
        """A Greek title is stripped the same way."""
        assert _strip_engagement_prefix(title=FB_TITLE_MARIANNA).startswith('Μαριάννα Παπαμακαρίου')

    def test_already_sanitized_separators(self):
        """A title whose separators are already spaces is still stripped."""
        assert _strip_engagement_prefix(title='17K views 376 reactions Real Title') == 'Real Title'

    def test_comma_grouped_count(self):
        """A comma-grouped count (1,234) is recognised."""
        assert _strip_engagement_prefix(title='1,234 views · 5 reactions | Real Title') == 'Real Title'

    def test_decimal_and_million_suffix(self):
        """Decimal and M-suffixed counts are recognised."""
        assert _strip_engagement_prefix(title='2.3M views · 1.4K reactions | Real Title') == 'Real Title'

    def test_singular_forms(self):
        """Singular 'view' and 'reaction' are recognised."""
        assert _strip_engagement_prefix(title='1 view · 1 reaction | Real Title') == 'Real Title'

    def test_uppercase(self):
        """Matching is case-insensitive (the inline (?i) in the pattern)."""
        assert _strip_engagement_prefix(title='17K VIEWS · 376 REACTIONS | Real Title') == 'Real Title'

    def test_no_spaces_around_separators(self):
        """Separators without surrounding spaces are consumed."""
        assert _strip_engagement_prefix(title='17K views·376 reactions|Real Title') == 'Real Title'

    def test_en_dash_separator(self):
        """An en-dash separator is consumed along with the prefix."""
        assert _strip_engagement_prefix(title='2.3M views · 4 reactions – Real Title') == 'Real Title'

    def test_views_without_reactions_untouched(self):
        """Both counters are required: a views-only prefix is left alone."""
        title = '2.3M views | Only views here'
        assert _strip_engagement_prefix(title=title) == title

    def test_reactions_without_views_untouched(self):
        """Both counters are required: a reactions-only prefix is left alone."""
        title = '376 reactions | Only reactions'
        assert _strip_engagement_prefix(title=title) == title

    def test_genuine_title_starting_with_count_untouched(self):
        """A real title that opens with a count and the word 'Views' is not a prefix."""
        assert _strip_engagement_prefix(title='3 Views of Mount Fuji') == '3 Views of Mount Fuji'

    def test_counters_not_leading_untouched(self):
        """Counters that are not at the start of the title are left alone."""
        title = 'My video: 100 views of the sunset'
        assert _strip_engagement_prefix(title=title) == title

    def test_plain_title_unchanged(self):
        """A title with no counters at all is returned unchanged."""
        assert _strip_engagement_prefix(title='Anastasia - To kokkino foustani') == \
            'Anastasia - To kokkino foustani'

    def test_prefix_only_title_returns_original(self):
        """A title that is nothing but the prefix keeps its original text (never empty)."""
        assert _strip_engagement_prefix(title='12K views · 3 reactions') == '12K views · 3 reactions'

    def test_empty_title(self):
        """An empty title is returned unchanged."""
        assert _strip_engagement_prefix(title='') == ''


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
