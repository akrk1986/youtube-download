# JS-files - Production Browser Scripts

This directory contains **production-ready JavaScript scripts** for users to paste into their browser console.

## Scripts

### capture-working-play-click.js
Captures ERTFlix token API URLs when clicking Play buttons on episode pages.

**Usage:**
1. Navigate to ERTFlix series page (e.g., `https://www.ertflix.gr/#/details/ERT_PS054741_E0`)
2. Open browser console (F12 → Console tab)
3. Paste the entire script and press Enter
4. Click any Play button
5. Copy the token API URL from console output

**Output:** Token API URLs that can be passed directly to `main-yt-dlp.py` for downloading.

### extract-ertflix-urls.js
Extracts episode page URLs from ERTFlix series pages.

**Usage:**
1. Navigate to ERTFlix series page
2. Open browser console
3. Paste script and press Enter
4. Copy URLs from `window.__ertflixEpisodeUrls`

**Output:** Array of episode detail page URLs.

### extract-parea-urls-v4.js
Extracts Parea episode URLs from image src attributes on series pages.

**Usage:**
1. Navigate to Parea series page
2. Open browser console
3. Paste script and press Enter
4. Copy URLs from console output

**Output:** Formatted episode URLs with episode numbers.

## Integration with main-yt-dlp.py

The captured token API URLs can be used directly:

```bash
# Set browser cookies for authentication
export YTDLP_USE_COOKIES=firefox  # or chrome

# Download using token URL
python main-yt-dlp.py --only-audio "https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?content_id=..."
```

The Python script automatically:
- Detects token API URLs
- Resolves them to playback URLs via the API
- Downloads the content with proper authentication

## Notes

- **Diagnostic scripts** are in `../JS-files-diag/` (for debugging, not general use)
- All scripts are read-only and don't modify ERTFlix pages
- Scripts work on ERTFlix website as of 2026-02
