# Changelog — Web App

All notable changes to the yt-dlp download web app (`webapp-yt-dlp.py` + the `webapp/` package) are
documented in this file. The web app carries its own `VERSION` (in `webapp/__init__.py`), independent
of `main-yt-dlp.py` — the app only drives that script as a subprocess. Main-script history is in
[../CHANGELOG.md](../CHANGELOG.md).

## [2026-07-03-2034] - disable clipboard watcher under WSL

### Changed
- **Clipboard watcher disabled under WSL** (`webapp/config.py`, `webapp/app.py`): the Start/Stop
  watching buttons are hidden and the poll timer is not created when running under WSL, where reading
  the Windows clipboard from the running NiceGUI server proved unreliable (works cleanly run natively
  on Windows). New UI-free `is_wsl()` helper (WSL env vars + `microsoft` kernel-release marker); the
  page gates both button visibility and the poll timer on `not is_wsl()`. The watcher code
  (`ClipboardWatcher`, start/stop handlers) is left intact — just never started under WSL. Windows and
  native Linux keep the feature active.

### Docs
- `webapp/README.md`: new **Known issues** section — the WSL disable, and that **native Linux is
  untested** (watch buttons left active there, but the pyperclip clipboard path is unverified — open
  item). New `test_is_wsl`.

## [2026-07-03-2008] - watch buttons only for prompt presets + preset URL prefill + wider clipboard match

### Added
- **Quick presets pre-fill the URL** (`webapp/presets.py`): the four `YT-DLP-presets` configs now
  carry the playlist URL hardcoded in their original PyCharm run configs, so selecting one fills the
  URL field (they never needed the clipboard watcher).

### Changed
- **Clipboard watcher shown only for URL-prompting presets** (`webapp/app.py`, `webapp/form.py`,
  `webapp/presets.py`): the **Start/Stop watching** buttons are visible only while a `YT-DLP-prompt`
  preset is selected (which is the only group that expects a user-supplied URL); they are hidden for
  the URL-prefilled quick presets and the linters. New `is_prompt_preset()` predicate +
  `FormView.current_is_prompt()`; `FormView` gains an `on_change` hook so the page re-syncs button
  visibility on preset switches (and stops an active watcher when leaving a prompt preset).
- **Clipboard watcher matches all download-able YouTube forms** (`webapp/services/clipboard_watcher.py`):
  the URL matcher now also accepts playlist (`playlist?list=`), `shorts/`, and YouTube Music
  (`music.youtube.com`) links, not just `watch?v=` / `youtu.be/` — so it never rejects a link the
  main script would download (a copied playlist now fills the field too).

## [2026-07-03-1858] - colour output log (ANSI→HTML) + non-interactive linter runs

