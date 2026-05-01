"""Exception hierarchy for ERTFlix series browser-automation."""


class ErtflixAutomationError(Exception):
    """Base exception for ERTFlix browser-automation errors."""


class BrowserLaunchFailed(ErtflixAutomationError):
    """Raised when Playwright cannot launch the Chromium browser."""


class NoSeasonsOrEpisodesFound(ErtflixAutomationError):
    """Raised when no season buttons or episode cards can be located on the page."""


class TokenCaptureTimeout(ErtflixAutomationError):
    """Raised when the token API URL is not observed within the timeout window."""


class BackToSeasons(ErtflixAutomationError):
    """Raised when the user requests to return to the season selection menu."""
