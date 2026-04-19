"""Unit tests for ERTFlix browser-automation helpers (no Playwright runtime)."""
import sys
from unittest.mock import MagicMock, patch

import pytest

from funcs_ertflix_automation import (TOKEN_URL_FRAGMENT, Episode, Season,
                                      build_ytdlp_argv, extract_episode_id,
                                      pick_episode, pick_season)


class TestExtractEpisodeId:
    """Tests for extract_episode_id."""

    def test_extracts_from_typical_image_src(self):
        """ERT IDs embedded in image URLs are matched."""
        src = 'https://imageservice.ertflix.opentv.com/images/v1/image/tvshow/ERT_PS054741_E14/foo.jpg'
        assert extract_episode_id(img_src=src) == 'ERT_PS054741_E14'

    def test_returns_none_for_non_matching(self):
        """Unrelated URLs return None."""
        assert extract_episode_id(img_src='https://example.com/cat.jpg') is None

    def test_returns_none_for_none_input(self):
        """None input returns None (no exception)."""
        assert extract_episode_id(img_src=None) is None

    def test_extracts_first_match(self):
        """When multiple IDs appear, the first one wins."""
        src = 'ERT_AAA_E1 and ERT_BBB_E2'
        assert extract_episode_id(img_src=src) == 'ERT_AAA_E1'


class TestBuildYtdlpArgv:
    """Tests for build_ytdlp_argv."""

    def test_basic_argv_structure(self):
        """argv contains interpreter, script, flag, and URL in order."""
        token = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?content_id=X'  # nosec B105
        argv = build_ytdlp_argv(token_url=token, passthrough_args=[])
        assert argv[0] == sys.executable
        assert argv[1] == 'main-yt-dlp.py'
        assert argv[2] == '--ertflix-program'
        assert argv[3] == token

    def test_passthrough_appended(self):
        """Pass-through flags appear after the URL in argv order."""
        token = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?X=Y'  # nosec B105
        argv = build_ytdlp_argv(
            token_url=token,
            passthrough_args=['--only-audio', '--audio-format', 'mp3'],
        )
        assert argv[-3:] == ['--only-audio', '--audio-format', 'mp3']

    def test_rejects_shell_metacharacters(self):
        """URL with shell metacharacters is rejected by sanitizer."""
        bad_url = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?x=y|rm'
        with pytest.raises(ValueError):
            build_ytdlp_argv(token_url=bad_url, passthrough_args=[])


class TestPickSeason:
    """Tests for pick_season."""

    def test_returns_selected_season(self):
        """ask() returning a Season propagates to the caller."""
        seasons = [
            Season(index=1, label='Season 1', selector='nav button'),
            Season(index=2, label='Season 2', selector='nav button'),
        ]
        fake_question = MagicMock()
        fake_question.ask.return_value = seasons[1]
        with patch('funcs_ertflix_automation.cli_prompts.questionary.select',
                   return_value=fake_question):
            assert pick_season(seasons=seasons) is seasons[1]

    def test_cancel_raises_keyboard_interrupt(self):
        """ask() returning None (Ctrl-C/Esc) raises KeyboardInterrupt."""
        seasons = [Season(index=1, label='Season 1', selector='nav button')]
        fake_question = MagicMock()
        fake_question.ask.return_value = None
        with patch('funcs_ertflix_automation.cli_prompts.questionary.select',
                   return_value=fake_question):
            with pytest.raises(KeyboardInterrupt):
                pick_season(seasons=seasons)

    def test_empty_list_raises_value_error(self):
        """An empty season list is an API misuse."""
        with pytest.raises(ValueError):
            pick_season(seasons=[])


class TestPickEpisode:
    """Tests for pick_episode."""

    def test_returns_selected_episode(self):
        """ask() returning an Episode propagates to the caller."""
        episodes = [
            Episode(index=1, title='Ep 1', episode_id='ERT_A_E1'),
            Episode(index=2, title='Ep 2', episode_id='ERT_A_E2'),
        ]
        fake_question = MagicMock()
        fake_question.ask.return_value = episodes[0]
        with patch('funcs_ertflix_automation.cli_prompts.questionary.select',
                   return_value=fake_question):
            assert pick_episode(episodes=episodes) is episodes[0]

    def test_cancel_raises_keyboard_interrupt(self):
        """ask() returning None raises KeyboardInterrupt."""
        episodes = [Episode(index=1, title='Ep 1', episode_id='ERT_A_E1')]
        fake_question = MagicMock()
        fake_question.ask.return_value = None
        with patch('funcs_ertflix_automation.cli_prompts.questionary.select',
                   return_value=fake_question):
            with pytest.raises(KeyboardInterrupt):
                pick_episode(episodes=episodes)


class TestTokenUrlFragment:
    """Tests for the TOKEN_URL_FRAGMENT constant used for filtering requests."""

    def test_matches_real_token_url(self):
        """The fragment is a substring of a real token URL."""
        real_url = (
            'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token'
            '?content_id=DRM_PS054741_DASH&type=account&content_URL=foo'
        )
        assert TOKEN_URL_FRAGMENT in real_url

    def test_does_not_match_video_manifest_url(self):
        """Direct manifest URLs do not contain the token fragment."""
        manifest = 'https://ert-ucdn.broadpeak-aas.com/bpk-vod/vod-nodrm/parea/index.mpd'
        assert TOKEN_URL_FRAGMENT not in manifest
