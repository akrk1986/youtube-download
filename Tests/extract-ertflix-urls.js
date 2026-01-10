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
// 7. Episodes will be automatically extracted and copied to clipboard
// 8. Paste into a text file
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

// Try to find ALL unique VOD slugs from links on the page
// This handles cases where a page uses multiple slug variations
const allVodLinks = document.querySelectorAll('a[href*="/vod/vod."]');
const detectedVodSlugs = new Set();

if (allVodLinks.length > 0) {
    allVodLinks.forEach(link => {
        // Extract slug from VOD URL: /vod/vod.NUMBER-SLUG-NUMBER
        const vodSlugMatch = link.href.match(/\/vod\/vod\.\d+-([\w-]+)-\d+/);
        if (vodSlugMatch) {
            detectedVodSlugs.add(vodSlugMatch[1] + '-');
        }
    });
}

// If no slugs detected, fall back to base slug
if (detectedVodSlugs.size === 0) {
    detectedVodSlugs.add(baseSlug);
}

// Build patterns for ALL detected slugs
const patterns = Array.from(detectedVodSlugs).map(slug => {
    const patternString = `https:\\/\\/www\\.ertflix\\.gr${langPath.replace('/', '\\/')}\\/vod\\/vod\\.\\d+-${slug}\\d+`;
    return new RegExp(patternString);
});

console.log(`Detected ${detectedVodSlugs.size} unique slug(s):`);
detectedVodSlugs.forEach(slug => {
    if (slug !== baseSlug) {
        console.log(`  - "${slug}" (differs from series slug "${baseSlug}")`);
    } else {
        console.log(`  - "${slug}"`);
    }
});
console.log(`\nGenerated ${patterns.length} pattern(s):`);
patterns.forEach((pattern, index) => {
    console.log(`  ${index + 1}. ${pattern}`);
});
console.log('');

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
    // Check if href matches ANY of the patterns
    const matchesAnyPattern = patterns.some(pattern => pattern.test(href));
    if (matchesAnyPattern) {
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

// Format output with multiple lines per episode
const formattedOutput = [];
const displayOutput = [];

results.forEach((item, index) => {
    // Parse episode number and title from text
    // Text format: "Επεισόδιο 1 - Title" or "Episode 1 - Title"
    const parts = item.text.split(' - ');
    const episodeNumberPart = parts[0] || `Episode ${index + 1}`;
    const titlePart = parts.slice(1).join(' - ') || 'No title';

    // Format for plain text output
    const plainBlock = [
        episodeNumberPart,
        item.url,
        `Title: ${titlePart}`,
        'Artists: TBD',
        'Download status: pending, started at: TBD',
        '' // Blank line
    ].join('\n');

    formattedOutput.push(plainBlock);

    // Format for console display (more compact)
    displayOutput.push(`${(index + 1).toString().padStart(3, ' ')}. ${episodeNumberPart}`);
    displayOutput.push(`     ${item.url}`);
    displayOutput.push(`     Title: ${titlePart}`);
});

// Display in console (first 3 episodes)
console.log(displayOutput.slice(0, 9).join('\n')); // 3 episodes × 3 lines = 9 lines

if (results.length > 3) {
    console.log(`\n     ... and ${results.length - 3} more episodes\n`);
}

// Copy plain text to clipboard
const urlList = formattedOutput.join('\n');

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
    console.log(`✓ SUCCESS: ${results.length} episodes copied to clipboard!`);
    console.log('='.repeat(80));
    console.log('\nFormat per episode:');
    console.log('  Line 1: Episode number');
    console.log('  Line 2: URL');
    console.log('  Line 3: Title: <title>');
    console.log('  Line 4: Artists: TBD');
    console.log('  Line 5: Download status: pending, started at: TBD');
    console.log('  Line 6: Blank line');
    console.log('\nYou can now paste into a text file.');
} else {
    console.log('⚠ Automatic clipboard copy not available.');
    console.log('='.repeat(80));
    console.log('\nMANUAL COPY METHOD:');
    console.log('  Type this in console:  ertflixUrls');
    console.log('  Then right-click the output and select "Copy object"');
}

// Make the data available as a variable for manual access
window.ertflixUrls = urlList;
console.log('\n' + '='.repeat(80));
console.log('Data stored in: window.ertflixUrls');
console.log('Type "ertflixUrls" in console to see all data');
console.log('='.repeat(80));

})(); // End of function scope
