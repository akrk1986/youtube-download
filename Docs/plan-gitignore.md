Revision 2 — 2026-05-06 10:09

# Plan: Fix .gitignore

## Issues Found

### 1. Missing — tool-generated dirs (newly created)
- `.skylos/` — created by skylos on first run; currently shows as untracked in `git status`

### 2. Missing — standard Python noise
Not in `.gitignore` but should be:
- `__pycache__/`
- `.mypy_cache/`
- `.pytest_cache/`
- `*.egg-info/`
- `.ruff_cache/`

### 3. Stale entries — possibly obsolete
- `/yt-audio-m4a` and `/yt-audio-flac` — old output dirs that predate the unified `yt-audio/` structure. Verify whether these directories still exist or can be removed from `.gitignore`.

### 4. Messy commented-out lines
```
#*.txt
#!requirements.txt
```
These are dead comments. Either uncomment and make them active rules, or delete them.

### 5. Redundant case variants for audio files
```
*.mp3
*.MP3
*.M4A
```
`.MP3` and `.M4A` are uppercase variants added for Windows. On Linux, `.gitignore` is case-sensitive, so both are needed. But `*.mp3` has a lowercase entry while `*.M4A` has no lowercase `*.m4a` — inconsistent. Audit the full set:
- `*.mp3` ✓  `*.MP3` ✓  — both present
- `*.m4a` ✗  `*.M4A` ✓  — lowercase missing
- `*.flac` ✓  `*.FLAC` ✗  — uppercase missing
- `*.webm` ✓  `*.WEBM` ✗  — uppercase missing (less critical)

### 6. Alignment with Category 3 (from plan-linter-scopes.md)
The linter-scope plan defines Category 3 (never scanned). Cross-check that every Category 3 dir is also in `.gitignore` (if it should not be tracked), or confirm it IS tracked intentionally (e.g. `Beta/` is tracked — correct).

---

## Proposed Changes

```gitignore
# --- Python tooling ---
__pycache__/
*.pyc
*.egg-info/
.mypy_cache/
.pytest_cache/
.ruff_cache/
.skylos/

# --- Virtual environments ---
.venv/
.venv-linux/
.venv-windows/
.venv-3.14/
.old-venv-3.14/
Tests/.venv-linux

# --- Download output ---
/yt-videos/
/yt-audio/
/yt-chapters/
/yt-audio-m4a/       # keep until confirmed obsolete
/yt-audio-flac/      # keep until confirmed obsolete
staging-mp3/
staging-mp4/

# --- Audio/media files ---
*.mp3
*.MP3
*.m4a
*.M4A
*.flac
*.FLAC
*.webm
*.wav
*.ogg

# --- Logs and runtime state ---
Logs/
Tests/e2e_state.json
Data/last_url.txt
Data/trello - greek-music-artists.json

# --- Test output dirs ---
Tests/Data/
Tests/yt-audio/
Tests/yt-videos/
Tests-UTF/

# --- Secrets and local config ---
git_excluded.py

# --- IDE ---
.idea/workspace.xml
.idea/shelf/

# --- Node/npm ---
node_modules/
package-lock.json

# --- ERTFlix Chromium profile ---
.ertflix-profile/

# --- Misc tools ---
.pyscn/
```

---

## Open Questions for the Session

1. **`/yt-audio-m4a` and `/yt-audio-flac`** — do these dirs still exist on disk? If not, safe to remove from `.gitignore`.
2. **`plan-*.md` files** — currently tracked in git (committed). Should they stay tracked, or be added to `.gitignore`?
3. **`Tests-UTF/`** — what was this? Still relevant?
4. **`.skylos/`** — confirm what skylos stores there (baseline data, cache?) to decide if it should ever be committed.

---

## Status: DONE — commit 90e2b07

All changes applied. Open questions resolved:
1. `/yt-audio-m4a` and `/yt-audio-flac` — both exist on disk → kept
2. `plan-*.md` — stay tracked in git (user decision)
3. `Tests-UTF/` — already gitignored, kept as-is
4. `.skylos/` — contains cache only → gitignored
