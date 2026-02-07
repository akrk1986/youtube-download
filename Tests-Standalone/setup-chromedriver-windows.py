#!/usr/bin/env python3
"""Download Windows chromedriver for use with Windows Chrome from WSL."""

import os
import platform
import subprocess
import zipfile
from pathlib import Path

import requests


def get_chrome_version() -> str:
    """Get the installed Chrome version from Windows."""
    chrome_path = '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe'

    if not os.path.exists(chrome_path):
        raise FileNotFoundError('Chrome not found in Windows')

    # Run chrome.exe --version from WSL
    try:
        result = subprocess.run(
            [chrome_path, '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        version_str = result.stdout.strip()
        # Extract version number (e.g., "Google Chrome 120.0.6099.109" -> "120.0.6099.109")
        version = version_str.split()[-1]
        # Get major version (e.g., "120.0.6099.109" -> "120")
        major_version = version.split('.')[0]
        return major_version
    except Exception as e:
        print(f'Error getting Chrome version: {e}')
        return '120'  # Default to recent version


def download_chromedriver(version: str, output_dir: Path) -> Path:
    """Download Windows chromedriver for the specified version."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # ChromeDriver download URL (for Chrome 115+, use Chrome for Testing endpoints)
    # For older versions, use the legacy endpoint
    try:
        major_version = int(version)
    except ValueError:
        major_version = 120

    if major_version >= 115:
        # New Chrome for Testing endpoint
        base_url = 'https://googlechromelabs.github.io/chrome-for-testing'

        # Get the latest version for this major version
        try:
            response = requests.get(f'{base_url}/latest-versions-per-milestone.json', timeout=10)
            response.raise_for_status()
            versions = response.json()

            if str(major_version) in versions['milestones']:
                full_version = versions['milestones'][str(major_version)]['version']
            else:
                print(f'Version {major_version} not found, using latest stable')
                response = requests.get(f'{base_url}/last-known-good-versions.json', timeout=10)
                response.raise_for_status()
                full_version = response.json()['channels']['Stable']['version']

            download_url = f'https://storage.googleapis.com/chrome-for-testing-public/{full_version}/win64/chromedriver-win64.zip'
        except Exception as e:
            print(f'Error fetching version info: {e}')
            # Fallback to a known stable version
            download_url = 'https://storage.googleapis.com/chrome-for-testing-public/120.0.6099.109/win64/chromedriver-win64.zip'
    else:
        # Legacy endpoint for Chrome < 115
        download_url = f'https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{version}'
        try:
            response = requests.get(download_url, timeout=10)
            response.raise_for_status()
            full_version = response.text.strip()
            download_url = f'https://chromedriver.storage.googleapis.com/{full_version}/chromedriver_win32.zip'
        except Exception as e:
            print(f'Error: {e}')
            return None

    print(f'Downloading chromedriver from: {download_url}')

    # Download the zip file
    zip_path = output_dir / 'chromedriver.zip'
    try:
        response = requests.get(download_url, timeout=30, stream=True)
        response.raise_for_status()

        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f'Downloaded to: {zip_path}')

        # Extract chromedriver.exe
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Find chromedriver.exe in the zip
            for file_info in zip_ref.namelist():
                if file_info.endswith('chromedriver.exe'):
                    # Extract just this file
                    chromedriver_path = output_dir / 'chromedriver.exe'
                    with zip_ref.open(file_info) as source, open(chromedriver_path, 'wb') as target:
                        target.write(source.read())
                    print(f'Extracted to: {chromedriver_path}')

                    # Clean up zip file
                    zip_path.unlink()

                    return chromedriver_path

        print('Error: chromedriver.exe not found in downloaded zip')
        return None

    except Exception as e:
        print(f'Error downloading chromedriver: {e}')
        return None


def main():
    """Main function."""
    print('=== Windows ChromeDriver Setup for WSL ===\n')

    # Check if running in WSL
    if 'microsoft' not in platform.uname().release.lower() and 'wsl' not in platform.uname().release.lower():
        print('Warning: This script is designed for WSL environments')

    # Get Chrome version
    print('Detecting Chrome version...')
    chrome_version = get_chrome_version()
    print(f'Chrome version: {chrome_version}\n')

    # Download chromedriver
    output_dir = Path.home() / '.local' / 'bin' / 'chromedriver-windows'
    chromedriver_path = download_chromedriver(version=chrome_version, output_dir=output_dir)

    if chromedriver_path and chromedriver_path.exists():
        print(f'\n✓ Success! ChromeDriver installed at: {chromedriver_path}')
        print(f'\nTo use it, set the environment variable:')
        print(f'export CHROMEDRIVER_PATH="{chromedriver_path}"')
    else:
        print('\n✗ Failed to download chromedriver')
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
