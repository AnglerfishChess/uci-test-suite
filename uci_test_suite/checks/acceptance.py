"""Checks that a mainstream UCI client — ``python-chess`` — can drive the engine end to end."""

import chess
import chess.engine

from uci_test_suite.checks.base import CheckFailure, Outcome
from uci_test_suite.checks.registry import acceptance_check
from uci_test_suite.checks.session import AcceptanceSession


@acceptance_check("pychess_handshake")
def check_pychess_handshake(session: AcceptanceSession) -> Outcome:
    """``python-chess`` completes the handshake and reads the engine's identity and options."""
    identifiers = dict(session.engine.id)
    missing = [key for key in ("name", "author") if not identifiers.get(key)]
    if missing:
        raise CheckFailure(f"python-chess did not read the engine {' and '.join(missing)}", id=identifiers)
    options = list(session.engine.options)
    if not options:
        raise CheckFailure("python-chess read no options from the engine")
    return Outcome(
        f"{identifiers['name']} accepted, {len(options)} options read",
        details={"id": identifiers, "options": options},
    )


@acceptance_check("pychess_play")
def check_pychess_play(session: AcceptanceSession) -> Outcome:
    """``python-chess`` gets a legal move out of the engine with ``play()``."""
    board = chess.Board()
    result = session.engine.play(board, chess.engine.Limit(time=0.25))
    if result.move is None:
        raise CheckFailure("python-chess got no move from the engine")
    if result.move not in board.legal_moves:
        raise CheckFailure(f"python-chess got the illegal move {result.move.uci()}", bestmove=result.move.uci())
    return Outcome(
        f"played {board.san(result.move)}",
        details={
            "bestmove": result.move.uci(),
            "bestmove_san": board.san(result.move),
            "ponder": result.ponder.uci() if result.ponder else None,
        },
    )


@acceptance_check("pychess_analyse")
def check_pychess_analyse(session: AcceptanceSession) -> Outcome:
    """``python-chess`` gets a scored analysis out of the engine with ``analyse()``."""
    board = chess.Board()
    info = session.engine.analyse(board, chess.engine.Limit(depth=8))
    if "score" not in info:
        raise CheckFailure("analysis carries no score", keys=sorted(str(key) for key in info))
    return Outcome(
        f"analysis at depth {info.get('depth')} scored {info['score'].white()}",
        details={
            "depth": info.get("depth"),
            "score": str(info["score"].white()),
            "keys": sorted(str(key) for key in info),
        },
    )
