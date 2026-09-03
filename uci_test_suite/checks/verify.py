"""Assertions shared by the checks; each one either passes quietly or raises :class:`CheckFailure`."""

from collections.abc import Callable, Sequence
from typing import Any, Final

import esca

from uci_test_suite.checks.base import CheckFailure
from uci_test_suite.checks.session import RawSession, SearchResult
from uci_test_suite.protocol import (
    BestMove,
    LineKind,
    ProtocolError,
    classify,
    is_lan_move,
    parse_bestmove,
    parse_id,
    parse_info,
    parse_option,
)
from uci_test_suite.transport import EngineDied, EngineTimeout

__all__ = [
    "malformed_lines",
    "move_details",
    "verify_move",
    "verify_responsive",
    "verify_single_bestmove",
]


def verify_responsive(session: RawSession, after: str, timeout: float | None = None) -> float:
    """Seconds the engine took to answer ``isready``; fails when it dies or stays silent."""
    try:
        return session.sync(timeout=timeout)
    except EngineTimeout:
        raise CheckFailure(f"engine stopped answering isready after {after}", after=after) from None
    except EngineDied as died:
        raise CheckFailure(f"engine died after {after}: {died}", after=after, returncode=died.returncode) from None


_PARSERS: Final[dict[LineKind, Callable[[str], object]]] = {
    LineKind.ID: parse_id,
    LineKind.OPTION: parse_option,
    LineKind.INFO: parse_info,
    LineKind.BESTMOVE: parse_bestmove,
}


def malformed_lines(lines: Sequence[str]) -> list[str]:
    """The given engine lines that use a UCI keyword but break its grammar, each with the reason."""
    broken: list[str] = []
    for text in lines:
        parser = _PARSERS.get(classify(text))
        if parser is None:
            continue
        try:
            parser(text)
        except ProtocolError as error:
            broken.append(f"{text} -- {error}")
    return broken


def verify_move(game: esca.Game, best: BestMove, where: str) -> esca.Move:
    """The best move as a move object; fails unless it is a LAN move that is legal in the given position."""
    fen = game.position.fen
    if best.is_null:
        raise CheckFailure(f"engine reports no move in {where}", bestmove=best.move, fen=fen)
    if not is_lan_move(best.move):
        raise CheckFailure(f"best move {best.move!r} is not long algebraic notation", bestmove=best.move, fen=fen)
    try:
        game.play(best.move)
    except ValueError:
        raise CheckFailure(f"best move {best.move} is illegal in {where}", bestmove=best.move, fen=fen) from None
    move = game.moves[-1]
    game.undo()
    return move


def verify_single_bestmove(result: SearchResult) -> None:
    """Fails unless the search produced exactly one ``bestmove`` and no unparsable lines."""
    if result.extra_bestmoves:
        raise CheckFailure(
            f"engine sent {1 + len(result.extra_bestmoves)} bestmove lines for one search",
            extra_bestmoves=list(result.extra_bestmoves),
        )
    if result.invalid_lines:
        raise CheckFailure(
            f"engine sent {len(result.invalid_lines)} unparsable lines during the search",
            invalid_lines=[f"{line} -- {reason}" for line, reason in result.invalid_lines],
        )


def move_details(game: esca.Game, result: SearchResult, move: esca.Move) -> dict[str, Any]:
    """The usual per-search details of a check result."""
    return {
        "fen": game.position.fen,
        "bestmove": result.bestmove.move,
        "bestmove_san": game.move_to_san(move),
        "ponder": result.bestmove.ponder,
        "elapsed_s": round(result.elapsed, 3),
        "info_lines": len(result.infos),
    }
