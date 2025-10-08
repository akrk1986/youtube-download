#!/usr/bin/env python3
"""
Test security measures for subprocess calls.
Tests URL sanitization and path validation without testing timeouts.
"""
import sys
import pytest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from funcs_utils import sanitize_url_for_subprocess, validate_file_path_security


class TestURLSanitization:
    """Test URL sanitization for subprocess calls."""

    def test_valid_youtube_url(self):
        """Valid YouTube URLs should pass through unchanged."""
        valid_urls = [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://youtu.be/dQw4w9WgXcQ',
            'https://www.youtube.com/playlist?list=PLRXnwzqAlx1NehOIsFdwtVbsZ0Orf71cE',
            'https://m.youtube.com/watch?v=dQw4w9WgXcQ',
            # URLs with ampersands in query strings (common in YouTube URLs)
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s',
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLxxx&index=5',
        ]
        for url in valid_urls:
            result = sanitize_url_for_subprocess(url)
            assert result == url, f'Valid URL was modified: {url}'

    def test_url_with_pipe_character(self):
        """URLs with pipe character should be rejected (shell metacharacter)."""
        url = 'https://www.youtube.com/watch?v=test|rm -rf /'
        with pytest.raises(ValueError, match='suspicious shell metacharacters'):
            sanitize_url_for_subprocess(url)

    def test_url_with_semicolon(self):
        """URLs with semicolon should be rejected (shell metacharacter)."""
        url = 'https://www.youtube.com/watch?v=test;whoami'
        with pytest.raises(ValueError, match='suspicious shell metacharacters'):
            sanitize_url_for_subprocess(url)

    def test_url_with_dollar_sign(self):
        """URLs with dollar sign should be rejected (shell metacharacter)."""
        url = 'https://www.youtube.com/watch?v=$PATH'
        with pytest.raises(ValueError, match='suspicious shell metacharacters'):
            sanitize_url_for_subprocess(url)

    def test_url_with_backtick(self):
        """URLs with backtick should be rejected (shell metacharacter)."""
        url = 'https://www.youtube.com/watch?v=`whoami`'
        with pytest.raises(ValueError, match='suspicious shell metacharacters'):
            sanitize_url_for_subprocess(url)

    def test_url_with_newline(self):
        """URLs with newline should be rejected (shell metacharacter)."""
        url = 'https://www.youtube.com/watch?v=test\nwhoami'
        with pytest.raises(ValueError, match='suspicious shell metacharacters'):
            sanitize_url_for_subprocess(url)

    def test_url_with_carriage_return(self):
        """URLs with carriage return should be rejected (shell metacharacter)."""
        url = 'https://www.youtube.com/watch?v=test\rwhoami'
        with pytest.raises(ValueError, match='suspicious shell metacharacters'):
            sanitize_url_for_subprocess(url)

    def test_url_with_less_than(self):
        """URLs with < should be rejected (shell metacharacter)."""
        url = 'https://www.youtube.com/watch?v=<script>'
        with pytest.raises(ValueError, match='suspicious shell metacharacters'):
            sanitize_url_for_subprocess(url)

    def test_url_with_greater_than(self):
        """URLs with > should be rejected (shell metacharacter)."""
        url = 'https://www.youtube.com/watch?v=>output.txt'
        with pytest.raises(ValueError, match='suspicious shell metacharacters'):
            sanitize_url_for_subprocess(url)

    def test_command_injection_attempt(self):
        """Command injection attempts should be blocked."""
        malicious_urls = [
            'https://youtube.com/test$(whoami)',
            'https://youtube.com/test`id`',
            'https://youtube.com/test|cat /etc/passwd',
            'https://youtube.com/test;ls -la',
        ]
        for url in malicious_urls:
            with pytest.raises(ValueError, match='suspicious shell metacharacters'):
                sanitize_url_for_subprocess(url)


