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
// EXTRACTION CODE
// =============================================================================

// Wrap in function to avoid variable redeclaration errors in Firefox
(function() {

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

// Group links by href to find the one with episode info
const linksByHref = {};
links.forEach(link => {
    const href = link.href;
    if (pattern.test(href)) {
        if (!linksByHref[href]) {
            linksByHref[href] = [];
        }
        linksByHref[href].push(link);
    }
});

// Process each unique episode URL
Object.keys(linksByHref).forEach(href => {
    if (seen.has(href)) return;
    seen.add(href);

    const episodeLinks = linksByHref[href];
    let episodeNumber = '';
    let episodeTitle = '';

    // Find the link that contains episode info (has the episodeNumber span)
    for (const link of episodeLinks) {
        // Look for episode number span
        const numberSpan = link.querySelector('[class*="episodeNumber"]');
        const titleSpan = link.querySelector('[class*="episodeSubtitle"]');

        if (numberSpan) {
            episodeNumber = numberSpan.textContent.trim();
        }
        if (titleSpan) {
            episodeTitle = titleSpan.textContent.trim();
        }

        // If we found both, we're done
        if (episodeNumber && episodeTitle) {
            break;
        }
    }

    // Combine episode number and title
    const text = episodeNumber && episodeTitle
        ? `${episodeNumber} - ${episodeTitle}`
        : episodeNumber || episodeTitle || 'No title found';

    results.push({ url: href, text: text });
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

// Copy URLs with text to clipboard (tab-separated)
const urlList = results.map(item => `${item.url}\t${item.text}`).join('\n');

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
    console.log(`✓ SUCCESS: ${results.length} URLs with text copied to clipboard!`);
    console.log('='.repeat(80));
    console.log('\nFormat: URL [TAB] Text (one per line)');
    console.log('You can now paste them into a text file or spreadsheet.');
} else {
    console.log('FIREFOX USERS: Automatic clipboard copy not available.');
    console.log('='.repeat(80));
    console.log('\nTo copy URLs with text, use one of these methods:');
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
console.log('URLs with text stored in: window.ertflixUrls');
console.log('Type "ertflixUrls" in console to see all data');
console.log('Format: URL [TAB] Episode_Number - Episode_Title');
console.log('='.repeat(80));

})(); // End of function scope
