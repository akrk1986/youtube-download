#!/usr/bin/env python3
"""
Test Gmail authentication with detailed error reporting.
Run this to diagnose Gmail notification issues.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from git_excluded import GMAIL_PARAMS
except ImportError:
    print('❌ GMAIL_PARAMS not found in git_excluded.py')
    sys.exit(1)

print('Gmail Configuration Check')
print('=' * 60)

# Check configuration
print('\n1. Checking GMAIL_PARAMS structure...')
required_keys = ['sender_email', 'sender_app_password', 'recipient_email']
for key in required_keys:
    value = GMAIL_PARAMS.get(key)
    if not value:
        print(f'   ❌ Missing or empty: {key}')
    else:
        if key == 'sender_app_password':
            print(f'   ✅ {key}: {"*" * len(value)} ({len(value)} characters)')
        else:
            print(f'   ✅ {key}: {value}')

print('\n2. Testing SMTP connection...')
import smtplib
try:
    server = smtplib.SMTP('smtp.gmail.com', 587, timeout=15)
    print('   ✅ Connected to smtp.gmail.com:587')

    server.starttls()
    print('   ✅ STARTTLS successful')

    print('\n3. Testing authentication...')
    print(f'   Using email: {GMAIL_PARAMS["sender_email"]}')
    print(f'   Using password: {"*" * len(GMAIL_PARAMS["sender_app_password"])} ({len(GMAIL_PARAMS["sender_app_password"])} chars)')

    server.login(GMAIL_PARAMS['sender_email'], GMAIL_PARAMS['sender_app_password'])
    print('   ✅ Authentication successful!')

    server.quit()
    print('\n✅ All checks passed!')
    print('\nYour Gmail credentials are correct.')

except smtplib.SMTPAuthenticationError as e:
    print(f'   ❌ Authentication failed: {e}')
    print('\n   Common causes:')
    print('   1. Not using an App Password (regular password won\'t work)')
    print('   2. App Password not generated correctly')
    print('   3. 2-Step Verification not enabled on Google account')
    print('\n   Steps to fix:')
    print('   1. Enable 2-Step Verification: https://myaccount.google.com/security')
    print('   2. Generate App Password: https://myaccount.google.com/apppasswords')
    print('   3. Use the 16-character App Password (not your regular password)')
    sys.exit(1)

except smtplib.SMTPConnectError as e:
    print(f'   ❌ Connection failed: {e}')
    print('   Check your internet connection')
    sys.exit(1)

except Exception as e:
    print(f'   ❌ Unexpected error: {type(e).__name__}: {e}')
    sys.exit(1)
