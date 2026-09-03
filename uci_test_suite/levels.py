"""The protocol layers the suite is organised in, and the ``--level`` selector grammar."""

import re
from enum import IntEnum
from typing import Final

__all__ = [
    "LEVEL_RANGE_SYNTAX",
    "MINIMUM_ENGINE",
    "Level",
    "format_levels",
    "parse_levels",
]

#: Human-readable form of what :func:`parse_levels` accepts.
LEVEL_RANGE_SYNTAX: Final[str] = "a level (2), an inclusive range (0-2), or a comma-separated list of both (0-2,5)"


class Level(IntEnum):
    """A layer of the UCI protocol, and the checks that speak for it."""

    PROCESS = 0
    HANDSHAKE = 1
    PLAY = 2
    SESSION = 3
    OPTIONAL = 4
    ROBUSTNESS = 5
    ACCEPTANCE = 6

    @property
    def tag(self) -> str:
        """Short form used in output, such as ``L3``."""
        return f"L{self.value}"

    @property
    def title(self) -> str:
        """Name of the layer, such as ``Session``."""
        return self.name.capitalize()

    @property
    def summary(self) -> str:
        """One line saying what the layer covers."""
        return _SUMMARIES[self]

    def __str__(self) -> str:
        return f"{self.tag} {self.title}"


_SUMMARIES: Final[dict[Level, str]] = {
    Level.PROCESS: "a well-behaved pipe citizen: starts, tolerates junk, quits cleanly",
    Level.HANDSHAKE: "uci/uciok, the engine identity, its option declarations, isready/readyok",
    Level.PLAY: "positions, timed searches, stop, and a legal bestmove every time",
    Level.SESSION: "a whole game session: ucinewgame, setoption, debug, the go limits, info lines",
    Level.OPTIONAL: "features an engine may decline; skipped unless it advertises them",
    Level.ROBUSTNESS: "unhappy paths: neither a crash nor a hang, and isready still answered",
    Level.ACCEPTANCE: "a mainstream UCI client (esca) drives the engine end to end",
}

#: The levels an engine must pass to be a UCI engine at all.
MINIMUM_ENGINE: Final[tuple[Level, ...]] = (Level.PROCESS, Level.HANDSHAKE, Level.PLAY)

_ITEM_RE: Final[re.Pattern[str]] = re.compile(r"^(\d+)(?:-(\d+))?$")


def parse_levels(text: str) -> frozenset[Level]:
    """
    The levels named by a selector such as ``2``, ``0-2`` or ``0-2,5``.

    Raises:
        ValueError: The selector is not of that shape, or names a level that does not exist.
    """
    selected: set[Level] = set()
    items = [item.strip() for item in text.split(",")]
    for item in items:
        match = _ITEM_RE.match(item)
        if match is None:
            raise ValueError(f"{item!r} is not {LEVEL_RANGE_SYNTAX}")
        low, high = _level(match.group(1)), _level(match.group(2) or match.group(1))
        if low > high:
            raise ValueError(f"range {item!r} counts down; write it as {high.value}-{low.value}")
        selected.update(Level(value) for value in range(low, high + 1))
    return frozenset(selected)


def _level(text: str) -> Level:
    try:
        return Level(int(text))
    except ValueError:
        raise ValueError(f"level {text} does not exist; levels are 0 to {max(Level).value}") from None


def format_levels(levels: frozenset[Level] | set[Level]) -> str:
    """The selected levels as a compact list of tags and ranges, such as ``L0-L2, L5``."""
    if not levels:
        return "none"
    ordered = sorted(levels)
    parts: list[str] = []
    start = previous = ordered[0]
    for level in ordered[1:]:
        if level == previous + 1:
            previous = level
            continue
        parts.append(_span(start, previous))
        start = previous = level
    parts.append(_span(start, previous))
    return ", ".join(parts)


def _span(start: Level, end: Level) -> str:
    return start.tag if start == end else f"{start.tag}-{end.tag}"
