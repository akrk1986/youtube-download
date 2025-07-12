"""Test program to search strings ignoring Greek diacritics."""

from greek_substr_search import greek_search

# Example usage and test cases
if __name__ == "__main__":
    # Test cases
    test_cases = [
        # Greek with diacritics
        ("καλημέρα", "καλη", True),   # "good morning" contains "good"
        ("φιλοσοφία", "σοφ", True),   # "philosophy" contains "sof"
        ("άνθρωπος", "ανθρωπ", True), # "human" with/without diacritics
        ("γεια σου", "σας", False),   # "hello you" doesn't contain "you (formal)"
        ("ἀρχαῖος", "αρχαι", True),    # ancient Greek with multiple diacritics
        ("κόσμος", "κοσμ", True),     # "world" contains "cosm"
        
        # Greek without diacritics
        ("καλημερα", "καλη", True),   # no diacritics in A
        ("φιλοσοφια", "σοφ", True),   # no diacritics in A
        ("ανθρωπος", "άνθρωπ", True), # no diacritics in A, diacritics in B
        
        # English text
        ("Hello world", "world", True),     # English A and B
        ("Hello world", "World", True),     # case-insensitive
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
