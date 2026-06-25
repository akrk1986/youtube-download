# Linter-watch scheduling

`pip-audit` and `freshness` are the two linters whose results drift over time **without any code
change** — new CVEs land against already-installed packages, and new stable releases appear on PyPI.
Two mechanisms cover this:

- **Production gate** (always on): `main-yt-dlp.py` and the LosslessCut driver call
  `gate_on_linter_freshness()` at startup and refuse to run if the two linters haven't run in the
  last 24h. Skip with `LINTER_GATE=off`. This is the real safety net — missing a scheduled watcher
  run is harmless.
- **Background watcher** (this doc): `av-utils/Utils/main-linter-watch.py` runs both linters on a
  soft interval, refreshes the shared state, and sends a Slack/Gmail notification **only when new
  items appear**. Scheduling it is optional and per-machine.

The watcher and its wrappers live in **`av-utils`**; state is shared across all sibling repos at
`av-utils/Data/linter-watch-state-<os>.json` (per-OS, git-ignored).

## Register the scheduler

### WSL / Linux — cron

```bash
crontab -e
```

Add (runs daily at 09:00, logging to the home dir):

```
0 9 * * * /mnt/c/Users/user/PycharmProjects/av-utils/Tools/run-linter-watch.sh >> ~/linter-watch.log 2>&1
```

A **systemd timer** is an alternative if you want journald logging + `systemctl list-timers`
visibility (systemd is PID 1 under this WSL distro, so it works).

### Windows — Task Scheduler

```powershell
schtasks /Create /SC DAILY /ST 09:00 /TN LinterWatch /TR "powershell -ExecutionPolicy Bypass -File C:\Users\user\PycharmProjects\av-utils\Tools\run-linter-watch.ps1"
```

Task Scheduler has built-in missed-run catch-up.

## Wrapper scripts

Both wrappers activate the shared per-OS venv, then run the watcher; extra args are forwarded:

- `av-utils/Tools/run-linter-watch.sh` (WSL/Linux)
- `av-utils/Tools/run-linter-watch.ps1` (Windows)

## Manual / ad-hoc use

```bash
source ../.venv-av-linux/bin/activate          # or ..\.venv-av-windows\Scripts\activate
python Utils/main-linter-watch.py              # honors the interval; no-op if run recently
python Utils/main-linter-watch.py --force      # ignore the interval, run now
python Utils/main-linter-watch.py --interval-days 7 --notify slack
```

Options: `--interval-days N` (default 1), `--notify {slack,gmail,both}` (default both), `--force`.
Credentials come from the git-excluded `av-utils/git_excluded.py` (`SLACK_WEBHOOK`, `GMAIL_PARAMS`).

## Seeding the state

The gate reports "never run" until the linters have run at least once. Seed it with either the
watcher above or, from any repo:

```bash
python run-linters.py --tool pip-audit freshness
```
