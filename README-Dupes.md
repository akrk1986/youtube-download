# Duplicate Inspection Workflow

Operating guide for finding and resolving duplicate songs with
`Utils/main-check-greek-singles.py`. This covers the **stage → inspect →
post-inspection** workflow only; for the full cross-checker (reports,
`--missing-action`, `--dupes-scope`) see [README-Utils.md](README-Utils.md).

## Why this exists

Suspected duplicates are scattered across many month folders. A tag app (mp3tag,
tagscan) opens one folder at a time, so inspecting dupes means constantly
switching folders. This workflow **moves each dupe group into its own staging
subfolder** (`Staging-Dupes/grp-NNNN/`) so you can inspect one group at a time,
records where each file came from in its metadata, and then files each file
according to your verdict.

The "state" lives in two standard tag fields — both shown as columns and
editable in mp3tag and tagscan, for mp3/m4a/flac:

- **Album Artist** — at staging the script writes `DUPE-ORIGIN[<path relative to
  --root>]` here. Script-managed; you don't touch it. Cleared on restore.
- **Copyright** — you type your verdict here during inspection: `duplicate` or
  `original` (leave blank = undecided). The script **never** writes the verdict —
  only you do — and it **persists** on the file.

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

Lists the dupe groups it *would* stage (into `Staging-Dupes/grp-NNNN/`
subfolders) as a table, touching nothing.

- **With** `--start-month`/`--end-month`: scans the in-range month folders only
  (in-folder duplicates within each month + cross-month duplicates across them).
  `01-Singles-All/` is **not** scanned.
- **Without** a range: scans `01-Singles-All/` **and** all month folders.

### 2. Stage — milk-run (perform the moves)

```bash
python Utils/main-check-greek-singles.py --stage-dupes milk-run \
    --start-month 2021-01 --end-month 2021-12
```

Each dupe group goes into its own `<root>/Staging-Dupes/grp-NNNN/` subfolder. For
each file the script writes `DUPE-ORIGIN[<origin>]` into its Album Artist tag, then
moves it into the group folder (named `<source-folder> — <filename>`). Group
numbers continue past any folders left from a previous run.

### 3. Inspect — manually, in mp3tag / tagscan

Open **one group folder** at a time, e.g. `Staging-Dupes/grp-0001/` — each holds
all the suspected copies of a single song. For each file: review the tags, listen,
then **type your verdict in the Copyright field** (leave the Album Artist /
`DUPE-ORIGIN[...]` field alone):

| Decision | Set Copyright to | Meaning |
|---|---|---|
| Redundant copy → discard | `duplicate` | A real duplicate → moved to `Dupes/` |
| A version to keep | `original` | Keep this one → restored; remembered so it isn't re-flagged |
| Undecided | leave blank | inspect later |

Two common cases:

- **True duplicates** (same recording, redundant): mark **one** copy `original`
  (the keeper) and the rest `duplicate`.
- **Different versions** (same title/artist, but genuinely different recordings —
  different year/album): mark **all** of them `original`.

The verdict must be exactly `duplicate` or `original` (case-insensitive). Anything
else (e.g. `not a duplicate`) is treated as *ambiguous* and the file is left
untouched.

### 4. Post-inspection — dry-run (preview)

```bash
python Utils/main-check-greek-singles.py --post-inspection dry-run
# only the groups you've inspected (inclusive range of grp-NNNN folders):
python Utils/main-check-greek-singles.py --post-inspection dry-run --staging-groups 1,3
```

Reads the staged files' verdicts and reports what it *would* do, moving nothing.
`--staging-groups N1,N2` limits it to `grp-N1`..`grp-NN` (`1,3` = grp-0001..grp-0003;
`5,5` = grp-0005 only); without it, all group folders are processed.

### 5. Post-inspection — milk-run (perform the moves)

```bash
python Utils/main-check-greek-singles.py --post-inspection milk-run
python Utils/main-check-greek-singles.py --post-inspection milk-run --staging-groups 1,3
```

