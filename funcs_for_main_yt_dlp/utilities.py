"""Utility functions for main script."""
import socket

import arrow


def format_elapsed_time(seconds: float) -> str:
    """Format elapsed time in seconds to a human-readable string."""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        return f'{hours}h {minutes}m {secs}s'
    elif minutes > 0:
        return f'{minutes}m {secs}s'
    else:
        return f'{secs}s'


def generate_session_id() -> str:
    """Generate a unique session identifier with timestamp and hostname."""
    hostname = socket.gethostname()
    timestamp = arrow.now().format('YYYY-MM-DD HH:mm')
    return f'[{timestamp} {hostname}]'
