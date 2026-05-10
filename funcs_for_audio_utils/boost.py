"""Audio volume boosting (re-exported from common_av.boost)."""
from common_av.boost import TARGET_PEAK_DB, AudioBooster, calculate_boost_value, detect_audio_levels

__all__ = ['TARGET_PEAK_DB', 'AudioBooster', 'calculate_boost_value', 'detect_audio_levels']
