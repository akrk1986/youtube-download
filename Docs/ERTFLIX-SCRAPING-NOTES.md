# ERTFlix URL Scraping Notes

## Problem

The ERTFlix website uses a React-based single-page application (SPA) that loads episode URLs dynamically via JavaScript/API calls. The URLs are **NOT present in the initial HTML** when you fetch the page with simple HTTP requests.

### Investigation Results

1. **No `<a>` tags with vod URLs** in the initial HTML
2. **No episode data** in embedded script tags or `___INITIAL_STATE___` object
3. **Dynamic loading** - Episode data is fetched via API after the page renders
4. **API endpoint unknown** - Standard API patterns (tested 9+ variations) all return 404

## Solutions

### Solution 1: Use Selenium (Browser Automation)

**File:** `Tests/scrape-with-selenium.py`

This approach uses Selenium to:
- Load the page in a headless Chrome browser
- Wait for JavaScript to execute and render the episode links
- Extract the dynamically-loaded URLs

**Requirements:**
```bash
pip install selenium
# Also need chromedriver installed (system-specific)
```

**Usage:**
```bash
python Tests/scrape-with-selenium.py --program parea
python Tests/scrape-with-selenium.py --program parea --output Tests/parea-urls.txt
python Tests/scrape-with-selenium.py --program parea --wait 15  # Wait longer for slow connections
```

**Pros:**
- Works with any dynamically-loaded content
- Gets exactly what a user sees in their browser
- No need to reverse-engineer API endpoints

**Cons:**
- Requires Selenium + chromedriver installation
- Slower than API calls (must render full page)
- More resource-intensive

### Solution 2: Find the Correct API Endpoint (Manual)

If you want to use the original script (`main-extract-ertflix-urls.py`), you need to:

1. Open the series page in Chrome/Firefox
2. Open Developer Tools (F12)
3. Go to Network tab
4. Filter by "XHR" or "Fetch"
5. Look for API calls that return episode data
6. Update `PROGRAM_CONFIGS` with the correct API endpoint URL

**Example of what to look for:**
- API calls to `api.app.ertflix.gr` or similar
- JSON responses containing episode/vod arrays
- Endpoints that return episode metadata

### Solution 3: Static URL Lists (Manual)

If the series has a small number of episodes, you can manually collect URLs by:
1. Opening the series page in a browser
2. Right-clicking episode links and copying URLs
3. Creating a text file with the URLs

## Why main-extract-ertflix-urls.py Doesn't Work

The script was originally designed for ERTFlix pages that had static HTML with episode links. However, ERTFlix now uses a modern React SPA architecture where:

- Initial HTML is minimal (just app container)
- React JavaScript loads and renders the UI
- Episode data is fetched from API after render
- No episode URLs exist until JavaScript executes

This is common for modern websites but requires different scraping techniques.

## Recommendation

**RECOMMENDED - Capture Script Method:** Use the browser console capture script (`JS-files/capture-working-play-click.js`)
- **What it does:** Intercepts network requests to capture token API URLs from Play buttons
- **Pros:** Simple, fast, reliable, no setup required, auto-copies to clipboard, saves summary to file
- **Time:** Takes 30 seconds per video
- **Process:** Paste script in console, click Play button, wait 3 seconds for summary
- **Output:** Token API URL in clipboard + summary file in Downloads folder
- **Cons:** Manual process (but very quick)
- **Status:** Active, maintained, works with current ERTFlix site

**OBSOLETE - Browser Console Extraction Methods:**
- `JS-files-diag/obsolete-extract-ertflix-urls.js` - Outdated (site changed)
- `JS-files-diag/obsolete-extract-parea-urls-v4.js` - Outdated (site changed)
- `Tests/extract-urls-from-console.md` - May be outdated (check file if exists)

**For automated scraping:** Selenium solution (`Tests/scrape-with-selenium.py`) is complex in WSL
- **Issue:** Requires Windows Chrome + Windows ChromeDriver coordination
- **Status:** Technical challenges with WSL/Windows interop
- **Alternative:** Run on native Linux/Mac or Windows Python

**For API-based scraping:** Use browser Developer Tools to find the API endpoint (`Tests/manual-api-discovery.md`)

## Technical Details

### Tested API Endpoints (All returned 404)

For series `ser.521736-parea-1`:
- `https://api.app.ertflix.gr/api/series/ser.521736-parea-1`
- `https://api.app.ertflix.gr/api/v1/series/ser.521736-parea-1`
- `https://api.app.ertflix.gr/series/ser.521736-parea-1`
- `https://api.app.ertflix.gr/v1/series/ser.521736-parea-1`
- `https://api.app.ertflix.gr/api/vod/series/ser.521736-parea-1`
- `https://api.app.ertflix.gr/api/series/521736`
- `https://api.app.ertflix.gr/api/v1/series/521736`
- `https://api.app.ertflix.gr/content/series/ser.521736-parea-1`
- `https://api.app.ertflix.gr/api/content/ser.521736-parea-1`

### Page Structure

- **Framework:** React SPA
- **API Base:** `https://api.app.ertflix.gr/`
- **Initial State:** `___INITIAL_STATE___` object (contains config, not episode data)
- **Episode Loading:** Client-side API calls (not in initial HTML)
