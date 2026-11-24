"""Light TUI: rich tables for display + questionary selects for input."""
# PEP 810: lazy on Python 3.15+, ignored (eager) on older versions; loaded when a picker is shown.
__lazy_modules__ = ['prompt_toolkit.key_binding', 'questionary', 'questionary.prompts.common',
                    'rich.console', 'rich.table']

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar
from collections.abc import Sequence

import questionary
from prompt_toolkit.key_binding import (KeyBindings, KeyPressEvent,
                                        merge_key_bindings)
from questionary.prompts.common import InquirerControl
from rich.console import Console
from rich.table import Table

from funcs_ertflix_automation.episode_scraper import Episode
from funcs_ertflix_automation.season_scraper import Season
from funcs_ertflix_automation.errors import BackToSeasons
from funcs_ertflix_automation.programs import Program


logger = logging.getLogger(__name__)

T = TypeVar('T')

_QUIT = '__quit__'
_BACK = '__back__'

# Arrow-key menu hint (replaces questionary's '(Use arrow keys)').
_MENU_INSTRUCTION = '(arrows or number, Enter to select)'
# Digits typed within this many seconds of each other form one number ('1' then '2' = 12).
_NUMBER_KEY_TIMEOUT_S = 1.0


def _fallback_numbered_prompt(prompt: str, labels: Sequence[str],
                              values: Sequence[T],
                              back_key: str | None = None,
                              header: str = '') -> T:
    """Plain numbered input prompt — used when questionary can't drive the console.

    Each label is expected to start with ``'<n>. '`` where ``<n>`` is the
    user-facing number shown in the rich table. The prompt accepts that
    number (not the list position), so the numbering stays consistent across
    the table, questionary list, and fallback list.

    ``q`` and ``0`` always quit. ``back_key`` (if set) triggers back-to-seasons.

    Args:
        prompt: Text shown before the numbered input.
        labels: Display labels (one per value, same length as ``values``).
        values: The values parallel to ``labels``; the chosen value is returned.
        back_key: Single character that triggers back-to-seasons (e.g. ``'s'``).
        header: Optional header line printed before the item list.

    Returns:
        T: The value at the chosen index.

    Raises:
        BackToSeasons: If the user enters the back key.
        KeyboardInterrupt: If the user quits or provides empty input.
    """
    if header:
        print(header)
    for label in labels:
        print(f'  {label}')
    index_map: dict[int, T] = {}
    for label, value in zip(labels, values):
        prefix = label.split('.', 1)[0].strip()
        try:
            index_map[int(prefix)] = value
        except ValueError:
            pass
    lo, hi = (min(index_map), max(index_map)) if index_map else (1, 1)
    while True:
        raw = input(f'{prompt} ').strip().lower()
        if not raw:
            raise KeyboardInterrupt('Selection cancelled (empty input)')
        if raw in ('q', '0'):
            raise KeyboardInterrupt('Quit')
        if back_key and raw == back_key:
            raise BackToSeasons('Back to season selection')
        try:
            num = int(raw)
        except ValueError:
            print(f'Enter a number between {lo} and {hi}.')
            continue
        if num in index_map:
            return index_map[num]
        print(f'Number out of range — enter a number between {lo} and {hi}.')


def _label_keys(labels: Sequence[str]) -> dict[str, int]:
    """Map each label's key ('12' in '12. Title', 'q' and '0' in 'q/0. Quit') to its position.

    Args:
        labels: Menu labels, each starting with ``'<key>. '``.

    Returns:
        dict[str, int]: Key text -> position in ``labels``.
    """
    keys: dict[str, int] = {}
    for position, label in enumerate(labels):
        prefix = label.split('.', 1)[0]
        for key in prefix.split('/'):
            if key.strip():
                keys[key.strip().lower()] = position
    return keys


def _add_number_keys(question: questionary.Question, labels: Sequence[str]) -> None:
    """Let typed keys move the highlight in an arrow-key menu.

    Digits typed within ``_NUMBER_KEY_TIMEOUT_S`` of each other form one number and move
    the highlight to the item with that number; ``q``/``s`` jump to Quit / Back. Enter
    then selects as usual. Does nothing if the menu's internals are not found.

    Args:
        question: The questionary select question (not yet asked).
        labels: Its labels, in menu order.
    """
    app = question.application
    control = next((c for c in app.layout.find_all_controls()
                    if isinstance(c, InquirerControl)), None)
    if control is None:
        logger.debug('Menu control not found; number keys not added.')
        return
    keys = _label_keys(labels=labels)
    typed_text = ''
    typed_at = 0.0

    def _jump(event: KeyPressEvent) -> None:
        """Move the highlight to the item whose key matches what was typed."""
        nonlocal typed_text, typed_at
        char = event.data.lower()
        now = time.monotonic()
        recent = char.isdigit() and now - typed_at <= _NUMBER_KEY_TIMEOUT_S
        text = (typed_text if recent else '') + char
        if text not in keys:
            text = char
        typed_text, typed_at = text, now
        if text in keys:
            control.pointed_at = keys[text]

    bindings = KeyBindings()
    for char in [*'0123456789', 'q', 's']:
        if char in '0123456789' or char in keys:
            bindings.add(char, eager=True)(_jump)
    app.key_bindings = merge_key_bindings([app.key_bindings, bindings]) if app.key_bindings else bindings