### Added
- **`webapp/ansi.py`** (UI-free, unit-tested): `ansi_to_html()` converts the ANSI SGR subset rich
  emits — bold / dim / italic / underline and the 16 basic + 24-bit truecolour foreground colours —
  into safe `<span style=…>` HTML, HTML-escaping the text first so no output line can inject markup;
  non-SGR escapes (cursor moves, OSC) are stripped. Emoji that rich places in a table cell (e.g.
  freshness's ⛔ held-by / ⚠ build-from-source badges) are wrapped in a `display:inline-block` sized
  to the exact `ch` count rich reserved for them (via rich's own `cell_len`), so the surrounding
  rich-table borders stay aligned in the browser's monospace font.

### Changed
- **Output log renders colour** (`webapp/app.py`): the `ui.log` is replaced by a small
  ANSI-rendering `_AnsiLog` (a `ui.scroll_area` of per-line `ui.html`, same max-lines trim +
  auto-scroll-to-bottom) so the linter's coloured rich tables and New/Stable badges show as colour
  instead of raw escape codes. The log is now **monospace** so the box-drawing tables line up.
- **Linter subprocess forces colour** (`webapp/runner.py`): running `run-linters.py` now sets
  `FORCE_COLOR=1` (so all rich output emits ANSI through the pipe, not just the one table that
  already forced it) and `COLUMNS=120` (a stable width for the wide tables).
- **Linter presets run non-interactively** (`webapp/presets.py`): every Run-Linters preset now
  passes `--batch`, so the freshness upgrade-script prompt (its only interactive step) is skipped —
  the web app streams output but cannot forward keystrokes. Requires the shared `common_linters`
  `--batch` flag (see the common-av-codebase changelog).
- `Tests/test_webapp.py`: added `ansi_to_html` coverage (escaping, colours, bold/italic, truecolour,
  escape-stripping, no-injection, emoji cell-width pinning); updated the linter-env assertion.

## [2026-06-30-1839] - clipboard watcher for YouTube URLs + --native launch flag

### Added
- **`--native` CLI flag** — launches a standalone desktop window instead of a browser tab (forces it
  on; `config.json` `native` still works as a fallback). Needs `pywebview` installed (manual/optional;
  on Windows it renders via the built-in Edge WebView2). `_parse_cli` now returns the native flag.
- **Clipboard watcher** (`webapp/services/clipboard_watcher.py`, UI-free): while the **Start watching**
  toggle is on, a 1 s `ui.timer` polls the OS clipboard (`pyperclip` off the event loop via
  `asyncio.to_thread`); on a **new** YouTube URL (`youtube.com/watch?v=`, `youtu.be/`, `m.youtube.com`)
  it fills the URL field (`FormView.set_url`) and shows a persistent OK notification. It never
  auto-starts a download. Enabling it ignores whatever is already on the clipboard. Empty/unreadable
  reads are skipped silently and watching continues (WSL's PowerShell-backed clipboard *raises* on an
  empty clipboard — a normal state, not a failure).
- **Start watching / Stop watching** buttons in the controls row (enabled-state mirrors the watcher).
- **`Tests/test_clipboard_watcher.py`** (8 tests): URL matching, last-seen reset on start, new-URL
  delivery, non-YouTube ignored, disabled no-op, and skip-and-stay-enabled on a failing read.

### Changed
- Dependency: `pyperclip` promoted to a declared direct dependency (+ `types-pyperclip` stub). The
  cross-platform `uvloop` lock marker (see project changelog) makes the shared lock installable on
  Windows, which `--native` needs there.

## [2026-06-30-1520] - "Exit web app" button + own version/changelog/readme

### Added
- The web app now has its **own `VERSION`** (`webapp/__init__.py`), shown in the page header and bumped
  independently of `main-yt-dlp.py`. Added this dedicated `webapp/CHANGELOG.md` and a `webapp/README.md`.

### Changed
- The shutdown control is now **Exit web app** — orange, octagon-✕ (`dangerous`) icon. Clicking it
  replaces the whole page with a blank page showing a yellow-background **"Web application was stopped"**
  banner, then stops the server. Shutdown runs on a background task with a 0.5 s delay (so the final
  page reaches the browser before the websocket closes); this replaces the earlier `ui.timer` approach,
  which raised "The parent element this slot belongs to has been deleted" because `page.clear()` had
  already removed the slot the click handler ran in.

## [2026-06-30-1408] - platform-aware cookie default + UI tweaks

### Changed
- The preset **cookie default is now platform-aware and configurable** — `firefox` on native Windows,
  `none` on WSL/Linux/macOS (where the Windows Firefox profile is unreachable, so
  `yt-dlp --cookies-from-browser firefox` would fail). Overridable via a `cookies` key in
  `webapp/config.json` (`none`/`firefox`/`chrome`). Presets carry a `COOKIES_FROM_CONFIG` sentinel that
  `FormView.apply_preset` resolves against `AppConfig.default_cookies` (the ERTFlix preset still forces
  `none`); the sentinel never reaches `build_command`.
- **UI**: the Launch / Cancel controls moved **above** the output log; added a shutdown button; the
  controls (title, form, preview, buttons) are capped to a readable width while only the **output log**
  spans the full browser width (useful on desktop).
- **Tests**: `Tests/test_webapp.py` updated for the sentinel; added `test_default_cookies_resolution`
  (config override / blank / invalid → platform default).

## [2026-06-30-1319] - initial NiceGUI web app wrapping main-yt-dlp.py

### Added
- **New web UI** (`webapp-yt-dlp.py` + `webapp/` package): a local NiceGUI app that exposes a curated
  set of the project's PyCharm run configurations as editable presets, shells out to `main-yt-dlp.py`
  (or `run-linters.py`) via `asyncio.create_subprocess_exec`, and streams the live output into a
  scrollable log. Mirrors the sibling `losslesscut-csv` web app. `main-yt-dlp.py` is unchanged; the app
  drives it as a subprocess.
  - Listens on **port 8081** by default (8080 is the sibling app); configurable via `--port` /
    `WEBAPP_PORT` env / `webapp/config.json` (in that precedence), same for host.
  - UI-free core (`config.py`, `presets.py`, `runner.py`, `validate.py`) is unit-tested without the
    NiceGUI runtime; `form.py` / `app.py` hold the nicegui shell.
  - Presets cover the `YT-DLP-presets`, `YT-DLP-prompt`, and `Run Linters` folders. `NOTIFICATIONS` is a
    radio defaulting to `NO` (`ALL` for the `ertflix-program` and `chapters list+download` presets); the
    three `*-boost` presets pre-fill the boost volume to `2.0`. The stale `--video` flag from the old run
    config is normalized to `--video-download-timeout`. Console-prompt sentinels (`--title prompt`)
    become editable Title/Artist/Album fields.
  - The interactive ERTFlix series browser (`main-ertflix-series.py`) is intentionally **not** exposed
    (its headed-Chromium / arrow-key flow can't run headless).
- **`Tests/test_webapp.py`**: command-mapping, preset-registry, and validator coverage.
- **Dependency**: `nicegui` added to `pyproject.toml`; `requirements.txt` recompiled (pins the
  nicegui/fastapi/uvicorn/starlette stack).
