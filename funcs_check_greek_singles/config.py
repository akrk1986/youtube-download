"""Tunable configuration for the Greek singles cross-checker."""

# Two songs are considered the same recording when their normalized
# (title, artist) align AND their durations differ by at most this many seconds.
# ABS-based tolerance (no ROUND X.5 boundary issue). Sub-second encoder jitter
# is well within this margin; distinct recordings of the same song (studio vs
# live) typically differ by 10s+. Raise it to cluster looser rips together.
DURATION_MATCH_MARGIN_SECONDS = 3.0
