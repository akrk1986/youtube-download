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

```powershell
python webapp-yt-dlp.py       # Windows; then open http://localhost:8081
```

### Host / port

Resolved in this precedence (highest first): CLI flag → environment variable → `webapp/config.json`
→ built-in default (`0.0.0.0:8081`; 8080 is the sibling `losslesscut-csv` app).

```bash
./webapp-yt-dlp.py --port 9000
WEBAPP_PORT=9000 ./webapp-yt-dlp.py
```

```powershell
python webapp-yt-dlp.py --port 9000       # Windows
$env:WEBAPP_PORT=9000; python webapp-yt-dlp.py
```

### Native desktop window

`--native` launches a standalone desktop window instead of a browser tab (`config.json` `native:
true` does the same; the CLI flag forces it on). It needs `pip install pywebview` and a desktop /
display — not available on a headless WSL box, where the browser tab is the way to go.

```bash
./webapp-yt-dlp.py --native
```

```powershell
python webapp-yt-dlp.py --native          # Windows
```

## Using the UI

1. Pick a **preset** from the dropdown (grouped by the originating run-config folder).
2. The form fields fill in from the preset; tweak anything (URL, mode, audio format, title/artist/
   album, boost, cookies, notifications, …). The text fields (URL, Title, Artist, Album, NOTIF_MSG
   suffix) show a **clear (✕) icon** while they hold text. The read-only **command preview** shows
   the exact `env … python main-yt-dlp.py …` that will run.
3. **Launch** — output streams into the log below. **Cancel** terminates the running process.
4. **Exit web app** (orange, octagon-✕) replaces the page with a "Web application was stopped"
   notice and stops the server.
5. **Start/Stop watching** (clipboard) — these two buttons appear **only when a `YT-DLP-prompt`
   preset is selected**, i.e. the presets that expect you to supply a URL. They are hidden for the
   quick `YT-DLP-presets` (which pre-fill their URL, see below) and the linters (which take no URL);
   switching away from a prompt preset also stops an active watcher. **They are also hidden entirely
   under WSL** (the watcher is disabled there — see [Known issues](#known-issues)). While watching,
   the app polls the OS clipboard once a second; when you copy a new **YouTube URL** — a video
   (`watch?v=`), playlist (`playlist?list=`), `youtu.be/`, `shorts/`, or `music.youtube.com` link —
   or a **Facebook video URL** (`watch?v=`, `<page>/videos/<id>`, `video.php?v=`, `reel/`,
   `share/v/` / `share/r/`, or an `fb.watch/` short link), it fills the URL field and shows a
   notification. A link copied out of a **Gmail message** (which arrives wrapped in a
   `google.com/url?q=…` redirect) is unwrapped and delivered as the clean target URL. It never
   auto-starts a download. A media URL **already on the clipboard when you click Start watching is
   picked up immediately** (the natural copy-the-link-first flow); a non-URL clipboard value is just
   the ignore-baseline. The clipboard is read directly from the OS (not the browser); reading it
   natively — from Windows, where the pipeline is most reliable — is recommended. An unreadable
   clipboard is skipped silently and watching continues. To diagnose a link that is not picked up,
   run `Tests-Standalone/main-clipboard-probe.py` — it prints every new clipboard value with the
   watcher's verdict.

Controls are capped to a readable width; only the output log spans the full browser width.

### Presets

| Folder           | Target            | Notes |
|------------------|-------------------|-------|
| `YT-DLP-presets` | `main-yt-dlp.py`  | audio-only / audio+video M4A, with and without volume boost; each **pre-fills its playlist URL** (hardcoded in the original run config), so no watcher is needed |
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
| `services/clipboard_watcher.py` | no     | `ClipboardWatcher` (pyperclip poll off the event loop, start/stop, new-media-URL callback) + `_is_media_url` (YouTube + Facebook) and `_extract_media_url` (Gmail/Google-redirect unwrapping) |
| `form.py`             | yes              | `FormView` widgets; `apply_preset` / `collect` / `set_url` |
| `app.py`              | yes              | page assembly, theme, Launch/Cancel/Exit/Watch-clipboard, `ui.run` |
| `webapp-yt-dlp.py`    | (entry)          | thin entry point → `webapp.app.run_app` |

## Tests

```bash
pytest Tests/test_webapp.py Tests/test_clipboard_watcher.py
```

Covers the UI-free logic only (command mapping, preset registry, cookie-default resolution,
validators, clipboard-watcher URL matching/unwrapping and delivery semantics) — it never boots the
NiceGUI runtime.

## Known issues

- **Clipboard watching is disabled under WSL.** Even though `pyperclip.paste()` can read the Windows
  clipboard from a WSL shell, the same read from the *running NiceGUI server* did not reliably fill
  the URL field in testing. Under WSL the Start/Stop-watching buttons are hidden and the poll timer is
  not created (`is_wsl()` in `config.py` gates it). Run the app **natively on Windows** for reliable
  clipboard watching. All other features work under WSL.
- **Native Linux is untested.** The web app has only been exercised on Windows and WSL. On native
  Linux the watch buttons are left **active**, but the pyperclip clipboard path there (which needs an
  `xclip` / `xsel` / `wl-paste` backend) is **unverified** — treat it as an open item until confirmed.
