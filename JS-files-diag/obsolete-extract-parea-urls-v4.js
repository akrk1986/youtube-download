// ERTFlix Parea URL Extractor v4 - Extract from Image URLs
//
// Designed for: https://www.ertflix.gr/#/details/ERT_PS054741_E0
//
// Instructions:
// 1. Open the page and wait for it to load
// 2. Press F12 > Console
// 3. Paste this script and press Enter
// 4. Episodes will be extracted and copied to clipboard

(function() {

console.clear();
console.log('='.repeat(80));
console.log('ERTFlix Parea URL Extractor v4 - Extract from Image URLs');
console.log('='.repeat(80));
console.log(`\nCurrent URL: ${window.location.href}\n`);

// =============================================================================
// Find all asset-card elements
// =============================================================================

const assetCards = document.querySelectorAll('.asset-card');
console.log(`Found ${assetCards.length} .asset-card elements\n`);

if (assetCards.length === 0) {
    console.log('❌ ERROR: No cards found!');
    return;
}

// =============================================================================
// Extract episode data from each card
// =============================================================================

console.log('Extracting episode data from cards...\n');

const results = [];
const seen = new Set();

assetCards.forEach((card, index) => {
    // Extract image URL (contains episode ID)
    const img = card.querySelector('img[src], img[data-src]');
    let episodeId = null;

    if (img) {
        const imgSrc = img.getAttribute('src') || img.getAttribute('data-src') || '';

        // Extract ERT ID from image URL
        // Pattern: https://imageservice.ertflix.opentv.com/images/v1/image/tvshow/ERT_PS027282/...
        const ertMatch = imgSrc.match(/\/tvshow\/(ERT_[A-Z0-9_]+)\//);
        if (ertMatch) {
            episodeId = ertMatch[1];
        }
    }

    // Extract guest name from aria-label
    const button = card.querySelector('button[aria-label]');
    let guestName = '';
    if (button) {
        const ariaLabel = button.getAttribute('aria-label');
        // aria-label format: "Καλεσμένος: Name" or "Καλεσμένη: Name"
        // Remove "Καλεσμένος: " or "Καλεσμένη: " prefix
        guestName = ariaLabel.replace(/^Καλεσμέν(ος|η):\s*/, '').trim();
    }

    // If we found an episode ID and haven't seen it before
    if (episodeId && !seen.has(episodeId)) {
        seen.add(episodeId);

        const episodeNumber = results.length + 1;
        const url = `https://www.ertflix.gr/#/details/${episodeId}`;
        const title = guestName || 'No title found';

        results.push({
            episodeNumber: episodeNumber,
            episodeId: episodeId,
            url: url,
            title: title
        });

        console.log(`  ✓ Episode ${episodeNumber}: ${episodeId} - ${title}`);
    } else if (!episodeId) {
        console.log(`  ⚠ Card ${index + 1}: No episode ID found in image URL`);
    }
});

// =============================================================================
// Display results and copy to clipboard
// =============================================================================

console.log('\n' + '='.repeat(80));

if (results.length === 0) {
    console.log('❌ ERROR: No episodes extracted!');
    console.log('='.repeat(80));
    return;
}

console.log(`✓ Successfully extracted ${results.length} episodes!\n`);

// Format output
const formattedOutput = [];
const displayOutput = [];

results.forEach((ep, index) => {
    // Format for plain text output
    const plainBlock = [
        `Episode ${ep.episodeNumber}`,
        ep.url,
        `Title: ${ep.title}`,
        'Artists: TBD',
        'Download status: pending, started at: TBD',
        '' // Blank line
    ].join('\n');

    formattedOutput.push(plainBlock);

    // Format for console display (more compact)
    displayOutput.push(`${(index + 1).toString().padStart(3, ' ')}. Episode ${ep.episodeNumber} (${ep.episodeId})`);
    displayOutput.push(`     ${ep.url}`);
    displayOutput.push(`     Title: ${ep.title}`);
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
    console.log('  Type this in console:  pareaUrlsV4');
    console.log('  Then right-click the output and select "Copy object"');
}

// Make data available as a variable
window.pareaUrlsV4 = urlList;
console.log('\n' + '='.repeat(80));
console.log('Data stored in: window.pareaUrlsV4');
console.log('Type "pareaUrlsV4" in console to see all data');
console.log('='.repeat(80));

})(); // End of function scope
