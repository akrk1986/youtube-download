"""Unit tests for ERTFlix browser-automation helpers (no Playwright runtime)."""
import importlib.util
import json
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from funcs_ertflix_automation.cli_prompts import _label_keys, _typed_key
from funcs_ertflix_automation import (KNOWN_PROGRAMS, TOKEN_URL_FRAGMENT,
                                      ApiMetadataStore, Episode, Program, Season,
                                      build_ytdlp_argv, describe_episode_order,
                                      discover_episodes,
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
        url, label, order = resolve_program(series_url='https://www.ertflix.gr/x',
                                            program_label='Custom', picker=picker)
        assert (url, label, order) == ('https://www.ertflix.gr/x', 'Custom', None)
        picker.assert_not_called()

    def test_resolve_known_program_without_url(self):
        """A known --program without a URL opens that program; no menu."""
        picker = MagicMock()
        url, label, order = resolve_program(series_url=None, program_label='parea', picker=picker)
        assert url.endswith('ERT_PS054741_E0')
        assert (label, order) == ('Parea', False)
        picker.assert_not_called()

    def test_resolve_url_with_known_program_keeps_order(self):
        """A URL plus a known --program takes that program's episode order."""
        _, _, order = resolve_program(series_url='https://www.ertflix.gr/x',
                                      program_label='to alati tis gis', picker=MagicMock())
        assert order is True

    def test_resolve_menu_uses_program_label(self):
        """With no URL and no --program, the menu choice supplies URL and label."""
        chosen = KNOWN_PROGRAMS[1]
        url, label, order = resolve_program(series_url=None, program_label=None,
                                            picker=lambda programs: chosen)
        assert (url, label, order) == (chosen.url, 'To Alati tis Gis', True)

    def test_resolve_menu_keeps_unknown_program_label(self):
        """An unknown --program still opens the menu, but its label is kept."""
        chosen = KNOWN_PROGRAMS[0]
        url, label, order = resolve_program(series_url=None, program_label='My Label',
                                            picker=lambda programs: chosen)
        assert (url, label, order) == (chosen.url, 'My Label', False)


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

    def test_program_order_oldest_first(self):
        """oldest_first=True numbers from the top even without 'Episode N' titles."""
        raw = [{'title': t} for t in ('First', 'Second', 'Third')]
        with patch('funcs_ertflix_automation.episode_scraper._poll_episodes_until_stable',
                   return_value=raw), \
                patch('funcs_ertflix_automation.episode_scraper._placeholder_card_count',
                      return_value=0):
            episodes = discover_episodes(page=MagicMock(), oldest_first=True)
        assert [e.index for e in episodes] == [1, 2, 3]

    def test_program_order_overrides_title_guess(self):
        """oldest_first=False wins over rising 'Episode N' titles."""
        raw = [{'title': f'Episode {n}'} for n in (1, 2, 3)]
        with patch('funcs_ertflix_automation.episode_scraper._poll_episodes_until_stable',
                   return_value=raw), \
                patch('funcs_ertflix_automation.episode_scraper._placeholder_card_count',
                      return_value=0):
            episodes = discover_episodes(page=MagicMock(), oldest_first=False)
        assert [e.index for e in episodes] == [3, 2, 1]

    def test_falling_numbered_titles_keep_newest_first(self):
        """Falling 'Επεισόδιο N' titles mean newest first."""
        episodes = self._discover(titles=['Επεισόδιο 3', 'Επεισόδιο 2', 'Επεισόδιο 1'])
        assert [e.index for e in episodes] == [3, 2, 1]


class TestPromptRunsOffMainThread:
    """The arrow-key menu must not run on the main thread (Playwright keeps a loop running there)."""

    def test_ask_runs_in_worker_thread(self):
        """ask() is called from a non-main thread and its answer is returned."""
        seen: dict[str, bool] = {}

        def _ask():
            seen['main'] = threading.current_thread() is threading.main_thread()
            return KNOWN_PROGRAMS[0]

        fake_question = MagicMock()
        fake_question.ask.side_effect = _ask
        with patch('funcs_ertflix_automation.cli_prompts.questionary.select',
                   return_value=fake_question):
            assert pick_program(programs=KNOWN_PROGRAMS) is KNOWN_PROGRAMS[0]
        assert seen == {'main': False}


class TestLabelKeys:
    """Tests for the number/letter keys read from menu labels."""

    def test_keys_from_labels(self):
        """'12. x' -> '12'; 'q/0. Quit' -> 'q' and '0'; 's. Back' -> 's'."""
        labels = ['12. Twelve', '2. Two', 's. Back to season selection', 'q/0. Quit']
        assert _label_keys(labels=labels) == {'12': 0, '2': 1, 's': 2, 'q': 3, '0': 3}


FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'ertflix-api'


def _store(*names: str) -> ApiMetadataStore:
    """Build a metadata store fed with the named fixture responses, in order."""
    store = ApiMetadataStore()
    for name in names:
        data = json.loads((FIXTURES / name).read_text(encoding='utf-8'))
        store.add_response(url=data['url'], body=data['body'])
    return store


class TestApiMetadataStore:
    """Tests for ApiMetadataStore against responses recorded from ERTFlix."""

    def test_season_numbers_by_label(self):
        """Both label styles map to the official number."""
        store = _store('alati-series.json', 'parea-series.json')
        assert store.season_number_for(label='Season 11') == 11
        assert store.season_number_for(label='Season 2026 - 2027') == 3
        assert store.season_number_for(label='Season 2024 - 2025') == 1
        assert store.season_number_for(label='Season 99') is None

    def test_match_by_title_with_date(self):
        """'In Crete…' is S11E01, broadcast 2023-12-09 (Athens time)."""
        store = _store('alati-series.json', 'alati-s11-editorials.json')
        found = store.match(season_number=11, title='In Crete with Antonis Martsakis')
        assert found is not None
        assert (found.episode_number, found.broadcast_date) == (1, '2023-12-09')

    def test_match_by_id(self):
        """An episode id matches even when the title differs."""
        store = _store('alati-s10-editorials.json')
        found = store.match(season_number=10, title='something else', episode_id='ERT_DS004209')
        assert found is not None and found.episode_number == 2

    def test_mediacard_prefixed_title(self):
        """The mediacard's 'E5 ‧ ' prefix is ignored when matching."""
        store = _store('parea-mediacard.json')
        found = store.match(season_number=3, title='A Tribute to the “Lord of the Minor Key”, '
                                                  'Stavros Kougioumtzis')
        assert found is not None and found.episode_number == 5

    def test_editorials_win_over_mediacard(self):
        """Episode data from editorials replaces the mediacard's, in either arrival order."""
        api = 'https://api.ertflix.opentv.com'
        mediacard = (f'{api}/metadata/v1/series/ERT_X/mediacard', {'series': {'seasons': [
            {'id': 'ERT_S1', 'SeasonNumber': 1, 'Title': 'Season 1', 'episodes': [
                {'id': 'ERT_E1', 'Title': 'E1 ‧ Short', 'episodeNumber': 1,
                 'broadcast': {'start': 1700000000}}]}]}})
        editorials = (f'{api}/metadata/delivery/v2/ERT/vod/editorials', {'editorials': [
            {'id': 'ERT_E1', 'Title': 'Full Title', 'SeasonNumber': 1, 'EpisodeNumber': '1',
             'seasonRef': 'ERT_S1', 'period': {'start': 1700000000.0}}]})
        for order in ((mediacard, editorials), (editorials, mediacard)):
            store = ApiMetadataStore()
            for url, body in order:
                store.add_response(url=url, body=body)
            found = store.match(season_number=1, title='', episode_id='ERT_E1')
            assert found is not None and found.title == 'Full Title'

    def test_broadcast_in_athens_time(self):
        """S2E1 aired 2025-10-18 22:00 Athens time (19:00 UTC)."""
        store = _store('parea-s2-editorials.json')
        found = store.match(season_number=2, title='Tribute to Apostolos Kaldaras')
        assert found is not None and found.broadcast is not None
        assert found.broadcast_date == '2025-10-18'
        assert (found.broadcast.hour, found.broadcast.utcoffset().total_seconds()) == (22, 3 * 3600)

    def test_shared_title_not_matched(self):
        """Two 'Holiday Special' episodes: title alone gives no match."""
        store = _store('parea-s2-editorials.json')
        assert store.match(season_number=2, title='Holiday Special') is None

    def test_other_hosts_ignored(self):
        """A response from another host is ignored."""
        store = ApiMetadataStore()
        store.add_response(url='https://www.ertflix.gr/assets/i18n/en.json', body={'series': []})
        assert not store.has_episodes


class TestEpisodesWithMetadata:
    """discover_episodes with ERTFlix data: official numbers, gaps, fallback."""

    @staticmethod
    def _discover(titles: list[str], store: ApiMetadataStore, season: int) -> list[Episode]:
        """Run discover_episodes with the DOM poll stubbed to return ``titles``."""
        raw = [{'title': title} for title in titles]
        with patch('funcs_ertflix_automation.episode_scraper._poll_episodes_until_stable',
                   return_value=raw), \
                patch('funcs_ertflix_automation.episode_scraper._placeholder_card_count',
                      return_value=0):
            return discover_episodes(page=MagicMock(), metadata=store, season_number=season)

    def test_season_11_official_numbers_and_gap(self):
        """Newest-first S11 page: 'In Crete…' is 1, the last card keeps its gap number 8."""
        store = _store('alati-series.json', 'alati-s11-editorials.json')
        titles = ['The Tradition of Refugees in Platy and Trikala Imathias. Cappadocians and '
                  'Northern Thracians',
                  'Rebetiko in "The Hellenic Project"', 'Musical Journey to Kastoria',
                  'In Crete with Antonis Martsakis']
        episodes = self._discover(titles=titles, store=store, season=11)
        assert [e.index for e in episodes] == [8, 5, 2, 1]
        assert episodes[0].broadcast == '2024-03-02'

    def test_unmatched_episode_keeps_position_number(self):
        """A card not in the data keeps its position-based number and has no date."""
        store = _store('alati-s11-editorials.json')
        episodes = self._discover(titles=['Unknown Title', 'In Crete with Antonis Martsakis'],
                                  store=store, season=11)
        assert (episodes[0].index, episodes[0].broadcast) == (2, '')
        assert episodes[1].index == 1


class TestSeasonsWithMetadata:
    """discover_seasons with ERTFlix data."""

    def test_official_numbers_win(self):
        """Year labels take the official numbers from the data."""
        page = _fake_page({'[role="tablist"] button': [
            'Season 2026 - 2027', 'Season 2025 - 2026', 'Season 2024 - 2025']})
        seasons = discover_seasons(page=page, metadata=_store('parea-series.json'))
        assert [s.index for s in seasons] == [3, 2, 1]

    def test_unknown_label_falls_back(self):
        """A label missing from the data falls back to the label rules."""
        page = _fake_page({'[role="tablist"] button': ['Season 12', 'Season 11']})
        seasons = discover_seasons(page=page, metadata=_store('alati-series.json'))
        assert [s.index for s in seasons] == [12, 11]


class TestDescribeEpisodeOrder:
    """Tests for the order label shown on each season's episode table."""

    @staticmethod
    def _episodes(*dates: str) -> list[Episode]:
        """Build episodes with the given broadcast dates ('' = no date)."""
        return [Episode(index=n, title=f'T{n}', broadcast=d) for n, d in enumerate(dates, start=1)]

    def test_newest_first(self):
        """Falling dates (undated cards skipped) -> newest first."""
        assert describe_episode_order(
            self._episodes('2024-03-02', '', '2023-12-16', '2023-12-09')) == 'Newest first'

    def test_oldest_first(self):
        """Rising dates -> oldest first."""
        assert describe_episode_order(
            self._episodes('2022-11-13', '2022-11-20', '2023-02-19')) == 'Oldest first'

    def test_unknown_without_dates(self):
        """No dates (or one) -> unknown, site order."""
        expected = 'Episode dates unknown, order same as on the site'
        assert describe_episode_order(self._episodes('', '')) == expected
        assert describe_episode_order(self._episodes('2022-11-13', '')) == expected

    def test_unknown_when_mixed(self):
        """Dates going both ways -> unknown, site order."""
        assert describe_episode_order(
            self._episodes('2023-01-01', '2023-03-01', '2023-02-01')) == (
            'Episode dates unknown, order same as on the site')


class TestHandoffDate:
    """The series browser passes the episode's broadcast date to main-yt-dlp.py as --date."""

    @staticmethod
    def _dry_run(broadcast: str, passthrough: list[str]) -> list[str]:
        """Run _execute_handoff in dry-run mode and return the logged hand-off argv."""
        module = _load_series_script()
        args, _ = module.parse_arguments(['--dry-run'])
        episode = Episode(index=1, title='In Crete', broadcast=broadcast)
        token = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?content_id=X'  # nosec B105
        with patch.object(module, 'build_ytdlp_argv', wraps=module.build_ytdlp_argv) as build, \
                patch('builtins.input', return_value=''):
            module._execute_handoff(args=args, program_label=None, token_url=token,  # pylint: disable=protected-access
                                    chosen_season=None, chosen_episode=episode,
                                    passthrough=passthrough)
        return build.call_args.kwargs['passthrough_args']

    def test_date_passed(self):
        """A known broadcast date is forwarded as --date YYYY-MM-DD."""
        assert self._dry_run(broadcast='2023-12-09', passthrough=['--only-audio']) == [
            '--date', '2023-12-09', '--only-audio']

    def test_no_date_when_unknown(self):
        """No broadcast date -> no --date."""
        assert '--date' not in self._dry_run(broadcast='', passthrough=[])

    def test_user_date_wins(self):
        """A --date the user forwarded is kept, not doubled."""
        passed = self._dry_run(broadcast='2023-12-09', passthrough=['--date', '2020-01-01'])
        assert passed == ['--date', '2020-01-01']

    def test_real_run_waits_for_enter(self):
        """After a real download the script waits for Enter and returns the exit code."""
        module = _load_series_script()
        args, _ = module.parse_arguments([])
        episode = Episode(index=1, title='In Crete', broadcast='2023-12-09')
        token = 'https://api.ertflix.opentv.com/urlbuilder/v1/playout/content/token?content_id=X'  # nosec B105
        with patch.object(module, 'hand_off_to_ytdlp', return_value=3), \
                patch('builtins.input', return_value='') as wait:
            code = module._execute_handoff(args=args, program_label=None, token_url=token,  # pylint: disable=protected-access
                                           chosen_season=None, chosen_episode=episode, passthrough=[])
        assert code == 3
        wait.assert_called_once_with('Download failed (exit code 3), press Enter to exit ')


class TestReviewFixes:
    """Regression tests for the code-review findings on the series browser."""

    def test_unmatched_number_clash_renumbered(self):
        """An unmatched card whose position number is an official number gets a free number."""
        store = _store('alati-series.json', 'alati-s11-editorials.json')
        titles = ['Unknown A', 'In Crete with Antonis Martsakis', 'Musical Journey to Kastoria']
        raw = [{'title': t} for t in titles]
        with patch('funcs_ertflix_automation.episode_scraper._poll_episodes_until_stable',
                   return_value=raw), \
                patch('funcs_ertflix_automation.episode_scraper._placeholder_card_count',
                      return_value=0):
            episodes = discover_episodes(page=MagicMock(), metadata=store, season_number=11,
                                         oldest_first=True)
        # 'Unknown A' would be 1 by position, but 1 is In Crete's official number.
        assert [e.index for e in episodes] == [3, 1, 2]
        assert len({e.index for e in episodes}) == len(episodes)

    def test_episode_zero_wins_key_zero(self):
        """With an item numbered 0, '0' selects it and Quit is reached with 'q' only."""
        episodes = [Episode(index=0, title='Special'), Episode(index=1, title='One')]
        fake_question = MagicMock()
        fake_question.ask.return_value = episodes[0]
        with patch('funcs_ertflix_automation.cli_prompts.questionary.select',
                   return_value=fake_question) as select:
            pick_episode(episodes=episodes, has_seasons=False)
        titles = [choice.title for choice in select.call_args.kwargs['choices']]
        assert titles[-1] == 'q. Quit'
        assert _label_keys(labels=titles)['0'] == 0

    def test_fallback_zero_selects_episode_zero(self):
        """In the numbered fallback, '0' picks episode 0 instead of quitting."""
        episodes = [Episode(index=0, title='Special'), Episode(index=1, title='One')]
        with patch('funcs_ertflix_automation.cli_prompts.questionary.select',
                   side_effect=RuntimeError('no console')), \
                patch('builtins.input', return_value='0'):
            assert pick_episode(episodes=episodes, has_seasons=False) is episodes[0]

    def test_unknown_number_keeps_highlight(self):
        """'1' then '0' in a 9-item menu: no item 10, so nothing is highlighted (not Quit)."""
        keys = _label_keys(labels=[*(f'{n}. T' for n in range(1, 10)), 'q/0. Quit'])
        text, position = _typed_key(keys=keys, typed_text='', char='1')
        assert (text, position) == ('1', 0)
        assert _typed_key(keys=keys, typed_text=text, char='0') == ('', None)
        assert _typed_key(keys=keys, typed_text='', char='0') == ('0', 9)

    def test_partial_season_data_sets_official_number(self):
        """Seasons keep their label numbers; only seasons found in the data get official_number."""
        page = _fake_page({'[role="tablist"] button': ['Season 12', 'Season 11']})
        seasons = discover_seasons(page=page, metadata=_store('alati-series.json'))
        assert [(s.index, s.official_number) for s in seasons] == [(12, None), (11, 11)]

    def test_user_date_with_equals_not_doubled(self):
        """A forwarded --date=YYYY-MM-DD is respected; no second --date is added."""
        passed = TestHandoffDate._dry_run(broadcast='2023-12-09', passthrough=['--date=2020-01-01'])
        assert passed == ['--date=2020-01-01']

    def test_malformed_entry_skips_only_itself(self):
        """A bad episode entry is skipped; the entries after it are still read."""
        store = ApiMetadataStore()
        store.add_response(
            url='https://api.ertflix.opentv.com/metadata/delivery/v2/ERT/vod/editorials',
            body={'editorials': [
                {'id': 'ERT_BAD', 'Title': 'Bad', 'SeasonNumber': 1},
                {'id': 'ERT_OK', 'Title': 'Good', 'SeasonNumber': 1, 'EpisodeNumber': '2',
                 'period': {'start': 1700000000}},
            ]})
        found = store.match(season_number=1, title='Good')
        assert found is not None and found.episode_number == 2