class TestPathValidation:
    """Test path validation for subprocess calls."""

    def test_valid_absolute_path(self, tmp_path):
        """Valid absolute paths should not raise errors."""
        test_file = tmp_path / 'test.mp3'
        test_file.touch()
        # Should not raise
        validate_file_path_security(test_file)

    def test_valid_relative_path(self, tmp_path):
        """Valid relative paths should not raise errors."""
        test_file = tmp_path / 'test.mp3'
        test_file.touch()
        # Should not raise (will be resolved to absolute)
        validate_file_path_security(test_file)

    def test_path_traversal_attempt(self, tmp_path):
        """Path traversal attempts using .. should be caught."""
        # Create a directory structure
        parent_dir = tmp_path / 'parent'
        child_dir = parent_dir / 'child'
        child_dir.mkdir(parents=True)

        # Try to access parent from child using ..
        traversal_path = child_dir / '..' / '..' / 'etc' / 'passwd'

        # This should work without expected_parent (just validates path can be resolved)
        # But let's test with expected_parent
        with pytest.raises(ValueError, match='outside expected directory'):
            validate_file_path_security(traversal_path, expected_parent=child_dir)

    def test_path_within_expected_directory(self, tmp_path):
        """Paths within expected directory should be allowed."""
        parent_dir = tmp_path / 'parent'
        parent_dir.mkdir()
        child_file = parent_dir / 'file.mp3'
        child_file.touch()

        # Should not raise
        validate_file_path_security(child_file, expected_parent=parent_dir)

    def test_path_outside_expected_directory(self, tmp_path):
        """Paths outside expected directory should be rejected."""
        dir1 = tmp_path / 'dir1'
        dir2 = tmp_path / 'dir2'
        dir1.mkdir()
        dir2.mkdir()

        file_in_dir2 = dir2 / 'file.mp3'
        file_in_dir2.touch()

        # File is in dir2, but we expect it in dir1
        with pytest.raises(ValueError, match='outside expected directory'):
            validate_file_path_security(file_in_dir2, expected_parent=dir1)

    def test_nonexistent_path(self, tmp_path):
        """Nonexistent paths should not raise if within expected directory."""
        parent_dir = tmp_path / 'parent'
        parent_dir.mkdir()
        nonexistent = parent_dir / 'does_not_exist.mp3'

        # Should not raise - we're just validating structure, not existence
        validate_file_path_security(nonexistent, expected_parent=parent_dir)

    def test_symlink_traversal_attempt(self, tmp_path):
        """Symlinks that escape expected directory should be caught."""
        import platform

        # Skip on Windows if symlink creation fails
        if platform.system() == 'Windows':
            pytest.skip('Symlink test may require admin privileges on Windows')

        parent_dir = tmp_path / 'parent'
        parent_dir.mkdir()

        outside_dir = tmp_path / 'outside'
        outside_dir.mkdir()
        outside_file = outside_dir / 'secret.txt'
        outside_file.write_text('secret')

        try:
            # Create symlink inside parent that points outside
            link_path = parent_dir / 'link_to_outside'
            link_path.symlink_to(outside_file)

            # This should be caught because resolved path is outside parent_dir
            with pytest.raises(ValueError, match='outside expected directory'):
                validate_file_path_security(link_path, expected_parent=parent_dir)
        except OSError:
            pytest.skip('Cannot create symlinks on this system')


class TestShellMetacharactersCompatibility:
    """Test that shell metacharacters are properly blocked on both Windows and Linux."""

    def test_all_blocked_metacharacters(self):
        """Verify all shell metacharacters are blocked regardless of OS."""
        import platform

        # These characters should be blocked on ALL platforms
        dangerous_chars = {
            '|': 'pipe (command chaining)',
            ';': 'semicolon (command separator)',
            '$': 'dollar (variable expansion)',
            '`': 'backtick (command substitution)',
            '\n': 'newline (command separator)',
            '\r': 'carriage return (command separator)',
            '<': 'less-than (input redirection)',
            '>': 'greater-than (output redirection)',
        }

        current_os = platform.system()
        print(f'\nTesting on {current_os}')

        for char, description in dangerous_chars.items():
            url = f'https://youtube.com/test{char}malicious'
            with pytest.raises(ValueError, match='suspicious shell metacharacters'):
                sanitize_url_for_subprocess(url)
            print(f'  ✓ Blocked {description}: {repr(char)}')

    def test_ampersand_allowed(self):
        """Test that ampersand is allowed (safe with subprocess list format)."""
        import platform

        # Ampersand is ALLOWED because:
        # - We use subprocess list format (not shell=True)
        # - It's common in YouTube URLs for query parameters
        # - With list format, & is just a regular character in the argument
        urls_with_ampersand = [
            'https://youtube.com/watch?v=xxx&t=10s',
            'https://youtube.com/watch?v=xxx&list=yyy&index=5',
        ]

        current_os = platform.system()
        print(f'\nTesting ampersand on {current_os}')

        for url in urls_with_ampersand:
            result = sanitize_url_for_subprocess(url)
            assert result == url
        print(f'  ✓ Ampersand correctly allowed on {current_os} (safe with list format)')


if __name__ == '__main__':
    # Run tests with verbose output
    import subprocess
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', __file__, '-v', '-s'],
        capture_output=False
    )
    sys.exit(result.returncode)
