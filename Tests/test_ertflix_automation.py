"""Unit tests for ERTFlix browser-automation helpers (no Playwright runtime)."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from funcs_ertflix_automation import (KNOWN_PROGRAMS, TOKEN_URL_FRAGMENT,
                                      Episode, Program, Season,
                                      build_ytdlp_argv, discover_episodes,
                                      discover_seasons, find_program,
                                      pick_episode, pick_program, pick_season,
                                      resolve_program)


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
            Episode(index=1, title='Ep 1'),
            Episode(index=2, title='Ep 2'),
        ]
        fake_question = MagicMock()
        fake_question.ask.return_value = episodes[0]
        with patch('funcs_ertflix_automation.cli_prompts.questionary.select',
                   return_value=fake_question):
            assert pick_episode(episodes=episodes) is episodes[0]

    def test_cancel_raises_keyboard_interrupt(self):
        """ask() returning None raises KeyboardInterrupt."""
        episodes = [Episode(index=1, title='Ep 1')]
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


class TestPrograms:
    """Tests for the known-program list, find_program and resolve_program."""

    def test_menu_order(self):
        """Parea first, Nykhta Stasou last."""
        labels = [p.label for p in KNOWN_PROGRAMS]
        assert labels == ['Parea', 'To Alati tis Gis', 'Nykhta Stasou']

    def test_find_program_ignores_case(self):
        """Lookup matches the label regardless of case and surrounding spaces."""
        found = find_program(label='  to alati TIS gis ')
        assert found is not None
        assert found.url.endswith('ERT_DS018967_E0')

    def test_find_program_miss(self):
        """An unknown label returns None."""
        assert find_program(label='Unknown Show') is None

    def test_resolve_url_given(self):
        """An explicit URL is used as-is with the --program label; no menu."""
        picker = MagicMock()
        url, label = resolve_program(series_url='https://www.ertflix.gr/x',
                                     program_label='Custom', picker=picker)
        assert (url, label) == ('https://www.ertflix.gr/x', 'Custom')
        picker.assert_not_called()

    def test_resolve_known_program_without_url(self):
        """A known --program without a URL opens that program; no menu."""
        picker = MagicMock()
        url, label = resolve_program(series_url=None, program_label='parea', picker=picker)
        assert url.endswith('ERT_PS054741_E0')
        assert label == 'Parea'
        picker.assert_not_called()

    def test_resolve_menu_uses_program_label(self):
        """With no URL and no --program, the menu choice supplies URL and label."""
        chosen = KNOWN_PROGRAMS[1]
        url, label = resolve_program(series_url=None, program_label=None,
                                     picker=lambda programs: chosen)
        assert (url, label) == (chosen.url, 'To Alati tis Gis')

    def test_resolve_menu_keeps_unknown_program_label(self):
        """An unknown --program still opens the menu, but its label is kept."""
        chosen = KNOWN_PROGRAMS[0]
        url, label = resolve_program(series_url=None, program_label='My Label',
                                     picker=lambda programs: chosen)
        assert (url, label) == (chosen.url, 'My Label')


class TestPickProgram:
    """Tests for pick_program."""

    def test_returns_selected_program(self):
        """ask() returning a Program propagates to the caller."""
        fake_question = MagicMock()
        fake_question.ask.return_value = KNOWN_PROGRAMS[2]
        with patch('funcs_ertflix_automation.cli_prompts.questionary.select',
                   return_value=fake_question):
            assert pick_program(programs=KNOWN_PROGRAMS) is KNOWN_PROGRAMS[2]

    def test_fallback_numbered_prompt(self):
        """When questionary fails, the numbered prompt maps '2' to the second program."""
        with patch('funcs_ertflix_automation.cli_prompts.questionary.select',
                   side_effect=RuntimeError('no console')), \
                patch('builtins.input', return_value='2'):
            assert pick_program(programs=KNOWN_PROGRAMS) is KNOWN_PROGRAMS[1]

    def test_fallback_quit(self):
        """'q' at the numbered prompt raises KeyboardInterrupt."""
        with patch('funcs_ertflix_automation.cli_prompts.questionary.select',
                   side_effect=RuntimeError('no console')), \
                patch('builtins.input', return_value='q'):
            with pytest.raises(KeyboardInterrupt):
                pick_program(programs=KNOWN_PROGRAMS)

    def test_empty_list_raises(self):
        """An empty program list is a programming error."""
        programs: list[Program] = []
        with pytest.raises(ValueError):
            pick_program(programs=programs)


def _load_series_script():
    """Import the hyphenated main-ertflix-series.py as a module."""
    path = Path(__file__).resolve().parent.parent / 'main-ertflix-series.py'
    spec = importlib.util.spec_from_file_location('main_ertflix_series', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestParseArguments:
    """Tests for main-ertflix-series.py parse_arguments (URL is optional)."""

    def test_forwarded_flag_value_not_taken_as_url(self):
        """Without a URL, 'mp3' in '--audio-format mp3' stays in the pass-through args."""
        args, unknown = _load_series_script().parse_arguments(
            ['--only-audio', '--audio-format', 'mp3'])
        assert args.series_url is None
        assert unknown == ['--only-audio', '--audio-format', 'mp3']

    def test_url_found_anywhere(self):
        """The URL is picked up wherever it appears and removed from the pass-through args."""
        url = 'https://www.ertflix.gr/#/details/ERT_PS054741_E0'
        args, unknown = _load_series_script().parse_arguments(
            ['--audio-format', 'mp3', url, '--program', 'Parea'])
        assert args.series_url == url
        assert args.program == 'Parea'
        assert unknown == ['--audio-format', 'mp3']


def _fake_page(labels_by_selector: dict[str, list[str]]) -> MagicMock:
    """Build a fake Playwright page whose selectors return buttons with the given aria-labels."""
    def _handle(label: str) -> MagicMock:
        handle = MagicMock()
        handle.get_attribute.return_value = label
        return handle

    page = MagicMock()
    page.query_selector_all.side_effect = lambda selector: [
        _handle(label) for label in labels_by_selector.get(selector, [])]
    return page


class TestDiscoverSeasons:
    """Tests for discover_seasons de-duplication and numbering."""

    def test_doubled_labels_deduplicated_and_numbered_from_label(self):
        """'Season 10' + 'Season Season 10' collapse into one season numbered 10, newest first."""
        page = _fake_page({
            '[role="tablist"] button': ['Season 10', 'Season 11'],
            '[class*="season" i]': ['Season Season 10', 'Season Season 11'],
        })
        seasons = discover_seasons(page=page)
        assert [(s.index, s.label) for s in seasons] == [(11, 'Season 11'), (10, 'Season 10')]

    def test_year_labels_numbered_by_rank(self):
        """Year labels (Parea) are numbered oldest = 1, listed newest first."""
        page = _fake_page({'[role="tablist"] button': [
            'Season 2024 - 2025', 'Season 2026 - 2027', 'Season 2025 - 2026']})
        seasons = discover_seasons(page=page)
        assert [(s.index, s.label) for s in seasons] == [
            (3, 'Season 2026 - 2027'), (2, 'Season 2025 - 2026'), (1, 'Season 2024 - 2025')]

    def test_labels_without_numbers_keep_position_numbering(self):
        """Greek-letter labels are numbered by DOM position, newest first."""
        page = _fake_page({'[role="tablist"] button': ['Κύκλος Β', 'Κύκλος Α']})
        seasons = discover_seasons(page=page)
        assert [(s.index, s.label) for s in seasons] == [(2, 'Κύκλος Β'), (1, 'Κύκλος Α')]


class TestDiscoverEpisodesNumbering:
    """Tests for episode numbering direction in discover_episodes."""

    @staticmethod
    def _discover(titles: list[str]) -> list[Episode]:
        """Run discover_episodes with the DOM poll stubbed to return ``titles``."""
        raw = [{'title': title} for title in titles]
        with patch('funcs_ertflix_automation.episode_scraper._poll_episodes_until_stable',
                   return_value=raw), \
                patch('funcs_ertflix_automation.episode_scraper._placeholder_card_count',
                      return_value=0):
            return discover_episodes(page=MagicMock())

    def test_oldest_first_page_numbered_from_top(self):
        """Rising 'Episode N' titles mean oldest first: the top card is episode 1."""
        titles = ['Part 1', 'Tribute', 'Part 2', *[f'Episode {n}' for n in range(4, 13)]]
        episodes = self._discover(titles=titles)
        assert [e.index for e in episodes] == list(range(1, 13))
        assert episodes[3].title == 'Episode 4' and episodes[3].index == 4

    def test_titled_page_numbered_newest_first(self):
        """Without numbered titles, the top card gets the highest number (Parea order)."""
        episodes = self._discover(titles=['Newest', 'Middle', 'Oldest'])
        assert [e.index for e in episodes] == [3, 2, 1]

    def test_falling_numbered_titles_keep_newest_first(self):
        """Falling 'Επεισόδιο N' titles mean newest first."""
        episodes = self._discover(titles=['Επεισόδιο 3', 'Επεισόδιο 2', 'Επεισόδιο 1'])
        assert [e.index for e in episodes] == [3, 2, 1]
