// ERTFlix Parea URL Extractor - Browser Console Script
//
// Designed for: https://www.ertflix.gr/#/details/ERT_PS054741_E0
//
// Instructions:
// 1. Open the Parea details page in your browser (Chrome works best)
//    URL: https://www.ertflix.gr/#/details/ERT_PS054741_E0
// 2. Wait 5-10 seconds for all episodes to load
// 3. Scroll down to ensure all episodes are visible
// 4. Press F12 to open Developer Tools
// 5. Click the Console tab
// 6. Clear the console
// 7. Copy and paste this entire file into the console
// 8. Press Enter
// 9. Episodes will be extracted and copied to clipboard
// 10. Paste into a text file
//
// This script extracts video URLs from episode play buttons on the details page.

// =============================================================================
// EXTRACTION CODE
// =============================================================================

// Wrap in function to avoid variable redeclaration errors
(function() {

const currentUrl = window.location.href;
console.clear();
console.log('='.repeat(80));
console.log('ERTFlix Parea URL Extractor');
console.log('='.repeat(80));
console.log(`\nCurrent page: ${currentUrl}`);

// Verify we're on a details page
if (!currentUrl.includes('#/details/ERT_PS054741_E0')) {
    console.log('\n⚠ WARNING: This script is designed for:');
    console.log('  https://www.ertflix.gr/#/details/ERT_PS054741_E0');
    console.log(`\nYou are on: ${currentUrl}`);
    console.log('\nThe script will attempt to extract episodes anyway...\n');
}

// =============================================================================
// STRATEGY 1: Look for video URLs in episode containers
// =============================================================================

console.log('Searching for episodes...\n');

const results = [];
const seen = new Set();

// Try multiple selectors to find episode containers
const selectors = [
    '[class*="episode"]',
    '[class*="Episode"]',
    '[class*="item"]',
    '[class*="card"]',
    'a[href*="/vod/"]',
    'a[href*="details"]',
    '[data-video-id]',
    '[data-episode]'
];

let episodeElements = [];

// Try each selector until we find episodes
for (const selector of selectors) {
    const elements = Array.from(document.querySelectorAll(selector));
    if (elements.length > 0) {
        console.log(`Found ${elements.length} elements with selector: ${selector}`);
        episodeElements = elements;
        break;
    }
}

if (episodeElements.length === 0) {
    console.log('⚠ No episode elements found with standard selectors.');
    console.log('Trying alternative approach...\n');

    // Fallback: Look for all links on the page
    episodeElements = Array.from(document.querySelectorAll('a'));
    console.log(`Found ${episodeElements.length} total links on page`);
}

// =============================================================================
// STRATEGY 2: Extract episode information from elements
// =============================================================================

episodeElements.forEach((element, index) => {
    // Try to find video URL from various sources
    let videoUrl = '';
    let episodeNumber = '';
    let episodeTitle = '';

    // Method 1: Check href attribute
    if (element.href) {
        const href = element.href;
        // Look for VOD URLs
        if (href.includes('/vod/') || href.includes('details/ERT')) {
            videoUrl = href;
        }
    }

    // Method 2: Check data attributes
    if (!videoUrl) {
        const dataId = element.getAttribute('data-video-id') ||
                      element.getAttribute('data-episode-id') ||
                      element.getAttribute('data-id');
        if (dataId) {
            // Try to construct URL from ID
            if (dataId.startsWith('ERT_')) {
                videoUrl = `https://www.ertflix.gr/#/details/${dataId}`;
            }
        }
    }

    // Method 3: Look for onclick handlers
    if (!videoUrl && element.onclick) {
        const onclickStr = element.onclick.toString();
        const urlMatch = onclickStr.match(/['"]([^'"]*(?:\/vod\/|details\/ERT)[^'"]*)['"]/);
        if (urlMatch) {
            videoUrl = urlMatch[1];
        }
    }

    // Extract episode information from the element or its children

    // Look for episode number in various places
    const numberSelectors = [
        '[class*="episode"]',
        '[class*="number"]',
        '[class*="index"]',
        '.episode-number',
        '.ep-num'
    ];

    for (const selector of numberSelectors) {
        const numElement = element.querySelector(selector);
        if (numElement && numElement.textContent.trim()) {
            episodeNumber = numElement.textContent.trim();
            break;
        }
    }

    // If no episode number found, try to extract from element's own text
    if (!episodeNumber) {
        const text = element.textContent || element.innerText || '';
        const epMatch = text.match(/(?:Επεισόδιο|Episode|Ep\.?)\s*(\d+)/i);
        if (epMatch) {
            episodeNumber = `Episode ${epMatch[1]}`;
        }
    }

    // Look for episode title
    const titleSelectors = [
        '[class*="title"]',
        '[class*="subtitle"]',
        '[class*="name"]',
        'h3',
        'h4',
        '.episode-title',
        '.ep-title'
    ];

    for (const selector of titleSelectors) {
        const titleElement = element.querySelector(selector);
        if (titleElement && titleElement.textContent.trim()) {
            episodeTitle = titleElement.textContent.trim();
            break;
        }
    }

    // If we found a video URL and haven't seen it before
    if (videoUrl && !seen.has(videoUrl)) {
        seen.add(videoUrl);

        // Generate fallback episode number if not found
        if (!episodeNumber) {
            episodeNumber = `Episode ${results.length + 1}`;
        }

        // Clean up title (remove episode number if it's repeated)
        if (episodeTitle && episodeNumber) {
            episodeTitle = episodeTitle.replace(new RegExp(episodeNumber, 'gi'), '').trim();
            episodeTitle = episodeTitle.replace(/^[-:]\s*/, '').trim();
        }

        if (!episodeTitle) {
            episodeTitle = 'No title found';
        }

        results.push({
            url: videoUrl,
            episodeNumber: episodeNumber,
            title: episodeTitle
        });
    }
});

// =============================================================================
// STRATEGY 3: If no URLs found, try to extract from page data
// =============================================================================

if (results.length === 0) {
    console.log('\n⚠ No episodes found using standard methods.');
    console.log('Attempting to extract from page data...\n');

    // Try to find data in window object or React components
    const dataKeys = ['__INITIAL_STATE__', '__data__', 'APP_STATE', 'pageData'];

    for (const key of dataKeys) {
        if (window[key]) {
            console.log(`Found data in window.${key}`);
            // Try to stringify and search for video IDs
            try {
                const dataStr = JSON.stringify(window[key]);
                const ertIds = dataStr.match(/ERT_PS054741_E\d+/g);
                if (ertIds) {
                    const uniqueIds = [...new Set(ertIds)];
                    uniqueIds.forEach((id, index) => {
                        results.push({
                            url: `https://www.ertflix.gr/#/details/${id}`,
                            episodeNumber: `Episode ${index + 1}`,
                            title: id
                        });
                    });
                    break;
                }
            } catch (e) {
                // Continue to next key
            }
        }
    }
}

// =============================================================================
// DISPLAY RESULTS
// =============================================================================

if (results.length === 0) {
    console.log('\n' + '='.repeat(80));
    console.log('❌ ERROR: No episodes found!');
    console.log('='.repeat(80));
    console.log('\nPossible solutions:');
    console.log('1. Make sure the page is fully loaded (wait 10 seconds)');
    console.log('2. Scroll down to ensure all episodes are visible');
    console.log('3. Try refreshing the page and running the script again');
    console.log('4. Check if the page structure has changed');
    console.log('\nDebug information:');
    console.log(`- Total links found: ${document.querySelectorAll('a').length}`);
    console.log(`- Links with "vod": ${document.querySelectorAll('a[href*="/vod/"]').length}`);
    console.log(`- Links with "details": ${document.querySelectorAll('a[href*="details"]').length}`);
    console.log(`- Elements with "episode" class: ${document.querySelectorAll('[class*="episode"]').length}`);
    return;
}

console.log(`\n✓ Found ${results.length} episodes:\n`);

// Format output
const formattedOutput = [];
const displayOutput = [];

results.forEach((item, index) => {
    // Format for plain text output
    const plainBlock = [
        item.episodeNumber,
        item.url,
        `Title: ${item.title}`,
        'Artists: TBD',
        'Download status: pending, started at: TBD',
        '' // Blank line
    ].join('\n');

    formattedOutput.push(plainBlock);

    // Format for console display (more compact)
    displayOutput.push(`${(index + 1).toString().padStart(3, ' ')}. ${item.episodeNumber}`);
    displayOutput.push(`     ${item.url}`);
    displayOutput.push(`     Title: ${item.title}`);
});

// Display first 3 episodes in console
console.log(displayOutput.slice(0, 9).join('\n')); // 3 episodes × 3 lines = 9 lines

if (results.length > 3) {
    console.log(`\n     ... and ${results.length - 3} more episodes\n`);
}

// Copy to clipboard
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
    console.log('  Type this in console:  pareaUrls');
    console.log('  Then right-click the output and select "Copy object"');
}

// Make data available as a variable
window.pareaUrls = urlList;
console.log('\n' + '='.repeat(80));
console.log('Data stored in: window.pareaUrls');
console.log('Type "pareaUrls" in console to see all data');
console.log('='.repeat(80));

})(); // End of function scope
