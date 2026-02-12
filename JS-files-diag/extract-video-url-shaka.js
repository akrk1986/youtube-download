// ERTFlix Video URL Extractor - Shaka Player Specific
//
// Instructions:
// 1. Open an episode page (e.g., https://www.ertflix.gr/#/details/ERT_PS027309)
// 2. Press F12 > Console
// 3. Paste this script and press Enter
// 4. Click the Play button on the page
// 5. The video URL will be captured and displayed

(function() {

console.clear();
console.log('='.repeat(80));
console.log('ERTFlix Video URL Extractor - Shaka Player');
console.log('='.repeat(80));
console.log(`\nCurrent URL: ${window.location.href}\n`);

// =============================================================================
// SECTION 1: Find Shaka Player instances
// =============================================================================

console.log('SECTION 1: Looking for Shaka Player instances...\n');

if (typeof window.shaka === 'undefined') {
    console.log('❌ ERROR: Shaka Player not found on this page!');
    return;
}

console.log('✓ Shaka Player library detected\n');

// Try to find the video element with Shaka Player attached
const videoElements = document.querySelectorAll('video');
console.log(`Found ${videoElements.length} video elements\n`);

let shakaPlayer = null;
let videoElement = null;

// Check if video elements have a player instance attached
for (const video of videoElements) {
    // Shaka Player instances are sometimes stored on the video element
    if (video.player) {
        shakaPlayer = video.player;
        videoElement = video;
        console.log('✓ Found Shaka Player instance attached to video element');
        break;
    }
}

// If not found on video element, check window object
if (!shakaPlayer) {
    const windowKeys = Object.keys(window);
    for (const key of windowKeys) {
        const value = window[key];
        if (value && value.constructor && value.constructor.name === 'Player') {
            shakaPlayer = value;
            console.log(`✓ Found Shaka Player instance in window.${key}`);
            break;
        }
    }
}

// =============================================================================
// SECTION 2: Monitor for manifest URL
// =============================================================================

console.log('\nSECTION 2: Setting up manifest URL capture...\n');

const capturedData = {
    manifestUrl: null,
    videoUrl: null,
    streamType: null
};

// Method 1: Intercept Shaka Player's load() method
if (shakaPlayer) {
    console.log('Intercepting existing Shaka Player instance...');

    const originalLoad = shakaPlayer.load.bind(shakaPlayer);
    shakaPlayer.load = function(manifestUri, startTime, mimeType) {
        console.log('\n' + '='.repeat(80));
        console.log('📹 SHAKA PLAYER LOAD INTERCEPTED!');
        console.log('='.repeat(80));
        console.log(`\nManifest URL: ${manifestUri}`);
        console.log(`Start time: ${startTime || 0}`);
        console.log(`MIME type: ${mimeType || 'auto-detect'}`);

        capturedData.manifestUrl = manifestUri;
        capturedData.streamType = manifestUri.includes('.m3u8') ? 'HLS' :
                                  manifestUri.includes('.mpd') ? 'DASH' : 'Unknown';

        console.log(`\nStream type: ${capturedData.streamType}`);

        // Store globally
        window.__ertflixVideoUrl = manifestUri;
        window.__ertflixStreamType = capturedData.streamType;

        console.log('\n✓ Video URL saved to: window.__ertflixVideoUrl');
        console.log('✓ Stream type saved to: window.__ertflixStreamType');

        console.log('\n' + '='.repeat(80));
        console.log('TO DOWNLOAD THIS VIDEO:');
        console.log('='.repeat(80));
        console.log(`\nyt-dlp "${manifestUri}"\n`);
        console.log('Or copy from: window.__ertflixVideoUrl');
        console.log('='.repeat(80));

        return originalLoad(manifestUri, startTime, mimeType);
    };

    console.log('✓ Shaka Player load() method intercepted');
}

// Method 2: Intercept Shaka Player constructor for new instances
const OriginalPlayer = window.shaka.Player;
window.shaka.Player = function(...args) {
    console.log('✓ New Shaka Player instance created');

    const player = new OriginalPlayer(...args);

    // Intercept the load method
    const originalLoad = player.load.bind(player);
    player.load = function(manifestUri, startTime, mimeType) {
        console.log('\n' + '='.repeat(80));
        console.log('📹 SHAKA PLAYER LOAD INTERCEPTED!');
        console.log('='.repeat(80));
        console.log(`\nManifest URL: ${manifestUri}`);
        console.log(`Start time: ${startTime || 0}`);
        console.log(`MIME type: ${mimeType || 'auto-detect'}`);

        capturedData.manifestUrl = manifestUri;
        capturedData.streamType = manifestUri.includes('.m3u8') ? 'HLS' :
                                  manifestUri.includes('.mpd') ? 'DASH' : 'Unknown';

        console.log(`\nStream type: ${capturedData.streamType}`);

        // Store globally
        window.__ertflixVideoUrl = manifestUri;
        window.__ertflixStreamType = capturedData.streamType;

        console.log('\n✓ Video URL saved to: window.__ertflixVideoUrl');
        console.log('✓ Stream type saved to: window.__ertflixStreamType');

        console.log('\n' + '='.repeat(80));
        console.log('TO DOWNLOAD THIS VIDEO:');
        console.log('='.repeat(80));
        console.log(`\nyt-dlp "${manifestUri}"\n`);
        console.log('Or copy from: window.__ertflixVideoUrl');
        console.log('='.repeat(80));

        return originalLoad(manifestUri, startTime, mimeType);
    };

    return player;
};

// Copy static methods and properties
Object.setPrototypeOf(window.shaka.Player, OriginalPlayer);
Object.setPrototypeOf(window.shaka.Player.prototype, OriginalPlayer.prototype);

console.log('✓ Shaka Player constructor intercepted');

// Method 3: Generic network interception
const originalFetch = window.fetch;
window.fetch = function(...args) {
    const url = args[0];
    if (typeof url === 'string') {
        if (url.includes('.m3u8') || url.includes('.mpd')) {
            console.log('\n' + '='.repeat(80));
            console.log('📹 VIDEO MANIFEST DETECTED (fetch)');
            console.log('='.repeat(80));
            console.log(`\nURL: ${url}`);

            capturedData.manifestUrl = url;
            capturedData.streamType = url.includes('.m3u8') ? 'HLS' : 'DASH';

            window.__ertflixVideoUrl = url;
            window.__ertflixStreamType = capturedData.streamType;

            console.log(`\nStream type: ${capturedData.streamType}`);
            console.log('\n✓ Video URL saved to: window.__ertflixVideoUrl');
            console.log('\n' + '='.repeat(80));
            console.log('TO DOWNLOAD THIS VIDEO:');
            console.log('='.repeat(80));
            console.log(`\nyt-dlp "${url}"\n`);
            console.log('='.repeat(80));
        }
    }
    return originalFetch.apply(this, args);
};

console.log('✓ Network fetch() intercepted');

// =============================================================================
// INSTRUCTIONS
// =============================================================================

console.log('\n\n' + '='.repeat(80));
console.log('READY TO CAPTURE VIDEO URL!');
console.log('='.repeat(80));
console.log('\nAll interceptors are active. Now:');
console.log('\n1. Click the Play button on the page');
console.log('2. The video manifest URL will be captured automatically');
console.log('3. The URL will be displayed above and saved to window.__ertflixVideoUrl');
console.log('4. Use yt-dlp command shown above to download the video');
console.log('\nWaiting for Play button click...');
console.log('='.repeat(80));

})(); // End of function scope
