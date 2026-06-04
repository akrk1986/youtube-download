"""Tests for the copy-audio-tags-to-video utility package."""
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# pylint: disable=wrong-import-position
from common_av.ffmpeg import get_ffmpeg_paths  # noqa: E402
from common_av.tags import (  # noqa: E402
    MP4_COMPOSER,
    MP4_COPYRIGHT,
    MP4_TITLE,
    AudioTags,
    write_m4a_tags,
    write_mp3_tags,
    write_mp4_video_tags,
)
from mutagen.mp4 import MP4  # noqa: E402

from funcs_copy_tags_to_video.audio_reader import read_audio_tags  # noqa: E402
from funcs_copy_tags_to_video.pairing import pair_audio_with_video  # noqa: E402
from funcs_copy_tags_to_video.tag_set import FieldChange  # noqa: E402
from funcs_copy_tags_to_video.video_writer import _changes_from_atoms  # noqa: E402

# pylint: enable=wrong-import-position


def _touch(directory: Path, name: str) -> Path:
    """Create an empty file in directory and return its path."""
    path = directory / name
    path.write_bytes(b'')
    return path


def _sample_tags() -> AudioTags:
    """Return a fully populated AudioTags fixture."""
    return AudioTags(title='My Title', artist='My Artist', album='My Program',
                     year='2021', composer='My Composer', comment='My Comment')


def _make_silent_audio(path: Path, codec: str) -> None:
    """Create a 0.3s silent audio file at path with ffmpeg, or skip if ffmpeg is missing."""
    ffmpeg = get_ffmpeg_paths()[0]
    if shutil.which(ffmpeg) is None and not Path(ffmpeg).exists():
        pytest.skip('ffmpeg not available')
    subprocess.run(  # nosec B603
        [ffmpeg, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono',
         '-t', '0.3', '-c:a', codec, str(path)],
        check=True, capture_output=True, encoding='utf-8', errors='replace',
    )


def _make_video(path: Path) -> None:
    """Create a 0.3s silent black .mp4 at path with ffmpeg, or skip if ffmpeg is missing."""
    ffmpeg = get_ffmpeg_paths()[0]
    if shutil.which(ffmpeg) is None and not Path(ffmpeg).exists():
        pytest.skip('ffmpeg not available')
    subprocess.run(  # nosec B603
        [ffmpeg, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=64x64:d=0.3',
         '-pix_fmt', 'yuv420p', str(path)],
        check=True, capture_output=True, encoding='utf-8', errors='replace',
    )


def test_pairing_matches_by_stem(tmp_path):
    """Audio files pair to same-stem .mp4 videos; others are unmatched."""
    audio_dir = tmp_path / 'audio'
    video_dir = tmp_path / 'video'
    audio_dir.mkdir()
    video_dir.mkdir()
    _touch(audio_dir, 'song-01.m4a')
    _touch(audio_dir, 'song-02.mp3')
    _touch(audio_dir, 'orphan.m4a')
    _touch(video_dir, 'song-01.mp4')
    _touch(video_dir, 'song-02.mp4')
    _touch(video_dir, 'lonely-video.mp4')

    pairs, audio_without_video, video_without_audio = pair_audio_with_video(
        audio_dir=audio_dir, video_dir=video_dir)

    paired_stems = sorted(audio.stem for audio, _ in pairs)
    assert paired_stems == ['song-01', 'song-02']
    assert [audio.name for audio in audio_without_video] == ['orphan.m4a']
    assert [video.name for video in video_without_audio] == ['lonely-video.mp4']


def test_pairing_case_insensitive_extensions(tmp_path):
    """Uppercase extensions still pair."""
    audio_dir = tmp_path / 'audio'
    video_dir = tmp_path / 'video'
    audio_dir.mkdir()
    video_dir.mkdir()
    _touch(audio_dir, 'clip.M4A')
    _touch(video_dir, 'clip.MP4')

    pairs, audio_without_video, video_without_audio = pair_audio_with_video(
        audio_dir=audio_dir, video_dir=video_dir)

    assert len(pairs) == 1
    assert not audio_without_video
    assert not video_without_audio


def test_field_change_will_write_rules():
    """will_write is True only for a non-empty value that differs from the old one."""
    assert FieldChange(label='t', atom=MP4_TITLE, old_value='', new_value='X').will_write
    assert FieldChange(label='t', atom=MP4_TITLE, old_value='A', new_value='B').will_write
    assert not FieldChange(label='t', atom=MP4_TITLE, old_value='X', new_value='X').will_write
    assert not FieldChange(label='t', atom=MP4_TITLE, old_value='X', new_value='').will_write


def test_changes_from_atoms_with_stub():
    """_changes_from_atoms reads existing atoms via .get and diffs all six fields."""
    existing = {MP4_TITLE: ['Old Title']}  # dict.get mimics mutagen MP4.get

    changes = _changes_from_atoms(reader=cast(MP4, existing), tags=_sample_tags())

    assert len(changes) == 6
    by_label = {change.label: change for change in changes}
    assert by_label['title'].old_value == 'Old Title'
    assert by_label['title'].new_value == 'My Title'
    assert by_label['title'].will_write
    assert by_label['artist'].old_value == ''
    assert by_label['album (program)'].new_value == 'My Program'


def test_read_m4a_round_trip(tmp_path):
    """read_audio_tags reads back the six fields written to an .m4a file."""
    target = tmp_path / 'song.m4a'
    _make_silent_audio(path=target, codec='aac')
    write_m4a_tags(audio_path=target, tags=_sample_tags())

    tags = read_audio_tags(audio_path=target)

    assert tags.title == 'My Title'
    assert tags.album == 'My Program'
    assert tags.year == '2021'
    assert tags.composer == 'My Composer'
    assert tags.comment == 'My Comment'


def test_read_mp3_comment_via_raw_id3(tmp_path):
    """The MP3 COMM fallback reads the comment EasyID3 does not expose."""
    target = tmp_path / 'song.mp3'
    _make_silent_audio(path=target, codec='libmp3lame')
    write_mp3_tags(audio_path=target, tags=_sample_tags())

    tags = read_audio_tags(audio_path=target)

    assert tags.title == 'My Title'
    assert tags.comment == 'My Comment'
    assert tags.composer == 'My Composer'


def test_write_mp4_video_routes_composer_to_copyright(tmp_path):
    """write_mp4_video_tags puts composer in ©cpy (General Copyright), not ©wrt."""
    video = tmp_path / 'clip.mp4'
    _make_video(path=video)

    write_mp4_video_tags(video_path=video, tags=_sample_tags())

    written = MP4(video)
    assert written.get(MP4_TITLE) == ['My Title']
    assert written.get(MP4_COPYRIGHT) == ['My Composer']
    assert written.get(MP4_COMPOSER) is None
