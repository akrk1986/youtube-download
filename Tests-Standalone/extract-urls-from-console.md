# Extract ERTFlix URLs Using Browser Console

This is the **simplest** and **most reliable** method to extract episode URLs from ERTFlix series pages.

## Steps

### 1. Open the Series Page

Open the series page in your browser:
- Example: https://www.ertflix.gr/series/ser.521736-parea-1

### 2. Wait for Page to Load

Wait for all episodes to appear on the page. Scroll down if needed to ensure all episodes are loaded.

### 3. Open Browser Console

Press `F12` to open Developer Tools, then click the **Console** tab.

### 4. Run the Extraction Script

**Option A: Use the saved script file**

Open `Tests/extract-ertflix-urls.js` in a text editor, copy the entire contents, paste into the console and press Enter.

**Option B: Use the code below**

Copy and paste this JavaScript code into the console and press Enter:

```javascript
// Extract all vod URLs matching the pattern
const pattern = /https:\/\/www\.ertflix\.gr\/vod\/vod\.\d+-parea-\d+/;
const links = Array.from(document.querySelectorAll('a[href*="/vod/vod."]'));

const results = [];
const seen = new Set();

links.forEach(link => {
    const href = link.href;
    if (pattern.test(href) && !seen.has(href)) {
        seen.add(href);
        const text = link.textContent.trim().replace(/\s+/g, ' ');
        results.push({ url: href, text: text });
    }
});

// Display results
console.log(`Found ${results.length} episodes:\n`);
results.forEach((item, index) => {
    console.log(`${index + 1}. ${item.url}`);
    if (item.text) {
        console.log(`   ${item.text}`);
    }
});

// Copy URLs to clipboard (one per line)
const urlList = results.map(item => item.url).join('\n');
copy(urlList);
console.log(`\n✓ ${results.length} URLs copied to clipboard!`);
```

### 5. Results

The script will:
1. Display all found URLs in the console
2. **Automatically copy them to your clipboard**

You can now paste the URLs into a text file.

## For Different Programs

To extract URLs for different programs, just change the `pattern` variable:

### Nykhta Stasou
```javascript
const pattern = /https:\/\/www\.ertflix\.gr\/en\/vod\/vod\.\d+-nukhta-stasou-\d+/;
```

### Aule Ton Chromaton
```javascript
const pattern = /https:\/\/www\.ertflix\.gr\/vod\/vod\.\d+-e-aule-ton-khromaton-\d+/;
```

### Parea
```javascript
const pattern = /https:\/\/www\.ertflix\.gr\/vod\/vod\.\d+-parea-\d+/;
```

## Save to File

Once you have the URLs in your clipboard:

### On Windows:
```powershell
# Paste the URLs into a file
notepad Tests\parea-urls.txt
```

### On Linux/WSL:
```bash
# Paste from clipboard to file (if xclip is installed)
xclip -o > Tests/parea-urls.txt

# Or just manually paste into a text editor
nano Tests/parea-urls.txt
```

## Why This Works

- No complex setup required
- Works with any dynamically-loaded website
- You see exactly what the browser renders
- Takes less than 30 seconds
- No Python dependencies needed

## Troubleshooting

### "copy is not defined" error

Some browsers don't support the `copy()` function in console. In that case:

1. Remove the `copy(urlList);` line
2. The URLs will still be displayed in the console
3. Manually select and copy them

### Not all episodes showing

- Scroll down to load more episodes (some sites use lazy loading)
- Wait a few seconds after scrolling
- Run the script again

### Pattern doesn't match

- Right-click on an episode link and select "Copy link address"
- Look at the URL format
- Adjust the pattern regex to match
