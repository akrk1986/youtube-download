"""Copy audio tags (title, artist, program->album, year, composer, comment) into video files.

Reads metadata from .m4a/.mp3 audio files (reusing funcs_audio_tag_handlers) and writes the
equivalent MP4 atoms into same-basename .mp4 videos via common_av.tags.write_mp4_video_tags
(in place, no re-encode). FLAC is not supported.
"""
from common_av.tags import AudioTags, write_mp4_video_tags

from funcs_copy_tags_to_video.audio_reader import read_audio_tags
from funcs_copy_tags_to_video.pairing import pair_audio_with_video
from funcs_copy_tags_to_video.tag_set import FieldChange
from funcs_copy_tags_to_video.video_writer import apply_tags_to_video, compute_changes

__all__ = [
    'AudioTags',
    'FieldChange',
    'apply_tags_to_video',
    'compute_changes',
    'pair_audio_with_video',
    'read_audio_tags',
    'write_mp4_video_tags',
]
