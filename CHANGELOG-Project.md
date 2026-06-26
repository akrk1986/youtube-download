# Changelog — Project & Tooling

All notable project-wide changes — linters, type checkers, dependency/CVE bumps, security review, and the shared virtual environment — are documented in this file. Main-script history is in [CHANGELOG.md](CHANGELOG.md); utility-script history is in [CHANGELOG-Utils.md](CHANGELOG-Utils.md).

## [2026-06-26-1626] - pip-audit WARNING state; pylint lints entry-point scripts

### Changed
- **`pip-audit`** (via the shared `common_linters`): now **blocks only on actionable findings**. It
  rates each CVE's fix versions for release-age stability and resolves to **FAIL** only when a CVE
  has a Stable, installable fix to apply; when CVEs exist but every fix is too new / missing / pinned
  away it is a **WARN** (summary shows `pip-audit (Warning)`, exit 0) — nothing safe to do, so the
  run is not failed; **PASS** when clean. The linter summary gained a `WARNING` status
  (`common_linters.core.ToolStatus`); only `FAIL` fails the run.

### Added
- **`run-linters.py`**: pylint now lints the hyphenated entry-point scripts (`main-yt-dlp.py`,
  `main-ertflix-series.py`, `run-linters.py`, `Utils/*.py`). `pylint .` skips hyphenated files during
  directory traversal, so they are passed as explicit file paths via `_PYLINT_ENTRY_POINTS`;
  `[tool.pylint.basic] module-naming-style = "any"` (already set) suppresses only the unavoidable
  module-name `C0103`. Rates 10.00/10.

## [2026-06-24-1854] - add python3 shebang to entry-point scripts

### Added
- **All entry-point scripts** (anything with a `__main__` guard — `main-yt-dlp.py`, `main-ertflix-series.py`, `run-linters.py`, `Utils/main-get-artists-from-trello.py`, and the `Tests-Standalone/` scripts): now start with `#!/usr/bin/env python3` so they can be run directly (`./script.py`) instead of failing in the shell. Non-functional tooling change; main-script `VERSION` constants are unchanged.

## [2026-06-19-2014] - freshness: release-age column + generated upgrade scripts

### Changed
- **`run-linters.py`**: the `freshness` tool now runs `pip list --outdated --format=json` so the shared `common_linters.run_freshness()` can post-process it. Output is now a `rich` table (Package / Current / Latest / Age (days) / Action): **Age** is days since the latest release was published on PyPI with a red **`New`** (`< 8` days) / green **`Stable`** (`≥ 8` days) badge, and **Action** flags sdist-only releases as `⚠ build from source` (the old always-`wheel` Type column is gone). It then writes `pip-upgrade-stable.sh` + `pip-upgrade-stable.ps1` (Stable packages only) and interactively offers to display/run the platform script; non-interactive callers skip the prompts. The feature itself lives in the shared `common-av-codebase` `common_linters/linters_funcs.py`.
- **`.gitignore`**: ignore the generated `pip-upgrade-stable.sh` / `pip-upgrade-stable.ps1` (regenerated every run, not source).

## [2026-06-14-1745] - pip CVE bump; deptry ignores transitive CVE pins

### Fixed
- **Shared venv**: upgraded `pip` 26.1.1 → 26.1.2, resolving `PYSEC-2026-196` (flagged by `pip-audit`). `pip` is the venv's own tooling, not a project dependency, so there is no `requirements.txt`/`pyproject.toml` change for it.
- **`pyproject.toml`**: added `idna` and `urllib3` to `[tool.deptry.per_rule_ignores] DEP002`. Both are intentional transitive CVE pins in `[project.dependencies]` (not imported directly), so deptry flagged them as unused; they are now ignored alongside the dev-tool entries. All linters pass again.

## [2026-06-06-1421] - Cap skylos <4.12 (Windows/py3.14 build fix; reconcile shared-venv drift)

### Fixed
- **`pyproject.toml` / `requirements.txt`**: capped `skylos` to `>=4.11.1,<4.12` (was `>=4.11.0`, pinned `4.11.0`). skylos `4.23.x` added a hard dependency on `tree-sitter-dart-orchard`, which ships **sdist-only** (no wheels) and fails to build on Windows + Python 3.14 (`Failed building wheel for tree-sitter-dart-orchard`). Capping below `4.12` drops that grammar and pins `skylos==4.11.1`. Also reconciles a version drift across the shared venv — the four sibling repos had diverged to `4.11.0 / 4.11.1 / 4.23.1 / 4.23.1`; all four now pin `4.11.1` with an identical 6-package tree-sitter set.

