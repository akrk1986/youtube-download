"""Greek singles library cross-checker.

Implementation split by concern (SRP / SoC):
- config       -- tunable constants (e.g. duration-match margin)
- models       -- SongKey / Song dataclasses (pure data)
- normalize    -- pure string-normalization helpers
- audio_reader -- file-system scan + tag reading
- database     -- SQLite schema, archive, insert, diff queries
- report       -- console (Rich) + CSV rendering

The thin orchestrator lives in Utils/main-check-greek-singles.py.
"""
