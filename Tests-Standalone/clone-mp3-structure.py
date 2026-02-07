#!/usr/bin/env python3
"""
Clone the ID3 structure from a working file to a broken file.
This preserves frame order, encoding patterns, and frame selection while keeping edited content.
"""
import sys
from pathlib import Path
import shutil

sys.path.append('..')

from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.id3 import TIT2, TPE1, TPE2, TALB, TDRC, TRCK, TENC, TSSE, COMM, TXXX, APIC, TCOM
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def clone_structure(template_file: Path, source_file: Path, output_file: Path) -> bool:
    """
    Clone the ID3 structure from template_file, using content from source_file.

    Uses consistent encoding pattern:
    - UTF-16 for main content: TIT2, TPE1, TPE2, TALB, TCOM (title, artist, albumartist, album, composer)
    - LATIN1 for metadata: TDRC, TRCK, TSSE, TXXX, COMM (year, track, software, comments)
    - UTF-16 for TENC (original filename with Turkish/Greek characters)

    Args:
        template_file: The working file with correct structure (e.g., before.mp3)
        source_file: The broken file with edited content (e.g., after-agg.mp3)
        output_file: Where to write the fixed file

    Returns:
        bool: True if successful
    """
    try:
        # Load both files
        template_id3 = ID3(template_file)
        source_id3 = ID3(source_file)

        logger.info(f'Template file: {template_file.name} ({len(template_id3.keys())} frames)')
        logger.info(f'Source file: {source_file.name} ({len(source_id3.keys())} frames)')

        # Copy the source file to output (preserves audio stream)
        shutil.copy2(source_file, output_file)
        logger.info(f'Copied audio stream to: {output_file.name}')

        # Load output file's ID3
        output_id3 = ID3(output_file)

        # Clear all frames from output
        output_id3.clear()
        logger.info('Cleared all ID3 frames from output')

        # Define encoding pattern (matches before.mp3 successful pattern)
        # encoding=1 is UTF-16, encoding=0 is LATIN1
        ENCODING_UTF16 = 1
        ENCODING_LATIN1 = 0

        # Helper function to get text from source or template
        def get_text(frame_id_key):
            if frame_id_key in source_id3 and hasattr(source_id3[frame_id_key], 'text'):
                return source_id3[frame_id_key].text
            elif frame_id_key in template_id3 and hasattr(template_id3[frame_id_key], 'text'):
                return template_id3[frame_id_key].text
            return None

        # Helper function to check if text needs UTF-16 (contains non-Latin1 chars)
        def needs_utf16(text):
            if not text:
                return False
            text_str = str(text[0]) if isinstance(text, list) else str(text)
            try:
                text_str.encode('latin-1')
                return False  # Can encode as Latin1, don't need UTF-16
            except (UnicodeEncodeError, UnicodeDecodeError):
                return True  # Contains non-Latin1 chars, need UTF-16

        # Add frames in template order, then add missing important frames
        processed_frame_types = set()

        # Process frames in template order first
        for frame_id in template_id3.keys():
            template_frame = template_id3[frame_id]
            frame_type = frame_id.split(':')[0]  # Get base frame type (e.g., 'COMM' from 'COMM:xyz')

            # Clone the frame
            if frame_id.startswith('APIC'):
                # For images, prefer source (newer), fallback to template
                if frame_id in source_id3:
                    output_id3.add(source_id3[frame_id])
                else:
                    output_id3.add(template_frame)
                logger.debug(f'Copied image frame: {frame_id}')
                processed_frame_types.add('APIC')

            elif frame_id.startswith('TXXX'):
                # For TXXX frames, auto-detect encoding based on content
                desc = template_frame.desc
                text = get_text(frame_id)
                if text is None:
                    text = template_frame.text if hasattr(template_frame, 'text') else []

                encoding = ENCODING_UTF16 if needs_utf16(text) else ENCODING_LATIN1
                new_frame = TXXX(encoding=encoding, desc=desc, text=text)
                output_id3.add(new_frame)
                enc_name = 'UTF-16' if encoding == ENCODING_UTF16 else 'LATIN1'
                logger.debug(f'Added TXXX frame: {frame_id} (encoding={enc_name})')

            elif frame_id.startswith('COMM') and 'ID3v1 Comment' in frame_id:
                # Only keep the ID3v1 Comment COMM frame, skip others to avoid duplicates
                text = get_text(frame_id)
                if text is None:
                    text = template_frame.text if hasattr(template_frame, 'text') else []

                encoding = ENCODING_UTF16 if needs_utf16(text) else ENCODING_LATIN1
                new_frame = COMM(
                    encoding=encoding,
                    lang='eng',
                    desc='ID3v1 Comment',
                    text=text
                )
                output_id3.add(new_frame)
                enc_name = 'UTF-16' if encoding == ENCODING_UTF16 else 'LATIN1'
                logger.debug(f'Added COMM frame: {frame_id} (encoding={enc_name})')
                processed_frame_types.add('COMM')

            elif frame_id.startswith('COMM') and 'ID3v1 Comment' not in frame_id:
                # Skip other COMM frames to avoid duplicates
                logger.debug(f'Skipped duplicate COMM frame: {frame_id}')
                continue

            elif frame_id == 'TIT2':
                # Title - UTF-16 for Turkish/Greek support
                text = get_text('TIT2') or ['']
                new_frame = TIT2(encoding=ENCODING_UTF16, text=text)
                output_id3.add(new_frame)
                logger.info(f'Added TIT2: {text} (encoding=UTF-16)')
                processed_frame_types.add('TIT2')

            elif frame_id == 'TPE1':
                # Artist - UTF-16 for Turkish/Greek support
                text = get_text('TPE1') or ['']
                new_frame = TPE1(encoding=ENCODING_UTF16, text=text)
                output_id3.add(new_frame)
                logger.info(f'Added TPE1: {text} (encoding=UTF-16)')
                processed_frame_types.add('TPE1')

            elif frame_id == 'TDRC':
                # Date/Year - auto-detect (usually LATIN1 but support UTF-16 if needed)
                text = get_text('TDRC') or ['']
                encoding = ENCODING_UTF16 if needs_utf16(text) else ENCODING_LATIN1
                new_frame = TDRC(encoding=encoding, text=text)
                output_id3.add(new_frame)
                enc_name = 'UTF-16' if encoding == ENCODING_UTF16 else 'LATIN1'
                logger.debug(f'Added TDRC: {text} (encoding={enc_name})')
                processed_frame_types.add('TDRC')

            elif frame_id == 'TENC':
                # Encoded by (original filename) - UTF-16 for Turkish/Greek support
                text = get_text('TENC') or ['']
                new_frame = TENC(encoding=ENCODING_UTF16, text=text)
                output_id3.add(new_frame)
                logger.debug(f'Added TENC (encoding=UTF-16)')
                processed_frame_types.add('TENC')

            elif frame_id == 'TSSE':
                # Software - auto-detect (usually LATIN1 but support UTF-16 if needed)
                text = get_text('TSSE') or template_frame.text if hasattr(template_frame, 'text') else ['']
                encoding = ENCODING_UTF16 if needs_utf16(text) else ENCODING_LATIN1
                new_frame = TSSE(encoding=encoding, text=text)
                output_id3.add(new_frame)
                enc_name = 'UTF-16' if encoding == ENCODING_UTF16 else 'LATIN1'
                logger.debug(f'Added TSSE (encoding={enc_name})')
                processed_frame_types.add('TSSE')

            else:
                # For any other frame, copy from template
                output_id3.add(template_frame)
                logger.debug(f'Copied frame: {frame_id}')
                processed_frame_types.add(frame_type)

        # Now add important frames from source that weren't in template
        # These are the standard music tags
        important_frames = {
            'TALB': (TALB, ENCODING_UTF16, 'Album'),
            'TPE2': (TPE2, ENCODING_UTF16, 'Album Artist'),
            'TRCK': (TRCK, ENCODING_LATIN1, 'Track Number'),
            'TCOM': (TCOM, ENCODING_UTF16, 'Composer')
        }

        for frame_id, (frame_class, encoding, description) in important_frames.items():
            if frame_id not in processed_frame_types and frame_id in source_id3:
                text = get_text(frame_id)
                if text:
                    new_frame = frame_class(encoding=encoding, text=text)
                    output_id3.add(new_frame)
                    encoding_name = 'UTF-16' if encoding == ENCODING_UTF16 else 'LATIN1'
                    logger.info(f'Added {frame_id} ({description}): {text} (encoding={encoding_name})')
                    processed_frame_types.add(frame_id)

        # Save with ID3v2.3 (same as template)
        output_id3.save(output_file, v2_version=3)
        logger.info(f'Saved output file: {output_file.name}')
        logger.info(f'Output has {len(output_id3.keys())} frames in template order')

        return True

    except Exception as e:
        logger.error(f'Error cloning structure: {e}')
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 4:
        print('Usage: python clone-mp3-structure.py <template.mp3> <source.mp3> <output.mp3>')
        print()
        print('Clone ID3 structure from template file while using content from source file.')
        print('This fixes encoding inconsistencies that confuse Android devices.')
        print()
        print('Example:')
        print('  python clone-mp3-structure.py before.mp3 after-agg.mp3 fixed.mp3')
        print()
        print('Arguments:')
        print('  template.mp3 - The working file with correct structure (e.g., before.mp3)')
        print('  source.mp3   - The broken file with your edited content (e.g., after-agg.mp3)')
        print('  output.mp3   - Where to write the fixed file')
        sys.exit(1)

    template_file = Path(sys.argv[1])
    source_file = Path(sys.argv[2])
    output_file = Path(sys.argv[3])

    # Validate inputs
    if not template_file.exists():
        logger.error(f'Template file not found: {template_file}')
        sys.exit(1)

    if not source_file.exists():
        logger.error(f'Source file not found: {source_file}')
        sys.exit(1)

    if output_file.exists():
        response = input(f'Output file {output_file.name} exists. Overwrite? (y/n): ')
        if response.lower() not in ('y', 'yes'):
            logger.info('Aborted')
            sys.exit(0)

    # Clone structure
    logger.info('Starting structure cloning...')
    logger.info('=' * 60)

    if clone_structure(template_file=template_file, source_file=source_file, output_file=output_file):
        logger.info('=' * 60)
        logger.info('SUCCESS! Structure cloned successfully.')
        logger.info(f'Output file: {output_file}')
        logger.info('')
        logger.info('Next steps:')
        logger.info(f'1. Verify: python Tests/compare-mp3-files.py {template_file.name} {output_file.name}')
        logger.info(f'2. Check bytes: python Tests/dump-mp3-bytes.py {output_file.name}')
        logger.info(f'3. Copy {output_file.name} to your Android phone and test!')
    else:
        logger.error('Failed to clone structure')
        sys.exit(1)


if __name__ == '__main__':
    main()
