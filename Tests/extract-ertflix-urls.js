// ERTFlix URL Extractor - Browser Console Script
//
// Instructions:
// 1. Open ANY series page in your browser
//    Examples:
//    - https://www.ertflix.gr/series/ser.521736-parea-1
//    - https://www.ertflix.gr/en/series/ser.27883-nykhta-stasou
//    - https://www.ertflix.gr/series/ser.99028-i-ayli-ton-chromaton
// 2. Wait 5-10 seconds for the page to fully load
// 3. Press F12 to open Developer Tools
// 4. Click the Console tab
// 5. Copy and paste this entire file into the console
// 6. Press Enter
// 7. URLs with text will be automatically extracted and copied to clipboard
//
// The script automatically detects which program you're viewing and
// generates the correct URL pattern - no manual configuration needed!

// =============================================================================
// EXTRACTION CODE
// =============================================================================

// Wrap in function to avoid variable redeclaration errors in Firefox
(function() {

// =============================================================================
// AUTO-DETECT PROGRAM FROM PAGE URL
// =============================================================================

const currentUrl = window.location.href;
console.clear();
console.log('='.repeat(80));
console.log('ERTFlix URL Extractor');
console.log('='.repeat(80));
console.log(`\nCurrent page: ${currentUrl}`);

// Extract series slug from URL
// URLs are like: https://www.ertflix.gr/series/ser.521736-parea-1
// or: https://www.ertflix.gr/en/series/ser.27883-nykhta-stasou
const seriesMatch = currentUrl.match(/\/series\/ser\.\d+-([\w-]+)/);

if (!seriesMatch) {
    console.log('\n❌ ERROR: Not on a series page!');
    console.log('This script must be run on a series page like:');
    console.log('  https://www.ertflix.gr/series/ser.XXXXXX-program-name');
    return;
}

const seriesSlug = seriesMatch[1];
console.log(`Detected series slug: ${seriesSlug}`);

// Detect language path (/en/ or not)
const hasEnglishPath = currentUrl.includes('/en/');
const langPath = hasEnglishPath ? '/en' : '';

// Remove trailing numbers from slug (e.g., "parea-1" -> "parea-")
// This handles season numbers in series URLs
const baseSlug = seriesSlug.replace(/\d+$/, '');

// Try to find the actual VOD slug from links on the page
// This handles cases where series slug differs from VOD slug (e.g., nykhta vs nukhta)
const allVodLinks = document.querySelectorAll('a[href*="/vod/vod."]');
let detectedVodSlug = baseSlug;

if (allVodLinks.length > 0) {
    const firstVodHref = allVodLinks[0].href;
    // Extract slug from VOD URL: /vod/vod.NUMBER-SLUG-NUMBER
    const vodSlugMatch = firstVodHref.match(/\/vod\/vod\.\d+-([\w-]+)-\d+/);
    if (vodSlugMatch) {
        detectedVodSlug = vodSlugMatch[1] + '-';
        if (detectedVodSlug !== baseSlug) {
            console.log(`Note: VOD slug differs from series slug`);
            console.log(`  Series uses: "${baseSlug}"`);
            console.log(`  VOD uses: "${detectedVodSlug}"`);
        }
    }
}

// Build pattern based on detected VOD slug
// Pattern: https://www.ertflix.gr[/en]/vod/vod.NNNNNN-SLUG-NN
const patternString = `https:\\/\\/www\\.ertflix\\.gr${langPath.replace('/', '\\/')}\\/vod\\/vod\\.\\d+-${detectedVodSlug}\\d+`;
const pattern = new RegExp(patternString);

console.log(`Generated pattern: ${pattern}\n`);

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
console.log(`\nFound ${results.length} episodes:\n`);

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
