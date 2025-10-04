"""Convert export from a Trello board to a simpler JSON."""
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def capitalize_greek_name(name: str) -> str:
    """
    If the name is all uppercase, capitalize each word (first letter uppercase, rest lowercase).
    Otherwise, return as is.
    """
    if name.isupper():
        return ' '.join(word.capitalize() for word in name.split())
    return name

def parse_card_name(card_name: str) -> Tuple[str, str, bool]:
    """
    Splits the card name into Greek and English names.
    - If 3 or more parts: use the first two, discard the rest.
    - If 2 parts: use both.
    - If 1 part: treat as Greek, English is empty, and return warning flag.
    Returns: (greek, english, warning)
    """
    parts = card_name.split(' - ')
    if len(parts) >= 2:
        greek = parts[0]
        english = parts[1]
        warning = False
    else:
        greek = parts[0]
        english = ''
        warning = True
    greek = capitalize_greek_name(greek.strip())
    return greek, english.strip(), warning

def extract_artists(
    trello_data: Dict[str, Any]
) -> Tuple[List[Dict[str, str]], int, int]:
    """
    Extracts artists from Trello JSON export.
    Returns the list of artists, number of lists, and number of cards.
    Prints a warning if a card name has only one part.
    """
    # Map list IDs to list names (only open lists)
    list_id_to_name = {
        lst['id']: lst['name']
        for lst in trello_data.get('lists', [])
        if not lst.get('closed', False)
    }
    artists: List[Dict[str, str]] = []
    card_count = 0
    for card in trello_data.get('cards', []):
        if card.get('closed', False):
            continue
        card_count += 1
        list_name = list_id_to_name.get(card['idList'], '')
        greek, english, warning = parse_card_name(card['name'])
        if warning:
            print(f"Warning: Card name '{card['name']}' in list '{list_name}' has only one part.")
        artist = {
            'Greek name': greek,
            'English name': english,
            'List': list_name
        }
        artists.append(artist)
    return artists, len(list_id_to_name), card_count

def main() -> None:
    parser = argparse.ArgumentParser(description='Extract artists from Trello JSON export.')
    parser.add_argument(
        '--trello-json',
        type=Path,
        default=Path('Data/Trello - greek-music-artists.json'),
        help='Path to Trello JSON export'
    )
    parser.add_argument(
        '--artists-json',
        type=Path,
        default=Path('Data/artists.json'),
        help='Output path for artists JSON'
    )
    args = parser.parse_args()

    with args.trello_json.open('r', encoding='utf-8') as f:
        trello_data = json.load(f)

    artists, num_lists, num_cards = extract_artists(trello_data)
    output = {'artists': artists}

    with args.artists_json.open('w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\nFound {num_lists} lists and {num_cards} cards.')

if __name__ == '__main__':
    main()
