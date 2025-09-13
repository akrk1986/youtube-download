"""Test cases for YouTube download scenarios."""

# Test case 1: Simple single video (extract audio)
VIDEO_SIMPLE = "https://youtu.be/Bg3KapGZEos?si=8jK0aVUJj_uIvXjG"

# Test case 2: Video with chapters (extract video only)
VIDEO_WITH_CHAPTERS = "https://youtu.be/-kg__VP2GIg?si=GX8oyXg6BohXcc0u"

# Test case 3: Playlist (extract audio) - Limited to first 10 videos for testing
_VIDEO_PLAYLIST = "https://www.youtube.com/playlist?list=PLFgquLnL59alCl_2TQvOiD5Vgm1hCaGSI"
VIDEO_PLAYLIST = 'https://youtube.com/playlist?list=PLRXnwzqAlx1NehOIsFdwtVbsZ0Orf71cE'