"""
Parsers for the engine-to-GUI half of the UCI protocol.

Every parser takes a single raw line. It returns ``None`` if the line is of another kind, and raises
:class:`ProtocolError` if the line is of the expected kind but violates the grammar.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final

__all__ = [
    "ENGINE_COMMANDS",
    "NULL_MOVES",
    "BestMove",
    "IdLine",
    "InfoLine",
    "LineKind",
    "OptionSpec",
    "OptionType",
    "ProtocolError",
    "Score",
    "classify",
    "is_lan_move",
    "keyword_of",
    "parse_bestmove",
    "parse_id",
    "parse_info",
    "parse_option",
]

#: Commands an engine may send to a GUI.
ENGINE_COMMANDS: Final[frozenset[str]] = frozenset(
    {"id", "uciok", "readyok", "bestmove", "copyprotection", "registration", "info", "option"}
)

#: Move tokens that stand for "no move".
NULL_MOVES: Final[frozenset[str]] = frozenset({"0000", "(none)", "none", "null"})

_LAN_MOVE_RE: Final[re.Pattern[str]] = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")


class ProtocolError(ValueError):
    """A line uses a known UCI keyword but breaks its grammar."""


class LineKind(StrEnum):
    """Kind of an engine output line."""

    ID = "id"
    UCIOK = "uciok"
    READYOK = "readyok"
    BESTMOVE = "bestmove"
    COPYPROTECTION = "copyprotection"
    REGISTRATION = "registration"
    INFO = "info"
    OPTION = "option"
    EMPTY = "empty"
    UNKNOWN = "unknown"


class OptionType(StrEnum):
    """The five UCI option types."""

    CHECK = "check"
    SPIN = "spin"
    COMBO = "combo"
    BUTTON = "button"
    STRING = "string"


def keyword_of(line: str) -> str | None:
    """
    The first engine command keyword in the line, skipping unrecognized leading tokens.

    ``None`` if the line carries no engine command keyword at all.
    """
    for token in line.split():
        if token in ENGINE_COMMANDS:
            return token
    return None


def classify(line: str) -> LineKind:
    """Kind of the line: its first engine command keyword, or ``EMPTY``/``UNKNOWN``."""
    if not line.strip():
        return LineKind.EMPTY
    keyword = keyword_of(line)
    return LineKind(keyword) if keyword is not None else LineKind.UNKNOWN


def is_lan_move(token: str) -> bool:
    """Whether the token is a move in the long algebraic notation UCI uses (null moves excluded)."""
    return bool(_LAN_MOVE_RE.match(token))


def _payload(line: str, keyword: str) -> list[str] | None:
    """Tokens following the given keyword, or ``None`` if the line is of another kind."""
    tokens = line.split()
    for index, token in enumerate(tokens):
        if token in ENGINE_COMMANDS:
            return tokens[index + 1 :] if token == keyword else None
    return None


@dataclass(frozen=True, slots=True)
class IdLine:
    """One ``id`` line: a key (``name``, ``author``, ...) and its free-form value."""

    key: str
    value: str


def parse_id(line: str) -> IdLine | None:
    """Parse an ``id`` line."""
    tokens = _payload(line, "id")
    if tokens is None:
        return None
    if len(tokens) < 2:
        raise ProtocolError(f"id line needs a key and a value: {line!r}")
    return IdLine(key=tokens[0], value=" ".join(tokens[1:]))


@dataclass(frozen=True, slots=True)
class OptionSpec:
    """One ``option`` line: an engine-settable option and its declared domain."""

    name: str
    type: OptionType
    default: str | None = None
    min: int | None = None
    max: int | None = None
    var: tuple[str, ...] = ()

    def warnings(self) -> tuple[str, ...]:
        """Ways in which this declaration is thinner than the spec asks, while staying usable."""
        problems: list[str] = []
        if self.type is OptionType.SPIN and (self.min is None or self.max is None):
            problems.append("spin option has no min/max")
        if self.type is OptionType.STRING and self.default is None:
            problems.append("string option has no default")
        return tuple(problems)

    def issues(self) -> tuple[str, ...]:
        """Ways in which this declaration contradicts the UCI spec; empty when it conforms."""
        problems: list[str] = []
        match self.type:
            case OptionType.CHECK:
                if self.default is None:
                    problems.append("check option has no default")
                elif self.default not in ("true", "false"):
                    problems.append(f"check option default is {self.default!r}, not true/false")
            case OptionType.SPIN:
                if self.default is None:
                    problems.append("spin option has no default")
                elif not _is_int(self.default):
                    problems.append(f"spin option default is not an integer: {self.default!r}")
                elif self.min is not None and self.max is not None:
                    if self.min > self.max:
                        problems.append(f"spin option has min {self.min} > max {self.max}")
                    if not self.min <= int(self.default) <= self.max:
                        problems.append(f"spin option default {self.default} outside [{self.min}, {self.max}]")
            case OptionType.COMBO:
                if not self.var:
                    problems.append("combo option has no var values")
                if self.default is None:
                    problems.append("combo option has no default")
                elif self.var and self.default not in self.var:
                    problems.append(f"combo option default {self.default!r} is not one of its var values")
            case OptionType.BUTTON:
                if self.default is not None or self.min is not None or self.max is not None or self.var:
                    problems.append("button option carries a default/min/max/var")
            case _:
                pass
        return tuple(problems)


def _is_int(text: str) -> bool:
    try:
        int(text)
    except ValueError:
        return False
    return True


_OPTION_VALUE_KEYWORDS: Final[frozenset[str]] = frozenset({"default", "min", "max", "var"})


def parse_option(line: str) -> OptionSpec | None:
    """
    Parse an ``option`` line.

    The option name spans everything between ``name`` and ``type``; a value spans everything up to the next
    ``default``/``min``/``max``/``var`` keyword.
    """
    tokens = _payload(line, "option")
    if tokens is None:
        return None
    if not tokens or tokens[0] != "name":
        raise ProtocolError(f"option line does not start with 'name': {line!r}")
    try:
        type_at = tokens.index("type")
    except ValueError:
        raise ProtocolError(f"option line has no 'type': {line!r}") from None

    name = " ".join(tokens[1:type_at])
    if not name:
        raise ProtocolError(f"option line has an empty name: {line!r}")
    if type_at + 1 >= len(tokens):
        raise ProtocolError(f"option line has no type value: {line!r}")
    try:
        option_type = OptionType(tokens[type_at + 1])
    except ValueError:
        raise ProtocolError(f"unknown option type {tokens[type_at + 1]!r}: {line!r}") from None

    values: dict[str, str] = {}
    variants: list[str] = []
    keyword: str | None = None
    words: list[str] = []

    def flush() -> None:
        if keyword is None:
            return
        value = " ".join(words)
        if keyword == "var":
            variants.append(value)
        else:
            values[keyword] = value

    for token in tokens[type_at + 2 :]:
        if token in _OPTION_VALUE_KEYWORDS:
            flush()
            keyword, words = token, []
        elif keyword is None:
            raise ProtocolError(f"unexpected token {token!r} after the option type: {line!r}")
        else:
            words.append(token)
    flush()

    for numeric in ("min", "max"):
        if numeric in values and not _is_int(values[numeric]):
            raise ProtocolError(f"option {numeric} is not an integer: {line!r}")

    return OptionSpec(
        name=name,
        type=option_type,
        default=values.get("default"),
        min=int(values["min"]) if "min" in values else None,
        max=int(values["max"]) if "max" in values else None,
        var=tuple(variants),
    )


@dataclass(frozen=True, slots=True)
class Score:
    """The ``score`` field of an ``info`` line; ``cp`` and ``mate`` are mutually exclusive."""

    cp: int | None = None
    mate: int | None = None
    bound: str | None = None


_INFO_INT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "depth",
        "seldepth",
        "time",
        "nodes",
        "multipv",
        "currmovenumber",
        "hashfull",
        "nps",
        "tbhits",
        "sbhits",
        "cpuload",
    }
)
_INFO_TOKEN_KEYS: Final[frozenset[str]] = frozenset({"currmove"})
_INFO_LIST_KEYS: Final[frozenset[str]] = frozenset({"pv", "refutation", "currline"})
_INFO_KEYS: Final[frozenset[str]] = _INFO_INT_KEYS | _INFO_TOKEN_KEYS | _INFO_LIST_KEYS | {"score", "string"}


@dataclass(frozen=True, slots=True)
class InfoLine:
    """One ``info`` line, as a mapping of its recognized fields; unknown tokens are dropped."""

    fields: dict[str, Any] = field(default_factory=dict)

    @property
    def depth(self) -> int | None:
        return self.fields.get("depth")

    @property
    def multipv(self) -> int | None:
        return self.fields.get("multipv")

    @property
    def nodes(self) -> int | None:
        return self.fields.get("nodes")

    @property
    def pv(self) -> tuple[str, ...]:
        return self.fields.get("pv", ())

    @property
    def score(self) -> Score | None:
        return self.fields.get("score")

    @property
    def string(self) -> str | None:
        return self.fields.get("string")


def parse_info(line: str) -> InfoLine | None:
    """Parse an ``info`` line."""
    tokens = _payload(line, "info")
    if tokens is None:
        return None

    fields: dict[str, Any] = {}
    index = 0
    while index < len(tokens):
        key = tokens[index]
        index += 1
        if key not in _INFO_KEYS:
            continue
        if key == "string":
            fields["string"] = " ".join(tokens[index:])
            break
        if key in _INFO_LIST_KEYS:
            start = index
            while index < len(tokens) and tokens[index] not in _INFO_KEYS:
                index += 1
            if start == index:
                raise ProtocolError(f"info {key} has no values: {line!r}")
            fields[key] = tuple(tokens[start:index])
            continue
        if key == "score":
            fields["score"], index = _parse_score(tokens, index, line)
            continue
        if index >= len(tokens):
            raise ProtocolError(f"info {key} has no value: {line!r}")
        value = tokens[index]
        index += 1
        if key in _INFO_INT_KEYS:
            if not _is_int(value):
                raise ProtocolError(f"info {key} is not an integer: {line!r}")
            fields[key] = int(value)
        else:
            fields[key] = value
    return InfoLine(fields=fields)


def _parse_score(tokens: list[str], index: int, line: str) -> tuple[Score, int]:
    """Parse the ``score`` sub-fields starting at the given index; returns the score and the next index."""
    cp: int | None = None
    mate: int | None = None
    bound: str | None = None
    while index < len(tokens):
        token = tokens[index]
        if token in ("cp", "mate"):
            if index + 1 >= len(tokens) or not _is_int(tokens[index + 1]):
                raise ProtocolError(f"info score {token} is not an integer: {line!r}")
            if token == "cp":
                cp = int(tokens[index + 1])
            else:
                mate = int(tokens[index + 1])
            index += 2
        elif token in ("lowerbound", "upperbound"):
            bound = token
            index += 1
        else:
            break
    if cp is None and mate is None:
        raise ProtocolError(f"info score has neither cp nor mate: {line!r}")
    return Score(cp=cp, mate=mate, bound=bound), index


@dataclass(frozen=True, slots=True)
class BestMove:
    """One ``bestmove`` line."""

    move: str
    ponder: str | None = None

    @property
    def is_null(self) -> bool:
        """Whether the engine reported that it has no move to make."""
        return self.move in NULL_MOVES


def parse_bestmove(line: str) -> BestMove | None:
    """Parse a ``bestmove`` line."""
    tokens = _payload(line, "bestmove")
    if tokens is None:
        return None
    if not tokens:
        raise ProtocolError(f"bestmove line has no move: {line!r}")
    move = tokens[0]
    ponder: str | None = None
    if len(tokens) > 1:
        if tokens[1] != "ponder":
            raise ProtocolError(f"unexpected token {tokens[1]!r} after the best move: {line!r}")
        if len(tokens) < 3:
            raise ProtocolError(f"bestmove ponder has no move: {line!r}")
        ponder = tokens[2]
    return BestMove(move=move, ponder=ponder)
