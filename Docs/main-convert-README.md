# main-convert.py - Audio Tag Conversion Tool

## Overview

`main-convert.py` is a utility script for copying audio metadata tags between MP3 and M4A files. It's designed to synchronize tags across different audio format versions of the same files.

## Features

- **Bidirectional tag copying**: MP3 ↔ M4A
- **Automatic file conversion**: Optionally create missing target files using ffmpeg
- **Original filename preservation**: Copies TENC (MP3) ↔ ©lyr (M4A) tags
- **Date normalization**: Converts YYYYMMDD format to YYYY
- **Flexible directory structure**: Supports custom directory layouts

## Usage

### Basic Syntax

```bash
python main-convert.py --source {mp3|m4a} [OPTIONS]
```

### Required Arguments

- `--source {mp3|m4a}`: Source audio format to read tags from

### Optional Arguments

- `--create-missing-files`: Convert and create missing target files before copying tags
- `--top-level-directory PATH`: Top-level directory containing MP3 and M4A subfolders

### Directory Structure

#### Default (without --top-level-directory)
```
project/
├── staging-mp3/       # MP3 source files
└── staging-m4a/       # M4A target files
```

#### Custom (with --top-level-directory)
```
custom-dir/
├── MP3/              # MP3 files (uppercase folder name)
└── M4A/              # M4A files (uppercase folder name)
```

## Examples

### Copy tags from MP3 to M4A (default directories)
```bash
python main-convert.py --source mp3
```

### Copy tags from M4A to MP3 (default directories)
```bash
python main-convert.py --source m4a
```

### Copy tags with automatic file conversion
```bash
python main-convert.py --source mp3 --create-missing-files
```

### Use custom directory structure
```bash
python main-convert.py --source mp3 --top-level-directory /path/to/audio-files
```

## Tag Mapping

### Standard Tags

| Common Name | MP3 Tag | M4A Atom | Description |
|-------------|---------|----------|-------------|
| Title | title | ©nam | Song title |
| Artist | artist | ©ART | Artist name |
| Album Artist | albumartist | aART | Album artist |
| Album | album | ©alb | Album name |
| Date | date | ©day | Release date (normalized to YYYY) |
| Track Number | tracknumber | trkn | Track number |
| Comment | COMM | ©cmt | Comments |
| Composer | composer | ©wrt | Composer |

### Special Tags

| Common Name | MP3 Tag | M4A Atom | Description |
|-------------|---------|----------|-------------|
| Original Filename | TENC | ©lyr | Original filename (without extension) |

**Note:** The `encodedby` field is mapped to:
- **MP3**: TENC frame (Encoded by)
- **M4A**: ©lyr atom (Unsynced lyrics)

This allows preservation of the original YouTube filename across format conversions.

## Date Normalization

The script automatically normalizes date formats:

- **Input**: `20241031` (YYYYMMDD format)
- **Output**: `2024` (YYYY format)

Supported date formats:
- YYYYMMDD (8 digits)
- YYYY (4 digits)
- ISO date strings (parsed with arrow library)

## File Conversion

When using `--create-missing-files`, the script will:

1. Check if target file exists
2. If missing or empty, convert from source format using ffmpeg
3. Copy tags to the newly converted file

**Conversion functions:**
- MP3 → M4A: Uses `convert_mp3_to_m4a()` from `funcs_audio_conversion.py`
- M4A → MP3: Uses `convert_m4a_to_mp3()` from `funcs_audio_conversion.py`

## Exit Codes

- **0**: Success (all files processed without warnings)
- **1**: Warnings occurred (missing files, conversion failures, etc.)

## Output

The script provides detailed output:

```
Copying tags from MP3 files to M4A files...
Processing: Song Title.mp3
  Written tags: title, artist, albumartist, date, album, tracknumber, encodedby

Completed: 10 files processed, 2 files converted, 0 warnings
```

## Requirements

- Python 3.10+
- mutagen library
- arrow library
- ffmpeg (for file conversion with --create-missing-files)

## Common Use Cases

### Synchronize tags after editing MP3 files
```bash
# 1. Edit MP3 tags in mp3tag or other tool
# 2. Copy updated tags to M4A versions
python main-convert.py --source mp3
```

### Create M4A versions from MP3 with tags
```bash
# Convert MP3 files to M4A and copy all tags
python main-convert.py --source mp3 --create-missing-files
```

### Batch update tags from M4A to MP3
```bash
# If you have properly tagged M4A files and want to update MP3 versions
python main-convert.py --source m4a
```

### Process files in custom directory structure
```bash
# Work with files in yt-audio directory structure
python main-convert.py --source mp3 --top-level-directory yt-audio
```

## Notes

- Only non-empty tag values are copied
- Existing tags in target files are overwritten
- Album artwork is not copied (must be embedded in original files)
- Track numbers are converted between string (MP3) and tuple (M4A) formats
- The script skips files that cannot be read or written

## Troubleshooting

### "Target file not found" warnings
- Use `--create-missing-files` to automatically convert missing files
- Or manually create target files first

### "Error reading tags" messages
- Check that files are valid audio files
- Ensure files are not corrupted or locked by another application

### Date format not normalized
- Check that date tag contains valid date format
- Script attempts multiple parsing methods before falling back to regex

## Related Scripts

- `main-yt-dlp.py`: Main YouTube downloader (generates tagged audio files)
- `funcs_audio_conversion.py`: Audio conversion functions
- `funcs_audio_tag_handlers.py`: Tag handler classes

## See Also

- [Project README](README.md)
- [CHANGELOG](Docs/CHANGELOG.md)
- [mp3tag Configuration Guide](Docs/Configuring%20mp3tag%20to%20display%20yt-dlp%20generated%20audio%20files.md)
