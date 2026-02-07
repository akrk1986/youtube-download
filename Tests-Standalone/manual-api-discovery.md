# Manual API Discovery for ERTFlix

Since the ERTFlix website loads episodes dynamically via JavaScript, we need to find the API endpoint it uses.

## Steps to Find the API Endpoint

1. **Open the series page in Chrome or Firefox**
   - Example: https://www.ertflix.gr/series/ser.521736-parea-1

2. **Open Developer Tools**
   - Press `F12` or right-click and select "Inspect"

3. **Go to the Network Tab**
   - Click on the "Network" tab in Developer Tools

4. **Filter by XHR/Fetch**
   - Click the "XHR" or "Fetch/XHR" button to filter network requests
   - This shows only API calls, not images/CSS/JS files

5. **Reload the Page**
   - Press `Ctrl+R` or `F5` to reload the page
   - Watch the Network tab as it loads

6. **Look for API Calls**
   - Look for requests to `api.app.ertflix.gr` or similar
   - Look for responses that contain episode data (JSON format)
   - Click on each request to see the response

7. **Identify the Correct Endpoint**
   - Find the request that returns a list of episodes/vods
   - Note the full URL (e.g., `https://api.app.ertflix.gr/v1/series/521736/episodes`)
   - Note the response format

8. **Test the Endpoint**
   - Copy the URL
   - Test it with curl or in your browser:
     ```bash
     curl "https://api.app.ertflix.gr/DISCOVERED/PATH" | python -m json.tool
     ```

9. **Update the Script**
   - Once you find the working endpoint, you can update `main-extract-ertflix-urls.py`
   - Or create a custom script to fetch and parse the JSON

## Example: What to Look For

You're looking for JSON responses that contain episode information like:

```json
{
  "episodes": [
    {
      "id": "vod.578113",
      "title": "Επεισόδιο 19",
      "url": "https://www.ertflix.gr/vod/vod.578113-parea-19"
    },
    ...
  ]
}
```

## Alternative: Extract URLs from Browser Console

If you can't find the API endpoint, you can extract URLs directly from the loaded page:

1. Load the series page in your browser
2. Wait for all episodes to load
3. Open the browser console (`F12` > Console tab)
4. Run this JavaScript code:

```javascript
// Extract all vod URLs
const links = Array.from(document.querySelectorAll('a[href*="/vod/vod."]'));
const urls = links.map(link => link.href).filter((url, index, self) => self.indexOf(url) === index);
console.log(urls.join('\n'));
```

5. Copy the output and save it to a text file

## Quick Test URLs

Try these potential API endpoints (replace `521736` with the series ID):

```bash
# Test various endpoint patterns
for path in \
  "api/series/ser.521736-parea-1" \
  "api/v1/series/ser.521736-parea-1" \
  "api/series/521736/episodes" \
  "v1/series/521736" \
  "api/content/series/ser.521736-parea-1"
do
  echo "Testing: https://api.app.ertflix.gr/$path"
  curl -s -o /dev/null -w "%{http_code}\n" "https://api.app.ertflix.gr/$path"
done
```

Look for responses with status code `200` (success).
