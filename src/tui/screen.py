"""Resizable curses interface launched by ``run_screen``."""

from __future__ import annotations

import sys
from contextlib import suppress
from dataclasses import dataclass
from math import ceil, isfinite
from typing import Dict, List

try:
    import curses
except ImportError:
    curses = None

from .formatters import Line, TABS, UNKNOWN, sections
from .layout import (
    Row,
    cell_width,
    diagnostic_rows,
    pack_fields,
    page,
    tab_body,
)
from .. import __version__
from ..monitor import Monitor

_STATUS_TONES = {
    "ONLINE": "good",
    "UPDATING": "warn",
    "API ERROR": "bad",
    "CONNECTION ERROR": "bad",
    "RATE LIMITED": "warn",
}
_ASCII_GLYPHS = str.maketrans("╭╮╰╯│─█░·—…", "++++|-#.:-.")


@dataclass
class _Navigation:
    """Active tab and scroll range for the current frame."""

    tab: int = 0
    offset: int = 0
    last: int = 0


class TerminalUnavailable(RuntimeError):
    """The fullscreen mode cannot start in the current terminal."""


def _duration(delay: float) -> str:
    if not isfinite(delay):
        return "Deferred"
    minutes, seconds = divmod(ceil(delay), 60)
    return f"{minutes:02}:{seconds:02}"


def _tabs(tab: str, width: int) -> List[Row]:
    """Retain the active tab label when space is limited."""
    tabs = [
        Line(f"[{name}]", "active") if name == tab else Line(name)
        for name in TABS
    ]
    rows = pack_fields(tabs, width)
    if len(rows) == 1:
        return rows
    return pack_fields([Line(f"[{tab}]", "active"), Line("Tab Views")], width)


def _headings(
    monitor: Monitor, tab: str, countdown: str, width: int
) -> List[Row]:
    """Pack status and timing above the tab row and any diagnostic text."""
    flags = [monitor.status]
    if monitor.changed:
        flags.append("IP CHANGED")
    if monitor.is_stale:
        flags.append("STALE")
    snapshot = monitor.snapshot
    updated = (
        snapshot.received_at.strftime("%H:%M:%S UTC") if snapshot else "—"
    )
    fields = [
        Line(f"iprate {__version__}", "accent"),
        Line(f"IPv4 {monitor.address or UNKNOWN}", "value"),
        Line(f"[{' · '.join(flags)}]", _STATUS_TONES.get(monitor.status, "")),
        Line(f"Updated {updated}", "muted"),
        Line(
            f"Next {countdown} / Interval {_duration(monitor.interval)}",
            "muted",
        ),
    ]
    headings = pack_fields(fields, width) + _tabs(tab, width)
    if snapshot and monitor.address != snapshot.address:
        stale = Line(f"STALE data for {snapshot.address}", "warn")
        headings.extend(pack_fields([stale], width))
    if monitor.problem:
        headings.extend(diagnostic_rows(Line(monitor.problem, "warn"), width))
    return headings


def _keys(width: int, scrolls: bool) -> Row:
    """Fit the key hints on one row while keeping the exit key visible."""
    scroll = "  Up/Down Scroll" if scrolls else ""
    full = f"Tab/Shift+Tab Views{scroll}  +/- Interval  r Refresh  q Quit"
    if cell_width(full) <= width:
        return [Line(full, "muted")]
    if width >= len("Tab  Up/Dn  +/-  r  q"):
        return [Line("Tab  Up/Dn  +/-  r  q", "muted")]
    return [Line("q Quit", "muted")]


def _palette() -> Dict[str, int]:
    """Use textual states with optional colors on capable terminals."""
    styles = {
        "column": curses.A_BOLD | curses.A_UNDERLINE,
        "value": curses.A_BOLD,
        "active": curses.A_BOLD | curses.A_REVERSE,
        "accent": curses.A_BOLD,
        "network": curses.A_BOLD,
        "classify": curses.A_BOLD,
    }
    if curses.has_colors():
        orange = 208
        warning = orange if curses.COLORS > orange else curses.COLOR_YELLOW
        colors = (
            ("good", curses.COLOR_GREEN),
            ("warn", warning),
            ("bad", curses.COLOR_RED),
            ("accent", curses.COLOR_CYAN),
            ("network", curses.COLOR_MAGENTA),
            ("classify", curses.COLOR_GREEN),
        )
        try:
            curses.use_default_colors()
            for index, (role, color) in enumerate(colors, 1):
                curses.init_pair(index, color, -1)
                styles[role] = curses.color_pair(index) | styles.get(role, 0)
        except curses.error:
            pass
    return styles


