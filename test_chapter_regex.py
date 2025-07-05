"""Test code."""
from process_mp3_files_for_tags import extract_chapter_info

def main() -> None:
    s = input('Enter the string: ')
    try:
        song_name, file_name, song_number = extract_chapter_info(s)
        print(f'Song Name: {song_name}')
        print(f'File Name: {file_name}')
        print(f'Song Number: {song_number}')
    except Exception as e:
        print(f'Error: {e}')


if __name__ == '__main__':
    main()