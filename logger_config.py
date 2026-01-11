"""Centralized logging configuration for the YouTube downloader application."""
import logging
import sys
from pathlib import Path
from datetime import datetime

from project_defs import MAX_LOG_FILES, GLOB_LOG_FILES


def _cleanup_old_logs(log_dir: Path) -> None:
    """
    Remove old log files to keep only the most recent MAX_LOG_FILES.

    Args:
        log_dir: Directory containing log files
    """
    # Get all log files matching our pattern
    log_files = sorted(log_dir.glob(GLOB_LOG_FILES), key=lambda p: p.stat().st_mtime, reverse=True)

    # Keep only the most recent MAX_LOG_FILES - 1 (to make room for the new one)
    files_to_keep = MAX_LOG_FILES - 1

    if len(log_files) >= files_to_keep:
        # Delete older log files
        for old_log in log_files[files_to_keep:]:
            try:
                old_log.unlink()
            except Exception:
                # Silently ignore errors (file might be locked, etc.)
                pass

def setup_logging(verbose: bool = False, log_to_file: bool = True, show_urls: bool = False) -> None:
    """
    Configure logging for the entire application.

    This should be called once at application startup. All modules using
    logging.getLogger(__name__) will automatically inherit this configuration.

    Args:
        verbose: If True, set log level to DEBUG; otherwise INFO
        log_to_file: If True, also write logs to file in Logs/ directory
        show_urls: If True, allow urllib3/requests to log URLs (may expose Slack webhook)
    """
    level = logging.DEBUG if verbose else logging.INFO

    # Create Logs directory if it doesn't exist
    log_dir = Path(__file__).parent / 'Logs'
    log_dir.mkdir(exist_ok=True)

    # Configure formatters
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if enabled)
    if log_to_file:
        # Clean up old log files to maintain MAX_LOG_FILES limit
        _cleanup_old_logs(log_dir)

        log_filename = f'yt-dlp_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        log_path = log_dir / log_filename

        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        root_logger.info(f'Logging to file: {log_path}')

    # Optionally suppress verbose output from third-party libraries
    if not verbose:
        logging.getLogger('yt_dlp').setLevel(logging.WARNING)
        logging.getLogger('mutagen').setLevel(logging.WARNING)

    # SECURITY: Suppress urllib3 and requests logging to prevent Slack webhook URL leaks
    # unless --show-urls flag is explicitly provided
    if not show_urls:
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
