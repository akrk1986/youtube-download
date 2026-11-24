"""Known ERTFlix programs offered in the program menu, and URL/label resolution."""
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Program:
    """One ERTFlix program the series browser can open without a URL.

    ``oldest_first`` is the order the program's page lists episodes in (True = episode 1
    at the top; None = not known, guessed from 'Episode N' titles). It only numbers
    episodes that are missing from the ERTFlix data.
    """

    label: str
    display_name: str
    url: str
    oldest_first: bool | None = None


# Menu order. Nykhta Stasou is last because its seasons have ended.
KNOWN_PROGRAMS: list[Program] = [
    Program(label='Parea', display_name='Παρέα',
            url='https://www.ertflix.gr/#/details/ERT_PS054741_E0', oldest_first=False),
    Program(label='To Alati tis Gis', display_name='Το Αλάτι της Γης',
            url='https://www.ertflix.gr/#/details/ERT_DS018967_E0', oldest_first=True),
    Program(label='Nykhta Stasou', display_name='Νύχτα Στάσου',
            url='https://www.ertflix.gr/#/details/ERT_PS054659_E0'),
]


def find_program(label: str, programs: Sequence[Program] = tuple(KNOWN_PROGRAMS)) -> Program | None:
    """Return the program whose label matches, ignoring case.

    Args:
        label: Program label to look up (e.g. ``'parea'``).
        programs: Programs to search.

    Returns:
        Program | None: The matching program, or None when there is no match.
    """
    wanted = label.strip().casefold()
    for program in programs:
        if program.label.casefold() == wanted:
            return program
    return None


def resolve_program(series_url: str | None, program_label: str | None,
                    picker: Callable[[Sequence[Program]], Program],
                    programs: Sequence[Program] = tuple(KNOWN_PROGRAMS),
                    ) -> tuple[str, str | None, bool | None]:
    """Decide which page to open, which label to use for the title, and the episode order.

    - A URL was given: use it as-is, with ``program_label`` (may be None); the episode
      order comes from a known program with that label, else it is unknown.
    - No URL, but ``program_label`` names a known program: open that program.
    - Otherwise: ask ``picker`` to choose; an explicit ``program_label`` still wins as the label.

    Args:
        series_url: URL from the command line, or None.
        program_label: ``--program`` value, or None.
        picker: Menu function returning the chosen program.
        programs: Programs to offer / search.

    Returns:
        tuple[str, str | None, bool | None]: The page URL, the program label, and whether
        the page lists episodes oldest first (None = not known).
    """
    known = find_program(label=program_label, programs=programs) if program_label else None
    if series_url:
        return series_url, program_label, known.oldest_first if known is not None else None
    if known is not None:
        return known.url, known.label, known.oldest_first
    chosen = picker(programs)
    return chosen.url, program_label or chosen.label, chosen.oldest_first
