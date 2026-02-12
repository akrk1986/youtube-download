# JS-files-diag - Diagnostic Browser Scripts

This directory contains **diagnostic and debugging scripts** used during development. These are **not intended for general use** - they were created to understand ERTFlix's internal behavior and are kept for reference.

## Contents

### Parea URL Extraction Attempts
- `extract-parea-urls.js` - Original attempt (didn't work - Angular routing complexity)
- `extract-parea-urls-diagnostic.js` - Episode discovery diagnostic
- `extract-parea-urls-v2.js` - Asset card extraction attempt
- `extract-parea-urls-v3.js` - Deep Angular analysis
- `extract-parea-urls-v4.js` - **Success** - Now in `../JS-files/` as production script

### Video URL Extraction Attempts
- `extract-video-url-diagnostic.js` - Diagnostic for video pages
- `extract-video-url-shaka.js` - Shaka Player interceptor attempt

### ERTFlix URL Extraction
- `extract-ertflix-urls-debug.js` - Debug version with verbose logging

## History

These scripts were created to reverse-engineer how ERTFlix:
- Uses Angular routing for navigation
- Loads episode data dynamically
- Calls token APIs for video playback
- Uses Shaka Player for video streaming

## Production Scripts

For **working scripts intended for users**, see `../JS-files/`:
- `capture-working-play-click.js` - Captures token API URLs
- `extract-ertflix-urls.js` - Extracts episode URLs
- `extract-parea-urls-v4.js` - Extracts Parea URLs

## Notes

- These scripts are kept for historical reference and debugging
- They may not work as-is (some were abandoned experiments)
- Diagnostic output is verbose and technical
- Use production scripts in `../JS-files/` for actual work
