// ERTFlix Parea Diagnostic Script - Discover Episode Data Sources
//
// Instructions:
// 1. Open https://www.ertflix.gr/#/details/ERT_PS054741_E0 in Chrome
// 2. Wait for the page to fully load (10+ seconds)
// 3. Open Developer Tools (F12) > Console tab
// 4. Paste this entire script and press Enter
// 5. Review the diagnostic output
//
// This script will help us understand:
// - What JavaScript framework is being used
// - Where episode data is stored
// - What API endpoints are being called
// - How to extract episode information

(function() {
    console.clear();
    console.log('='.repeat(80));
    console.log('ERTFlix Parea Diagnostic Script');
    console.log('='.repeat(80));
    console.log(`\nCurrent URL: ${window.location.href}\n`);

    // =============================================================================
    // SECTION 1: Detect JavaScript Framework
    // =============================================================================

    console.log('SECTION 1: JavaScript Framework Detection');
    console.log('-'.repeat(80));

    const frameworks = {
        React: () => {
            return !!document.querySelector('[data-reactroot], [data-reactid]') ||
                   typeof window.React !== 'undefined' ||
                   Object.keys(window).some(key => key.startsWith('__REACT'));
        },
        Vue: () => {
            return typeof window.Vue !== 'undefined' ||
                   !!document.querySelector('[data-v-]') ||
                   Object.keys(window).some(key => key.includes('__VUE'));
        },
        Angular: () => {
            return typeof window.angular !== 'undefined' ||
                   !!document.querySelector('[ng-app], [ng-controller]') ||
                   typeof window.getAllAngularRootElements === 'function';
        },
        jQuery: () => typeof window.jQuery !== 'undefined' || typeof window.$ !== 'undefined'
    };

    Object.entries(frameworks).forEach(([name, detector]) => {
        const detected = detector();
        console.log(`  ${detected ? '✓' : '✗'} ${name}: ${detected ? 'DETECTED' : 'Not found'}`);
    });

    // =============================================================================
    // SECTION 2: Search for Episode Data in Window Object
    // =============================================================================

    console.log('\nSECTION 2: Window Object Data Search');
    console.log('-'.repeat(80));

    const windowKeys = Object.keys(window);
    const dataKeys = windowKeys.filter(key =>
        key.includes('data') ||
        key.includes('state') ||
        key.includes('DATA') ||
        key.includes('STATE') ||
        key.includes('store') ||
        key.includes('STORE') ||
        key.includes('__')
    );

    console.log(`Found ${dataKeys.length} potential data keys in window object:`);
    dataKeys.slice(0, 20).forEach(key => {
        console.log(`  - window.${key}`);
    });

    if (dataKeys.length > 20) {
        console.log(`  ... and ${dataKeys.length - 20} more\n`);
    }

    // Try to find episode data in these keys
    console.log('\nSearching for ERT video IDs in window data:');
    let foundEpisodeData = false;

    for (const key of dataKeys) {
        try {
            const data = window[key];
            if (data && typeof data === 'object') {
                const jsonStr = JSON.stringify(data);

                // Look for ERT video IDs (pattern: ERT_PS054741_E followed by digits)
                const ertIds = jsonStr.match(/ERT_PS054741_E\d+/g);

                if (ertIds && ertIds.length > 0) {
                    const uniqueIds = [...new Set(ertIds)];
                    console.log(`\n  ✓ Found ${uniqueIds.length} episode IDs in window.${key}:`);
                    uniqueIds.slice(0, 5).forEach(id => {
                        console.log(`    - ${id}`);
                    });
                    if (uniqueIds.length > 5) {
                        console.log(`    ... and ${uniqueIds.length - 5} more`);
                    }
                    foundEpisodeData = true;

                    // Save for later use
                    window.__DIAGNOSTIC_EPISODE_DATA = {
                        source: key,
                        episodeIds: uniqueIds,
                        fullData: data
                    };
                }
            }
        } catch (e) {
            // Skip circular references or non-serializable objects
        }
    }

    if (!foundEpisodeData) {
        console.log('  ✗ No episode IDs found in window object');
    }

    // =============================================================================
    // SECTION 3: Examine DOM Structure
    // =============================================================================

    console.log('\n\nSECTION 3: DOM Structure Analysis');
    console.log('-'.repeat(80));

    // Look for common patterns
    const patterns = [
        { selector: '[class*="episode"]', label: 'Episode elements' },
        { selector: '[class*="Episode"]', label: 'Episode elements (capitalized)' },
        { selector: '[data-episode]', label: 'data-episode attributes' },
        { selector: '[data-video]', label: 'data-video attributes' },
        { selector: '[data-id]', label: 'data-id attributes' },
        { selector: 'a[href*="ERT"]', label: 'Links with ERT in href' },
        { selector: 'button[class*="play"]', label: 'Play buttons' },
        { selector: 'button[class*="Play"]', label: 'Play buttons (capitalized)' },
        { selector: '[class*="card"]', label: 'Card elements' },
        { selector: '[class*="Card"]', label: 'Card elements (capitalized)' },
        { selector: 'video', label: 'Video elements' },
        { selector: '[class*="player"]', label: 'Player elements' }
    ];

    patterns.forEach(({ selector, label }) => {
        const elements = document.querySelectorAll(selector);
        const count = elements.length;
        console.log(`  ${count > 0 ? '✓' : '✗'} ${label}: ${count} found`);

        if (count > 0 && count <= 5) {
            // Show first element's relevant attributes
            const first = elements[0];
            const attrs = Array.from(first.attributes).map(a => `${a.name}="${a.value}"`);
            console.log(`    First element: <${first.tagName.toLowerCase()} ${attrs.slice(0, 3).join(' ')}>`);
        }
    });

    // =============================================================================
    // SECTION 4: Extract All Class Names
    // =============================================================================

    console.log('\n\nSECTION 4: Unique CSS Class Names');
    console.log('-'.repeat(80));

    const allElements = document.querySelectorAll('*');
    const allClasses = new Set();

    allElements.forEach(el => {
        if (el.className && typeof el.className === 'string') {
            el.className.split(/\s+/).forEach(cls => {
                if (cls) allClasses.add(cls);
            });
        }
    });

    const sortedClasses = Array.from(allClasses).sort();
    const relevantClasses = sortedClasses.filter(cls =>
        cls.toLowerCase().includes('episode') ||
        cls.toLowerCase().includes('video') ||
        cls.toLowerCase().includes('card') ||
        cls.toLowerCase().includes('item') ||
        cls.toLowerCase().includes('play')
    );

    console.log(`Total unique classes: ${sortedClasses.length}`);
    console.log(`Relevant classes (episode/video/card/item/play): ${relevantClasses.length}`);

    if (relevantClasses.length > 0) {
        console.log('\nRelevant classes:');
        relevantClasses.slice(0, 20).forEach(cls => {
            console.log(`  - .${cls}`);
        });
        if (relevantClasses.length > 20) {
            console.log(`  ... and ${relevantClasses.length - 20} more`);
        }
    }

    // =============================================================================
    // SECTION 5: Try to Find Main App Container
    // =============================================================================

    console.log('\n\nSECTION 5: Main App Container Search');
    console.log('-'.repeat(80));

    const containerSelectors = [
        '#app',
        '#root',
        '[id*="app"]',
        '[id*="App"]',
        '[id*="root"]',
        '[class*="app"]',
        '[class*="App"]',
        'main',
        '[role="main"]'
    ];

    containerSelectors.forEach(selector => {
        const container = document.querySelector(selector);
        if (container) {
            console.log(`  ✓ Found container: ${selector}`);
            console.log(`    - Tag: <${container.tagName.toLowerCase()}>`);
            console.log(`    - ID: ${container.id || '(none)'}`);
            console.log(`    - Classes: ${container.className || '(none)'}`);
            console.log(`    - Child count: ${container.children.length}`);
        }
    });

    // =============================================================================
    // SECTION 6: Network Request Monitoring (if possible)
    // =============================================================================

    console.log('\n\nSECTION 6: Network Request Information');
    console.log('-'.repeat(80));
    console.log('To see API requests:');
    console.log('  1. Go to Developer Tools > Network tab');
    console.log('  2. Look for XHR/Fetch requests');
    console.log('  3. Common patterns to look for:');
    console.log('     - /api/... endpoints');
    console.log('     - Requests with "ERT_PS054741" in the URL or response');
    console.log('     - JSON responses containing episode data');

    // =============================================================================
    // SECTION 7: Interactive Element Search
    // =============================================================================

    console.log('\n\nSECTION 7: Interactive Elements');
    console.log('-'.repeat(80));

    const buttons = document.querySelectorAll('button');
    const links = document.querySelectorAll('a');

    console.log(`Total buttons: ${buttons.length}`);
    console.log(`Total links: ${links.length}`);

    // Find buttons with episode-related text or classes
    const episodeButtons = Array.from(buttons).filter(btn => {
        const text = btn.textContent.toLowerCase();
        const classes = btn.className.toLowerCase();
        return text.includes('play') ||
               text.includes('watch') ||
               text.includes('episode') ||
               classes.includes('play') ||
               classes.includes('episode');
    });

    if (episodeButtons.length > 0) {
        console.log(`\nFound ${episodeButtons.length} episode-related buttons:`);
        episodeButtons.slice(0, 5).forEach((btn, i) => {
            console.log(`  ${i + 1}. Text: "${btn.textContent.trim().substring(0, 50)}"`);
            console.log(`     Classes: ${btn.className}`);
            console.log(`     onclick: ${btn.onclick ? 'YES' : 'NO'}`);
        });
    }

    // =============================================================================
    // SECTION 8: Final Recommendations
    // =============================================================================

    console.log('\n\n' + '='.repeat(80));
    console.log('DIAGNOSTIC SUMMARY & NEXT STEPS');
    console.log('='.repeat(80));

    if (foundEpisodeData) {
        console.log('\n✓ SUCCESS: Found episode data in window object!');
        console.log('  Access it with: window.__DIAGNOSTIC_EPISODE_DATA');
        console.log('\nYou can extract episodes with:');
        console.log('  window.__DIAGNOSTIC_EPISODE_DATA.episodeIds.forEach(id => {');
        console.log('    console.log(`https://www.ertflix.gr/#/details/${id}`);');
        console.log('  });');
    } else {
        console.log('\n⚠ No episode data found in window object.');
        console.log('\nRECOMMENDED NEXT STEPS:');
        console.log('  1. Check Network tab (F12 > Network) for API requests');
        console.log('  2. Look for XHR/Fetch requests after page loads');
        console.log('  3. Examine response data in those requests');
        console.log('  4. Share any API endpoint URLs you find');
        console.log('\nAlternative: Inspect episode elements in the page:');
        console.log('  1. Right-click an episode card/button');
        console.log('  2. Select "Inspect Element"');
        console.log('  3. Look for data attributes or click handlers');
        console.log('  4. Share the HTML structure');
    }

    console.log('\n' + '='.repeat(80));
    console.log('Diagnostic complete. Share this output for further analysis.');
    console.log('='.repeat(80));

})();
