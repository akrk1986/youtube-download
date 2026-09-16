#!/usr/bin/env python3
"""Tests for _strip_engagement_prefix (Facebook's '<n> views <m> reactions <k> shares ' title prefix)."""
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
    """Verify leading '<count> <counter><sep>' groups (views/reactions/shares, any order) are removed."""

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

    def test_views_only(self):
        """A single views counter is a prefix."""
        assert _strip_engagement_prefix(title='2.3M views | Real Title') == 'Real Title'

    def test_reactions_only(self):
        """A single reactions counter is a prefix."""
        assert _strip_engagement_prefix(title='31 reactions | Real Title') == 'Real Title'

    def test_reactions_only_sanitized(self):
        """A single counter with already-sanitized separators is stripped."""
        assert _strip_engagement_prefix(title='31 reactions Real Title') == 'Real Title'

    def test_reactions_and_shares(self):
        """Reactions followed by shares, with no views counter, is a prefix."""
        assert _strip_engagement_prefix(title='15K reactions · 3.2K shares | Real Title') == 'Real Title'

    def test_reverse_order(self):
        """Counters are recognised in any order."""
        assert _strip_engagement_prefix(title='3.2K shares · 17K views | Real Title') == 'Real Title'

    def test_three_counters(self):
        """Three counters in a row are all removed."""
        assert _strip_engagement_prefix(title='1K views · 20 reactions · 5 shares | Real Title') == 'Real Title'

    def test_singular_share(self):
        """Singular 'share' is recognised."""
        assert _strip_engagement_prefix(title='1 share | Real Title') == 'Real Title'

    def test_genuine_title_starting_with_listed_counter_is_stripped(self):
        """Accepted trade-off: a real title opening with a listed counter loses it."""
        assert _strip_engagement_prefix(title='3 Views of Mount Fuji') == 'of Mount Fuji'

    def test_unlisted_counter_untouched(self):
        """A count followed by a word outside the closed list is not a prefix."""
        assert _strip_engagement_prefix(title='3 Likes and a Song') == '3 Likes and a Song'

    def test_unlisted_counter_stops_the_run(self):
        """Stripping stops at the first unlisted counter."""
        assert _strip_engagement_prefix(title='15K reactions · 40 comments | Real Title') == \
            '40 comments | Real Title'

    def test_word_boundary_viewers_untouched(self):
        """'viewers' is not 'views': the counter word must end at a word boundary."""
        assert _strip_engagement_prefix(title='2 viewers and a Song') == '2 viewers and a Song'

    def test_word_boundary_shared_untouched(self):
        """'shared' is not 'share'."""
        assert _strip_engagement_prefix(title='3 shared memories') == '3 shared memories'

    def test_counters_not_leading_untouched(self):
        """Counters that are not at the start of the title are left alone."""
        title = 'My video: 100 reactions and 3 shares'
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
