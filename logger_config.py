"""Centralized logging configuration for the YouTube downloader application."""
import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(verbose: bool = False, log_to_file: bool = True) -> None:
    """
    Configure logging for the entire application.

    This should be called once at application startup. All modules using
    logging.getLogger(__name__) will automatically inherit this configuration.

    Args:
        verbose: If True, set log level to DEBUG; otherwise INFO
        log_to_file: If True, also write logs to file in Logs/ directory
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
