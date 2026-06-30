# Changelog — Web App

All notable changes to the yt-dlp download web app (`webapp-yt-dlp.py` + the `webapp/` package) are
documented in this file. The web app carries its own `VERSION` (in `webapp/__init__.py`), independent
of `main-yt-dlp.py` — the app only drives that script as a subprocess. Main-script history is in
[../CHANGELOG.md](../CHANGELOG.md).

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
