Revision 1 — 2026-05-05 11:30

# Code Review — Python Skills Findings

Review of codebase against: python-anti-patterns, python-code-style, python-design-patterns, python-security, python-type-safety skills.

---

## 1. Bug (Real Defect) — Fix First

**`funcs_utils/file_operations.py:147`**

```python
if audio_file.suffix == 'mp3':   # BUG: always False
```

`Path.suffix` returns `'.mp3'` (with dot). Comparing to `'mp3'` (no dot) is always `False`.
Every MP3 moved by `organize_media_files_silent()` gets tracked as M4A in the returned dict.

**Fix:**
```python
if audio_file.suffix.lower() == '.mp3':
```

---

## 2. Code Style — String Quoting

**`main-qb-notify.py`** — 4 double-quoted strings that should be single-quoted:

- Line 22: `description="Send Slack notification for completed torrent"`
- Line 27: `help="Name of the completed torrent"`
- Line 32: `help="Full path to the downloaded content"`
- Line 49: `payload = {"text": message}` → `{'text': message}`

---

## 3. Code Style — Redundant Case Handling

**`funcs_for_main_yt_dlp/file_organization.py:74-78`**

```python
if path.endswith('.mp3') or path.endswith('.MP3'):
elif path.endswith('.m4a') or path.endswith('.M4A'):
elif path.endswith('.flac') or path.endswith('.FLAC'):
```

Should be:
```python
if path.lower().endswith('.mp3'):
elif path.lower().endswith('.m4a'):
elif path.lower().endswith('.flac'):
```

---

## 4. os.path in Standalone Scripts (Low Priority)

`Tests-Standalone/` files use `os.path.exists()` / `os.path.expanduser()` instead of `pathlib.Path`:
- `setup-chromedriver-windows.py:17`
- `scrape-with-selenium.py:73, 78, 79, 89`
- `test_mp4_tag_keys.py:46`

---

## Status: Pending User Approval
