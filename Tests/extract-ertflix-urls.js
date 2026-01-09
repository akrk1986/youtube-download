// ERTFlix URL Extractor - Browser Console Script
//
// Instructions:
// 1. Open the series page in your browser (e.g., https://www.ertflix.gr/series/ser.521736-parea-1)
// 2. Press F12 to open Developer Tools
// 3. Click the Console tab
// 4. Copy and paste this entire file into the console
// 5. Press Enter
// 6. URLs will be displayed and copied to clipboard
//
// To extract URLs for different programs, change the pattern variable below:

// =============================================================================
// CONFIGURATION: Change this pattern for different programs
// =============================================================================

// Parea (default)
const pattern = /https:\/\/www\.ertflix\.gr\/vod\/vod\.\d+-parea-\d+/;

// Uncomment one of these for other programs:
// const pattern = /https:\/\/www\.ertflix\.gr\/en\/vod\/vod\.\d+-nukhta-stasou-\d+/;  // Nykhta Stasou
// const pattern = /https:\/\/www\.ertflix\.gr\/vod\/vod\.\d+-e-aule-ton-khromaton-\d+/;  // Aule Ton Chromaton

// Or create a custom pattern:
// const pattern = /https:\/\/www\.ertflix\.gr\/vod\/vod\.\d+-YOUR-PATTERN-\d+/;

// =============================================================================
// EXTRACTION CODE (no need to modify below this line)
// =============================================================================

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

// Display results in console
console.clear();
console.log('='.repeat(80));
console.log('ERTFlix URL Extractor');
console.log('='.repeat(80));
console.log(`\nPattern: ${pattern}\n`);
console.log(`Found ${results.length} episodes:\n`);

results.forEach((item, index) => {
    console.log(`${(index + 1).toString().padStart(3, ' ')}. ${item.url}`);
    if (item.text) {
        console.log(`     Text: ${item.text}`);
    }
});

// Copy URLs to clipboard (one per line)
const urlList = results.map(item => item.url).join('\n');

// Try automatic clipboard copy (works in Chrome/Edge, not Firefox)
let copied = false;
if (typeof copy === 'function') {
    try {
        copy(urlList);
        copied = true;
    } catch (e) {
        copied = false;
    }
}

console.log('\n' + '='.repeat(80));
if (copied) {
    console.log(`✓ SUCCESS: ${results.length} URLs copied to clipboard!`);
    console.log('='.repeat(80));
    console.log('\nYou can now paste them into a text file.');
} else {
    console.log('FIREFOX USERS: Automatic clipboard copy not available.');
    console.log('='.repeat(80));
    console.log('\nTo copy URLs, use one of these methods:');
    console.log('');
    console.log('METHOD 1 - Copy from variable:');
    console.log('  Type this in console:  ertflixUrls');
    console.log('  Then right-click the output and select "Copy object"');
    console.log('');
    console.log('METHOD 2 - Manual copy:');
    console.log('  Scroll up and manually select the URLs listed above');
    console.log('');
    console.log('METHOD 3 - Use Chrome/Edge instead (has auto-copy feature)');
}

// Make the URL list available as a variable for manual access
window.ertflixUrls = urlList;
console.log('\n' + '='.repeat(80));
console.log('URLs stored in: window.ertflixUrls');
console.log('Type "ertflixUrls" in console to see all URLs');
console.log('='.repeat(80));
