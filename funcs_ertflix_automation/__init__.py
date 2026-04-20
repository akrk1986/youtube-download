"""Browser-automation helpers that obtain ERTFlix token URLs interactively.

Modules:
    errors: Exception hierarchy.
    browser_session: Playwright lifecycle and token interception.
    dom_scraper: Season/episode discovery and Play-button click.
    cli_prompts: Rich tables + questionary select menus.
    handoff: Subprocess hand-off to main-yt-dlp.py.
"""
from funcs_ertflix_automation.browser_session import (DEFAULT_PROFILE_DIR,
                                                      TOKEN_URL_FRAGMENT,
                                                      BrowserSession)
from funcs_ertflix_automation.cli_prompts import (pick_episode, pick_season,
                                                  render_episodes_table,
                                                  render_seasons_table)
from funcs_ertflix_automation.dom_scraper import (ASSET_CARD_SELECTOR,
                                                  PLAY_BUTTON_IN_CARD_SELECTOR,
                                                  SEASON_BUTTON_SELECTORS,
                                                  Episode, Season,
                                                  click_episode_play,
                                                  discover_episodes,
                                                  discover_seasons,
                                                  dump_debug_dom,
                                                  select_season)
from funcs_ertflix_automation.errors import (BackToSeasons,
                                             BrowserLaunchFailed,
                                             ErtflixAutomationError,
                                             NoSeasonsOrEpisodesFound,
                                             TokenCaptureTimeout)
from funcs_ertflix_automation.handoff import build_ytdlp_argv, hand_off_to_ytdlp

__all__ = [
    'DEFAULT_PROFILE_DIR',
    'TOKEN_URL_FRAGMENT',
    'ASSET_CARD_SELECTOR',
    'PLAY_BUTTON_IN_CARD_SELECTOR',
    'SEASON_BUTTON_SELECTORS',
    'BrowserSession',
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
    'click_episode_play',
    'dump_debug_dom',
    'render_seasons_table',
    'render_episodes_table',
    'pick_season',
    'pick_episode',
    'build_ytdlp_argv',
    'hand_off_to_ytdlp',
]
