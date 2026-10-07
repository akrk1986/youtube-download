"""YouTube/Facebook media-URL matching, shared by the webapp clipboard watcher and the mail fetcher.

Recognises the video URL forms yt-dlp accepts for YouTube and Facebook, and unwraps the Google
redirect (``google.com/url?q=<encoded target>&…``) that Gmail puts around links in messages.
"""

import re
from urllib.parse import parse_qs, urlparse

# Matches the YouTube URL forms yt-dlp accepts, so the matcher never rejects a link the main script
# would happily download: a video (watch?v=…), a playlist (playlist?list=…), a youtu.be/<id> short
# link, or a shorts/<id> link — with an optional scheme and www./m./music. subdomain. A watch link
# that also carries a &list=… playlist matches via the watch?v= branch.
_YOUTUBE_RE = re.compile(
    r'^(?:https?://)?(?:www\.|m\.|music\.)?'
    r'(?:youtube\.com/(?:watch\?v=|playlist\?list=|shorts/)|youtu\.be/)',
    re.IGNORECASE,
)

# Matches the Facebook video URL forms yt-dlp accepts: a watch link (watch?v=… / watch/?v=…), a
# page/user video permalink (<page>/videos/<id>), the legacy video.php?v=… form, a reel, a share
# link (share/v/… or share/r/…), or an fb.watch/<id> short link — with an optional scheme and
# www./m./web. subdomain. A bare profile/page URL (facebook.com/<page>) deliberately does NOT match.
_FACEBOOK_RE = re.compile(
    r'^(?:https?://)?'
    r'(?:(?:www\.|m\.|web\.)?facebook\.com/'
    r'(?:watch/?\?v=|video\.php\?v=|reel/|share/[rv]/|[^/?#]+/videos/)'
    r'|fb\.watch/)',
    re.IGNORECASE,
)


# Matches the Google redirect wrapper Gmail puts around links in messages: right-clicking a link
# in a Gmail message and copying it yields 'https://www.google.com/url?q=<encoded target>&source=
# gmail&…' (country TLDs like google.co.il appear too), not the target URL itself.
_GOOGLE_REDIRECT_RE = re.compile(
    r'^(?:https?://)?(?:www\.)?google\.[a-z]{2,3}(?:\.[a-z]{2})?/url\?',
    re.IGNORECASE,
)


def unwrap_google_redirect(value: str) -> str:
    """Return the target URL from a Google/Gmail redirect wrapper, or the value unchanged.

    Args:
        value: A candidate string (already stripped).

    Returns:
        str: The URL-decoded ``q`` (or ``url``) query parameter when the value is a
            ``google.com/url?…`` redirect carrying one, otherwise the value as-is.
    """
    if not _GOOGLE_REDIRECT_RE.match(value):
        return value
    query = parse_qs(urlparse(value).query)
    for param in ('q', 'url'):
        target = query.get(param)
        if target and target[0].strip():
            return target[0].strip()
    return value


def extract_media_url(value: str) -> str | None:
    """Return the media URL carried by a string, or None when there is none.

    Unwraps a Gmail/Google redirect first, so a link copied out of a Gmail message is
    recognised and delivered as the clean target URL.

    Args:
        value: A candidate string.

    Returns:
        str | None: The (unwrapped, stripped) media URL, or None when the value is not one.
    """
    candidate = unwrap_google_redirect(value.strip())
    return candidate if is_media_url(candidate) else None


def is_media_url(value: str) -> bool:
    """Return whether a string looks like a downloadable YouTube or Facebook video URL.

    Args:
        value: A candidate string.

    Returns:
        bool: True for YouTube watch/playlist/shorts/youtu.be links and Facebook video links
            (watch?v=, <page>/videos/, video.php?v=, reel, share, fb.watch).
    """
    stripped = value.strip()
    return bool(_YOUTUBE_RE.match(stripped) or _FACEBOOK_RE.match(stripped))
