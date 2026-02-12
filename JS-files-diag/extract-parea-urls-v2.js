// ERTFlix Parea URL Extractor v2 - Targets Angular App with .asset-card elements
//
// Designed for: https://www.ertflix.gr/#/details/ERT_PS054741_E0
//
// Instructions:
// 1. Open the Parea details page in your browser
// 2. Wait 10+ seconds for all episodes to load
// 3. Scroll down to ensure all episodes are visible
// 4. Press F12 to open Developer Tools > Console tab
// 5. Paste this entire script and press Enter
// 6. Episodes will be extracted and copied to clipboard
//
// This version targets Angular's .asset-card elements

(function() {

console.clear();
console.log('='.repeat(80));
console.log('ERTFlix Parea URL Extractor v2 (Angular + Asset Cards)');
console.log('='.repeat(80));
console.log(`\nCurrent URL: ${window.location.href}\n`);

// =============================================================================
// STEP 1: Find all asset-card elements
// =============================================================================

console.log('STEP 1: Looking for episode cards...');

const assetCards = document.querySelectorAll('.asset-card');
console.log(`Found ${assetCards.length} .asset-card elements\n`);

if (assetCards.length === 0) {
    console.log('❌ ERROR: No .asset-card elements found!');
    console.log('Make sure the page is fully loaded and episodes are visible.');
    return;
}

// =============================================================================
// STEP 2: Extract data from each card
// =============================================================================

console.log('STEP 2: Extracting episode data...\n');

const results = [];
const seen = new Set();

assetCards.forEach((card, index) => {
    console.log(`Processing card ${index + 1}/${assetCards.length}...`);

    // Try multiple methods to extract the episode URL and info
    let videoUrl = '';
    let episodeNumber = '';
    let episodeTitle = '';

    // METHOD 1: Look for links inside the card
    const links = card.querySelectorAll('a[href]');
    for (const link of links) {
        const href = link.href;
        // Look for ERTFlix URLs with video IDs
        if (href.includes('ertflix.gr') && (href.includes('/details/') || href.includes('/vod/'))) {
            videoUrl = href;
            break;
        }
    }

    // METHOD 2: Check card's own attributes and onclick handlers
    if (!videoUrl) {
        // Check data attributes
        const dataAttrs = ['data-url', 'data-href', 'data-link', 'data-video-id', 'data-id'];
        for (const attr of dataAttrs) {
            const value = card.getAttribute(attr);
            if (value && (value.includes('ERT_') || value.includes('/'))) {
                if (value.startsWith('http')) {
                    videoUrl = value;
                } else if (value.startsWith('ERT_')) {
                    videoUrl = `https://www.ertflix.gr/#/details/${value}`;
                } else if (value.startsWith('/')) {
                    videoUrl = `https://www.ertflix.gr${value}`;
                }
                break;
            }
        }
    }

    // METHOD 3: Check onclick or ng-click handlers
    if (!videoUrl) {
        const ngClick = card.getAttribute('ng-click') || card.getAttribute('[click]') || '';
        const onclick = card.getAttribute('onclick') || '';
        const combined = ngClick + ' ' + onclick;

        // Look for ERT IDs or URLs in the handlers
        const ertIdMatch = combined.match(/ERT_[A-Z0-9_]+/);
        if (ertIdMatch) {
            videoUrl = `https://www.ertflix.gr/#/details/${ertIdMatch[0]}`;
        }
    }

    // METHOD 4: Look in all text content for ERT IDs as fallback
    if (!videoUrl) {
        const cardHtml = card.innerHTML;
        const ertIdMatch = cardHtml.match(/ERT_PS054741_E\d+/);
        if (ertIdMatch) {
            videoUrl = `https://www.ertflix.gr/#/details/${ertIdMatch[0]}`;
        }
    }

    // Extract episode information
    // Look for episode number in various text elements
    const textElements = card.querySelectorAll('*');
    for (const el of textElements) {
        const text = el.textContent || '';

        // Look for "Επεισόδιο X" or "Episode X" patterns
        if (!episodeNumber) {
            const epMatch = text.match(/(?:Επεισόδιο|Episode|Ep\.?)\s*(\d+)/i);
            if (epMatch && text.trim().length < 50) { // Avoid matching in long descriptions
                episodeNumber = text.trim();
            }
        }

        // Look for titles (usually in heading tags or specific classes)
        if (!episodeTitle && (el.tagName === 'H3' || el.tagName === 'H4' || el.tagName === 'H5')) {
            const title = el.textContent.trim();
            if (title && title.length > 3 && title.length < 200) {
                episodeTitle = title;
            }
        }

        // Also check for title classes
        if (!episodeTitle) {
            const classes = el.className || '';
            if (classes.includes('title') || classes.includes('name')) {
                const title = el.textContent.trim();
                if (title && title.length > 3 && title.length < 200) {
                    episodeTitle = title;
                }
            }
        }
    }

    // Generate fallback values if needed
    if (!episodeNumber) {
        episodeNumber = `Episode ${index + 1}`;
    }

    if (!episodeTitle) {
        episodeTitle = 'No title found';
    }

    // Clean up episode title (remove episode number if it's duplicated)
    if (episodeTitle.includes(episodeNumber)) {
        episodeTitle = episodeTitle.replace(episodeNumber, '').trim();
        episodeTitle = episodeTitle.replace(/^[-:]\s*/, '').trim();
    }

    if (!episodeTitle || episodeTitle === episodeNumber) {
        episodeTitle = 'No title found';
    }

    // Add to results if we found a URL and haven't seen it before
    if (videoUrl && !seen.has(videoUrl)) {
        seen.add(videoUrl);
        results.push({
            url: videoUrl,
            episodeNumber: episodeNumber,
            title: episodeTitle
        });
        console.log(`  ✓ Found: ${episodeNumber} - ${videoUrl.substring(0, 60)}...`);
    } else if (!videoUrl) {
        console.log(`  ⚠ Card ${index + 1}: No URL found`);
        // Debug: Show card's innerHTML (first 200 chars)
        console.log(`    Card HTML preview: ${card.innerHTML.substring(0, 200).replace(/\s+/g, ' ')}...`);
    }
});

// =============================================================================
// STEP 3: Display results
// =============================================================================

console.log('\n' + '='.repeat(80));

if (results.length === 0) {
    console.log('❌ ERROR: No episodes extracted!');
    console.log('='.repeat(80));
    console.log('\nDebug: Let\'s examine the first .asset-card element:');

    const firstCard = assetCards[0];
    if (firstCard) {
        console.log('\nFirst card HTML:');
        console.log(firstCard.outerHTML.substring(0, 500));
        console.log('\n...(truncated)');

        console.log('\nFirst card links:');
        const links = firstCard.querySelectorAll('a');
        links.forEach((link, i) => {
            console.log(`  ${i + 1}. href="${link.href}"`);
            console.log(`     text="${link.textContent.trim().substring(0, 50)}"`);
        });

        console.log('\nFirst card attributes:');
        Array.from(firstCard.attributes).forEach(attr => {
            console.log(`  ${attr.name}="${attr.value}"`);
        });
    }

    console.log('\n' + '='.repeat(80));
    console.log('Please share this debug output so we can fix the extractor.');
    console.log('='.repeat(80));
    return;
}

console.log(`✓ Successfully extracted ${results.length} episodes!\n`);

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
    console.log('  Type this in console:  pareaUrlsV2');
    console.log('  Then right-click the output and select "Copy object"');
}

// Make data available as a variable
window.pareaUrlsV2 = urlList;
console.log('\n' + '='.repeat(80));
console.log('Data stored in: window.pareaUrlsV2');
console.log('Type "pareaUrlsV2" in console to see all data');
console.log('='.repeat(80));

})(); // End of function scope