| Verdict | Action |
|---|---|
| `duplicate` | moved to `<root>/Dupes/` (a holding area — delete these yourself later) |
| `original` | moved back to its original folder; only the Album Artist marker is cleared — the `original` verdict **stays** on the file |
| none yet | reported as *pending*, left in its group folder |
| ambiguous / unmarked | reported, left in place (never moved) |

A group folder is removed once it has no files left, so finished groups disappear
from `Staging-Dupes/`.

Repeat steps 3–5 as many times as you like — inspect a batch, run
post-inspection, inspect more. Nothing is deleted by the script.

### Aborting a staging run

To send **every** staged file straight back to its original folder without
inspecting or marking anything, use `--unstage` (it reads each file's
`DUPE-ORIGIN` marker, moves it back, clears the marker, and leaves the verdict
untouched):

```bash
python Utils/main-check-greek-singles.py --unstage dry-run    # preview
python Utils/main-check-greek-singles.py --unstage milk-run   # do it
```

`--unstage` also accepts `--staging-groups N1,N2` to restore only a range of group
folders; emptied folders are removed.

## Golden rule

Always run **dry-run** before **milk-run**, at both the stage and the
post-inspection step.

## Flags

| Flag | Values | Description |
|---|---|---|
| `--stage-dupes` | `dry-run`, `milk-run` | Move each dupe group into its own `Staging-Dupes/grp-NNNN/` subfolder, recording each file's origin in its Album Artist tag. |
| `--post-inspection` | `dry-run`, `milk-run` | File staged files by their Copyright verdict: `duplicate` → `Dupes/`, `original` → restored to origin (verdict kept). Honors `--staging-groups`. |
| `--unstage` | `dry-run`, `milk-run` | Abort: move staged files back to their origin (from the `DUPE-ORIGIN` marker), ignoring the verdict and leaving it untouched. No verdict needed. Honors `--staging-groups`. |
| `--staging-groups` | `N1,N2` | Limit `--post-inspection` / `--unstage` to a contiguous inclusive range of group folders (`7,10` = grp-0007..grp-0010; `7,7` = grp-0007 only). Default: all groups. |
| `--staging-dir` | path | Staging folder. Default `<root>/Staging-Dupes`. |
| `--dupes-dir` | path | Folder for confirmed duplicates (for eventual deletion). Default `<root>/Dupes`. |
| `--start-month` / `--end-month` | `yyyy-mm` or `yyyy` | Inclusive month-folder range that bounds `--stage-dupes`. |
| `--root` | path | Greek music root containing `01-Singles-All` and `03-Singles-by-Month`. Default `~/Music/Greek`. |

`--stage-dupes`, `--post-inspection`, and `--unstage` are mutually exclusive with
each other and with `--missing-action` / `--dupes-scope`.

## Notes

- **State fields:** origin lives in **Album Artist** (ID3 `TPE2` / MP4 `aART` /
  Vorbis `ALBUMARTIST`) and the verdict in **Copyright** (ID3 `TCOP` / MP4 `cprt`
  / Vorbis `COPYRIGHT`) — both standard fields shown as columns and editable in
  mp3tag and tagscan, and normally redundant/empty on these files. (Grouping was
  tried first but mp3tag won't column it and tagscan ignores it; the comment tag
  is avoided because it holds the source URL.)
- **The script never writes the verdict — only you do.** It manages only the
  Album Artist origin marker (writes it on staging, clears it on restore).
- **`original` persists and is remembered.** On the next run the dupe check still
  detects clusters, but a cluster whose members are **all** marked `original` is
  **skipped** (you already judged it). If a cluster has any new/unmarked member,
  the **whole** cluster is re-staged — originals included — so you can compare the
  newcomer against the existing versions. This catches a true duplicate that turns
  up later in a folder an earlier run didn't scan, without re-bugging you about
  versions you've already cleared.
- **Timestamps:** original file mtimes are preserved across tag writes and moves.
- **Group folders** (`grp-NNNN`) are numbered per staging run, continuing past any
  folders left from a previous run so a re-stage never collides; a folder is
  removed once it is empty.
- **Staged filenames** are prefixed with the source folder for readability; the
  authoritative origin is the Album Artist `DUPE-ORIGIN[...]` tag, not the filename.
