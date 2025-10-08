"""Artist search utilities for Greek music artists."""
import json
import re
from pathlib import Path
from funcs_utils import remove_diacritics

def load_artists(artists_json_path: Path) -> list[dict[str, str]]:
    """Load artists from a JSON file."""
    with artists_json_path.open('r', encoding='utf-8') as f:
        data = json.load(f)
    return data['artists']

def _artist_search_variants(full_name: str) -> list[str]:
    """Generate all search variants for a given full name, including last name only."""
    parts = full_name.strip().split()
    variants = set()
    if len(parts) >= 2:
        first, last = parts[0], parts[-1]
        # 1. First-name Last-name
        variants.add(f"{first} {last}")
        # 2. Last-name First-name
        variants.add(f"{last} {first}")
        # 3. F. Last-name and F Last-name
        initial = first[0]
        variants.add(f"{initial}. {last}")
        variants.add(f"{initial} {last}")
        # 4. Last name only
        variants.add(last)
    else:
        # Single name, just use as is
        variants.add(full_name.strip())
    return list(variants)

def find_artists_in_string(text: str, artists: list[dict[str, str]]) -> tuple[int, str]:
    """
    Return (number of unique artists found, 'A1 + A2 + ...') or (0, '') if none.
    Advanced matching: for each artist, look for:
      1. "First-name Last-name"
      2. "Last-name First-name"
      3. "F. Last-name" and "F Last-name"
      4. "Last-name" only
    For both Greek and English names.
    """
    found: set[str] = set()
    # normalize Greek strings by replacing diacritics with base letter
    lowered_text_x = text.lower()
    lowered_text = remove_diacritics(lowered_text_x)
    for artist in artists:
        greek_x = artist['Greek name']
        greek = remove_diacritics(greek_x)
        english = artist['English name']
        # For both Greek and English names, generate all search variants
        for name in filter(None, [greek, english]):
            for variant in _artist_search_variants(name):
                # Use regex for word boundary matching (to avoid partial matches)
                pattern = r'\b' + re.escape(variant) + r'\b'
                if re.search(pattern, lowered_text, flags=re.IGNORECASE):
                    found.add(greek_x)
                    break  # Only need to add once per artist
    if not found:
        return 0, ""
    result = ' + '.join(sorted(found))
    return len(found), result
