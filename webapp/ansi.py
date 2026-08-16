"""ANSI SGR → HTML conversion for the web app's output log (UI-free, unit-tested).

The linter subprocess (rich tables, coloured New/Stable/held badges) emits ANSI SGR escape codes.
NiceGUI's log renders text verbatim, so the raw escapes show up as noise and the colour is lost.
This module turns the small SGR subset rich emits — bold / dim / italic / underline and the 8 basic
plus 8 bright foreground colours (and 24-bit truecolour, for completeness) — into safe
``<span style=…>`` HTML, HTML-escaping the text first so no output line can inject markup. Any other
escape sequence (cursor moves, OSC titles, …) is stripped.

A terminal palette is only meaningful relative to the background it is drawn on: SGR 30 (black) and
SGR 97 (bright white) sit at opposite ends, and whichever end matches the background disappears.
The palette is therefore chosen from the configured theme via :func:`palette_for` — see
:data:`DARK_PALETTE` and :data:`LIGHT_PALETTE`.
"""

import html
import re
from collections.abc import Sequence
from dataclasses import dataclass

from rich.cells import cell_len

# Emoji that rich may place in a table cell (e.g. freshness's ⛔ held-by / ⚠ build-from-source
# badges). Rich pads each cell assuming the glyph occupies ``cell_len`` monospace columns, but a
# browser renders the emoji glyph at its own width, so the trailing table border drifts. We wrap each
# match in an inline-block sized to exactly that many ``ch`` (see :func:`_render_glyphs`). Box-drawing
# characters (U+2500–U+257F) are deliberately outside these ranges — they render at 1 cell already.
_EMOJI_RE = re.compile(
    '(?:'
    '[\U0001f300-\U0001faff]'   # symbols & pictographs, supplemental, extended-A
    '|[☀-⛿]'          # miscellaneous symbols (⛔ ⚠ …)
    '|[✀-➿]'          # dingbats
    '|[⬀-⯿]'          # miscellaneous symbols & arrows
    '|[\U0001f1e6-\U0001f1ff]'  # regional-indicator letters
    ')️?'                  # optional VS16 emoji-presentation selector
)

# CSI SGR ("Select Graphic Rendition"): ESC '[' <params> 'm' — the only sequence we translate.
_SGR_RE = re.compile('\x1b\\[([0-9;]*)m')
# Any other escape sequence is dropped: OSC (ESC ']' … BEL/ST), other CSI (ESC '[' … final byte
# that is not 'm'), and lone two-byte escapes.
_OTHER_ESC_RE = re.compile(
    '\x1b\\][^\x07\x1b]*(?:\x07|\x1b\\\\)'   # OSC: ESC ] … (BEL | ST)
    '|\x1b\\[[0-9;?]*[A-Za-ln-z]'            # CSI ending in a final byte other than 'm'
    '|\x1b[@-Z\\\\-_]'                       # two-byte escape (ESC + single Fe byte)
)

@dataclass(frozen=True)
class AnsiPalette:
    """The foreground colours and dim strength used to render SGR codes on one log background."""

    fg: dict[int, str]
    dim_opacity: float


@dataclass
class _Style:
    """Mutable running SGR state as the converter walks one line of text."""

    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    fg: str | None = None

    def css(self, dim_opacity: float) -> str:
        """Render the active attributes as a CSS declaration string (empty when none active).

        Args:
            dim_opacity: Opacity applied for SGR 2 (dim), from the active palette.

        Returns:
            str: Semicolon-separated CSS declarations, or '' when the style is the default.
        """
        parts: list[str] = []
        if self.bold:
            parts.append('font-weight:bold')
        if self.dim:
            parts.append(f'opacity:{dim_opacity}')
        if self.italic:
            parts.append('font-style:italic')
        if self.underline:
            parts.append('text-decoration:underline')
        if self.fg is not None:
            parts.append(f'color:{self.fg}')
        return ';'.join(parts)


