# Playwright / Chromium Update Recovery

Steps to take after the Playwright-managed Chromium binary is reinstalled or upgraded — most commonly after `python -m playwright install chromium`. Affects `main-ertflix-series.py`, which is the only script in this project that drives Chromium.

## Symptom

Running `main-ertflix-series.py` fails immediately after `<launched> pid=...`. The Playwright log shows:

```
- [pid=...] <gracefully close start>
- [pid=...] <kill>
- [pid=...] <process did exit: exitCode=2147483651, signal=null>
```

…followed by the script's catch-all:

```
ERROR - Could not launch Chromium (headless=False). On WSL use WSLg or run from
native Windows Python. Cause: BrowserType.launch_persistent_context: Target
page, context or browser has been closed
```

The "WSL use WSLg" hint is a generic fallback message and is not the real cause when this happens on native Windows.

## Cause

`main-ertflix-series.py` keeps a persistent Chromium profile at `./.ertflix-profile/` (controlled by the `--profile-dir` flag, default `.ertflix-profile/`). After Playwright installs a newer Chromium version, the profile written by the previous Chromium is incompatible — Chromium starts, fails to parse the profile, and exits within milliseconds. Playwright sees the connection drop and tears the process down.

## Fix

Run from the project root with the project venv active.

### 1. Make sure the new browser is actually installed

```powershell
# Windows PowerShell or cmd
python -m playwright install chromium
python -m playwright --version
```

```bash
# Linux / WSL / macOS
source ../.venv-av-linux/bin/activate
python -m playwright install chromium
python -m playwright --version
```

### 2. Delete the stale persistent profile

Choose the form that matches your shell:

```cmd
:: Windows cmd.exe
rmdir /s /q .ertflix-profile
```

```powershell
# Windows PowerShell
Remove-Item -Recurse -Force .\.ertflix-profile
```

```bash
# Linux / WSL / macOS
rm -rf .ertflix-profile
```

`.ertflix-profile/` is git-ignored and contains only Chromium session state (cookies, cache, recent tabs). Deleting it just means you'll need to log into ERTFlix again on the next run, in the headed Chromium window.

### 3. Re-run

```bash
python main-ertflix-series.py <ERTFlix series URL>
```

A fresh Chromium window should open and stay alive. The script pauses for you to log in / switch the page language before scraping.

## Optional: confirming Chromium itself is healthy

If step 2 didn't fix it, run Chromium **outside** Playwright to see whether the binary itself is broken (corporate AV, missing VC++ redist, etc. can also kill Chromium on launch):

```powershell
# Windows — pick the version that matches `python -m playwright --version` output
& "$env:LOCALAPPDATA\ms-playwright\chromium-<VER>\chrome-win64\chrome.exe" --user-data-dir=C:\Temp\chrome-test about:blank
```

```bash
# Linux / WSL
~/.cache/ms-playwright/chromium-<VER>/chrome-linux/chrome --user-data-dir=/tmp/chrome-test about:blank
```

If that standalone launch also dies, the Python package isn't the problem — investigate antivirus exclusions for the `ms-playwright` directory, then reinstall the browser:

```
python -m playwright install --force chromium
```

## Optional: using a throw-away profile each run

You can sidestep the stale-profile issue entirely by pointing `--profile-dir` at a fresh path:

```bash
python main-ertflix-series.py --profile-dir C:\Temp\ertflix-session <URL>
```

The trade-off is that you have to log into ERTFlix every run. Useful for debugging, less convenient day-to-day.
