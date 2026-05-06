# Linter Scope Guide — Three-Tier System

All linter scope decisions live in **`project_defs.py`**. Edit that file when the project structure changes; the linters pick it up automatically.

---

## The three tiers

| Tier | What | Lists in `project_defs.py` |
|------|------|---------------------------|
| **Cat 1 — Primary code** | Fully linted by all tools | `PRIMARY_DIRS`, `PRIMARY_FILES` |
| **Cat 2 — Scratch/ephemeral** | Excluded from strict linters (mypy, ty, pylint, pydoclint, dead-code scanners) | `SCRATCH_DIRS`, `SCRATCH_FILES` |
| **Cat 3 — Non-code** | Excluded from every tool | `EXCLUDED_DIRS` |

---

## When you add a new directory

1. **It's a permanent code package** (e.g. `funcs_new_feature/`) → add it to `PRIMARY_DIRS`.
2. **It's a scratch/test dir created by Claude** (e.g. `Tests-Scratch/`) → add it to `SCRATCH_DIRS`.
3. **It's output, cache, venv, or third-party** (e.g. `yt-transcripts/`, `.new-cache/`) → add it to `EXCLUDED_DIRS` **and** `.gitignore`.

## When you add a new top-level script

1. **It's a permanent entry point** (e.g. `main-new-tool.py`) → add it to `PRIMARY_FILES`.
2. **It's a one-off Claude-generated script** → add it to `SCRATCH_FILES`.

## When you remove a directory or file

Remove it from whichever list it was in. If it was in `EXCLUDED_DIRS`, also remove it from `.gitignore`.

---

## Tools that need manual sync

Four tools read their exclusions from `pyproject.toml`, not from `project_defs.py`. Keep them in sync manually when `EXCLUDED_DIRS` changes:

| Tool | Config location |
|------|----------------|
| `ruff` | `[tool.ruff] exclude` |
| `mypy` | `[tool.mypy] exclude` |
| `bandit` | `[tool.bandit] exclude` |
| `deptry` | `[tool.deptry]` |

---

## Special cases: `Tests/` and `Tests-Standalone/`

Both are **Cat 1** but are currently excluded from **pylint** and **pydoclint** because pytest patterns (in-function imports, fixture args, protected access) generate too many false positives. This is a temporary state tracked in `run-linters.py` `_build_cmd()`.

When the `Tests-Standalone/` Cat1/Cat2 split is done, remove `'Tests'` and `'Tests-Standalone'` from the manual extra-exclusion lists in the `pylint` and `pydoclint` cases in `_build_cmd()`.