# 8 basic + 8 bright foreground colours for a DARK log background (the shipped default, bg #1e1e1e).
# Every entry clears WCAG AA (4.5:1) against #1e1e1e — the un-brightened VS Code basics do not (red
# 3.2:1, cyan 3.1:1), and black/white/bright-white would vanish outright, so the basic slots borrow
# the bright hues and the bright slots are lifted further. Ordering is preserved: each bright colour
# stays lighter than its basic counterpart.
DARK_PALETTE: AnsiPalette = AnsiPalette(
    fg={
        30: '#949494', 31: '#ff7b72', 32: '#23d18b', 33: '#e5c07b',
        34: '#79c0ff', 35: '#d670d6', 36: '#29b8db', 37: '#e5e5e5',
        90: '#a8a8a8', 91: '#ffa198', 92: '#56d364', 93: '#f5f543',
        94: '#a5d6ff', 95: '#f0a0f0', 96: '#6ee7f0', 97: '#f5f5f5',
    },
    # 0.7 dropped dim grey to ~2.5:1 on the dark background; 0.85 keeps every dimmed entry readable.
    dim_opacity=0.85,
)

# The same palette for a LIGHT log background (the original VS Code-derived table, which was tuned
# for light): here it is black that must stay black and white that must be darkened to be seen.
LIGHT_PALETTE: AnsiPalette = AnsiPalette(
    fg={
        30: '#000000', 31: '#cd3131', 32: '#0dbc79', 33: '#b58900',
        34: '#2472c8', 35: '#bc3fbc', 36: '#0e7490', 37: '#3b3b3b',
        90: '#767676', 91: '#f14c4c', 92: '#23d18b', 93: '#c19c00',
        94: '#3b8eea', 95: '#d670d6', 96: '#11a8cd', 97: '#000000',
    },
    dim_opacity=0.7,
)


def palette_for(dark: bool) -> AnsiPalette:
    """Return the ANSI palette that stays legible on the configured log background.

    Args:
        dark: Whether the log is drawn on a dark background (``ThemeConfig.dark``).

    Returns:
        AnsiPalette: :data:`DARK_PALETTE` when dark, else :data:`LIGHT_PALETTE`.
    """
    return DARK_PALETTE if dark else LIGHT_PALETTE


def ansi_to_html(text: str, palette: AnsiPalette = DARK_PALETTE) -> str:
    """Convert one line's ANSI SGR escapes into HTML spans, HTML-escaping the text.

    Args:
        text: A single output line that may contain ANSI SGR escape codes.
        palette: The colours to render SGR foreground codes with; defaults to the dark-background
            palette, matching the shipped default theme.

    Returns:
        str: HTML with the styled runs wrapped in ``<span style=…>`` and all text HTML-escaped.
    """
    text = _OTHER_ESC_RE.sub('', text)
    style = _Style()
    out: list[str] = []
    pos = 0
    for match in _SGR_RE.finditer(text):
        chunk = text[pos:match.start()]
        if chunk:
            out.append(_wrap(chunk=chunk, style=style, palette=palette))
        codes = [int(part) for part in match.group(1).split(';') if part != ''] or [0]
        _apply_codes(style=style, codes=codes, palette=palette)
        pos = match.end()
    tail = text[pos:]
    if tail:
        out.append(_wrap(chunk=tail, style=style, palette=palette))
    return ''.join(out)


def lines_to_html(lines: Sequence[str], css_class: str,
                  palette: AnsiPalette = DARK_PALETTE) -> str:
    """Render a batch of output lines as one HTML fragment, one wrapped ``div`` per line.

    Lets the caller commit a whole burst of output to the page as a single element instead of one
    element per line; each line keeps its own block so the per-line wrapping CSS still applies.

    Args:
        lines: The raw output lines (each may contain ANSI SGR escape codes).
        css_class: Class applied to each line's wrapping ``div``.
        palette: The colours to render SGR foreground codes with.

    Returns:
        str: The concatenated per-line ``div`` elements, with all text HTML-escaped.
    """
    return ''.join(
        f'<div class="{css_class}">{ansi_to_html(text=line, palette=palette)}</div>'
        for line in lines
    )