## [2026-06-06-1351] - Drop stale per-project venv references (shared venvs only)

### Changed
- **`pyproject.toml`, `ruff.toml`, `pyrightconfig.json`, `project_defs.py`, `.gitignore`, `Tests-Standalone/test_rerun.py`**: removed all references to the obsolete per-project virtual environments (`.venv`, `.venv-linux`, `.venv-3.14`, `.venv-windows`, `.old-venv-3.14`) from the lint exclude lists, the gitignore, and the test rerun command. Only the two shared parent-dir venvs (`.venv-av-linux` / `.venv-av-windows`) are referenced now; the test command activates `../.venv-av-linux`. The leftover `.venv-linux/` directory (gitignored) was deleted. The radon `*.venv*` exclude glob is kept as a generic safety net.

## [2026-06-06-1328] - Remove uv; standardize on pip-compile

### Removed
- **`uv.lock`**: deleted. The project no longer uses `uv`; the shared per-OS venv is provisioned with plain `pip` and the pinned `requirements.txt` is regenerated with `pip-compile pyproject.toml requirements.in -o requirements.txt` (matching the `av-utils` model).
- **`.gitattributes`**: dropped the `uv.lock` LF rule and the uv-specific comment; `pyproject.toml` / `requirements.txt` stay pinned to LF.

### Changed
- **`main-ertflix-series.py`, `README.md`, `CLAUDE.md`**: replaced the `uv sync` / `uv add` setup instructions with `source ../.venv-av-linux/bin/activate` + `pip install -r requirements.txt`.

## [2026-06-06-1110] - Move ty to 0.0.44 (latest published)

### Changed
- **`pyproject.toml` / `requirements.txt`**: raised the `ty` floor from `0.0.34` to `0.0.44`, the latest published release. ty checks pass clean across all four sibling projects (youtube-download, LosslessCut-csv, av-utils, common-av-codebase) with no new diagnostics. Floors raised in lockstep so the shared venv stays consistent.

## [2026-06-06-1043] - Raise ty floor to 0.0.34 (fixes shared-venv project_defs collision)

### Fixed
- **`pyproject.toml` / `requirements.txt`**: raised the `ty` type-checker pin from `0.0.33` to `0.0.34`. ty 0.0.33 folded the shared parent-dir venv (`../.venv-av-windows`) into its first-party search root, so the sibling projects' top-level `project_defs.py` modules collided and ty bound the av-utils stub instead of the local one — emitting 41 false `unresolved-import` errors. 0.0.34 fixes the resolution. The floor was raised in the sibling repos' `pyproject.toml` as well so a reinstall can't regress to 0.0.33.

## [2026-06-05-1533] - Remove dead logging constants orphaned by the av-utils split

### Fixed
- **`project_defs.py`**: removed `MAX_LOG_FILES` and `GLOB_LOG_FILES`, which became unused once `funcs_utils/logger_config.py` moved to `common_av.log_config` (where the constants are inlined). skylos flagged them as new dead code; the rest of the suite stays green.

## [2026-06-05-1404] - Promote shared code to common-av; split utilities into av-utils

### Changed
- **Promoted shared code into `common-av-codebase`**: the `funcs_audio_tag_handlers/` and `funcs_notifications/` packages plus `remove_diacritics` / `setup_logging` now live in `common_av` (`tag_handlers`, `notifications`, `text`, `log_config`), consumed by both this repo and the new `av-utils` sibling. The in-repo copies were removed; `funcs_utils` re-exports the helper names for backward compatibility.
- **`pyproject.toml` / `requirements.txt`**: dropped `Pillow`, `requests`, and `types-requests` from `[project.dependencies]` (only the now-extracted utilities imported them; `requests` remains transitively). Removed `types-requests` from the deptry `DEP002` ignore list. Recompiled `requirements.txt`.

## [2026-06-02-1854] - Bump pyjwt 2.12.1 -> 2.13.0 (PYSEC-2026-175/177/178/179)

### Fixed
- **`requirements.in` / `requirements.txt`**: added a `pyjwt>=2.13.0` security override (recompiled to `2.13.0`) to clear **PYSEC-2026-175 / 177 / 178 / 179**, flagged by pip-audit in the shared venv. `pyjwt` is transitive (via `skylos -> mcp`, which requires `>=2.10.1`), not imported directly; the override lives in `requirements.in` next to the existing `starlette` pin. pip-audit now reports no known vulnerabilities.

