"""Light TUI: rich tables for display + questionary selects for input."""
import logging
from typing import Sequence, TypeVar

import questionary
from rich.console import Console
from rich.table import Table

from funcs_ertflix_automation.dom_scraper import Episode, Season
from funcs_ertflix_automation.errors import BackToSeasons


logger = logging.getLogger(__name__)

T = TypeVar('T')

_QUIT = '__quit__'
_BACK = '__back__'


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
        The value at the chosen index.
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


def _select_or_fallback(prompt: str, labels: Sequence[str],
                        values: Sequence[T],
                        use_search_filter: bool = False,
                        back_key: str | None = None,
                        fallback_header: str = '') -> T:
    """Use questionary if available, otherwise fall back to numbered input.

    Args:
        prompt: Prompt text.
        labels: Display labels parallel to ``values``.
        values: Values to choose from.
        use_search_filter: Pass through to questionary.select.
        back_key: Character that triggers back-to-seasons in the fallback prompt.
        fallback_header: Header line printed above the item list in fallback mode.

    Returns:
        The selected value.
    """
    choices = [questionary.Choice(title=label, value=value)
               for label, value in zip(labels, values)]
    try:
        result = questionary.select(
            prompt, choices=choices, use_search_filter=use_search_filter,
        ).ask()
    except Exception:  # noqa: BLE001
        logger.debug('Interactive TUI unavailable; falling back to numbered prompt.')
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


def pick_season(seasons: Sequence[Season]) -> Season:
    """Prompt the user to choose a season via arrow-key select.

    ``q`` or ``0`` quit the script (raises ``KeyboardInterrupt``).

    Args:
        seasons: Seasons to choose from (must be non-empty).

    Returns:
        Season: The selected season.
    """
    if not seasons:
        raise ValueError('pick_season called with an empty season list')
    labels = [f'{s.index}. {s.label}' for s in seasons]
    labels.append('q/0. Quit')
    values: list[Season | str] = [*seasons, _QUIT]
    return _select_or_fallback(  # type: ignore[return-value]
        prompt='Choose season (q/0 to quit):',
        labels=labels,
        values=values,
        fallback_header='Seasons to select from:',
    )


def pick_episode(episodes: Sequence[Episode], has_seasons: bool = True) -> Episode:
    """Prompt the user to choose an episode via arrow-key select + type-to-filter.

    ``q`` or ``0`` quit the script. ``s`` returns to the season selector
    (only when ``has_seasons`` is True).

    Args:
        episodes: Episodes to choose from (must be non-empty).
        has_seasons: Whether a season selector is available (shows ``s`` option).

    Returns:
        Episode: The selected episode.
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
    return _select_or_fallback(  # type: ignore[return-value]
        prompt=f'Choose episode — type to filter ({hint}):',
        labels=labels,
        values=values,
        use_search_filter=True,
        back_key='s' if has_seasons else None,
        fallback_header='Episodes to select from:',
    )
