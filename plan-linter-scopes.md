Revision 1 — 2026-05-05 23:42

# Plan: Three-Tier Linter Scope System

## Goal

Replace the current per-tool ad-hoc exclusion lists with a single, centrally-defined three-tier file classification. Every linter should read from the same source of truth.

---

## The Three Categories

### Category 1 — Primary Code (full linting)
All Python and JS/TS files that are part of the deliverable: main scripts, packages, tests, and standalone utilities written *by the project* and checked into git as permanent fixtures.

**Includes:**
- `main-*.py` (all top-level entry points)
- `funcs_*/` (all 7 packages)
- `run-linters.py`, `project_defs.py`, `git_excluded.py`
- `Tests/` (pytest suite + E2E runner)
- `Tests-Standalone/` (standalone utility scripts)
- `JS-files/` (production browser scripts)

**Linting:** all tools apply — ruff, mypy, ty, bandit, pylint, pydoclint, vulture, skylos, deadcode, pyupgrade, eslint, jshint, etc.

---

### Category 2 — Claude-generated test/scratch files (light or no linting)
Temporary Python/JS/TS scripts and functions created by Claude during debugging, exploration, or one-off testing. Not part of the main codebase. May be messy or incomplete by design.

**Includes:**
- Any file Claude creates in `Tests/` or `Tests-Standalone/` that is ephemeral
- One-off diagnostic scripts (e.g. `test_*.py` scratch files not committed)
- `JS-files-diag/` (diagnostic browser scripts — already marked obsolete/diag)

**Linting:** excluded from strict tools (mypy, ty, pylint, pydoclint). Optionally included in ruff for basic syntax. Not included in dead-code scanners (skylos, deadcode, vulture).

**Open question:** How does Claude (or the user) mark a file as Category 2? Options:
- A dedicated directory (e.g. `Scratch/` or `Tests-Claude/`)
- A naming convention (e.g. `_claude_*.py`)
- A manifest file listing Category 2 paths

---

### Category 3 — Non-code (excluded from all tools)
Virtual environments, beta/legacy code, output directories, logs, and third-party assets.

**Includes:**
- `.venv`, `.venv-linux`, `.venv-windows`, `.venv-3.14`
- `Beta/`
- `node_modules/`
- `yt-videos/`, `yt-audio/`, `yt-chapters/` (download output)
- `Logs/`
- `.git/`, `.idea/`, `.mypy_cache/`, `.pytest_cache/`
- `JS-files-diag/` (obsolete diagnostic scripts — currently Category 2 or 3, to decide)

---

## Current Problem

Each tool has its own exclusion list, defined differently:

| Tool | How exclusions are specified |
|------|------------------------------|
| `ty` | hardcoded list in `_build_cmd()` |
| `vulture` | comma-joined string in `_build_cmd()` |
| `skylos` | repeated `--exclude-folder` flags in `_build_cmd()` |
| `deadcode` | comma-joined string in `_build_cmd()` |
| `ruff` | `pyproject.toml [tool.ruff] exclude` |
| `mypy` | `pyproject.toml [tool.mypy] exclude` |
| `bandit` | `pyproject.toml [tool.bandit]` |
| `deptry` | `pyproject.toml [tool.deptry]` |
| `pylint` | `--ignore=Beta` flag |
| `pydoclint` | explicit target list in `_build_cmd()` |
| `pyupgrade` | `EXCLUDED_DIRS` in `project_defs.py` |

`EXCLUDED_DIRS` in `project_defs.py` is the closest thing to a central list, but only `pyupgrade` uses it.

---

## Proposed Solution

### Step 1 — Define three lists in `project_defs.py`

```python
# Category 1: scanned by all linters
PRIMARY_DIRS: list[str] = [
    'funcs_for_main_yt_dlp', 'funcs_video_info', 'funcs_utils',
    'funcs_audio_processing', 'funcs_audio_tag_handlers',
    'funcs_for_audio_utils', 'funcs_notifications',
    'funcs_ertflix_automation',
    'Tests', 'Tests-Standalone',
    'JS-files',
]
PRIMARY_FILES: list[str] = [
    'main-yt-dlp.py', 'main-ertflix-series.py', 'main-get-artists-from-trello.py',
    'main-convert.py', 'main-boost-mp3-or-mp4.py', 'main-qb-notify.py',
    'main-qb-notify-gmail.py', 'run-linters.py', 'project_defs.py',
]

# Category 3: excluded from all tools
EXCLUDED_DIRS: list[str] = [
    '.venv', '.venv-linux', '.venv-windows', '.venv-3.14',
    'Beta', 'node_modules',
    'yt-videos', 'yt-audio', 'yt-chapters', 'Logs',
    '.git', '.idea', '.mypy_cache', '.pytest_cache', '__pycache__',
]
```

Category 2 definition to be decided (see open question above).

### Step 2 — Update `run-linters.py` `_build_cmd()`

All per-tool exclusion lists replaced with references to `EXCLUDED_DIRS` (and optionally `PRIMARY_DIRS` for tools that use an inclusion model like `pydoclint` and `pylint`).

### Step 3 — Sync `pyproject.toml`

Tools that read config from `pyproject.toml` (ruff, mypy, bandit, deptry) need their `exclude` lists updated to match `EXCLUDED_DIRS`. Consider whether these can be auto-generated or if they stay manually synced.

### Step 4 — Decide Category 2 boundary

Key question for the session: should `JS-files-diag/` be Category 2 (light linting) or Category 3 (excluded entirely)? It contains obsolete scripts but they are tracked in git. Likely Category 3 given they are marked `obsolete-*`.

---

## Open Questions for the Session

1. **Category 2 boundary mechanism** — directory, naming convention, or manifest?
2. **`JS-files-diag/`** — Category 2 or 3?
3. **`pyproject.toml` sync** — auto-generate from `project_defs.py` or keep manually in sync?
4. **Tools with inclusion models** (pydoclint, pylint use target lists, not exclusion lists) — switch to exclusion model or keep as-is?
5. **`Tests-Standalone/`** — currently Category 1 in this plan, but some scripts there are Claude-generated ephemeral. Should it be split?

---

## Status: Pending session start