## [2026-06-02-1829] - run-linters uses shared common_linters package

### Added
- **Line-length-consistency check**: `run-linters.py` now fails when ruff's `line-length` and pylint's `max-line-length` disagree (both are `120` today). It runs on a full `run-linters.py` invocation and on `--tool ruff` / `--tool pylint` (so the pre-commit hook enforces it too), and prints both values with their config sources.

### Changed
- **`run-linters.py`**: the generic machinery (parsers, tool runners, grouped output, `main()`) moved to the shared `common_linters.linters_funcs` module. This script now keeps only project-specific config (`EXCLUDED_DIRS`, `TOOLS`, `ALL_TOOLS`) and a `build_cmd(name, root)` callable; ~540 lines removed.
- **Imports**: `common_av.linters_defs` → `common_linters.linters_defs` in `run-linters.py` and `git-hooks/pre_commit_lint.py` (the shared linter-tool lists moved into the new `common_linters` package in `common-av-codebase`).
- **`pyproject.toml`**: `[tool.deptry.per_rule_ignores] DEP003` extended with `common_linters` (the editable `common-av` dist now ships two top-level packages: `common_av` and `common_linters`).

## [2026-06-01-1926] - Git pre-commit hook + shared linter list

### Added
- **`git-hooks/pre-commit`** — POSIX `sh` shim selecting the shared per-OS venv (WSL / Git-for-Windows) and prepending its bin to `PATH` (git hooks run without the venv activated).
- **`git-hooks/pre_commit_lint.py`** — runs the canonical linters via `run-linters.py` only when staged changes include `.py`/`.js` files; skips docs-only and `VERSION`-only commits; exits 1 (blocks) on any failure. Bypass with `git commit --no-verify`.
- **`Utils/install-git-hooks.py`** — one-time `core.hooksPath` install (`--uninstall` to disable). Idempotent; run once per clone.

### Changed
- **`run-linters.py`**: the linter tool list now comes from the shared `common_av.linters_defs.LINTER_TOOLS` (single source of truth across the sibling projects). It is filtered locally (`_FULLY_EXCLUDED={'deadcode'}`, `_DEFAULT_SKIP={'skylos'}`); the resulting `TOOLS` / `ALL_TOOLS` (and `--list`) are unchanged. The hook imports `CANONICAL_LINTER_TOOLS` from the same module.

## [2026-05-24-1404] - Linters: skylos opt-in, bandit excludes Tests/; bump starlette (PYSEC-2026-161)

### Fixed
- **`requirements.in` / `requirements.txt`**: added a `starlette>=1.0.1` security override (re-compiled to `1.1.0`) to clear **PYSEC-2026-161**, flagged by pip-audit. `starlette` is transitive (via `skylos -> mcp`), not imported directly; the override lives in `requirements.in` (its scope note widened to cover CVE pins on transitive deps). pip-audit now reports no known vulnerabilities.
- **`pyproject.toml`**: added `Tests` to `[tool.bandit].exclude_dirs`. It already excluded `Tests-Standalone`, and pylint/ty/pydoclint exclude both — bandit was the odd one out. The ffmpeg test fixtures' `subprocess.run([...])` calls were tripping B603/B607 (false positives in test code); bandit `High: 6` → clean.

### Changed
- **`run-linters.py`**: `skylos` removed from the default `TOOLS` set (it is slow); it stays runnable via `--tool skylos` and listed by `--list` (mirrors how `radon` is opt-in). A no-arg / "run all" invocation no longer includes it.

## [2026-05-20-2000] - Bump idna 3.11->3.15 (CVE-2026-45409)

### Fixed
- **`requirements.txt`**: upgraded `idna` to `3.15` in the shared venv and re-synced the pin (it had drifted to `3.11` while `3.13` was installed). Clears `CVE-2026-45409` flagged by pip-audit. `idna` is transitive (anyio / httpx / requests). The remaining pip-audit advisory (`pyjwt` PYSEC-2025-183) is left as-is — `pyjwt` is unused by this project (transitive via `mcp`, which is itself undeclared/unused here) and has no fixed release available.

## [2026-05-20-1826] - Drop unrecognized Pyright config keys