def _wrap(chunk: str, style: _Style, palette: AnsiPalette) -> str:
    """Render a text run to HTML (escaped, emoji fixed-width) and apply the active SGR style.

    Args:
        chunk: Raw (unescaped) text run.
        style: The active SGR state for this run.
        palette: The active palette (supplies the dim opacity).

    Returns:
        str: The rendered run, wrapped in a colour/attribute ``<span>`` only when a style applies.
    """
    inner = _render_glyphs(chunk=chunk)
    css = style.css(dim_opacity=palette.dim_opacity)
    if css:
        return f'<span style="{css}">{inner}</span>'
    return inner


def _render_glyphs(chunk: str) -> str:
    """HTML-escape a run, pinning each emoji to the monospace-cell width rich reserved for it.

    Rich lays out its tables assuming an emoji occupies ``cell_len`` terminal columns; wrapping the
    glyph in a ``display:inline-block`` of exactly that many ``ch`` reproduces that width in the
    browser so the surrounding table borders stay aligned.

    Args:
        chunk: Raw (unescaped) text run, possibly containing emoji.

    Returns:
        str: HTML with the text escaped and each emoji wrapped in a fixed-width span.
    """
    out: list[str] = []
    pos = 0
    for match in _EMOJI_RE.finditer(chunk):
        out.append(html.escape(chunk[pos:match.start()]))
        glyph = match.group(0)
        out.append(
            f'<span style="display:inline-block;width:{cell_len(glyph)}ch;text-align:center">'
            f'{html.escape(glyph)}</span>'
        )
        pos = match.end()
    out.append(html.escape(chunk[pos:]))
    return ''.join(out)


def _apply_codes(style: _Style, codes: list[int], palette: AnsiPalette) -> None:
    """Mutate the running style in place for a sequence of SGR parameter codes.

    Args:
        style: The running SGR state to update.
        codes: The integer parameters from one SGR escape (already split on ';').
        palette: The active palette supplying the foreground colours.
    """
    index = 0
    while index < len(codes):
        code = codes[index]
        if code in (38, 48):  # extended colour selector — consume its sub-parameters.
            index += _consume_extended_color(style=style, codes=codes, index=index)
            continue
        _apply_code(style=style, code=code, palette=palette)
        index += 1


def _consume_extended_color(style: _Style, codes: list[int], index: int) -> int:
    """Handle a 38/48 extended-colour run; set the foreground for truecolour, skip 256-colour.

    Only 24-bit truecolour (``38;2;r;g;b``) is mapped exactly; 256-colour (``38;5;n``) params are
    consumed but not translated (rich emits basic 16-colour codes here). Background (48) is ignored.

    Args:
        style: The running SGR state to update.
        codes: The full parameter list.
        index: Position of the 38/48 selector within ``codes``.

    Returns:
        int: How many parameters to advance past (the selector plus its consumed sub-parameters).
    """
    selector = codes[index]
    mode = codes[index + 1] if index + 1 < len(codes) else None
    if mode == 2 and index + 4 < len(codes):
        if selector == 38:
            style.fg = f'#{codes[index + 2]:02x}{codes[index + 3]:02x}{codes[index + 4]:02x}'
        return 5
    if mode == 5 and index + 2 < len(codes):
        return 3
    return 1


def _apply_code(style: _Style, code: int, palette: AnsiPalette) -> None:
    """Apply a single, non-extended SGR code to the running style.

    Args:
        style: The running SGR state to update.
        code: One SGR parameter code (0 reset, 1 bold, 3 italic, 31 red, …).
        palette: The active palette supplying the foreground colours.
    """
    if code == 0:
        style.bold = style.dim = style.italic = style.underline = False
        style.fg = None
    elif code == 1:
        style.bold = True
    elif code == 2:
        style.dim = True
    elif code == 3:
        style.italic = True
    elif code == 4:
        style.underline = True
    elif code == 22:
        style.bold = style.dim = False
    elif code == 23:
        style.italic = False
    elif code == 24:
        style.underline = False
    elif code == 39:
        style.fg = None
    elif code in palette.fg:
        style.fg = palette.fg[code]
