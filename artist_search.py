"""Artist search utilities for Greek music artists."""

import json
from pathlib import Path
from typing import List, Set, Dict

def load_artists(artists_json_path: Path) -> List[Dict[str, str]]:
    """Load artists from a JSON file."""
    with artists_json_path.open('r', encoding='utf-8') as f:
        data = json.load(f)
    return data['artists']

def find_artists_in_string(text: str, artists: list[dict]) -> tuple[int, str]:
    """Return (number of unique artists found, 'A1 + A2 + ...') or (0, '') if none."""
    found: set[str] = set()
    lowered_text = text.lower()
    for artist in artists:
        greek = artist['Greek name']
        english = artist['English name']
        # Check for Greek name
        if greek and greek.lower() in lowered_text:
            found.add(greek)
        # Check for English name
        if english and english.lower() in lowered_text:
            found.add(greek)
    if not found:
        return 0, ""
    result = ' + '.join(sorted(found))
    return len(found), result