def _fallback_text(content: str, encoding: str) -> str:
    """Preserve terminal columns when an encoding lacks a character."""
    visible = []
    for char in content.translate(_ASCII_GLYPHS):
        try:
            char.encode(encoding)
        except UnicodeEncodeError:
            char = "?" * cell_width(char)
        visible.append(char)
    return "".join(visible)


def _paint(
    window: curses.window, rows: List[Row], styles: Dict[str, int]
) -> None:
    """Draw the occupied rows from the top, preserving field colors."""
    encoding = window.encoding
    ascii_art = encoding.lower().replace("-", "") != "utf8"
    for index, row in enumerate(rows):
        column = 0
        for part in row:
            text = (
                _fallback_text(part.text, encoding) if ascii_art else part.text
            )
            window.addstr(index, column, text, styles.get(part.tone, 0))
            column += cell_width(part.text)


def _draw(
    window: curses.window,
    monitor: Monitor,
    body: List[Row],
    nav: _Navigation,
    countdown: str,
    styles: Dict[str, int],
) -> None:
    """Render just the header, visible data, and controls."""
    height, width = window.getmaxyx()
    tab = TABS[nav.tab]
    header = _headings(monitor, tab, countdown, width)
    space = height - len(header) - 1
    window.erase()
    if width <= len("q Quit") or space < 1:
        if height and width > 1:
            window.addnstr(0, 0, "Enlarge terminal (q quits)", width - 1)
        return

    visible, nav.offset, nav.last = page(body, space, nav.offset)
    _paint(window, header + visible + [_keys(width - 1, nav.last > 0)], styles)


def _handle(key: int, nav: _Navigation, monitor: Monitor) -> None:
    """Apply a navigation or refresh key to the active session."""
    tab_step = {9: 1, curses.KEY_BTAB: -1}.get(key)
    scroll_step = {curses.KEY_DOWN: 1, curses.KEY_UP: -1}.get(key)
    interval_step = {ord("+"): -1, ord("-"): 1}.get(key)
    if tab_step is not None:
        nav.tab = (nav.tab + tab_step) % len(TABS)
        nav.offset = 0
    elif scroll_step is not None:
        nav.offset = min(nav.last, max(0, nav.offset + scroll_step))
    elif key in (curses.KEY_HOME, curses.KEY_END):
        nav.offset = 0 if key == curses.KEY_HOME else nav.last
    elif interval_step is not None:
        monitor.change_interval(interval_step)
    elif key in (ord("r"), ord("R")):
        monitor.refresh()


def _loop(window: curses.window) -> None:
    """Refresh the screen after state, input, or terminal size changes."""
    with suppress(curses.error):
        curses.curs_set(0)
    window.timeout(150)
    styles = _palette()
    monitor = Monitor()
    nav = _Navigation()
    frame = None
    layout = None
    body: List[Row] = []

    key = -1
    while key not in (ord("q"), ord("Q")):
        _handle(key, nav, monitor)
        monitor.poll()
        snapshot = monitor.snapshot
        countdown = (
            "Updating" if monitor.busy else _duration(monitor.remaining)
        )
        size = window.getmaxyx()
        current_layout = id(snapshot), nav.tab, size[1]
        if current_layout != layout:
            tab = TABS[nav.tab]
            body = tab_body(sections(snapshot, tab), tab, size[1])
            layout = current_layout
        current = (
            size[0],
            current_layout,
            nav.offset,
            monitor.address,
            monitor.status,
            monitor.changed,
            monitor.problem,
            countdown,
            monitor.interval,
        )
        if current != frame:
            _draw(window, monitor, body, nav, countdown, styles)
            window.refresh()
            frame = current

        key = window.getch()


def run_screen() -> None:
    """Run the interactive session and let curses restore the terminal."""
    if curses is None:
        raise TerminalUnavailable("Python curses support is required.")
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise TerminalUnavailable("Interactive mode requires a terminal.")
    try:
        curses.wrapper(_loop)
    except curses.error as error:
        message = f"Cannot use this terminal: {error}"
        raise TerminalUnavailable(message) from error
