"""Convert export from a Trello board to a simpler JSON."""
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

def parse_card_name(card_name: str) -> Dict[str, str]:
    """
    Splits the card name into Greek and English names.
    - If 3 or more parts: use the first two, discard the rest.
    - If 2 parts: use both.
    - If 1 part: treat as Greek, English is empty.
    """
    parts = card_name.split(' - ')
    if len(parts) >= 2:
        greek = parts[0]
        english = parts[1]
    else:
        greek = parts[0]
        english = ''
    return {"Greek name": greek.strip(), "English name": english.strip()}

def extract_artists(trello_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Extracts artists from Trello JSON export.
    Each artist is a dict with Greek name, English name, and list name.
    """
    # Map list IDs to list names (only open lists)
    list_id_to_name = {
        lst['id']: lst['name']
        for lst in trello_data.get('lists', [])
        if not lst.get('closed', False)
    }
    artists: List[Dict[str, str]] = []
    for card in trello_data.get('cards', []):
        if card.get('closed', False):
            continue
        list_name = list_id_to_name.get(card['idList'], '')
        names = parse_card_name(card['name'])
        artist = {
            "Greek name": names["Greek name"],
            "English name": names["English name"],
            "List": list_name
        }
        artists.append(artist)
    return artists

def main() -> None:
    parser = argparse.ArgumentParser(description="Extract artists from Trello JSON export.")
    parser.add_argument(
        '--trello-json',
        type=Path,
        default=Path.cwd() / Path('Data') / Path('trello - greek-music-artists.json'),
        help='Path to Trello JSON export'
    )
    parser.add_argument(
        '--artists-json',
        type=Path,
        default=Path.cwd() / Path('Data') / Path('artists.json'),
        help='Output path for artists JSON'
    )
    args = parser.parse_args()

    with args.trello_json.open('r', encoding='utf-8') as f:
        trello_data = json.load(f)

    artists = extract_artists(trello_data)
    print(f'Extracted {len(artists)} artists, in {len(trello_data["lists"])} lists')
    output = {"artists": artists}

    with args.artists_json.open('w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    main()
