"""Scan MP3 files in a folder, detect artists in Title, and update tags accordingly."""
from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError
from funcs_process_audio_tags_common import extract_chapter_info
from funcs_artist_search import load_artists, find_artists_in_string
from funcs_utils import sanitize_string


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
        else:
            art = audio.get('artist')
            alb_art = audio.get('albumartist')
            print(f"No known artist in title, a/aa tags='{art}'/'{alb_art}'")

        if upd_title:
            audio['title'] = clean_title
        if count > 0 or upd_title:
            audio.save(mp3_file)
            print(f"Updated {mp3_file.name}: title may have been modified, artist/album artist set to '{artist_string}'")
        else:
            print(f"No artist found in title for {mp3_file.name}")

def set_tags_in_chapter_mp3_files(mp3_folder: Path) -> int:
    """
    Set 'title' and 'tracknumber' tags in MP3 chapter files in the given folder.
    File name pattern from chapters, as extracted by YT-DLP:
    <original file name> - <song # (3 digits)> <song name from playlist> [<YouTube ID in playlist> (e.g. 'F_vC6A1EKAw')]
    A possible regex: (.*) - ([0-9]{3}) (.*) (.*).mp3
    We need two strings: <song #> (group 2), <song name from playlist> (group 3).

    :param mp3_folder: Path to audio files folder
    :return: # of files whose title was modified
    """
    ctr = 0
    for mp3_file in mp3_folder.glob("*.mp3"):
        try:
            audio = EasyID3(mp3_file)
        except ID3NoHeaderError:
            # If no ID3 tag exists, create one
            audio = EasyID3()
        except Exception:
            # probably not a valid MP3 file, ignore
            continue

        song_name, file_name, song_number = extract_chapter_info(file_name=mp3_file.name)
        print(f"title, f_name, song_#: '{song_name}', '{file_name}, '{song_number}'")
        if song_name is None:
            continue
        try:
            audio['title'] = song_name
            if song_number:
                audio['tracknumber'] = str(int(song_number))
            audio.save(mp3_file)
            ctr += 1
        except Exception as e:
            # no chapter file, ignore
            print(f"ERR: {e}")

    return ctr
