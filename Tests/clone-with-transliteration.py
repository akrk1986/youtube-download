#!/usr/bin/env python3
"""
Clone MP3 structure with smart Turkish transliteration.
- Preserves UTF-16 Turkish text in critical fields (TIT2, TPE1, TENC)
- Transliterates Turkish to ASCII in other fields (TALB, TPE2, TCOM) to avoid Android UTF-16 limit
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


def transliterate_turkish(text: str) -> str:
    """
    Transliterate Turkish characters to ASCII equivalents.

    Turkish characters:
    ç → c, ğ → g, ı → i, İ → I, ö → o, ş → s, ü → u
    Ç → C, Ğ → G, Ö → O, Ş → S, Ü → U

    Also handles Greek characters commonly mixed with Turkish.
    """
    # Turkish character mappings
    turkish_map = {
        'ç': 'c', 'Ç': 'C',
        'ğ': 'g', 'Ğ': 'G',
        'ı': 'i', 'İ': 'I',
        'ö': 'o', 'Ö': 'O',
        'ş': 's', 'Ş': 'S',
        'ü': 'u', 'Ü': 'U',
    }

    # Greek character mappings (common ones + accented variants)
    greek_map = {
        'α': 'a', 'Α': 'A', 'ά': 'a', 'Ά': 'A',
        'β': 'b', 'Β': 'B',
        'γ': 'g', 'Γ': 'G',
        'δ': 'd', 'Δ': 'D',
        'ε': 'e', 'Ε': 'E', 'έ': 'e', 'Έ': 'E',
        'ζ': 'z', 'Ζ': 'Z',
        'η': 'i', 'Η': 'I', 'ή': 'i', 'Ή': 'I',
        'θ': 'th', 'Θ': 'Th',
        'ι': 'i', 'Ι': 'I', 'ί': 'i', 'Ί': 'I', 'ϊ': 'i', 'ΐ': 'i',
        'κ': 'k', 'Κ': 'K',
        'λ': 'l', 'Λ': 'L',
        'μ': 'm', 'Μ': 'M',
        'ν': 'n', 'Ν': 'N',
        'ξ': 'x', 'Ξ': 'X',
        'ο': 'o', 'Ο': 'O', 'ό': 'o', 'Ό': 'O',
        'π': 'p', 'Π': 'P',
        'ρ': 'r', 'Ρ': 'R',
        'σ': 's', 'ς': 's', 'Σ': 'S',
        'τ': 't', 'Τ': 'T',
        'υ': 'y', 'Υ': 'Y', 'ύ': 'y', 'Ύ': 'Y', 'ϋ': 'y', 'ΰ': 'y',
        'φ': 'f', 'Φ': 'F',
        'χ': 'ch', 'Χ': 'Ch',
        'ψ': 'ps', 'Ψ': 'Ps',
        'ω': 'o', 'Ω': 'O', 'ώ': 'o', 'Ώ': 'O',
    }

    result = []
    for char in text:
        if char in turkish_map:
            result.append(turkish_map[char])
        elif char in greek_map:
            result.append(greek_map[char])
        else:
            result.append(char)

    return ''.join(result)


def clone_with_transliteration(template_file: Path, source_file: Path, output_file: Path) -> bool:
    """
    Clone structure with smart transliteration to work around Android UTF-16 limits.

    Strategy:
    - UTF-16 for critical fields: TIT2 (title), TPE1 (artist), TENC (original filename)
    - LATIN1 with transliteration for: TALB, TPE2, TCOM (album, albumartist, composer)
    - LATIN1 for metadata: TDRC, TRCK, TSSE, TXXX, COMM
    """
    try:
        template_id3 = ID3(template_file)
        source_id3 = ID3(source_file)

        logger.info(f'Template: {template_file.name} ({len(template_id3.keys())} frames)')
        logger.info(f'Source: {source_file.name} ({len(source_id3.keys())} frames)')

        # Copy audio stream
        shutil.copy2(source_file, output_file)
        output_id3 = ID3(output_file)
        output_id3.clear()

        ENCODING_UTF16 = 1
        ENCODING_LATIN1 = 0

        def get_text(frame_id_key):
            if frame_id_key in source_id3 and hasattr(source_id3[frame_id_key], 'text'):
                return source_id3[frame_id_key].text
            elif frame_id_key in template_id3 and hasattr(template_id3[frame_id_key], 'text'):
                return template_id3[frame_id_key].text
            return None

        def transliterate_text_list(text_list):
            """Transliterate a text list (as used in mutagen frames)."""
            if not text_list:
                return text_list
            return [transliterate_turkish(str(t)) for t in text_list]

        processed_frames = set()

        # Process frames in template order
        for frame_id in template_id3.keys():
            template_frame = template_id3[frame_id]

            if frame_id.startswith('APIC'):
                # Images - copy as-is
                if frame_id in source_id3:
                    output_id3.add(source_id3[frame_id])
                else:
                    output_id3.add(template_frame)
                logger.debug(f'Copied image: {frame_id}')
                processed_frames.add('APIC')

            elif frame_id.startswith('TXXX'):
                # TXXX frames - transliterate and use LATIN1
                desc = template_frame.desc
                text = get_text(frame_id)
                if text is None:
                    text = template_frame.text if hasattr(template_frame, 'text') else []

                # Transliterate
                text = transliterate_text_list(text)
                new_frame = TXXX(encoding=ENCODING_LATIN1, desc=desc, text=text)
                output_id3.add(new_frame)
                logger.debug(f'Added TXXX: {frame_id} (LATIN1, transliterated)')

            elif frame_id.startswith('COMM'):
                # COMM frames - transliterate and use LATIN1
                if 'ID3v1 Comment' in frame_id:
                    text = get_text(frame_id)
                    if text is None:
                        text = template_frame.text if hasattr(template_frame, 'text') else []

                    text = transliterate_text_list(text)
                    new_frame = COMM(encoding=ENCODING_LATIN1, lang='eng', desc='ID3v1 Comment', text=text)
                    output_id3.add(new_frame)
                    logger.debug(f'Added COMM: {frame_id} (LATIN1, transliterated)')
                    processed_frames.add('COMM')
                else:
                    # Skip duplicate COMM frames
                    logger.debug(f'Skipped duplicate COMM: {frame_id}')

            elif frame_id == 'TIT2':
                # Title - KEEP UTF-16 for both Turkish and Greek (matches before.mp3 pattern)
                text = get_text('TIT2') or ['']
                new_frame = TIT2(encoding=ENCODING_UTF16, text=text)
                output_id3.add(new_frame)
                logger.info(f'Added TIT2: {text} (UTF-16, preserved)')
                processed_frames.add('TIT2')

            elif frame_id == 'TPE1':
                # Artist - KEEP UTF-16 for Turkish
                text = get_text('TPE1') or ['']
                new_frame = TPE1(encoding=ENCODING_UTF16, text=text)
                output_id3.add(new_frame)
                logger.info(f'Added TPE1: {text} (UTF-16, preserved)')
                processed_frames.add('TPE1')

            elif frame_id == 'TENC':
                # Original filename - KEEP UTF-16 for Turkish
                text = get_text('TENC') or ['']
                new_frame = TENC(encoding=ENCODING_UTF16, text=text)
                output_id3.add(new_frame)
                logger.debug(f'Added TENC (UTF-16, preserved)')
                processed_frames.add('TENC')

            elif frame_id == 'TDRC':
                # Year - LATIN1 (numbers only)
                text = get_text('TDRC') or ['']
                new_frame = TDRC(encoding=ENCODING_LATIN1, text=text)
                output_id3.add(new_frame)
                logger.debug(f'Added TDRC: {text} (LATIN1)')
                processed_frames.add('TDRC')

            elif frame_id == 'TSSE':
                # Software - LATIN1
                text = get_text('TSSE') or template_frame.text if hasattr(template_frame, 'text') else ['']
                new_frame = TSSE(encoding=ENCODING_LATIN1, text=text)
                output_id3.add(new_frame)
                logger.debug(f'Added TSSE (LATIN1)')
                processed_frames.add('TSSE')

            else:
                # Copy other frames as-is
                output_id3.add(template_frame)
                logger.debug(f'Copied frame: {frame_id}')
                processed_frames.add(frame_id.split(':')[0])

        # Add extra frames from source (TALB, TPE2, TRCK, TCOM) with transliteration
        extra_frames = {
            'TALB': (TALB, 'Album'),
            'TPE2': (TPE2, 'Album Artist'),
            'TCOM': (TCOM, 'Composer'),
            'TRCK': (TRCK, 'Track')
        }

        for frame_id, (frame_class, description) in extra_frames.items():
            if frame_id not in processed_frames and frame_id in source_id3:
                text = get_text(frame_id)
                if text:
                    # Transliterate Turkish/Greek to ASCII
                    text_transliterated = transliterate_text_list(text)
                    new_frame = frame_class(encoding=ENCODING_LATIN1, text=text_transliterated)
                    output_id3.add(new_frame)
                    logger.info(f'Added {frame_id} ({description}): {text} → {text_transliterated} (LATIN1, transliterated)')
                    processed_frames.add(frame_id)

        # Save
        output_id3.save(output_file, v2_version=3)
        logger.info(f'Saved: {output_file.name} with {len(output_id3.keys())} frames')

        return True

    except Exception as e:
        logger.error(f'Error: {e}')
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 4:
        print('Usage: python clone-with-transliteration.py <template.mp3> <source.mp3> <output.mp3>')
        print()
        print('Clone structure with Turkish transliteration for Android compatibility.')
        print('- UTF-16 preserved: Title, Artist, Original Filename')
        print('- Transliterated to ASCII: Album, Album Artist, Composer')
        sys.exit(1)

    template_file = Path(sys.argv[1])
    source_file = Path(sys.argv[2])
    output_file = Path(sys.argv[3])

    if not template_file.exists():
        logger.error(f'Template not found: {template_file}')
        sys.exit(1)

    if not source_file.exists():
        logger.error(f'Source not found: {source_file}')
        sys.exit(1)

    if output_file.exists():
        response = input(f'{output_file.name} exists. Overwrite? (y/n): ')
        if response.lower() not in ('y', 'yes'):
            sys.exit(0)

    logger.info('Creating MP3 with transliteration...')
    logger.info('=' * 60)

    if clone_with_transliteration(template_file=template_file, source_file=source_file, output_file=output_file):
        logger.info('=' * 60)
        logger.info('SUCCESS!')
        logger.info('Copy this file to Android and test.')
        logger.info('Turkish chars transliterated in Album/AlbumArtist/Composer fields.')
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
