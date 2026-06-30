# yt-dlp Download Web App

A local browser UI ([NiceGUI](https://nicegui.io/)) that wraps the `main-yt-dlp.py` driver. It
exposes a curated set of the project's PyCharm run configurations as editable **presets**, shells
out to `main-yt-dlp.py` (or `run-linters.py`) as a subprocess, and streams the live output into a
scrollable log. The driver scripts are never modified — the app only invokes them.

Its version is tracked separately from `main-yt-dlp.py`: see `VERSION` in `webapp/__init__.py`
(shown in the page header) and the history in [CHANGELOG.md](CHANGELOG.md).

## Setup (one time)

```bash
source ../.venv-av-linux/bin/activate      # Windows: ..\.venv-av-windows\Scripts\activate
pip install -r requirements.txt            # installs nicegui + its stack (if not already present)
```

## Running

From the repository root, with the shared venv active:

```bash
./webapp-yt-dlp.py            # then open http://localhost:8081
```

### Host / port

Resolved in this precedence (highest first): CLI flag → environment variable → `webapp/config.json`
→ built-in default (`0.0.0.0:8081`; 8080 is the sibling `losslesscut-csv` app).

```bash
./webapp-yt-dlp.py --port 9000
WEBAPP_PORT=9000 ./webapp-yt-dlp.py
```

## Using the UI

1. Pick a **preset** from the dropdown (grouped by the originating run-config folder).
2. The form fields fill in from the preset; tweak anything (URL, mode, audio format, title/artist/
   album, boost, cookies, notifications, …). The read-only **command preview** shows the exact
   `env … python main-yt-dlp.py …` that will run.
3. **Launch** — output streams into the log below. **Cancel** terminates the running process.
4. **Exit web app** (orange, octagon-✕) replaces the page with a "Web application was stopped"
   notice and stops the server.

Controls are capped to a readable width; only the output log spans the full browser width.

### Presets

| Folder           | Target            | Notes |
|------------------|-------------------|-------|
| `YT-DLP-presets` | `main-yt-dlp.py`  | audio-only / audio+video M4A, with and without volume boost |
| `YT-DLP-prompt`  | `main-yt-dlp.py`  | interactive-metadata variants, chapters list+download, ertflix-program (token URL), video-only rerun |
| `Run Linters`    | `run-linters.py`  | all tools / `--tool pip-audit` / `--tool freshness` (the download form is hidden) |

The interactive ERTFlix **series browser** (`main-ertflix-series.py`) is intentionally not exposed —
its headed-Chromium / arrow-key flow can't run in a headless subprocess.

### Cookies (platform-aware default)

The cookie source defaults to **`firefox` on native Windows** and **`none` on WSL/Linux/macOS**
(where the Windows Firefox profile is unreachable, so `--cookies-from-browser firefox` would fail).
Override per run via the **Cookies** dropdown, or change the default for the whole app by setting
`"cookies"` (`none` / `firefox` / `chrome`) in `webapp/config.json`.

## Configuration (`webapp/config.json`)

| Key             | Default     | Meaning |
|-----------------|-------------|---------|
| `host`          | `0.0.0.0`   | Listen host (LAN-reachable). |
| `port`          | `8081`      | Listen port. |
| `cookies`       | `""`        | Default cookie source; blank ⇒ platform-aware. |
| `boost_default` | `2.0`       | Pre-filled boost factor. |
| `native`        | `false`     | Run in a native desktop window. |
| `reload`        | `false`     | NiceGUI file-watch hot reload. |
| `theme`         | (object)    | Dark mode, colours, fonts (validated before use). |

A NiceGUI `storage_secret` is read from the gitignored top-level `git_excluded.py`
(`STORAGE_SECRET`), with a development fallback when absent.

## Architecture

UI-free, unit-tested core vs. the NiceGUI shell:

| Module                | Imports nicegui? | Responsibility |
|-----------------------|------------------|----------------|
| `config.py`           | no               | `AppConfig` + `load_config` / `resolve_host_port`; host/port/cookie resolution |
| `presets.py`          | no               | the preset registry (each a `DriverParams`) |
| `runner.py`           | no               | `DriverParams`, `build_command` (argv vs env routing), `DriverProcess` (async subprocess + stream + cancel) |
| `validate.py`         | no               | URL / theme-string guards |
| `form.py`             | yes              | `FormView` widgets; `apply_preset` / `collect` |
| `app.py`              | yes              | page assembly, theme, Launch/Cancel/Exit, `ui.run` |
| `webapp-yt-dlp.py`    | (entry)          | thin entry point → `webapp.app.run_app` |

## Tests

```bash
pytest Tests/test_webapp.py
```

Covers the UI-free logic only (command mapping, preset registry, cookie-default resolution,
validators) — it never boots the NiceGUI runtime.
