"""Season and episode metadata from the JSON the ERTFlix page loads.

The page fetches its season list and episode lists from ``api.ertflix.opentv.com``. Those
responses carry the official season/episode numbers and each episode's broadcast date, which
the page itself does not show. ``ApiMetadataStore`` collects them (fed by the browser session's
response hook) and answers lookups by season label and by episode id / title.

Three endpoints are used:

- ``/metadata/delivery/ERT/vod/series`` — the seasons: ref, ``SeasonNumber``, ``Title``.
- ``/metadata/v1/series/<ref>/mediacard`` — each season's newest episodes (loaded with the page).
- ``/metadata/delivery/v2/ERT/vod/editorials`` — every episode of one season (loaded when that
  season is clicked). Wins over the mediacard when both describe the same episode.
"""
import logging
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse

import arrow

API_HOST = 'api.ertflix.opentv.com'
# Broadcast times are UTC epoch seconds; ERTFlix airs in Greek time.
LOCAL_TZ = 'Europe/Athens'

_SERIES_PATH_RE = re.compile(r'/metadata/delivery/ERT/vod/series/?$')
_MEDIACARD_PATH_RE = re.compile(r'/metadata/v1/series/[^/]+/mediacard/?$')
_EDITORIALS_PATH_RE = re.compile(r'/metadata/delivery/v2/ERT/vod/editorials/?$')
# The mediacard prefixes some titles with the episode number: 'E5 ‧ A Tribute to ...'.
_MEDIACARD_TITLE_PREFIX_RE = re.compile(r'^E\d+\s*‧\s*')
# Season-button labels carry a 'Season' word the API titles may lack ('Season 2026 - 2027').
_SEASON_WORD_RE = re.compile(r'^(?:season|σεζόν|σεζον|κύκλος|κυκλος)\s+', re.IGNORECASE)
_SPACES_RE = re.compile(r'\s+')
# Errors a malformed API entry can raise while being read; such an entry is skipped.
_PARSE_ERRORS = (KeyError, TypeError, ValueError, arrow.parser.ParserError)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApiEpisode:
    """One episode as described by the ERTFlix API."""

    season_number: int
    episode_number: int
    title: str
    episode_id: str
    broadcast: arrow.Arrow | None

    @property
    def broadcast_date(self) -> str:
        """Return the broadcast date as ``YYYY-MM-DD`` in Greek time ('' when unknown)."""
        return self.broadcast.format('YYYY-MM-DD') if self.broadcast is not None else ''


