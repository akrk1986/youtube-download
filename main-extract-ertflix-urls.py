#!/usr/bin/env python3
"""
Extract VOD URLs from ERTFlix series page.

This script fetches a series page from ertflix.gr and extracts all VOD URLs
matching the pattern: https://www.ertflix.gr/vod/vod.XX-e-aule-ton-khromaton-XX
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List

import requests


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
        print(f"Error fetching URL: {e}", file=sys.stderr)
        raise


def _extract_vod_urls(html_content: str, pattern: str) -> List[str]:
    """
    Extract URLs matching a specific pattern from HTML content.

    Args:
        html_content: The HTML content to search
        pattern: Regular expression pattern to match URLs

    Returns:
        List of unique URLs matching the pattern (order preserved)
    """
    matches = re.findall(pattern, html_content)

    # Remove duplicates while preserving order
    seen = set()
    unique_matches = []
    for match in matches:
        if match not in seen:
            seen.add(match)
            unique_matches.append(match)

    return unique_matches


def _save_urls_to_file(urls: List[str], output_path: Path) -> None:
    """
    Save URLs to a file, one per line.

    Args:
        urls: List of URLs to save
        output_path: Path to the output file
    """
    try:
        with output_path.open('w', encoding='utf-8') as f:
            for url in urls:
                f.write(f"{url}\n")
        print(f"Saved {len(urls)} URLs to {output_path}")
    except IOError as e:
        print(f"Error writing to file: {e}", file=sys.stderr)
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
        '--url',
        type=str,
        default='https://www.ertflix.gr/series/ser.99028-i-ayli-ton-chromaton',
        help='URL of the series page to process'
    )

    parser.add_argument(
        '--pattern',
        type=str,
        default=r'https://www\.ertflix\.gr/vod/vod\.\d+-e-aule-ton-khromaton-\d+',
        help='Regex pattern to match VOD URLs'
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
        help='Request timeout in seconds'
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
        # Fetch page content
        print(f"Fetching page: {args.url}")
        html_content = _fetch_page_content(url=args.url, timeout=args.timeout)

        # Extract URLs
        print(f"Extracting URLs matching pattern...")
        urls = _extract_vod_urls(html_content=html_content, pattern=args.pattern)

        # Display results
        print(f"\nFound {len(urls)} unique URLs:")
        print("-" * 80)
        for i, url in enumerate(urls, 1):
            print(f"{i:3d}. {url}")

        # Save to file if requested
        if args.output:
            _save_urls_to_file(urls=urls, output_path=args.output)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())