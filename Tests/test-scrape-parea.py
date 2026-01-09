#!/usr/bin/env python3
"""Test script to examine the structure of ERTFlix series pages."""

import re
import requests
from bs4 import BeautifulSoup


def analyze_page(url: str) -> None:
    """Analyze the structure of a series page."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        print(f'Fetching: {url}')
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')

        # Check for <a> tags with vod URLs
        print('\n=== Looking for <a> tags with vod URLs ===')
        vod_pattern = re.compile(r'vod\.\d+')
        found_links = []

        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if vod_pattern.search(href):
                found_links.append(href)
                print(f'Found: {href}')
                print(f'  Text: {link.get_text(strip=True)[:100]}')

        print(f'\nTotal <a> tags with vod URLs: {len(found_links)}')

        # Check for script tags with vod references
        print('\n=== Looking for script tags with vod references ===')
        script_vods = []
        for script in soup.find_all('script'):
            if script.string:
                vods = vod_pattern.findall(script.string)
                if vods:
                    script_vods.extend(vods)
                    print(f'Found {len(vods)} vod references in script tag')

        print(f'\nTotal vod references in scripts: {len(set(script_vods))}')
        print(f'Unique vod IDs: {sorted(set(script_vods))[:10]}...')  # Show first 10

        # Look for JSON data in scripts
        print('\n=== Looking for JSON data structures ===')
        for script in soup.find_all('script'):
            if script.string and ('___INITIAL_STATE___' in script.string or 'window.__' in script.string):
                # Try to find episode/vod data
                if 'episodes' in script.string.lower() or 'vods' in script.string.lower():
                    print('Found script with episode/vod references')
                    # Show a snippet
                    snippet = script.string[:500]
                    print(f'Snippet: {snippet}...')

        # Look for API endpoint patterns in script src URLs
        print('\n=== Analyzing script sources for API patterns ===')
        for script in soup.find_all('script', src=True):
            src = script.get('src', '')
            if 'static' in src or 'main' in src or 'chunk' in src:
                print(f'Found bundled script: {src}')
                # Try to fetch and analyze the bundle
                if src.startswith('/'):
                    bundle_url = f'https://www.ertflix.gr{src}'
                elif src.startswith('http'):
                    bundle_url = src
                else:
                    continue

                try:
                    bundle_response = requests.get(bundle_url, headers=headers, timeout=10)
                    if bundle_response.status_code == 200:
                        bundle_text = bundle_response.text
                        # Look for API endpoint patterns
                        api_patterns = re.findall(r'["\']/(api|v\d+)/[a-zA-Z/]+["\']', bundle_text)
                        if api_patterns:
                            print(f'  API patterns found: {set(api_patterns)[:5]}')
                        # Look for "series" or "episodes" API calls
                        series_apis = re.findall(r'["\'][^"\']*(?:series|episodes|vods)[^"\']*["\']', bundle_text)
                        if series_apis:
                            print(f'  Series/episode API patterns: {set(series_apis)[:5]}')
                except Exception as e:
                    print(f'  Error analyzing bundle: {e}')

    except Exception as e:
        print(f'Error: {e}')


def try_api_endpoints(series_id: str, series_slug: str) -> None:
    """Try different API endpoint patterns to find episode data."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    # Extract numeric ID from series_id (e.g., 'ser.521736-parea-1' -> '521736')
    numeric_id = re.search(r'\d+', series_id).group() if re.search(r'\d+', series_id) else ''

    api_patterns = [
        f'https://api.app.ertflix.gr/api/series/{series_id}',
        f'https://api.app.ertflix.gr/api/v1/series/{series_id}',
        f'https://api.app.ertflix.gr/series/{series_id}',
        f'https://api.app.ertflix.gr/v1/series/{series_id}',
        f'https://api.app.ertflix.gr/api/vod/series/{series_id}',
        f'https://api.app.ertflix.gr/api/series/{numeric_id}',
        f'https://api.app.ertflix.gr/api/v1/series/{numeric_id}',
        f'https://api.app.ertflix.gr/content/series/{series_id}',
        f'https://api.app.ertflix.gr/api/content/{series_id}',
    ]

    print('\n=== Trying API endpoints ===')
    for url in api_patterns:
        try:
            print(f'\nTrying: {url}')
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                print(f'  SUCCESS! Status: {response.status_code}')
                print(f'  Content-Type: {response.headers.get("Content-Type")}')
                try:
                    data = response.json()
                    print(f'  JSON keys: {list(data.keys())[:10]}')
                    # Look for episodes/vods in the response
                    if isinstance(data, dict):
                        for key in ['episodes', 'vods', 'items', 'data', 'results']:
                            if key in data:
                                print(f'  Found "{key}" with {len(data[key])} items')
                except Exception as e:
                    print(f'  Response length: {len(response.text)} chars')
            else:
                print(f'  Status: {response.status_code}')
        except requests.Timeout:
            print(f'  TIMEOUT')
        except Exception as e:
            print(f'  Error: {type(e).__name__}')


if __name__ == '__main__':
    # Test with parea
    print('==' * 40)
    print('Testing: Parea')
    print('==' * 40)
    analyze_page('https://www.ertflix.gr/series/ser.521736-parea-1')

    print('\n')
    print('==' * 40)
    print('API Endpoint Discovery')
    print('==' * 40)
    try_api_endpoints('ser.521736-parea-1', 'parea-1')
