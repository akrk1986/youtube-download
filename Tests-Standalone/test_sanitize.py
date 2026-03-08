#!/usr/bin/env python3
"""Test script for the updated sanitize_string function."""

import sys
sys.path.append('..')

from funcs_utils import sanitize_string

def test_sanitize_string():
    """Test cases for the sanitize_string function."""

    test_cases = [
        # (input, expected_output, description)
        ('Hello 😀 World.txt', 'Hello World.txt', 'Emoji replacement and space compression'),
        ('  Leading spaces.txt', 'Leading spaces.txt', 'Leading spaces removal'),
        ('Multiple    spaces    inside.txt', 'Multiple spaces inside.txt', 'Multiple spaces compression'),
        ('Trailing spaces   .txt', 'Trailing spaces.txt', 'Trailing spaces before extension'),
        ('Café français.txt', 'Café français.txt', 'French characters preserved'),
        ('Türkçe dosya.txt', 'Türkçe dosya.txt', 'Turkish characters preserved'),
        ('İstanbul şehir.txt', 'İstanbul şehir.txt', 'Turkish special characters preserved'),
        ('Αρχείο ελληνικό.txt', 'Αρχείο ελληνικό.txt', 'Greek characters preserved'),
        ('קובץ עברי.txt', 'קובץ עברי.txt', 'Hebrew characters preserved'),
        ('中文文件.txt', 'untitled.txt', 'Chinese characters replaced - empty filename'),
        ('Русский файл.txt', 'untitled.txt', 'Russian characters replaced - empty filename'),
        ('Mix 🎵 café Türkçe Αρχείο קובץ 中文 русский.txt', 'Mix café Türkçe Αρχείο קובץ.txt', 'Mixed characters'),
        ('   😀  Multiple   spaces  🎵  .txt', 'Multiple spaces.txt', 'Complex case'),
        ('filename', 'filename', 'No extension'),
        ('', '', 'Empty string'),
        ('.txt', 'untitled.txt', 'Extension only'),
    ]

    print('Testing sanitize_string function:')
    print('=' * 60)

    for i, (input_str, expected, description) in enumerate(test_cases, 1):
        result = sanitize_string(input_str)
        status = '✅ PASS' if result == expected else '❌ FAIL'
        print(f'Test {i}: {status}')
        print(f'  Description: {description}')
        print(f"  Input:    '{input_str}'")
        print(f"  Expected: '{expected}'")
        print(f"  Result:   '{result}'")
        if result != expected:
            print('  ❌ MISMATCH!')
        print()

if __name__ == '__main__':
    test_sanitize_string()
