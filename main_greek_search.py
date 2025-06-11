import unicodedata

def remove_diacritics(text: str) -> str:
    """
    Remove diacritics from Greek text by normalizing to NFD form
    and filtering out combining characters (diacritical marks).
    """
    # Normalize to NFD (decomposed form)
    normalized = unicodedata.normalize('NFD', text)
    # Filter out combining characters (diacritics)
    without_diacritics = ''.join(
        char for char in normalized 
        if unicodedata.category(char) != 'Mn'
    )
    return without_diacritics

def greek_search(big_string: str, sub_string: str) -> bool:
    """
    Check if sub_string appears in big_string, ignoring Greek diacritics.
    
    Args:
        big_string (str): The string to search in
        sub_string (str): The string to search for
    
    Returns:
        bool: True if sub_string is found in big_string (ignoring diacritics), False otherwise
    """
    # Remove diacritics from both strings
    big_string_clean = remove_diacritics(text=big_string)
    sub_string_clean = remove_diacritics(text=sub_string)
    
    # Convert to lowercase for case-insensitive search
    big_string_clean = big_string_clean.lower()
    sub_string_clean = sub_string_clean.lower()
    
    # Check if sub_string appears in big_string
    return sub_string_clean in big_string_clean

# Example usage and test cases
if __name__ == "__main__":
    # Test cases
    test_cases = [
        # Greek with diacritics
        ("καλημέρα", "καλη", True),  # "good morning" contains "good"
        ("φιλοσοφία", "σοφ", True),   # "philosophy" contains "sof"
        ("άνθρωπος", "ανθρωπ", True), # "human" with/without diacritics
        ("γεια σου", "σας", False),   # "hello you" doesn't contain "you (formal)"
        ("ἀρχαῖος", "αρχαι", True),  # ancient Greek with multiple diacritics
        ("κόσμος", "κοσμ", True),     # "world" contains "cosm"
        
        # Greek without diacritics
        ("καλημερα", "καλη", True),   # no diacritics in A
        ("φιλοσοφια", "σοφ", True),   # no diacritics in A
        ("ανθρωπος", "άνθρωπ", True), # no diacritics in A, diacritics in B
        
        # English text
        ("Hello world", "world", True),     # English A and B
        ("Hello world", "World", True),     # case insensitive
        ("Programming", "gram", True),      # English substring
        ("Python code", "java", False),     # English no match
        
        # Mixed Greek and English
        ("Hello κόσμος", "κοσμ", True),     # English + Greek
        ("καλημέρα world", "world", True),  # Greek + English
        ("Test άνθρωπος", "ανθρωπ", True),  # Mixed with diacritics
        
        # Empty strings and edge cases
        ("", "", True),                     # both empty
        ("test", "", True),                 # empty search string
        ("", "test", False),                # empty text
    ]
    
    print("Testing Greek search function:")
    for big_string, sub_string, expected in test_cases:
        result = greek_search(big_string=big_string, sub_string=sub_string)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{big_string}' contains '{sub_string}': {result} (expected: {expected})")