class ApiMetadataStore:
    """Collect ERTFlix season/episode metadata from API responses and answer lookups."""

    def __init__(self) -> None:
        """Start with no data."""
        self._season_by_ref: dict[str, int] = {}
        self._season_by_label: dict[str, int] = {}
        self._episodes: dict[tuple[int, int], ApiEpisode] = {}
        self._from_editorials: set[tuple[int, int]] = set()
        self._key_by_id: dict[str, tuple[int, int]] = {}
        self._keys_by_title: dict[str, set[tuple[int, int]]] = {}

    @property
    def has_episodes(self) -> bool:
        """Return True once any episode data has been collected."""
        return bool(self._episodes)

    def add_response(self, url: str, body: object) -> None:
        """Take in one JSON response; responses from other endpoints are ignored.

        Args:
            url: The response URL.
            body: The parsed JSON body.
        """
        parsed = urlparse(url)
        if (parsed.hostname or '').lower() != API_HOST or not isinstance(body, dict):
            return
        try:
            if _SERIES_PATH_RE.search(parsed.path):
                self._add_series(body=body)
            elif _MEDIACARD_PATH_RE.search(parsed.path):
                self._add_mediacard(body=body)
            elif _EDITORIALS_PATH_RE.search(parsed.path):
                self._add_editorials(body=body)
        except _PARSE_ERRORS as exc:
            logger.debug(f'Could not parse ERTFlix metadata from {parsed.path}: {exc}')

    def season_number_for(self, label: str) -> int | None:
        """Return the official season number for a season-button label.

        Args:
            label: The button label, e.g. ``'Season 11'`` or ``'Season 2026 - 2027'``.

        Returns:
            int | None: The season number, or None when the label is not known.
        """
        return self._season_by_label.get(_normalize_season_label(label=label))

    def match(self, season_number: int | None, title: str, episode_id: str = '') -> ApiEpisode | None:
        """Find the API episode for a card on the page.

        Matches on ``episode_id`` first, then on the normalized title. A title shared by
        several episodes (e.g. two 'Holiday Special' parts) is not matched.

        Args:
            season_number: The selected season's official number (None = any season).
            title: The card's title.
            episode_id: The card's episode id ('' when unknown).

        Returns:
            ApiEpisode | None: The episode, or None when there is no unique match.
        """
        key = self._key_by_id.get(episode_id) if episode_id else None
        if key is not None and season_number in (None, key[0]):
            return self._episodes[key]
        keys = self._keys_by_title.get(_normalize_title(title=title), set())
        if season_number is not None:
            keys = {k for k in keys if k[0] == season_number}
        if len(keys) == 1:
            return self._episodes[next(iter(keys))]
        return None

    def _add_series(self, body: dict[str, object]) -> None:
        """Record season refs, numbers and titles from the ``vod/series`` response."""
        for season in _as_list(value=body['series']):
            try:
                number = self._add_season(season=season)
            except _PARSE_ERRORS as exc:
                logger.debug(f'Skipping malformed ERTFlix season entry: {exc!r}')
                continue
            logger.debug(f"ERTFlix season {number} {season.get('Title')!r}: "
                         f"ReverseSortOrder={season.get('ReverseSortOrder')}")

    def _add_mediacard(self, body: dict[str, object]) -> None:
        """Record each season's newest episodes from the series mediacard."""
        series = body['series']
        if not isinstance(series, dict):
            return
        for season in _as_list(value=series.get('seasons', [])):
            try:
                number = self._add_season(season=season)
            except _PARSE_ERRORS as exc:
                logger.debug(f'Skipping malformed ERTFlix mediacard season: {exc!r}')
                continue
            for item in _as_list(value=season.get('episodes', [])):
                try:
                    broadcast = item.get('broadcast') or {}
                    episode = ApiEpisode(
                        season_number=number,
                        episode_number=int(item['episodeNumber']),
                        title=_MEDIACARD_TITLE_PREFIX_RE.sub('', str(item['Title'])),
                        episode_id=str(item['id']),
                        broadcast=_to_local(epoch=broadcast.get('start')),
                    )
                except _PARSE_ERRORS as exc:
                    logger.debug(f'Skipping malformed ERTFlix mediacard episode: {exc!r}')
                    continue
                self._add_episode(episode=episode, from_editorials=False)

    def _add_editorials(self, body: dict[str, object]) -> None:
        """Record every episode of one season from the ``editorials`` response."""
        for item in _as_list(value=body['editorials']):
            try:
                season = item.get('SeasonNumber')
                number = int(season) if season is not None else self._season_by_ref[str(item['seasonRef'])]
                period = item.get('period') or {}
                episode = ApiEpisode(
                    season_number=number,
                    episode_number=int(item['EpisodeNumber']),
                    title=str(item['Title']),
                    episode_id=str(item['id']),
                    broadcast=_to_local(epoch=period.get('start')),
                )
            except _PARSE_ERRORS as exc:
                logger.debug(f'Skipping malformed ERTFlix episode entry: {exc!r}')
                continue
            self._add_episode(episode=episode, from_editorials=True)

    def _add_season(self, season: dict) -> int:
        """Record one season's ref and label, and return its official number.

        A missing ``SeasonNumber`` / ``id`` / ``Title`` (KeyError) or a non-numeric
        ``SeasonNumber`` (ValueError) propagates; callers skip that entry.

        Args:
            season: One season entry from the API.

        Returns:
            int: The season's official number.
        """
        number = int(season['SeasonNumber'])
        self._season_by_ref[str(season['id'])] = number
        self._season_by_label[_normalize_season_label(label=str(season['Title']))] = number
        return number

    def _add_episode(self, episode: ApiEpisode, from_editorials: bool) -> None:
        """Store an episode; an editorials entry replaces a mediacard one, never the reverse.

        Ids and titles from both sources point at the same episode, so a card can be
        matched by either.
        """
        key = (episode.season_number, episode.episode_number)
        if from_editorials or key not in self._from_editorials:
            self._episodes[key] = episode
        if from_editorials:
            self._from_editorials.add(key)
        self._key_by_id[episode.episode_id] = key
        self._keys_by_title.setdefault(_normalize_title(title=episode.title), set()).add(key)


def _as_list(value: object) -> list[dict]:
    """Return the dict items of a JSON list (anything else gives an empty list)."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _to_local(epoch: object) -> arrow.Arrow | None:
    """Convert UTC epoch seconds to Greek time (None when missing)."""
    if epoch in (None, ''):
        return None
    return arrow.get(float(str(epoch))).to(LOCAL_TZ)


def _normalize_title(title: str) -> str:
    """Normalize a title for matching: strip the 'E5 ‧ ' prefix, NFKC, casefold, collapse spaces."""
    text = _MEDIACARD_TITLE_PREFIX_RE.sub('', title.strip())
    return _SPACES_RE.sub(' ', unicodedata.normalize('NFKC', text)).casefold().strip()


def _normalize_season_label(label: str) -> str:
    """Normalize a season label: drop a leading 'Season' word, casefold, collapse spaces."""
    text = _SPACES_RE.sub(' ', unicodedata.normalize('NFKC', label)).strip()
    return _SEASON_WORD_RE.sub('', text).casefold()
