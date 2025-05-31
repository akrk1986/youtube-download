"""Artist search utilities for Greek music artists."""

import json
from pathlib import Path
from typing import List, Set, Dict

def load_artists(artists_json_path: Path) -> List[Dict[str, str]]:
    """Load artists from a JSON file."""
    with artists_json_path.open('r', encoding='utf-8') as f:
        data = json.load(f)
    return data['artists']

def find_artists_in_string(text: str, artists: List[Dict[str, str]]) -> str:
    """Return Greek names of artists found in the text ('' if none, 'A1 + A2' if multiple)."""
    found: Set[str] = set()
    lowered_text = text.lower()
    for artist in artists:
        greek = artist['Greek name']
        english = artist['English name']
        if greek and greek.lower() in lowered_text:
            found.add(greek)
        if english and english.lower() in lowered_text:
            found.add(greek)
    if not found:
        return ""
    return ' + '.join(sorted(found))
