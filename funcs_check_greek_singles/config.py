"""Tunable configuration for the Greek singles cross-checker."""

# Two songs are considered the same recording when their normalized
# (title, artist) align AND their durations differ by at most this many seconds.
# ABS-based tolerance (no ROUND X.5 boundary issue). Sub-second encoder jitter
# is well within this margin; distinct recordings of the same song (studio vs
# live) typically differ by 10s+. Raise it to cluster looser rips together.
DURATION_MATCH_MARGIN_SECONDS = 4.0

# --- Dupe staging / post-inspection workflow ---
# Suspected dupes are moved here (one flat folder) so a single tag-app session
# can inspect them without switching folders. Lives under --root.
STAGING_DIRNAME = 'Staging-Dupes'
# Files the user marks as real duplicates are moved here for eventual deletion.
DUPES_DIRNAME = 'Dupes'
# Written into the Album Artist tag at staging as 'DUPE-ORIGIN[<path relative to
# root>]'; the user appends a verdict after the ']'. Bracket-delimited so paths
# with spaces parse unambiguously.
STATE_TAG_MARKER = 'DUPE-ORIGIN'
# Verdict tokens the user appends in the Album Artist tag (case-insensitive, exact).
VERDICT_DUPLICATE = 'duplicate'      # real duplicate -> move to Dupes/
VERDICT_NOT_DUPLICATE = 'dupe-ok'    # not a duplicate -> restore to origin folder
