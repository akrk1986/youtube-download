"""Tests for cutting long audio Title tags after artist detection (funcs_audio_processing.unified)."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from funcs_audio_processing.unified import cut_title_tags_in_videos, set_artists_in_audio_files
from project_defs import MAX_TITLE_TAG_LENGTH

LONG_TITLE = ("Έτσι είν' η ζωή Χριστίνα Σάλτη, Μαρίνα Μανωλάκου Χρήστος Παπαδόπουλος "
              'Μπουζούκι: Κωσταντίνος Σταμελάκος Πρώτη εκτέλεση: Βίκυ Μοσχολιού')


def _run(tmp_path: Path, title: str) -> tuple[MagicMock, MagicMock]:
    """Run set_artists_in_audio_files on one fake M4A whose Title tag is the given title."""
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / 'song.m4a').touch()
    handler = MagicMock()
    handler.get_file_glob.return_value = '*.m4a'
    handler.TAG_TITLE = 'title'
    handler.get_tag.return_value = title
    handler.handle_format_specific_tasks.return_value = False
    handler.has_track_number.return_value = False
    with patch('funcs_audio_processing.unified.load_artists', return_value=[]), \
         patch('funcs_audio_processing.unified.find_artists_in_string', return_value=(0, '')) as mock_find:
        set_artists_in_audio_files(audio_folder=tmp_path, artists_json=tmp_path / 'artists.json', handler=handler)
    return handler, mock_find


def test_artist_detection_reads_full_title_then_tag_is_cut(tmp_path: Path) -> None:
    """Detection sees the whole title; the saved Title tag is then cut to MAX_TITLE_TAG_LENGTH."""
    assert len(LONG_TITLE) > MAX_TITLE_TAG_LENGTH
    handler, mock_find = _run(tmp_path=tmp_path, title=LONG_TITLE)

    assert mock_find.call_args.kwargs['text'] == LONG_TITLE
    handler.set_tag.assert_called_once_with(audio=handler.open_audio_file.return_value, tag_name='title',
                                            value=LONG_TITLE[:MAX_TITLE_TAG_LENGTH].rstrip())
    handler.save_audio_file.assert_called_once()


def test_short_title_left_alone(tmp_path: Path) -> None:
    """A title within the limit is not rewritten, and with nothing else to fix the file is not saved."""
    handler, _ = _run(tmp_path=tmp_path, title='Short Song')

    handler.set_tag.assert_not_called()
    handler.save_audio_file.assert_not_called()


def test_video_and_audio_titles_cut_identically(tmp_path: Path) -> None:
    """A video's Title tag is cut by the same rule as its audio, so both carry the same title."""
    (tmp_path / 'song.MP4').touch()  # extension match is case-insensitive
    (tmp_path / 'notes.txt').touch()
    video = MagicMock()
    with patch('funcs_audio_processing.unified.M4ATagHandler') as mock_handler_cls:
        handler = mock_handler_cls.return_value
        handler.TAG_TITLE = 'title'
        handler.open_audio_file.return_value = video
        handler.get_tag.return_value = LONG_TITLE
        cut_title_tags_in_videos(video_folder=tmp_path)

    handler.open_audio_file.assert_called_once_with(file_path=tmp_path / 'song.MP4')
    handler.set_tag.assert_called_once_with(audio=video, tag_name='title',
                                            value=LONG_TITLE[:MAX_TITLE_TAG_LENGTH].rstrip())
    handler.save_audio_file.assert_called_once_with(audio=video, file_path=tmp_path / 'song.MP4')

    audio_handler, _ = _run(tmp_path=tmp_path / 'audio', title=LONG_TITLE)
    assert audio_handler.set_tag.call_args.kwargs['value'] == handler.set_tag.call_args.kwargs['value']
