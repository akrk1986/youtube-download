"""Scan MP3 files in a folder, detect artists in Title, and update tags accordingly."""
from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError
from artist_search import load_artists, find_artists_in_string
from utils import sanitize_string


def set_artists_in_mp3_files(mp3_folder: Path, artists_json: Path) -> None:
    """Based on artists list loaded from an external file, scan the MP3 file title,
     and check if it contains any artist names from the artists list.
    If found, set the ID3 tags 'artist' and 'album artist' to the artist name(s).
    """
    artists = load_artists(artists_json_path=artists_json)
    for mp3_file in mp3_folder.glob("*.mp3"):
        try:
            audio = EasyID3(mp3_file)
        except ID3NoHeaderError:
            # If no ID3 tag exists, create one
            audio = EasyID3()
        title = audio.get("title", [""])[0]
        if not title:
            print(f"Skipping {mp3_file.name}: No Title tag found.")
            continue
        # Sanitize the title
        clean_title = sanitize_string(dirty_string=title)
        upd_title = clean_title != title
        # Look for known artists in title
        count, artist_string = find_artists_in_string(title, artists)
        if count > 0:
            audio["artist"] = [artist_string]
            audio["albumartist"] = [artist_string]
        if upd_title:
            audio['title'] = clean_title
        if count > 0 or upd_title:
            audio.save(mp3_file)
            print(f"Updated {mp3_file.name}: title may have been modified, artist/album artist set to '{artist_string}'")
        else:
            print(f"No artist found in title for {mp3_file.name}")

def set_title_in_chapter_mp3_files(mp3_folder: Path) -> int:
    """
    Clean up 'title' tag in MP3 chapter files.
    File name pattern:
    <original file name> - <song # (3 digits)> <song name from playlist> [<YouTube ID in playlist> (e.g. 'F_vC6A1EKAw')]
    A possible regex: (.*) - (\d\d\d) (.*) (\[.*\])
    We need two strings: <song #> (group 2), <song name from playlist> (group 3).

    :param mp3_folder: Path to audio files folder
    :return: # of files whose title was modified
    """
    return 0