### Fixed
- **`pyrightconfig.json`**: removed `pythonPath` and `reportUnusedParameter`, both flagged "unrecognized setting" by the Pyright CLI (1.1.408). `pythonPath` was redundant (`venvPath` + `venv` resolve all imports); `reportUnusedParameter` is not a real Pyright rule and was a no-op — Pyright already suppresses underscore-prefixed unused params by default. Pyright CLI now reports zero config warnings.

## [2026-05-18-2123] - Clear pre-existing mypy + bandit findings; pin Pyright pythonPath

### Fixed
- **`funcs_video_info/metadata.py`**: added `# type: ignore[union-attr]` on the playlist-entry for-loop (line 142), matching the same exemption already applied on line 137. yt-dlp's `PagedList` is iterable at runtime but its type stubs do not declare `__iter__`. Clears the last mypy error in the repo (`Found 1 error in 1 file` → `Success: no issues found in 68 source files`).
- **`Tests/test_check_greek_singles.py`**: replaced 6 hardcoded `Path('/tmp/x.mp3')` paths with `Path('/test/x.mp3')` (bandit B108 `hardcoded_tmp_directory`). These are synthetic `Song.file_path` values used only for dataclass assertions; nothing opens them. `/test/...` matches the convention already in the `_insert` test helper. Clears bandit cleanly (`Medium: 6` → `Medium: 0`).
- **`pyrightconfig.json`**: added explicit `pythonPath: '../.venv-av-linux/bin/python3'`. With only `venvPath` + `venv` the test file still surfaced `Import "pytest" / "arrow" could not be resolved`; the explicit `pythonPath` closes the resolution gap.

## [2026-05-15-1650] - Fix pip-audit + trim linter exclude dirs

### Fixed
- **`run-linters.py`**: pip-audit invocation switched from `--strict` to `--skip-editable`. `--strict` treated the local editable `common-av` install (not on PyPI) as a hard failure and aborted before checking anything else; `--skip-editable` skips it cleanly and surfaces the skip reason in the output.
- **`uv.lock`, `requirements.txt`**: bumped urllib3 transitive dep `2.6.3 → 2.7.0`, fixing CVE-2026-44431 and CVE-2026-44432 (only visible once pip-audit could actually scan).

### Changed
- **`project_defs.py`**: trimmed `EXCLUDED_DIRS` to directories that actually exist on disk. Removed stale entries (`.venv`, `.venv-windows`, `.venv-3.14`, `.old-venv-3.14`, `staging-mp3`, `staging-mp4`, `Tests-UTF`) and added currently-existing ones (`staging`, `.pyscn`, `.claude`, `.ertflix-profile`). `yt-audio-flac` stays — it is an on-demand output dir declared via `AUDIO_OUTPUT_DIR_FLAC`. Affects ty / pylint / ruff / pydoclint / vulture / skylos / pyupgrade since they all consume this list.
- **`pyproject.toml`**: same cleanup for `[tool.bandit].exclude_dirs` (dropped `.venv-3.14`, `.venv-windows`, `.venv`, `Tests/.venv-linux`).

## [2026-05-07-1919] - Fix pylint to pass on Windows

