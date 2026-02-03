"""Security helper functions for subprocess calls."""
from pathlib import Path


def sanitize_url_for_subprocess(url: str) -> str:
    """
    Sanitize URL before passing to subprocess (defense in depth).
    Even though we use list format (not shell=True), we validate
    that URLs don't contain shell metacharacters as an extra safety measure.

    Note: Ampersand (&) is NOT blocked because:
    - It's commonly used in YouTube URLs for query parameters (?v=xxx&t=10s)
    - With subprocess list format (not shell=True), & is just a regular character
    - It does NOT enable command chaining when using subprocess.run([cmd, arg1, arg2])

    Args:
        url: The URL to sanitize

    Returns:
        The original URL if safe

    Raises:
        ValueError: If URL contains suspicious characters
    """
    # Shell metacharacters that should never appear in a URL
    # Note: & is intentionally excluded - it's safe with list format and common in URLs
    shell_metacharacters = {'|', ';', '$', '`', '\n', '\r', '<', '>'}

    if any(char in url for char in shell_metacharacters):
        raise ValueError(f'URL contains suspicious shell metacharacters: {url}')

    return url


def validate_file_path_security(file_path: Path, expected_parent: Path | None = None) -> None:
    """
    Validate that a file path is safe to use in subprocess calls.
    Checks for path traversal attempts and ensures path is within expected directory.

    Args:
        file_path: Path to validate
        expected_parent: Optional parent directory that file_path should be within

    Raises:
        ValueError: If path is suspicious or outside expected parent
    """
    try:
        # Resolve to absolute path to detect '..' traversal
        resolved_path = file_path.resolve()

        # If expected parent provided, ensure file is within it
        if expected_parent:
            expected_parent_resolved = expected_parent.resolve()
            if not str(resolved_path).startswith(str(expected_parent_resolved)):
                raise ValueError(f'Path {file_path} is outside expected directory {expected_parent}')

    except (OSError, RuntimeError) as e:
        raise ValueError(f'Invalid or suspicious file path {file_path}: {e}')
