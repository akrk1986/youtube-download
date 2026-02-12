"""Audio utility functions package.

This package contains audio processing utilities:
- boost: Audio volume boosting using ffmpeg
- conversion: Audio format conversion (MP3 ↔ M4A)
"""

# Import boost functions and classes
from funcs_for_audio_utils.boost import (
    MP3Booster,
    MP4Booster,
    TARGET_PEAK_DB,
    calculate_boost_value,
    detect_audio_levels,
)

# Import conversion functions
from funcs_for_audio_utils.conversion import (
    convert_m4a_to_mp3,
    convert_mp3_to_m4a,
    get_ffmpeg_path,
    get_ffprobe_path,
)

__all__ = [
    # Boost
    'detect_audio_levels',
    'calculate_boost_value',
    'MP3Booster',
    'MP4Booster',
    'TARGET_PEAK_DB',
    # Conversion
    'convert_mp3_to_m4a',
    'convert_m4a_to_mp3',
    'get_ffmpeg_path',
    'get_ffprobe_path',
]
