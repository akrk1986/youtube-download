// ERTFlix - Capture Working Play Button Click
//
// Run this on the MAIN page where Play buttons work!
// URL: https://www.ertflix.gr/#/details/ERT_PS054741_E0
//
// Instructions:
// 1. Open the MAIN page with all 32 episodes
// 2. Press F12 > Console
// 3. Paste this script and press Enter
// 4. Click any Play button
// 5. The script will capture what happens

(function() {

console.clear();
console.log('='.repeat(80));
console.log('ERTFlix - Capture Working Play Button Click');
console.log('='.repeat(80));
console.log(`\nCurrent URL: ${window.location.href}\n`);

// =============================================================================
// Monitor URL changes
// =============================================================================

console.log('Setting up URL change monitor...\n');

let lastUrl = window.location.href;

const urlObserver = setInterval(() => {
    const currentUrl = window.location.href;
    if (currentUrl !== lastUrl) {
        console.log('\n' + '='.repeat(80));
        console.log('📍 URL CHANGED!');
        console.log('='.repeat(80));
        console.log(`\nFrom: ${lastUrl}`);
        console.log(`To:   ${currentUrl}\n`);

        window.__ertflixNavigationUrl = currentUrl;

        console.log('✓ New URL saved to: window.__ertflixNavigationUrl');

        // Extract episode ID from URL
        const ertMatch = currentUrl.match(/ERT_[A-Z0-9_]+/);
        if (ertMatch) {
            console.log(`✓ Episode ID: ${ertMatch[0]}`);
            window.__ertflixEpisodeId = ertMatch[0];
        }

        console.log('='.repeat(80));

        lastUrl = currentUrl;
    }
}, 100);

window.__stopUrlObserver = () => {
    clearInterval(urlObserver);
    console.log('✓ URL observer stopped');
};

console.log('✓ URL change monitor active');

// =============================================================================
// Monitor network requests for video URLs and token API calls
// =============================================================================

console.log('Setting up network request monitor...\n');

const capturedUrls = [];
const tokenApiUrls = [];

// Intercept fetch
const originalFetch = window.fetch;
window.fetch = function(...args) {
    const url = args[0];
    if (typeof url === 'string') {
        // Check for token API calls
        if (url.includes('api.ertflix.opentv.com/urlbuilder/v1/playout/content/token')) {
            console.log('\n' + '='.repeat(80));
            console.log('🔑 TOKEN API CALL DETECTED (fetch)');
            console.log('='.repeat(80));
            console.log(`\nToken API URL: ${url}\n`);

            if (!tokenApiUrls.includes(url)) {
                tokenApiUrls.push(url);
            }

            window.__ertflixTokenApiUrl = url;
            console.log('✓ Token API URL saved to: window.__ertflixTokenApiUrl');
            console.log('\nTO DOWNLOAD WITH PYTHON:');
            console.log(`export YTDLP_USE_COOKIES=firefox  # or chrome`);
            console.log(`python main-yt-dlp.py --only-audio "${url}"`);
            console.log('='.repeat(80));
        }
        // Log video-related requests
        else if (url.includes('.m3u8') || url.includes('.mpd') ||
            url.includes('manifest') || url.includes('stream') ||
            url.includes('video') || url.includes('/vod/')) {

            console.log('\n' + '='.repeat(80));
            console.log('📹 VIDEO-RELATED REQUEST DETECTED (fetch)');
            console.log('='.repeat(80));
            console.log(`\nURL: ${url}\n`);

            if (!capturedUrls.includes(url)) {
                capturedUrls.push(url);
            }

            if (url.includes('.m3u8') || url.includes('.mpd')) {
                window.__ertflixVideoUrl = url;
                console.log('✓ Video manifest URL saved to: window.__ertflixVideoUrl');
                console.log('\nTO DOWNLOAD:');
                console.log(`yt-dlp "${url}"`);
            }

            console.log('='.repeat(80));
        }
    }
    return originalFetch.apply(this, args);
};

// Intercept XMLHttpRequest
const originalOpen = window.XMLHttpRequest.prototype.open;
window.XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    if (typeof url === 'string') {
        // Check for token API calls
        if (url.includes('api.ertflix.opentv.com/urlbuilder/v1/playout/content/token')) {
            console.log('\n' + '='.repeat(80));
            console.log('🔑 TOKEN API CALL DETECTED (XHR)');
            console.log('='.repeat(80));
            console.log(`\nToken API URL: ${url}\n`);

            if (!tokenApiUrls.includes(url)) {
                tokenApiUrls.push(url);
            }

            window.__ertflixTokenApiUrl = url;
            console.log('✓ Token API URL saved to: window.__ertflixTokenApiUrl');
            console.log('\nTO DOWNLOAD WITH PYTHON:');
            console.log(`export YTDLP_USE_COOKIES=firefox  # or chrome`);
            console.log(`python main-yt-dlp.py --only-audio "${url}"`);
            console.log('='.repeat(80));
        }
        // Log video-related requests
        else if (url.includes('.m3u8') || url.includes('.mpd') ||
            url.includes('manifest') || url.includes('stream') ||
            url.includes('video') || url.includes('/vod/')) {

            console.log('\n' + '='.repeat(80));
            console.log('📹 VIDEO-RELATED REQUEST DETECTED (XHR)');
            console.log('='.repeat(80));
            console.log(`\nURL: ${url}\n`);

            if (!capturedUrls.includes(url)) {
                capturedUrls.push(url);
            }

            if (url.includes('.m3u8') || url.includes('.mpd')) {
                window.__ertflixVideoUrl = url;
                console.log('✓ Video manifest URL saved to: window.__ertflixVideoUrl');
                console.log('\nTO DOWNLOAD:');
                console.log(`yt-dlp "${url}"`);
            }

            console.log('='.repeat(80));
        }
    }
    return originalOpen.apply(this, [method, url, ...rest]);
};

console.log('✓ Network request monitor active');

// =============================================================================
// Intercept Shaka Player (if present)
// =============================================================================

if (typeof window.shaka !== 'undefined') {
    console.log('Setting up Shaka Player interceptor...\n');

    const OriginalPlayer = window.shaka.Player;
    window.shaka.Player = function(...args) {
        const player = new OriginalPlayer(...args);

        const originalLoad = player.load.bind(player);
        player.load = function(manifestUri, startTime, mimeType) {
            console.log('\n' + '='.repeat(80));
            console.log('📹 SHAKA PLAYER LOAD CALLED!');
            console.log('='.repeat(80));
            console.log(`\nManifest URI: ${manifestUri}`);
            console.log(`Stream type: ${manifestUri.includes('.m3u8') ? 'HLS' : 'DASH'}`);

            window.__ertflixVideoUrl = manifestUri;

            console.log('\n✓ Saved to: window.__ertflixVideoUrl');
            console.log('\nTO DOWNLOAD:');
            console.log(`yt-dlp "${manifestUri}"`);
            console.log('='.repeat(80));

            return originalLoad(manifestUri, startTime, mimeType);
        };

        return player;
    };

    Object.setPrototypeOf(window.shaka.Player, OriginalPlayer);
    Object.setPrototypeOf(window.shaka.Player.prototype, OriginalPlayer.prototype);

    console.log('✓ Shaka Player interceptor active');
}

// =============================================================================
// Monitor click events on Play buttons
// =============================================================================

console.log('\nSetting up Play button click monitor...\n');

document.addEventListener('click', (event) => {
    const target = event.target;

    // Check if clicked element or parent is a play button
    const playButton = target.closest('button[aria-label*="play" i], button[aria-label*="Αναπαραγωγή" i], button[class*="play" i], .asset-card button');

    if (playButton) {
        console.log('\n' + '='.repeat(80));
        console.log('👆 PLAY BUTTON CLICKED!');
        console.log('='.repeat(80));

        const card = playButton.closest('.asset-card');
        if (card) {
            // Try to find episode info from the card
            const img = card.querySelector('img[src], img[data-src]');
            if (img) {
                const imgSrc = img.getAttribute('src') || img.getAttribute('data-src');
                const ertMatch = imgSrc.match(/ERT_[A-Z0-9_]+/);
                if (ertMatch) {
                    console.log(`\nEpisode ID (from image): ${ertMatch[0]}`);
                    window.__ertflixClickedEpisodeId = ertMatch[0];
                }
            }

            const ariaLabel = playButton.getAttribute('aria-label');
            if (ariaLabel) {
                console.log(`Button aria-label: ${ariaLabel}`);
            }
        }

        console.log('\nWaiting for navigation or video load...');
        console.log('='.repeat(80));
    }
}, true); // Use capture phase

console.log('✓ Play button click monitor active');

// Store captured URLs globally
window.__capturedVideoRequests = capturedUrls;
window.__ertflixTokenApiUrls = tokenApiUrls;

// =============================================================================
// INSTRUCTIONS
// =============================================================================

console.log('\n\n' + '='.repeat(80));
console.log('READY TO CAPTURE!');
console.log('='.repeat(80));
console.log('\nAll monitors are active. Now:');
console.log('\n1. Click any Play button on this page');
console.log('2. Watch the console output above');
console.log('3. The script will capture:');
console.log('   - Token API URLs (🔑 - USE THESE for downloads!)');
console.log('   - Video manifest URLs (if loaded directly)');
console.log('   - URL changes (if it navigates)');
console.log('   - Episode IDs');
console.log('\n4. After clicking, check:');
console.log('   - window.__ertflixTokenApiUrl (MAIN: token API URL)');
console.log('   - window.__ertflixTokenApiUrls (array of all token URLs)');
console.log('   - window.__ertflixVideoUrl (if video URL found)');
console.log('   - window.__ertflixNavigationUrl (if URL changed)');
console.log('   - window.__ertflixClickedEpisodeId (episode from card)');
console.log('\n💡 TIP: Token API URLs are what you need for batch downloads!');
console.log('   They handle authentication automatically.');
console.log('\nWaiting for Play button click...');
console.log('='.repeat(80));

})(); // End of function scope
