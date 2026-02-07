"""Test script to demonstrate the session ID format for Slack notifications."""
import socket
import arrow


def generate_session_id() -> str:
    """Generate a unique session identifier with timestamp and hostname."""
    hostname = socket.gethostname()
    timestamp = arrow.now().format('YYYY-MM-DD HH:mm')
    return f'[{timestamp} {hostname}]'


if __name__ == '__main__':
    session_id = generate_session_id()
    print(f'Session ID format: {session_id}')
    print()
    print('Example Slack message:')
    print('=' * 60)
    print('🚀 Download STARTED')
    print()
    print(f'*Session:* {session_id}')
    print()
    print('*URL:* https://www.youtube.com/watch?v=dQw4w9WgXcQ')
    print()
    print('*Parameters:*')
    print('  • only_audio: True')
    print('  • split_chapters: True')
    print('=' * 60)
