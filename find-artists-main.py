"""Search for Greek music artists in a string using artists.json."""

import argparse
from pathlib import Path
from artist_search import load_artists, find_artists_in_string

def main() -> None:
    parser = argparse.ArgumentParser(description="Search for Greek music artists in a string.")
    parser.add_argument('--artists-json', type=Path, default=Path('Data/artists.json'),
                        help='Path to artists.json file')
    parser.add_argument('input_string', type=str, nargs='?', default=None,
                        help='String to search for artist names')
    args = parser.parse_args()

    # Prompt if not provided as argument
    if args.input_string is None:
        try:
            args.input_string = input("Enter the string to search for artist names: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")  # For clean newline
            args.input_string = ""

    if not args.input_string:
        print("")  # Output empty string as required
        return

    artists = load_artists(args.artists_json)
    n_found, result = find_artists_in_string(args.input_string, artists)
    print(f"Found {n_found} artists, result: '{result}'")

if __name__ == '__main__':
    main()
