"""
URL extraction utilities for text and ODF files.
"""

import re
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from project_defs import VALID_DOMAINS_ALL


def extract_urls_from_file(file_path: str) -> List[str]:
    """
    Extract all URLs from a text file (.txt) or ODF file (.odt).

    Args:
        file_path: Path to the file to extract URLs from

    Returns:
        List of URLs found in the file

    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If the file format is not supported
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f'File not found: {file_path}')

    # Get file extension (case-insensitive)
    extension = path.suffix.lower()

    if extension == '.txt':
        content = _extract_text_from_txt(file_path=file_path)
    elif extension == '.odt':
        content = _extract_text_from_odt(file_path=file_path)
    else:
        raise ValueError(f'Unsupported file format: {extension}. Only .txt and .odt files are supported.')

    # Extract URLs using regex
    urls = _extract_urls_from_text(text=content)

    return urls


def _extract_text_from_txt(file_path: str) -> str:
    """
    Extract text content from a plain text file.

    Args:
        file_path: Path to the text file

    Returns:
        Text content of the file
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def _extract_text_from_odt(file_path: str) -> str:
    """
    Extract text content from an ODF (.odt) file.

    Args:
        file_path: Path to the ODT file

    Returns:
        Text content of the file
    """
    try:
        from odf import text, teletype  # type: ignore[import-untyped]
        from odf.opendocument import load  # type: ignore[import-untyped]
    except ImportError:
        raise ImportError('odfpy package is required to read .odt files. Install it with: pip install odfpy')

    doc = load(file_path)
    all_text = []

    # Extract all text elements from the document
    for paragraph in doc.getElementsByType(text.P):
        para_text = teletype.extractText(paragraph)
        if para_text:
            all_text.append(para_text)

    return '\n'.join(all_text)


def _extract_urls_from_text(text: str) -> List[str]:
    """
    Extract all URLs from text using regex, filtered by VALID_DOMAINS_ALL.

    Args:
        text: Text content to extract URLs from

    Returns:
        List of URLs found in the text that match valid domains
    """
    # Regex pattern to match URLs
    # Matches http://, https://, and www. URLs
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'

    urls = re.findall(url_pattern, text)

    # Remove trailing punctuation that might have been captured
    cleaned_urls = []
    for url in urls:
        # Remove trailing punctuation like ), ., ,, etc.
        url = url.rstrip('.,;:!?)]}')
        cleaned_urls.append(url)

    # Filter URLs to only include those from valid domains
    valid_urls = []
    for url in cleaned_urls:
        if _is_valid_domain(url=url):
            valid_urls.append(url)

    return valid_urls


def is_valid_domain_url(url: str) -> bool:
    """
    Check if a URL's domain is in VALID_DOMAINS_ALL.

    This function validates that a URL's domain matches one of the valid domains
    defined in project_defs.VALID_DOMAINS_ALL (YouTube, Facebook, ERTFlix, etc.).

    Args:
        url: URL to check

    Returns:
        True if the URL's domain matches one of the valid domains, False otherwise
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Check if the domain matches any valid domain
        for valid_domain in VALID_DOMAINS_ALL:
            if domain == valid_domain or domain.endswith('.' + valid_domain):
                return True

        return False
    except Exception:
        # If URL parsing fails, skip this URL
        return False


def _is_valid_domain(url: str) -> bool:
    """
    Internal wrapper for is_valid_domain_url.

    Args:
        url: URL to check

    Returns:
        True if the URL's domain matches one of the valid domains, False otherwise
    """
    return is_valid_domain_url(url=url)


def print_urls_from_file(file_path: str) -> None:
    """
    Extract and print all URLs from a file.

    Args:
        file_path: Path to the file to extract URLs from
    """
    try:
        urls = extract_urls_from_file(file_path=file_path)

        if not urls:
            print(f'No URLs found in {file_path}')
            return

        print(f'Found {len(urls)} URL(s) in {file_path}:')
        print()
        for i, url in enumerate(urls, 1):
            print(f'{i}. {url}')

    except Exception as e:
        print(f'Error: {e}')
