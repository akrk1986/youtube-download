"""Browser-automation helpers that obtain ERTFlix token URLs interactively.

Modules:
    errors: Exception hierarchy.
    api_metadata: Official season/episode numbers + broadcast dates from the ERTFlix API.
    browser_session: Playwright lifecycle and token interception.
    season_scraper: Season discovery and selection.
    episode_scraper: Episode DOM scraping and debug DOM dump.
    player_scraper: Play-button click and episode info extraction.
    programs: Known programs for the program menu.
    cli_prompts: Rich tables + questionary select menus.
    handoff: Subprocess hand-off to main-yt-dlp.py.
"""
from funcs_ertflix_automation.api_metadata import ApiEpisode, ApiMetadataStore
from funcs_ertflix_automation.browser_session import (DEFAULT_PROFILE_DIR,
                                                      TOKEN_URL_FRAGMENT,
                                                      BrowserSession)
from funcs_ertflix_automation.cli_prompts import (pick_episode, pick_program,
                                                  pick_season,
                                                  render_episodes_table,
                                                  render_seasons_table)
from funcs_ertflix_automation.episode_scraper import (Episode,
                                                      describe_episode_order,
                                                      discover_episodes,
                                                      dump_debug_dom)
from funcs_ertflix_automation.player_scraper import click_episode_play
from funcs_ertflix_automation.season_scraper import (ASSET_CARD_SELECTOR,
                                                     PLAY_BUTTON_IN_CARD_SELECTOR,
                                                     SEASON_BUTTON_SELECTORS,
                                                     Season, discover_seasons,
                                                     select_season)
from funcs_ertflix_automation.errors import (BackToSeasons,
                                             BrowserLaunchFailed,
                                             ErtflixAutomationError,
                                             NoSeasonsOrEpisodesFound,
                                             TokenCaptureTimeout)
from funcs_ertflix_automation.programs import (KNOWN_PROGRAMS, Program,
                                               find_program, resolve_program)
from funcs_ertflix_automation.handoff import build_ytdlp_argv, hand_off_to_ytdlp

__all__ = [
    'DEFAULT_PROFILE_DIR',
    'TOKEN_URL_FRAGMENT',
    'ASSET_CARD_SELECTOR',
    'PLAY_BUTTON_IN_CARD_SELECTOR',
    'SEASON_BUTTON_SELECTORS',
    'BrowserSession',
    'ApiEpisode',
    'ApiMetadataStore',
    'KNOWN_PROGRAMS',
    'Program',
    'find_program',
    'resolve_program',
    'pick_program',
    'Season',
    'Episode',
    'ErtflixAutomationError',
    'BackToSeasons',
    'BrowserLaunchFailed',
    'NoSeasonsOrEpisodesFound',
    'TokenCaptureTimeout',
    'discover_seasons',
    'select_season',
    'discover_episodes',
    'describe_episode_order',
    'click_episode_play',
    'dump_debug_dom',
    'render_seasons_table',
    'render_episodes_table',
    'pick_season',
    'pick_episode',
    'build_ytdlp_argv',
    'hand_off_to_ytdlp',
]
