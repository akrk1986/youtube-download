"""Scan M4A files in a folder, detect artists in Title, and update tags accordingly."""
from pathlib import Path
from mutagen.mp4 import MP4
from funcs_process_audio_tags_common import extract_chapter_info, sanitize_album_name
from funcs_artist_search import load_artists, find_artists_in_string
from funcs_utils import sanitize_string


def set_artists_in_m4a_files(m4a_folder: Path, artists_json: Path) -> None:
    """Based on artists list loaded from an external file, scan the M4A file title,
       and check if it contains any artist names from the artists list.
       If found, set the MP4 tags 'artist' and 'album artist' to the artist name(s).
    """
    artists = load_artists(artists_json_path=artists_json)
    for m4a_file in m4a_folder.glob('*.m4a'):
        try:
            audio = MP4(m4a_file)
        except Exception:
            # If file cannot be read as MP4, skip it
            print(f'Skipping {m4a_file.name}: Cannot read as MP4 file.')
            continue

        title_list = audio.get('\xa9nam', [])
        title = title_list[0] if title_list else ''
        if not title:
            print(f'Skipping {m4a_file.name}: No Title tag found.')
            continue

        # Sanitize the title
        clean_title = sanitize_string(dirty_string=title)
        upd_title = clean_title != title

        # Fix year format: convert YYYYMMDD to YYYY if needed
        date_list = audio.get('\xa9day', [])
        upd_date = False
        if date_list:
            date_str = str(date_list[0])
            # If date is in YYYYMMDD format (8 digits), extract just the year (first 4 digits)
            if len(date_str) == 8 and date_str.isdigit():
                year = date_str[:4]
                audio['\xa9day'] = [year]
                upd_date = True
                print(f'Fixed date format: {date_str} -> {year}')

        # Look for known artists in title
        count, artist_string = find_artists_in_string(title, artists)
        if count > 0:
            audio['\xa9ART'] = [artist_string]
            audio['aART'] = [artist_string]
        else:
            art = audio.get('\xa9ART', [])
            alb_art = audio.get('aART', [])
            print(f"No known artist in title, a/aa tags='{art}'/'{alb_art}'")

        # Clear track number for non-chapter files (single videos and playlists)
        upd_track = False
        if 'trkn' in audio and audio['trkn']:
            audio['trkn'] = []  # Clear track number
            upd_track = True

        if upd_title:
            audio['\xa9nam'] = [clean_title]
        if count > 0 or upd_title or upd_date or upd_track:
            audio.save(m4a_file)
            print(f"Updated {m4a_file.name}: title may have been modified, artist/album artist set to '{artist_string}'")
        else:
            print(f'No artist found in title for {m4a_file.name}')

def set_tags_in_chapter_m4a_files(m4a_folder: Path, uploader: str = None, video_title: str = None) -> int:
    """
    Set 'title' and 'tracknumber' tags in M4A chapter files in the given folder.
    File name pattern from chapters, as extracted by YT-DLP:
    <original file name> - <song # (3 digits)> <song name from playlist> [<YouTube ID in playlist> (e.g. 'F_vC6A1EKAw')]
    A possible regex: (.*) - ([0-9]{3}) (.*) (.*).m4a
    We need two strings: <song #> (group 2), <song name from playlist> (group 3).

    :param m4a_folder: Path to audio files folder
    :return: # of files whose title was modified
    """
    ctr = 0
    for m4a_file in m4a_folder.glob('*.m4a'):
        try:
            audio = MP4(m4a_file)
        except Exception:
            # probably not a valid M4A file, ignore
            continue

        song_name, file_name, song_number = extract_chapter_info(file_name=m4a_file.name)
        print(f"title, f_name, song_#: '{song_name}', '{file_name}', '{song_number}'")
        if song_name is None:
            continue
        try:
            audio['\xa9nam'] = [song_name]
            if song_number:
                audio['trkn'] = [(int(song_number), 0)]

            # Fix year format: convert YYYYMMDD to YYYY if needed
            date_list = audio.get('\xa9day', [])
            if date_list:
                date_str = str(date_list[0])
                # If date is in YYYYMMDD format (8 digits), extract just the year (first 4 digits)
                if len(date_str) == 8 and date_str.isdigit():
                    year = date_str[:4]
                    audio['\xa9day'] = [year]
                    print(f'Fixed date format: {date_str} -> {year}')

            # If no artist is set and we have an uploader, use uploader as artist
            current_artist = audio.get('\xa9ART', [])
            current_albumartist = audio.get('aART', [])

            if (not current_artist or current_artist == [''] or current_artist == ['NA']) and uploader:
                audio['\xa9ART'] = [uploader]
                audio['aART'] = [uploader]
                print(f"Set artist/albumartist to uploader '{uploader}' for chapter file")

            # If no album is set and we have a video title, use sanitized video title as album
            current_album = audio.get('\xa9alb', [])

            if (not current_album or current_album == [''] or current_album == ['NA']) and video_title:
                sanitized_album = sanitize_album_name(video_title)
                if sanitized_album:
                    audio['\xa9alb'] = [sanitized_album]
                    print(f"Set album to sanitized video title '{sanitized_album}' for chapter file")

            audio.save(m4a_file)
            ctr += 1
        except Exception as e:
            # no chapter file, ignore
            print(f'ERR: {e}')

    return ctr
