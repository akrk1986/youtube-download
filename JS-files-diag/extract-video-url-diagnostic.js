// ERTFlix Video URL Diagnostic Script
//
// Instructions:
// 1. Open an episode page (e.g., https://www.ertflix.gr/#/details/ERT_PS027309)
// 2. Wait for the page to fully load
// 3. Press F12 > Console
// 4. Paste this script and press Enter
// 5. Follow the instructions in the output
//
// This script will help find the actual video stream URL

(function() {

console.clear();
console.log('='.repeat(80));
console.log('ERTFlix Video URL Diagnostic');
console.log('='.repeat(80));
console.log(`\nCurrent URL: ${window.location.href}\n`);

// =============================================================================
// SECTION 1: Find video elements
// =============================================================================

console.log('SECTION 1: Looking for video elements...\n');
console.log('-'.repeat(80));

const videoElements = document.querySelectorAll('video');
console.log(`Found ${videoElements.length} <video> elements\n`);

if (videoElements.length > 0) {
    videoElements.forEach((video, index) => {
        console.log(`Video ${index + 1}:`);
        console.log(`  src: ${video.src || '(none)'}`);
        console.log(`  currentSrc: ${video.currentSrc || '(none)'}`);
        console.log(`  poster: ${video.poster || '(none)'}`);
        console.log(`  preload: ${video.preload}`);
        console.log(`  autoplay: ${video.autoplay}`);

        // Check for source elements inside video tag
        const sources = video.querySelectorAll('source');
        if (sources.length > 0) {
            console.log(`  <source> elements:`);
            sources.forEach((src, i) => {
                console.log(`    ${i + 1}. src="${src.src}" type="${src.type}"`);
            });
        }

        console.log('');
    });
}

// =============================================================================
// SECTION 2: Look for video players (common libraries)
// =============================================================================

console.log('\nSECTION 2: Detecting video player libraries...\n');
console.log('-'.repeat(80));

const players = {
    'Video.js': () => typeof window.videojs !== 'undefined',
    'JW Player': () => typeof window.jwplayer !== 'undefined',
    'Plyr': () => typeof window.Plyr !== 'undefined',
    'Shaka Player': () => typeof window.shaka !== 'undefined',
    'Dash.js': () => typeof window.dashjs !== 'undefined',
    'HLS.js': () => typeof window.Hls !== 'undefined',
    'Bitmovin': () => typeof window.bitmovin !== 'undefined',
    'THEOplayer': () => typeof window.THEOplayer !== 'undefined'
};

let detectedPlayer = null;

Object.entries(players).forEach(([name, detector]) => {
    const detected = detector();
    console.log(`  ${detected ? '✓' : '✗'} ${name}: ${detected ? 'DETECTED' : 'Not found'}`);
    if (detected) {
        detectedPlayer = name;
    }
});

// =============================================================================
// SECTION 3: Look for Play buttons
// =============================================================================

console.log('\n\nSECTION 3: Looking for Play buttons...\n');
console.log('-'.repeat(80));

const playButtons = document.querySelectorAll(
    'button[aria-label*="play" i], button[aria-label*="Αναπαραγωγή" i], ' +
    'button[class*="play" i], .play-button, [class*="PlayButton"]'
);

console.log(`Found ${playButtons.length} potential play buttons\n`);

if (playButtons.length > 0) {
    playButtons.forEach((btn, index) => {
        console.log(`Play button ${index + 1}:`);
        console.log(`  aria-label: ${btn.getAttribute('aria-label') || '(none)'}`);
        console.log(`  class: ${btn.className}`);
        console.log(`  id: ${btn.id || '(none)'}`);
        console.log(`  disabled: ${btn.disabled}`);
        console.log('');
    });
}

// =============================================================================
// SECTION 4: Search window object for video URLs
// =============================================================================

console.log('\nSECTION 4: Searching for video URLs in window object...\n');
console.log('-'.repeat(80));

const windowKeys = Object.keys(window);
const foundUrls = [];

// Common video URL patterns
const videoPatterns = [
    /\.m3u8/i,       // HLS playlist
    /\.mpd/i,        // DASH manifest
    /\.mp4/i,        // MP4 video
    /\.webm/i,       // WebM video
    /streaming/i,    // Streaming URLs
    /video/i,        // Video URLs
    /manifest/i      // Manifest files
];

for (const key of windowKeys) {
    try {
        const value = window[key];
        if (value && typeof value === 'object') {
            const jsonStr = JSON.stringify(value);

            // Check each pattern
            videoPatterns.forEach(pattern => {
                if (pattern.test(jsonStr)) {
                    // Found a potential video URL
                    const matches = jsonStr.match(/(https?:\/\/[^\s"']+\.(?:m3u8|mpd|mp4|webm)[^\s"']*)/gi);
                    if (matches) {
                        matches.forEach(url => {
                            if (!foundUrls.includes(url)) {
                                foundUrls.push(url);
                            }
                        });
                    }
                }
            });
        }
    } catch (e) {
        // Skip circular references
    }
}

if (foundUrls.length > 0) {
    console.log(`✓ Found ${foundUrls.length} potential video URLs:\n`);
    foundUrls.forEach((url, i) => {
        console.log(`  ${i + 1}. ${url}`);
    });
} else {
    console.log('✗ No video URLs found in window object');
}

// =============================================================================
// SECTION 5: Monitor network requests
// =============================================================================

console.log('\n\nSECTION 5: Network Request Monitoring\n');
console.log('-'.repeat(80));
console.log('Setting up network request interceptor...\n');

// Store original fetch
const originalFetch = window.fetch;
const capturedRequests = [];

// Intercept fetch requests
window.fetch = function(...args) {
    const url = args[0];
    if (typeof url === 'string') {
        // Check if it's a video-related request
        if (url.includes('.m3u8') || url.includes('.mpd') ||
            url.includes('.mp4') || url.includes('video') ||
            url.includes('stream') || url.includes('manifest')) {
            capturedRequests.push(url);
            console.log(`📹 Intercepted video request: ${url}`);
        }
    }
    return originalFetch.apply(this, args);
};

// Store original XMLHttpRequest
const originalXHR = window.XMLHttpRequest;
const openOriginal = originalXHR.prototype.open;

originalXHR.prototype.open = function(method, url, ...rest) {
    if (typeof url === 'string') {
        // Check if it's a video-related request
        if (url.includes('.m3u8') || url.includes('.mpd') ||
            url.includes('.mp4') || url.includes('video') ||
            url.includes('stream') || url.includes('manifest')) {
            capturedRequests.push(url);
            console.log(`📹 Intercepted XHR video request: ${url}`);
        }
    }
    return openOriginal.apply(this, [method, url, ...rest]);
};

console.log('✓ Network interceptor installed!\n');
console.log('Now try clicking the Play button...\n');

// Store interceptor cleanup function
window.__cleanupVideoInterceptor = function() {
    window.fetch = originalFetch;
    window.XMLHttpRequest.prototype.open = openOriginal;
    console.log('✓ Network interceptor removed');
};

// Store captured requests globally
window.__capturedVideoRequests = capturedRequests;

// =============================================================================
// SECTION 6: Check Network tab manually
// =============================================================================

console.log('\n' + '='.repeat(80));
console.log('INSTRUCTIONS');
console.log('='.repeat(80));
console.log('\n1. Keep this console open');
console.log('2. Go to Network tab (F12 > Network)');
console.log('3. Filter by "media" or "m3u8" or "mpd"');
console.log('4. Click the Play button on the page');
console.log('5. Watch for video stream requests in Network tab');
console.log('\nCommon patterns to look for:');
console.log('  - .m3u8 files (HLS streaming)');
console.log('  - .mpd files (DASH streaming)');
console.log('  - .mp4 files (direct video)');
console.log('  - URLs with "stream" or "video" or "manifest"');
console.log('\n6. If you see video requests, they will be logged above');
console.log('7. Check: window.__capturedVideoRequests');
console.log('\nTo cleanup: window.__cleanupVideoInterceptor()');
console.log('\n' + '='.repeat(80));

})(); // End of function scope