def _select_or_fallback(prompt: str, labels: Sequence[str],
                        values: Sequence[T],
                        back_key: str | None = None,
                        fallback_header: str = '') -> T:
    """Use questionary if available, otherwise fall back to numbered input.

    The arrow-key menu also takes typed numbers (see ``_add_number_keys``).

    Args:
        prompt: Prompt text.
        labels: Display labels parallel to ``values``.
        values: Values to choose from.
        back_key: Character that triggers back-to-seasons in the fallback prompt.
        fallback_header: Header line printed above the item list in fallback mode.

    Returns:
        T: The selected value.

    Raises:
        BackToSeasons: If the user chooses to go back to seasons.
        KeyboardInterrupt: If the user quits or cancels the selection.
    """
    choices = [questionary.Choice(title=label, value=value)
               for label, value in zip(labels, values)]
    try:
        question = questionary.select(prompt, choices=choices, instruction=_MENU_INSTRUCTION)
        _add_number_keys(question=question, labels=labels)
        # Playwright's sync API keeps an asyncio loop running in the main thread, and
        # prompt_toolkit cannot start its own loop there ('asyncio.run() cannot be called
        # from a running event loop'). A worker thread has no running loop.
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(question.ask).result()
    except Exception as exc:  # noqa: BLE001
        logger.debug(f'Interactive TUI unavailable ({exc}); falling back to numbered prompt.')
        return _fallback_numbered_prompt(
            prompt=prompt, labels=labels, values=values, back_key=back_key,
            header=fallback_header,
        )
    if result is None:
        raise KeyboardInterrupt(f'{prompt} cancelled')
    if result == _QUIT:
        raise KeyboardInterrupt('Quit')
    if result == _BACK:
        raise BackToSeasons('Back to season selection')
    return result


def render_seasons_table(seasons: Sequence[Season]) -> None:
    """Print a rich table of seasons.

    Args:
        seasons: Seasons to display.
    """
    console = Console()
    table = Table(title='Available seasons')
    table.add_column('#', justify='right', style='cyan', no_wrap=True)
    table.add_column('Label', style='white')
    for season in seasons:
        table.add_row(str(season.index), season.label)
    console.print(table)


def render_episodes_table(episodes: Sequence[Episode]) -> None:
    """Print a rich table of episodes.

    Args:
        episodes: Episodes to display.
    """
    console = Console()
    table = Table(title='Available episodes', expand=True)
    table.add_column('#', justify='right', style='cyan', no_wrap=True, min_width=3)
    table.add_column('Duration', style='yellow', no_wrap=True)
    table.add_column('Title', style='white', ratio=2)
    table.add_column('Description', style='dim white', ratio=3)
    for episode in episodes:
        table.add_row(
            str(episode.index),
            episode.duration,
            episode.title,
            episode.description,
        )
    console.print(table)


def pick_program(programs: Sequence[Program]) -> Program:
    """Prompt the user to choose an ERTFlix program via arrow-key select.

    ``q`` or ``0`` quit the script (raises ``KeyboardInterrupt``).

    Args:
        programs: Programs to choose from (must be non-empty).

    Returns:
        Program: The selected program.

    Raises:
        ValueError: If the programs list is empty.
    """
    if not programs:
        raise ValueError('pick_program called with an empty program list')
    labels = [f'{n}. {p.label} ({p.display_name})' for n, p in enumerate(programs, start=1)]
    labels.append('q/0. Quit')
    values: list[Program | str] = [*programs, _QUIT]
    return _select_or_fallback(  # type: ignore
        prompt='Choose program (q/0 to quit):',
        labels=labels,
        values=values,
        fallback_header='Programs to select from:',
    )


def pick_season(seasons: Sequence[Season]) -> Season:
    """Prompt the user to choose a season via arrow-key select.

    ``q`` or ``0`` quit the script (raises ``KeyboardInterrupt``).

    Args:
        seasons: Seasons to choose from (must be non-empty).

    Returns:
        Season: The selected season.

    Raises:
        ValueError: If the seasons list is empty.
    """
    if not seasons:
        raise ValueError('pick_season called with an empty season list')
    labels = [f'{s.index}. {s.label}' for s in seasons]
    labels.append('q/0. Quit')
    values: list[Season | str] = [*seasons, _QUIT]
    return _select_or_fallback(  # type: ignore
        prompt='Choose season (q/0 to quit):',
        labels=labels,
        values=values,
        fallback_header='Seasons to select from:',
    )


def pick_episode(episodes: Sequence[Episode], has_seasons: bool = True) -> Episode:
    """Prompt the user to choose an episode via arrow keys or by typing its number.

    ``q`` or ``0`` quit the script. ``s`` returns to the season selector
    (only when ``has_seasons`` is True).

    Args:
        episodes: Episodes to choose from (must be non-empty).
        has_seasons: Whether a season selector is available (shows ``s`` option).

    Returns:
        Episode: The selected episode.

    Raises:
        ValueError: If the episodes list is empty.
    """
    if not episodes:
        raise ValueError('pick_episode called with an empty episode list')
    labels = [f'{e.index}. {e.title}' for e in episodes]
    values: list[Episode | str] = [*episodes]
    if has_seasons:
        labels.append('s. Back to season selection')
        values.append(_BACK)
    labels.append('q/0. Quit')
    values.append(_QUIT)
    hint = 'q/0 quit, s seasons' if has_seasons else 'q/0 quit'
    return _select_or_fallback(  # type: ignore
        prompt=f'Choose episode ({hint}):',
        labels=labels,
        values=values,
        back_key='s' if has_seasons else None,
        fallback_header='Episodes to select from:',
    )
