"""Tests for DoVi profile-5 detection and torrent good/bad notification messages."""
import json
import subprocess
import types
from pathlib import Path

import pytest

from funcs_for_qb_notify import dovi, hook
from funcs_notifications.torrent_message import (
    build_torrent_email_message,
    build_torrent_slack_message,
)

PROFILE5_JSON = json.dumps({'streams': [
    {'codec_type': 'audio'},
    {'codec_type': 'video',
     'side_data_list': [{'side_data_type': 'DOVI configuration record', 'dv_profile': 5}]},
]})
PROFILE8_JSON = json.dumps({'streams': [
    {'codec_type': 'video', 'side_data_list': [{'dv_profile': 8}]},
]})
NO_DOVI_JSON = json.dumps({'streams': [{'codec_type': 'video', 'side_data_list': []}]})


def _fake_run(stdout: str, returncode: int = 0):
    """Return a stub for subprocess.run yielding the given stdout/returncode."""
    def _run(*_args, **_kwargs):
        return types.SimpleNamespace(returncode=returncode, stdout=stdout)
    return _run


@pytest.fixture(autouse=True)
def _stub_ffprobe(monkeypatch):
    """Avoid resolving a real ffprobe binary during tests."""
    monkeypatch.setattr(dovi, '_get_ffprobe_path', lambda: 'ffprobe')


def test_profile5_detected(monkeypatch):
    """A video stream with dv_profile 5 is flagged bad."""
    monkeypatch.setattr(dovi.subprocess, 'run', _fake_run(PROFILE5_JSON))
    assert dovi.file_is_dovi_profile5(file_path=Path('x.mp4')) is True


def test_profile8_is_good(monkeypatch):
    """DoVi profile 8 is not flagged."""
    monkeypatch.setattr(dovi.subprocess, 'run', _fake_run(PROFILE8_JSON))
    assert dovi.file_is_dovi_profile5(file_path=Path('x.mp4')) is False


def test_no_dovi_is_good(monkeypatch):
    """A file without DoVi side-data returns no profile and is good."""
    monkeypatch.setattr(dovi.subprocess, 'run', _fake_run(NO_DOVI_JSON))
    assert dovi._video_dovi_profile(file_path=Path('x.mp4')) is None
    assert dovi.file_is_dovi_profile5(file_path=Path('x.mp4')) is False


def test_probe_failure_returns_none(monkeypatch):
    """A non-zero ffprobe exit yields no profile (treated as good)."""
    monkeypatch.setattr(dovi.subprocess, 'run', _fake_run('', returncode=1))
    assert dovi._video_dovi_profile(file_path=Path('x.mp4')) is None


def test_path_is_bad_directory(monkeypatch, tmp_path):
    """A directory containing one profile-5 video among others is bad."""
    (tmp_path / 'good1.mp4').write_bytes(b'')
    (tmp_path / 'bad.mkv').write_bytes(b'')
    (tmp_path / 'notes.txt').write_bytes(b'')

    def _profile(file_path: Path):
        return 5 if file_path.name == 'bad.mkv' else None

    monkeypatch.setattr(dovi, '_video_dovi_profile', _profile)
    assert dovi.path_is_bad(path=tmp_path) is True


def test_path_is_bad_all_good(monkeypatch, tmp_path):
    """A directory with no profile-5 video is good."""
    (tmp_path / 'a.mp4').write_bytes(b'')
    (tmp_path / 'b.mkv').write_bytes(b'')
    monkeypatch.setattr(dovi, '_video_dovi_profile', lambda file_path: None)
    assert dovi.path_is_bad(path=tmp_path) is False


def test_path_is_bad_probe_exception(monkeypatch, tmp_path):
    """A probe error is caught and treated as good."""
    video = tmp_path / 'a.mp4'
    video.write_bytes(b'')

    def _raise(file_path: Path):
        raise subprocess.SubprocessError('boom')

    monkeypatch.setattr(dovi, 'file_is_dovi_profile5', _raise)
    assert dovi.path_is_bad(path=tmp_path) is False


def test_email_message_bad():
    """Bad email message uses the warning emoji and DoVi headline."""
    msg = build_torrent_email_message(name='Film', path='/dl/Film', is_bad=True)
    assert '⚠️' in msg.subject
    assert 'DoVi Profile 5' in msg.subject
    assert '⚠️' in msg.html_body
    assert '<b>Name:</b> Film' in msg.html_body


def test_email_message_good():
    """Good email message keeps the green check and plain headline."""
    msg = build_torrent_email_message(name='Film', path='/dl/Film', is_bad=False)
    assert '✅' in msg.subject
    assert 'DoVi' not in msg.subject


def test_slack_message_bad():
    """Bad Slack message uses the :warning: shortcode and DoVi headline."""
    text = build_torrent_slack_message(name='Film', path='/dl/Film', is_bad=True)
    assert ':warning:' in text
    assert 'DoVi Profile 5' in text


def test_slack_message_good():
    """Good Slack message uses the :white_check_mark: shortcode."""
    text = build_torrent_slack_message(name='Film', path='/dl/Film', is_bad=False)
    assert ':white_check_mark:' in text
    assert 'DoVi' not in text


def _capture_hook_cmd(monkeypatch, is_bad: bool) -> list[str]:
    """Run run_hook with stubbed detection + subprocess; return the notifier argv."""
    captured: dict[str, list[str]] = {}

    def _run(cmd, **_kwargs):
        captured['cmd'] = cmd
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(hook, 'path_is_bad', lambda path: is_bad)
    monkeypatch.setattr(hook.subprocess, 'run', _run)
    rc = hook.run_hook(name='Film', path=Path('/dl/Film'), notifier_script='main-qb-notify-gmail.py')
    assert rc == 0
    return captured['cmd']


def test_run_hook_passes_bad_status(monkeypatch):
    """run_hook forwards --status bad and the chosen notifier when content is bad."""
    cmd = _capture_hook_cmd(monkeypatch, is_bad=True)
    assert cmd[-2:] == ['--status', 'bad']
    assert cmd[-3] == '/dl/Film'
    assert cmd[1].endswith('main-qb-notify-gmail.py')


def test_run_hook_passes_good_status(monkeypatch):
    """run_hook forwards --status good when content is good."""
    cmd = _capture_hook_cmd(monkeypatch, is_bad=False)
    assert cmd[-2:] == ['--status', 'good']
