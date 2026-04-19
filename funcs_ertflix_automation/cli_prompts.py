"""Light TUI: rich tables for display + questionary selects for input."""
import logging
from typing import Sequence, TypeVar

import questionary
from rich.console import Console
from rich.table import Table

from funcs_ertflix_automation.dom_scraper import Episode, Season


logger = logging.getLogger(__name__)

T = TypeVar('T')


def _fallback_numbered_prompt(prompt: str, labels: Sequence[str],
                              values: Sequence[T]) -> T:
    """Plain numbered input prompt — used when questionary can't drive the console.

    Args:
        prompt: Text shown before the numbered input.
        labels: Display labels (one per value, same length as ``values``).
        values: The values parallel to ``labels``; the chosen value is returned.

    Returns:
        The value at the chosen index.
    """
    for idx, label in enumerate(labels, start=1):
        print(f'  {idx}. {label}')
    while True:
        raw = input(f'{prompt} [1-{len(values)}]: ').strip()
        if not raw:
            raise KeyboardInterrupt('Selection cancelled (empty input)')
        try:
            choice = int(raw)
        except ValueError:
            print(f'Please enter a number between 1 and {len(values)}.')
            continue
        if 1 <= choice <= len(values):
            return values[choice - 1]
        print(f'Out of range. Enter 1-{len(values)}.')


def _select_or_fallback(prompt: str, labels: Sequence[str],
                        values: Sequence[T],
                        use_search_filter: bool = False) -> T:
    """Use questionary if available, otherwise fall back to numbered input.

    Args:
        prompt: Prompt text.
        labels: Display labels parallel to ``values``.
        values: Values to choose from.
        use_search_filter: Pass through to questionary.select.

    Returns:
        The selected value.
    """
    choices = [questionary.Choice(title=label, value=value)
               for label, value in zip(labels, values)]
    try:
        result = questionary.select(
            prompt, choices=choices, use_search_filter=use_search_filter,
        ).ask()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f'Interactive TUI unavailable ({exc.__class__.__name__}); '
            'falling back to numbered prompt.'
        )
        return _fallback_numbered_prompt(
            prompt=prompt, labels=labels, values=values,
        )
    if result is None:
        raise KeyboardInterrupt(f'{prompt} cancelled')
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
    table = Table(title='Available episodes')
    table.add_column('#', justify='right', style='cyan', no_wrap=True)
    table.add_column('Episode ID', style='magenta', no_wrap=True)
    table.add_column('Title', style='white')
    for episode in episodes:
        table.add_row(str(episode.index), episode.episode_id, episode.title)
    console.print(table)


def pick_season(seasons: Sequence[Season]) -> Season:
    """Prompt the user to choose a season via arrow-key select.

    Args:
        seasons: Seasons to choose from (must be non-empty).

    Returns:
        Season: The selected season.
    """
    if not seasons:
        raise ValueError('pick_season called with an empty season list')
    labels = [f'{s.index}. {s.label}' for s in seasons]
    return _select_or_fallback(
        prompt='Choose season:', labels=labels, values=list(seasons),
    )


def pick_episode(episodes: Sequence[Episode]) -> Episode:
    """Prompt the user to choose an episode via arrow-key select + type-to-filter.

    Args:
        episodes: Episodes to choose from (must be non-empty).

    Returns:
        Episode: The selected episode.
    """
    if not episodes:
        raise ValueError('pick_episode called with an empty episode list')
    labels = [f'{e.index}. {e.episode_id} - {e.title}' for e in episodes]
    return _select_or_fallback(
        prompt='Choose episode (type to filter):',
        labels=labels,
        values=list(episodes),
        use_search_filter=True,
    )
