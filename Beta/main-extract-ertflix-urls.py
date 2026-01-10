#!/usr/bin/env python3
"""
Extract VOD URLs from ERTFlix series page.

This script fetches a series page from ertflix.gr and extracts all VOD URLs
matching a specified pattern, along with their associated link text.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup


# Program configurations: (main_page_url, url_pattern)
PROGRAM_CONFIGS = {
    'nykhta': (
        'https://www.ertflix.gr/en/series/ser.27883-nykhta-stasou',
        r'https://www\.ertflix\.gr/en/vod/vod\.\d+-nukhta-stasou-\d+'
    ),
    'chromaton': (
        'https://www.ertflix.gr/series/ser.99028-i-ayli-ton-chromaton',
        r'https://www\.ertflix\.gr/vod/vod\.\d+-e-aule-ton-khromaton-\d+'
    ),
    'parea': (
        'https://www.ertflix.gr/series/ser.521736-parea-1',
        r'https://www\.ertflix\.gr/vod/vod\.\d+-parea-\d+'
        #'https://www.ertflix.gr/vod/vod.578113-parea-19'
    ),

}


def _fetch_page_content(url: str, timeout: int = 30) -> str:
    """
    Fetch the HTML content of a web page.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds

    Returns:
        The HTML content as a string

    Raises:
        requests.RequestException: If the request fails
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f'Error fetching URL: {e}', file=sys.stderr)
        raise


def _extract_vod_urls(html_content: str, pattern: str) -> List[Tuple[str, str]]:
    """
    Extract URLs matching a specific pattern from HTML content along with their link text.

    Args:
        html_content: The HTML content to search
        pattern: Regular expression pattern to match URLs

    Returns:
        List of tuples (url, text) for unique URLs matching the pattern (order preserved)
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    pattern_re = re.compile(pattern)

    # Remove duplicates while preserving order
    seen = set()
    unique_matches = []

    # Find all <a> tags
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')

        # Check if href matches the pattern
        if pattern_re.search(href):
            # Extract text, excluding image tags
            text_parts = []
            for content in link.contents:
                # Skip img tags and other non-text elements
                if hasattr(content, 'name') and content.name == 'img':
                    continue
                # Get text content
                if hasattr(content, 'get_text'):
                    text_parts.append(content.get_text(strip=True))
                elif isinstance(content, str):
                    text_parts.append(content.strip())

            link_text = ' '.join(text_parts).strip()

            # Add to results if not seen before
            if href not in seen:
                seen.add(href)
                unique_matches.append((href, link_text))

    return unique_matches


def _save_urls_to_file(urls: List[Tuple[str, str]], output_path: Path) -> None:
    """
    Save URLs and their text to a file.

    Args:
        urls: List of tuples (url, text) to save
        output_path: Path to the output file
    """
    try:
        with output_path.open('w', encoding='utf-8') as f:
            for url, text in urls:
                if text:
                    f.write(f'{url}\t{text}\n')
                else:
                    f.write(f'{url}\n')
        print(f'Saved {len(urls)} URLs to {output_path}')
    except IOError as e:
        print(f'Error writing to file: {e}', file=sys.stderr)
        raise


def _parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Extract VOD URLs from ERTFlix series page',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        '--program',
        type=str,
        choices=list(PROGRAM_CONFIGS.keys()),
        help=f'Program name (available: {", ".join(PROGRAM_CONFIGS.keys())})'
    )

    parser.add_argument(
        '--url',
        type=str,
        help='URL of the series page to process (overrides --program)'
    )

    parser.add_argument(
        '--pattern',
        type=str,
        help='Regex pattern to match VOD URLs (overrides --program)'
    )

    parser.add_argument(
        '--output',
        type=Path,
        help='Output file to save URLs (optional)'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='Request timeout in seconds (default: %(default)s)'
    )

    return parser.parse_args()


def main() -> int:
    """
    Main function to extract and display/save VOD URLs.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    args = _parse_arguments()

    try:
        # Determine URL and pattern based on program or explicit arguments
        if args.program:
            page_url, url_pattern = PROGRAM_CONFIGS[args.program]
            # Allow explicit overrides
            if args.url:
                page_url = args.url
            if args.pattern:
                url_pattern = args.pattern
        else:
            # Both url and pattern must be provided if program is not specified
            if not args.url or not args.pattern:
                print('Error: Either --program or both --url and --pattern must be provided', file=sys.stderr)
                return 1
            page_url = args.url
            url_pattern = args.pattern

        # Fetch page content
        print(f'Fetching page: {page_url}')
        html_content = _fetch_page_content(url=page_url, timeout=args.timeout)

        # Extract URLs
        print(f'Extracting URLs matching pattern...')
        print(f'Pattern: {url_pattern}')
        print()
        urls = _extract_vod_urls(html_content=html_content, pattern=url_pattern)

        # Display results
        print(f'Found {len(urls)} unique URLs:')
        print('-' * 100)
        for i, (url, text) in enumerate(urls, 1):
            if text:
                print(f'{i:3d}. {url}')
                print(f'     Text: {text}')
            else:
                print(f'{i:3d}. {url}')

        # Save to file if requested
        if args.output:
            _save_urls_to_file(urls=urls, output_path=args.output)

        return 0

    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())