### Fixed
- **`run-linters.py`**: force `encoding='utf-8', errors='replace'` on all `subprocess.run` calls — fixes garbled emoji output (e.g. pylint's `🎉 No violations 🎉`) on Windows CP1252 consoles; wrap long `subprocess.run` calls to stay under 120 chars; move `_build_cmd` inline pylint disable to `disable-next` line (was 129 chars)
- **`pyproject.toml`**: disable `R0903` (too-few-public-methods) globally — intentional for single-purpose strategy/state classes (`AudioBooster`, `_ProgressLogState`, etc.)

## [2026-05-07-1906] - Fix skylos to pass on Windows/Python 3.14

### Fixed
- **`run-linters.py`**: skylos command now includes `--baseline` flag and excludes `JS-files/`; `run_skylos()` overridden to filter `unused parameter` lines (baseline doesn't capture parameter fingerprints; all are interface false positives — only genuine dead functions/classes/variables fail)
- **`.skylos/baseline.json`**: committed baseline that suppresses known function/variable false positives (`_SilentLogger` dynamic dispatch, `reset()` kept intentionally, etc.); `.gitignore` narrowed from `.skylos/` to `.skylos/cache/` so baseline is tracked
- **`main-get-artists-from-trello.py`**: removed unused `VERSION` variable
- **`project_defs.py`**: converted dead `PRIMARY_DIRS/FILES`, `SCRATCH_DIRS/FILES` Python constants to inline comments (three-tier classification preserved as text)
- **`pyproject.toml`**: added `skylos` to deptry DEP002 ignore list

## [2026-05-01-1453] - Add ty/pip-audit/deptry linters + pin uv files to LF

### Added
- **`run-linters.py`**: three new tools wired into the harness, mirroring sister project `LosslessCut-csv`:
  - `ty` — Astral type checker (complements mypy)
  - `pip-audit` — scans installed deps for known CVEs
  - `deptry` — detects unused/missing/misplaced dependencies
  - New parsers: `_parse_pip_audit`, `_parse_deptry` (ty reuses `_parse_line_colon`).
  - New `_build_cmd` branches, runner functions, and dispatch entries in `_PARSERS` / `_TOOL_RUNNERS`.
- **`pyproject.toml`**: added `ty>=0.0.33`, `pip-audit>=2.10.0`, `deptry>=0.25.1` to dependencies + new `[tool.deptry]` section with the standard exclude list.
- **`.gitattributes`** (new file): pins `pyproject.toml`, `uv.lock`, and `requirements.txt` to LF line endings to prevent CRLF churn after `uv sync` / `uv add` / `uv export` on Windows-side checkouts.
- `requirements.txt` and `uv.lock` regenerated.

### Notes
- New tools surface real findings (59 ty diagnostics, 35 bandit lows, 3 pip-audit CVEs, 14 deptry false-positives, etc.); these are not addressed in this commit. See `Logs/lint-reports-2026-05-01-1441/SUMMARY.md` for the triage backlog.

## [2026-03-10-1818] - Sync run-linters improvements from LosslessCut-csv

### Changed
- **`pyproject.toml`**: added `[tool.bandit]` section with `exclude_dirs` and `skips = ['B101']` — bandit config now centralised alongside other tool configs
- **`run-linters.py`**: simplified bandit command to `bandit -r . -c pyproject.toml` (dropped inline `-x` and `--skip` flags); removed unused `root: Path` parameter from `_print_grouped_by_files()`
- **`CLAUDE.md`**: noted that bandit exclusions are configured in `pyproject.toml`

## [2026-03-09-1831] - Remove flake8 (replaced by ruff)

### Changed
- **`requirements.txt`**: removed `flake8` package (replaced by `ruff`)
- **`.flake8`**: deleted config file (no longer needed)
- **`CLAUDE.md`**: removed flake8 and isort from linting tools list (replaced by `ruff`)

## [2026-03-09-1817] - Security Review Fixes

### Fixed
- **`funcs_utils/security.py`**: replace `str.startswith()` with `Path.is_relative_to()` in `validate_file_path_security()` — fixes path-prefix bypass where a sibling directory (e.g. `yt-audio2`) could falsely pass the parent check for `yt-audio`
- **`funcs_video_info/url_validation.py`**: remove dead `except urllib.error.URLError` block in `get_timeout_for_url()` (urlparse never raises it); narrow broad `except Exception` to `except (ValueError, AttributeError)` in `validate_video_url()`
- **`funcs_utils/yt_dlp_utils.py`**: log a warning when `YTDLP_USE_COOKIES` is set to an unrecognized browser value instead of silently defaulting to Firefox

### Added
- **`Tests/test_security_measures.py`**: new `test_path_prefix_bypass` test covering the path-prefix fix (20 security tests, was 19)

## [2026-03-08-1924] - run-linters.py: --group-by-files mode

### Added
- **`run-linters.py`**: new `--group-by-files` flag that re-groups linting findings by source file instead of by tool
  - Works with `--tool <name>` (one tool) or alone (all tools sequentially)
  - New `Issue` dataclass (`filename`, `tool`, `text`)
  - `_run_tool_capture()` — silent variant of `_run_tool` that returns `(exit_code, output)`
  - Per-tool output parsers: `_parse_line_colon` (mypy/pylint/vulture/jshint), `_parse_ruff`, `_parse_bandit`, `_parse_radon`, `_parse_eslint`, `_parse_pyupgrade`
  - `_run_tool_grouped()` and `_print_grouped_by_files()` — grouped execution and display
  - `_build_cmd()` — centralised command builder (refactors all `run_*` functions to use it)
  - Fixed pydoclint parser: uses `_parse_radon` (bare filename + indented issues format)

## [2026-03-08-1923] - Linting Orchestration Script

### Added
- **`run-linters.py`**: new script that runs any of 10 linting tools (ruff, mypy, bandit, pydoclint, pylint, vulture, radon, pyupgrade, eslint, jshint) via `--tool <name>`; `--list` prints tool names for Claude sub-agent discovery
- **CLAUDE.md**: new "Linting" section documents all tools and the Claude parallel sub-agent workflow

### Fixed
- Pre-existing ruff E501/F401 violations in `file_organization.py`, `main-yt-dlp.py`, and `Tests-Standalone/scrape-with-selenium.py`

## [2026-03-08-1837] - pydoclint Docstring Fixes

### Fixed
- **DOC203** (return type mismatch): Added type prefixes to Returns sections across 30+ functions in `funcs_for_main_yt_dlp/`, `funcs_utils/`, `funcs_audio_processing/`, `funcs_notifications/`, `funcs_video_info/`, `main-yt-dlp.py`, `main-qb-notify.py`
- **DOC101/103** (missing args): Added missing `video_dir`/`chapter_name_map` to `organize_media_files` and `data` to `MessageBuilder.build_message`
- **DOC111** (type hints in docstring args): Removed type hints from Args sections in `greek_search` and `get_chapter_count`
- **DOC201** (no return section): Added Returns section to `parse_arguments`
- **DOC501/503** (missing Raises): Added `Raises` sections to `_extract_text_from_odt` (ImportError) and `get_timeout_for_url` (ValueError)
- **DOC502** (spurious Raises): Removed erroneous `SystemExit` Raises section from `validate_and_get_url` (uses `sys.exit()`, not `raise`)
- **pyproject.toml**: Added `allow-init-docstring = true` to suppress DOC301 globally (policy: document `__init__` args at the function, not the class)

## [2026-03-08-1708] - Ruff Linter Setup + Lint Fixes

### Added
- **`ruff.toml`**: ruff linter configuration (`line-length = 120`, rules E/W/F, `Beta/` and `.venv-*` excluded, I001 import-sorting suppressed)
- **`ruff` package**: added to `requirements.txt`

### Fixed
- **F401** (unused imports): removed or `# noqa`-suppressed unused imports across 12 files including `ertflix_token_handler.py`, `e2e_main.py`, standalone test scripts
- **F541** (f-strings without placeholders): removed `f` prefix from ~30 plain strings across test and main scripts
- **E501** (lines too long): wrapped long lines in `unified.py`, `chapter_remux.py`, `main-convert.py`, `main-yt-dlp.py`, and multiple standalone test files
- **W292** (no newline at end of file): added missing trailing newlines in 10 standalone test files
- **W293** (blank lines with whitespace): stripped trailing whitespace from blank lines in `main_greek_search.py` and `main-boost-mp3-or-mp4.py`
- **F841** (unused variables): replaced unused `result` with `_` in `test_rerun.py`; removed `as e` from 3 bare exception handlers
- **E402** (import not at top): moved `import smtplib` to top of `test_gmail_auth.py`

## [2026-03-05-1139] - Type Safety Review + PEP 8 Blank Lines

### Changed
- **Type annotations**: replaced bare `dict`/`list` with parameterized generics (`dict[str, Any]`, `list[NotificationHandler]`) across 9 files
- **Modern union syntax**: replaced `Optional[str]` with `str | None` in `funcs_notifications/message_builder.py`
- **Type narrowing**: added explicit `video_info is not None` guards in `main-yt-dlp.py` to fix mypy `union-attr` errors
- **PEP 8 blank lines**: fixed all E302/E303/E305 violations — added missing 2-blank-line separators between top-level functions in 5 files (`common.py`, `unified.py`, `artist_search.py`, `logger_config.py`, `main-get-artists-from-trello.py`)
- **CLAUDE.md**: documented type annotation conventions (modern union syntax, parameterized generics) and PEP 8 blank line rules

## [2026-02-27-1827] - Shared Virtual Environment

### Added
- **Shared virtual environment** at the `PycharmProjects` root level, replacing per-project venvs for both `LosslessCut-csv` and `youtube-download`
  - Windows: `C:\Users\user\PycharmProjects\.venv-3.14\` (Python 3.14)
  - Linux/WSL: `/mnt/c/Users/user/PycharmProjects/.venv-linux\` (system Python)
  - Combined `requirements.txt` at `PycharmProjects\requirements.txt`
- Updated `README.md` installation section to reference the shared venv
