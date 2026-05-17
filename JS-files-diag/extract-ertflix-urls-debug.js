// ERTFlix URL Extractor - DEBUG VERSION
// This version shows more information to help troubleshoot issues

(function() {

console.log('='.repeat(80));
console.log('ERTFlix URL Extractor - DEBUG MODE');
console.log('='.repeat(80));

// Configuration
const pattern = /https:\/\/www\.ertflix\.gr\/vod\/vod\.\d+-parea-\d+/;

console.log('\n1. Pattern:', pattern);

// Find all links
const allLinks = document.querySelectorAll('a[href*="/vod/vod."]');
console.log(`\n2. Found ${allLinks.length} total links with "/vod/vod." in href`);

if (allLinks.length === 0) {
    console.log('\n❌ ERROR: No VOD links found on page!');
    console.log('Possible reasons:');
    console.log('  - Page is not fully loaded (wait a few seconds and try again)');
    console.log('  - You are on the wrong page');
    console.log('  - The page structure has changed');
    console.log('\nCurrent page URL:', window.location.href);
    return;
}

// Show first few links
console.log('\nFirst 3 link hrefs:');
Array.from(allLinks).slice(0, 3).forEach((link, i) => {
    console.log(`  ${i + 1}. ${link.href}`);
});

// Filter by pattern
const links = Array.from(allLinks).filter(link => pattern.test(link.href));
console.log(`\n3. Links matching pattern: ${links.length}`);

if (links.length === 0) {
    console.log('\n❌ ERROR: Pattern did not match any links!');
    console.log('\nPattern:', pattern);
    console.log('\nExample href:', allLinks[0]?.href);
    console.log('\nDoes it match? Try adjusting the pattern.');
    return;
}

// Group by href
const linksByHref = {};
links.forEach(link => {
    const href = link.href;
    if (!linksByHref[href]) {
        linksByHref[href] = [];
    }
    linksByHref[href].push(link);
});

const uniqueUrls = Object.keys(linksByHref);
console.log(`\n4. Unique episode URLs: ${uniqueUrls.length}`);

// Process each episode
const results = [];
const seen = new Set();

Object.keys(linksByHref).forEach(href => {
    if (seen.has(href)) return;
    seen.add(href);

    const episodeLinks = linksByHref[href];
    let episodeNumber = '';
    let episodeTitle = '';

    // Debug: Show structure of first episode
    if (results.length === 0) {
        console.log(`\n5. DEBUG: First episode has ${episodeLinks.length} links with same href`);
        episodeLinks.forEach((link, i) => {
            const numberSpan = link.querySelector('[class*="episodeNumber"]');
            const titleSpan = link.querySelector('[class*="episodeSubtitle"]');
            console.log(`  Link ${i + 1}:`);
            console.log(`    - Has episodeNumber span: ${!!numberSpan}`);
            console.log(`    - Has episodeSubtitle span: ${!!titleSpan}`);
            if (numberSpan) console.log(`    - Episode number: "${numberSpan.textContent.trim()}"`);
            if (titleSpan) console.log(`    - Episode title: "${titleSpan.textContent.trim()}"`);
        });
    }

    // Find episode info
    for (const link of episodeLinks) {
        const numberSpan = link.querySelector('[class*="episodeNumber"]');
        const titleSpan = link.querySelector('[class*="episodeSubtitle"]');

        if (numberSpan) {
            episodeNumber = numberSpan.textContent.trim();
        }
        if (titleSpan) {
            episodeTitle = titleSpan.textContent.trim();
        }

        if (episodeNumber && episodeTitle) {
            break;
        }
    }

    const text = episodeNumber && episodeTitle
        ? `${episodeNumber} - ${episodeTitle}`
        : episodeNumber || episodeTitle || 'No title found';

    results.push({ url: href, text: text });
});

// Display results
console.log('\n' + '='.repeat(80));
console.log(`SUCCESS: Found ${results.length} episodes\n`);

results.slice(0, 5).forEach((item, i) => {
    console.log(`${(i + 1).toString().padStart(3, ' ')}. ${item.url}`);
    console.log(`     Text: ${item.text}`);
});

if (results.length > 5) {
    console.log(`\n... and ${results.length - 5} more episodes`);
}

// Try to copy to clipboard
const urlList = results.map(item => `${item.url}\t${item.text}`).join('\n');
window.ertflixUrls = urlList;

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
    console.log(`✓ ${results.length} URLs copied to clipboard!`);
} else {
    console.log('Clipboard copy not available (Firefox)');
    console.log('Type "ertflixUrls" in console to see all data');
}
console.log('='.repeat(80));

})();
