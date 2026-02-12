// ERTFlix Parea URL Extractor v3 - Deep Dive into Angular Component Data
//
// Designed for: https://www.ertflix.gr/#/details/ERT_PS054741_E0
//
// Instructions:
// 1. Open the page and wait for it to load
// 2. Press F12 > Console
// 3. Paste this script and press Enter

(function() {

console.clear();
console.log('='.repeat(80));
console.log('ERTFlix Parea URL Extractor v3 - Deep Angular Analysis');
console.log('='.repeat(80));

const assetCards = document.querySelectorAll('.asset-card');
console.log(`\nFound ${assetCards.length} .asset-card elements\n`);

if (assetCards.length === 0) {
    console.log('❌ ERROR: No cards found!');
    return;
}

// =============================================================================
// STEP 1: Show FULL HTML of first 3 cards
// =============================================================================

console.log('STEP 1: Examining first 3 cards in detail...\n');
console.log('='.repeat(80));

for (let i = 0; i < Math.min(3, assetCards.length); i++) {
    const card = assetCards[i];
    console.log(`\nCARD ${i + 1} FULL HTML:`);
    console.log('-'.repeat(80));
    console.log(card.outerHTML);
    console.log('-'.repeat(80));
}

// =============================================================================
// STEP 2: Try to access Angular component data
// =============================================================================

console.log('\n\nSTEP 2: Attempting to access Angular component data...\n');
console.log('='.repeat(80));

const firstCard = assetCards[0];

// Try to get Angular debug data
try {
    // Angular stores component data in __ngContext__ or similar properties
    const angularProps = Object.keys(firstCard).filter(key => key.includes('ng') || key.includes('__'));

    if (angularProps.length > 0) {
        console.log('Found Angular properties on first card:');
        angularProps.forEach(prop => {
            console.log(`  - ${prop}`);
            try {
                const value = firstCard[prop];
                if (value && typeof value === 'object') {
                    console.log(`    Type: object (${Object.keys(value).length} keys)`);
                    // Try to find episode data
                    const stringified = JSON.stringify(value, null, 2);
                    if (stringified.includes('ERT_') || stringified.includes('episode')) {
                        console.log('    ✓ Contains episode data!');
                        console.log(stringified.substring(0, 500));
                    }
                } else {
                    console.log(`    Value: ${value}`);
                }
            } catch (e) {
                console.log(`    (cannot access)`);
            }
        });
    } else {
        console.log('No Angular properties found on card element');
    }
} catch (e) {
    console.log('Cannot access Angular data:', e.message);
}

// =============================================================================
// STEP 3: Look for episode data in aria-labels and other text
// =============================================================================

console.log('\n\nSTEP 3: Extracting text data from all cards...\n');
console.log('='.repeat(80));

const episodeData = [];

assetCards.forEach((card, index) => {
    const data = {
        index: index + 1,
        ariaLabel: null,
        buttonText: null,
        allText: null,
        imageAlt: null,
        imageSrc: null
    };

    // Find button with aria-label
    const button = card.querySelector('button[aria-label]');
    if (button) {
        data.ariaLabel = button.getAttribute('aria-label');
    }

    // Get all button text
    const allButtons = card.querySelectorAll('button');
    if (allButtons.length > 0) {
        data.buttonText = Array.from(allButtons).map(b => b.textContent.trim()).join(' | ');
    }

    // Get all text content
    data.allText = card.textContent.trim();

    // Find images
    const img = card.querySelector('img');
    if (img) {
        data.imageAlt = img.getAttribute('alt');
        data.imageSrc = img.getAttribute('src') || img.getAttribute('data-src');
    }

    episodeData.push(data);
});

// Display first 5 episodes
console.log('Episode data extracted from first 5 cards:\n');
episodeData.slice(0, 5).forEach(ep => {
    console.log(`Episode ${ep.index}:`);
    console.log(`  aria-label: ${ep.ariaLabel || '(none)'}`);
    console.log(`  buttonText: ${ep.buttonText || '(none)'}`);
    console.log(`  imageAlt: ${ep.imageAlt || '(none)'}`);
    console.log(`  imageSrc: ${ep.imageSrc ? ep.imageSrc.substring(0, 80) + '...' : '(none)'}`);
    console.log(`  allText: ${ep.allText.substring(0, 100)}...`);
    console.log('');
});

// =============================================================================
// STEP 4: Look for patterns in image URLs
// =============================================================================

console.log('\nSTEP 4: Analyzing image URLs for episode IDs...\n');
console.log('='.repeat(80));

const imageUrls = episodeData
    .filter(ep => ep.imageSrc)
    .map(ep => ep.imageSrc);

if (imageUrls.length > 0) {
    console.log(`Found ${imageUrls.length} image URLs\n`);
    console.log('First 3 image URLs:');
    imageUrls.slice(0, 3).forEach((url, i) => {
        console.log(`  ${i + 1}. ${url}`);

        // Try to extract episode ID from image URL
        const ertMatch = url.match(/ERT_[A-Z0-9_]+/);
        if (ertMatch) {
            console.log(`     ✓ Found ERT ID: ${ertMatch[0]}`);
        }
    });
}

// =============================================================================
// STEP 5: Try to construct episode URLs from pattern
// =============================================================================

console.log('\n\nSTEP 5: Attempting to construct episode URLs...\n');
console.log('='.repeat(80));

// The current page URL is: https://www.ertflix.gr/#/details/ERT_PS054741_E0
// Episodes are likely: ERT_PS054741_E1, ERT_PS054741_E2, etc.

const currentUrl = window.location.href;
const baseIdMatch = currentUrl.match(/ERT_PS054741_E(\d+)/);

if (baseIdMatch) {
    console.log('Current page episode number:', baseIdMatch[1]);
    console.log('\nAttempting to construct episode URLs based on pattern...\n');

    // Check if we can find episode numbers in the cards
    const episodesWithNumbers = [];

    episodeData.forEach(ep => {
        // Try to extract episode number from aria-label or text
        const allText = (ep.ariaLabel || '') + ' ' + (ep.allText || '');

        // Look for Greek "Επεισόδιο X" or English "Episode X"
        const epMatch = allText.match(/(?:Επεισόδιο|Episode)\s*(\d+)/i);

        if (epMatch) {
            episodesWithNumbers.push({
                cardIndex: ep.index,
                episodeNumber: parseInt(epMatch[1]),
                episodeId: `ERT_PS054741_E${epMatch[1]}`,
                url: `https://www.ertflix.gr/#/details/ERT_PS054741_E${epMatch[1]}`,
                title: ep.ariaLabel || ep.allText.substring(0, 100)
            });
        } else if (ep.imageSrc) {
            // Try to extract from image URL
            const ertMatch = ep.imageSrc.match(/ERT_PS054741_E(\d+)/);
            if (ertMatch) {
                episodesWithNumbers.push({
                    cardIndex: ep.index,
                    episodeNumber: parseInt(ertMatch[1]),
                    episodeId: `ERT_PS054741_E${ertMatch[1]}`,
                    url: `https://www.ertflix.gr/#/details/ERT_PS054741_E${ertMatch[1]}`,
                    title: ep.ariaLabel || ep.allText.substring(0, 100)
                });
            }
        }
    });

    if (episodesWithNumbers.length > 0) {
        console.log(`✓ Successfully identified ${episodesWithNumbers.length} episodes!\n`);

        // Format output
        const formattedOutput = [];
        const displayOutput = [];

        episodesWithNumbers.forEach((ep, index) => {
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
            displayOutput.push(`${(index + 1).toString().padStart(3, ' ')}. Episode ${ep.episodeNumber}`);
            displayOutput.push(`     ${ep.url}`);
            displayOutput.push(`     Title: ${ep.title.substring(0, 80)}`);
        });

        // Display first 3 episodes in console
        console.log(displayOutput.slice(0, 9).join('\n')); // 3 episodes × 3 lines = 9 lines

        if (episodesWithNumbers.length > 3) {
            console.log(`\n     ... and ${episodesWithNumbers.length - 3} more episodes\n`);
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
            console.log(`✓ SUCCESS: ${episodesWithNumbers.length} episodes copied to clipboard!`);
            console.log('='.repeat(80));
            console.log('\nYou can now paste into a text file.');
        } else {
            console.log('⚠ Automatic clipboard copy not available.');
            console.log('='.repeat(80));
            console.log('\nMANUAL COPY METHOD:');
            console.log('  Type this in console:  pareaUrlsV3');
            console.log('  Then right-click the output and select "Copy object"');
        }

        // Make data available as a variable
        window.pareaUrlsV3 = urlList;
        console.log('\n' + '='.repeat(80));
        console.log('Data stored in: window.pareaUrlsV3');
        console.log('Type "pareaUrlsV3" in console to see all data');
        console.log('='.repeat(80));

    } else {
        console.log('⚠ Could not extract episode numbers from cards.');
        console.log('\nPlease manually inspect the cards and share:');
        console.log('1. What text or numbers identify each episode?');
        console.log('2. Are episode numbers visible anywhere on the page?');
    }

} else {
    console.log('⚠ Could not determine episode ID pattern from current URL.');
}

})(); // End of function scope
