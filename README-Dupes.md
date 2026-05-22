# Duplicate Inspection Workflow

Operating guide for finding and resolving duplicate songs with
`Utils/main-check-greek-singles.py`. This covers the **stage → inspect →
post-inspection** workflow only; for the full cross-checker (reports,
`--missing-action`, `--dupes-scope`) see [README-Utils.md](README-Utils.md).

## Why this exists

Suspected duplicates are scattered across many month folders. A tag app (mp3tag,
tagscan) opens one folder at a time, so inspecting dupes means constantly
switching folders. This workflow **moves all suspected duplicates into one
staging folder** so you can inspect them in a single session, records where each
file came from in its metadata, and then files each file according to your
verdict.

The "state" lives in two standard tag fields — both shown as columns and
editable in mp3tag and tagscan, for mp3/m4a/flac:

- **Album Artist** — at staging the script writes `DUPE-ORIGIN[<path relative to
  --root>]` here. Script-managed; you don't touch it.
- **Copyright** — you type your verdict here during inspection: `duplicate` or
  `dupe-ok` (leave blank = undecided).

Both fields are redundant/empty on these files, so using them loses nothing.
mtimes (file timestamps) are preserved through every move and tag write.

## The sequence

Activate the virtual environment first:

```bash
source ../.venv-av-linux/bin/activate      # Linux/WSL
```

### 1. Stage — dry-run (preview)

```bash
python Utils/main-check-greek-singles.py --stage-dupes dry-run \
    --start-month 2021-01 --end-month 2021-12
```

Lists every suspected duplicate it *would* move into `Staging-Dupes/`, touching
nothing.

- **With** `--start-month`/`--end-month`: scans the in-range month folders only
  (in-folder duplicates within each month + cross-month duplicates across them).
  `01-Singles-All/` is **not** scanned.
- **Without** a range: scans `01-Singles-All/` **and** all month folders.

### 2. Stage — milk-run (perform the moves)

```bash
python Utils/main-check-greek-singles.py --stage-dupes milk-run \
    --start-month 2021-01 --end-month 2021-12
```

For each file: writes `DUPE-ORIGIN[<origin>]` into its Album Artist tag, then moves it
to `<root>/Staging-Dupes/` (named `<source-folder> — <filename>`).

### 3. Inspect — manually, in mp3tag / tagscan

Open **only** `Staging-Dupes/` (one folder, no switching). For each file: review
the tags, listen, then **type your verdict in the Copyright field** (leave the
Album Artist / `DUPE-ORIGIN[...]` field alone):

| Decision | Set Copyright to | Meaning |
|---|---|---|
| Real duplicate | `duplicate` | Same song, same year/album → discard |
| Not a duplicate | `dupe-ok` | Same song but different year/album → keep |
| Undecided | leave blank | inspect later |

The verdict must be exactly `duplicate` or `dupe-ok` (case-insensitive). Anything
else (e.g. `not a duplicate`) is treated as *ambiguous* and the file is left
untouched.

### 4. Post-inspection — dry-run (preview)

```bash
python Utils/main-check-greek-singles.py --post-inspection dry-run
```

Reads each staged file's verdict and reports what it *would* do, moving nothing.

### 5. Post-inspection — milk-run (perform the moves)

```bash
python Utils/main-check-greek-singles.py --post-inspection milk-run
```

| Verdict | Action |
|---|---|
| `duplicate` | moved to `<root>/Dupes/` (a holding area — delete these yourself later) |
| `dupe-ok` | moved back to its original folder; the Album Artist + Copyright tags are cleared |
| none yet | reported as *pending*, left in `Staging-Dupes/` |
| ambiguous / unmarked | reported, left in place (never moved) |

Repeat steps 3–5 as many times as you like — inspect a batch, run
post-inspection, inspect more. Nothing is deleted by the script.

## Golden rule

Always run **dry-run** before **milk-run**, at both the stage and the
post-inspection step.

## Flags

| Flag | Values | Description |
|---|---|---|
| `--stage-dupes` | `dry-run`, `milk-run` | Move suspected duplicates into the staging folder, recording each file's origin in its Album Artist tag. |
| `--post-inspection` | `dry-run`, `milk-run` | File staged files by their Copyright verdict: `duplicate` → `Dupes/`, `dupe-ok` → restored to origin. |
| `--staging-dir` | path | Staging folder. Default `<root>/Staging-Dupes`. |
| `--dupes-dir` | path | Folder for confirmed duplicates (for eventual deletion). Default `<root>/Dupes`. |
| `--start-month` / `--end-month` | `yyyy-mm` or `yyyy` | Inclusive month-folder range that bounds `--stage-dupes`. |
| `--root` | path | Greek music root containing `01-Singles-All` and `03-Singles-by-Month`. Default `~/Music/Greek`. |

`--stage-dupes` and `--post-inspection` are mutually exclusive with each other and
with `--missing-action` / `--dupes-scope`.

## Notes

- **State fields:** origin lives in **Album Artist** (ID3 `TPE2` / MP4 `aART` /
  Vorbis `ALBUMARTIST`) and the verdict in **Copyright** (ID3 `TCOP` / MP4 `cprt`
  / Vorbis `COPYRIGHT`) — both standard fields shown as columns and editable in
  mp3tag and tagscan, and normally redundant/empty on these files. Both are
  cleared on restore. (Grouping was tried first but mp3tag won't column it and
  tagscan ignores it; the comment tag is avoided because it holds the source URL.)
- **Timestamps:** original file mtimes are preserved across tag writes and moves.
- **Re-runnable:** the steps read state from the files themselves, so they can be
  run repeatedly and resumed at any point.
- **Staged filenames** are prefixed with the source folder for readability; the
  authoritative origin is the Album Artist `DUPE-ORIGIN[...]` tag, not the filename.
