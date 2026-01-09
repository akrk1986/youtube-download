#!/usr/bin/env python3
"""
Scrape ERTFlix series pages using Selenium to render JavaScript.

This script uses Selenium to load the page, wait for JavaScript to execute,
and then extract the episode URLs that are dynamically loaded.
"""

import argparse
import re
import time
from pathlib import Path
from typing import List, Tuple

# Note: Requires selenium and webdriver-manager
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError as e:
    print(f'Error: Required package not found: {e}')
    print('Install with: pip install selenium webdriver-manager')
    exit(1)


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
    ),
}


def extract_urls_with_selenium(page_url: str, url_pattern: str, wait_seconds: int = 10) -> List[Tuple[str, str]]:
    """
    Extract URLs using Selenium to render JavaScript.

    Args:
        page_url: URL of the series page
        url_pattern: Regex pattern to match URLs
        wait_seconds: Seconds to wait for page to load

    Returns:
        List of tuples (url, text) for matching URLs
    """
    import platform
    import os

    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in background
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    # Check if running in WSL and use Windows Chrome if available
    chromedriver_path = None
    if 'microsoft' in platform.uname().release.lower() or 'wsl' in platform.uname().release.lower():
        windows_chrome = '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe'
        if os.path.exists(windows_chrome):
            chrome_options.binary_location = windows_chrome
            print(f'Using Windows Chrome: {windows_chrome}')

            # Use Windows chromedriver
            default_chromedriver = os.path.expanduser('~/.local/bin/chromedriver-windows/chromedriver.exe')
            if os.path.exists(default_chromedriver):
                chromedriver_path = default_chromedriver
                print(f'Using Windows ChromeDriver: {chromedriver_path}')
            elif 'CHROMEDRIVER_PATH' in os.environ:
                chromedriver_path = os.environ['CHROMEDRIVER_PATH']
                print(f'Using ChromeDriver from env: {chromedriver_path}')

    driver = None
    try:
        # Initialize the driver
        if chromedriver_path and os.path.exists(chromedriver_path):
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # Fall back to automatic driver management
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)

        print(f'Loading page: {page_url}')
        driver.get(page_url)

        # Wait for page to load
        print(f'Waiting {wait_seconds} seconds for JavaScript to execute...')
        time.sleep(wait_seconds)

        # Get all links
        links = driver.find_elements(By.TAG_NAME, 'a')
        print(f'Found {len(links)} total links on page')

        # Filter links matching pattern
        pattern_re = re.compile(url_pattern)
        matched_urls = []
        seen = set()

        for link in links:
            try:
                href = link.get_attribute('href')
                if href and pattern_re.search(href):
                    text = link.text.strip()
                    if href not in seen:
                        seen.add(href)
                        matched_urls.append((href, text))
            except Exception as e:
                # Ignore stale elements
                continue

        return matched_urls

    finally:
        if driver:
            driver.quit()


def save_urls_to_file(urls: List[Tuple[str, str]], output_path: Path) -> None:
    """Save URLs and their text to a file."""
    with output_path.open('w', encoding='utf-8') as f:
        for url, text in urls:
            if text:
                f.write(f'{url}\t{text}\n')
            else:
                f.write(f'{url}\n')
    print(f'Saved {len(urls)} URLs to {output_path}')


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Extract VOD URLs from ERTFlix series page using Selenium',
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
        '--wait',
        type=int,
        default=10,
        help='Seconds to wait for page to load (default: %(default)s)'
    )

    return parser.parse_args()


def main() -> int:
    """Main function."""
    args = parse_arguments()

    # Determine URL and pattern
    if args.program:
        page_url, url_pattern = PROGRAM_CONFIGS[args.program]
        if args.url:
            page_url = args.url
        if args.pattern:
            url_pattern = args.pattern
    else:
        if not args.url or not args.pattern:
            print('Error: Either --program or both --url and --pattern must be provided')
            return 1
        page_url = args.url
        url_pattern = args.pattern

    try:
        print(f'Pattern: {url_pattern}\n')

        # Extract URLs
        urls = extract_urls_with_selenium(
            page_url=page_url,
            url_pattern=url_pattern,
            wait_seconds=args.wait
        )

        # Display results
        print(f'\nFound {len(urls)} unique matching URLs:')
        print('-' * 100)
        for i, (url, text) in enumerate(urls, 1):
            if text:
                print(f'{i:3d}. {url}')
                print(f'     Text: {text}')
            else:
                print(f'{i:3d}. {url}')

        # Save to file if requested
        if args.output:
            save_urls_to_file(urls=urls, output_path=args.output)

        return 0

    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
