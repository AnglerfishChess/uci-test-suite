"""L6 — a mainstream UCI client, ``python-chess``, drives the engine end to end."""

import chess
import chess.engine

from uci_test_suite.checks.base import CheckFailure, Outcome
from uci_test_suite.checks.registry import acceptance_check
from uci_test_suite.checks.session import AcceptanceSession


@acceptance_check("pychess_handshake", budget=25.0)
def check_pychess_handshake(session: AcceptanceSession) -> Outcome:
    """``python-chess`` completes the handshake and reads the engine's identity and options."""
    identifiers = dict(session.engine.id)
    missing = [key for key in ("name", "author") if not identifiers.get(key)]
    if missing:
        raise CheckFailure(f"python-chess did not read the engine {' and '.join(missing)}", id=identifiers)
    options = list(session.engine.options)
    return Outcome(
        f"{identifiers['name']} accepted, {len(options)} options read",
        details={"id": identifiers, "options": options},
    )


@acceptance_check("pychess_play", budget=25.0)
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


@acceptance_check("pychess_analyse", budget=45.0)
def check_pychess_analyse(session: AcceptanceSession) -> Outcome:
    """
    ``python-chess`` gets an analysis out of the engine with ``analyse()``.

    A search that reports no score still conforms: ``info score`` is optional in the spec.
    """
    board = chess.Board()
    info = session.engine.analyse(board, chess.engine.Limit(depth=8))
    keys = sorted(str(key) for key in info)
    score = info.get("score")
    return Outcome(
        f"analysis at depth {info.get('depth')} scored {score.white()}"
        if score is not None
        else f"analysis at depth {info.get('depth')}, no score reported",
        details={
            "depth": info.get("depth"),
            "score": str(score.white()) if score is not None else None,
            "keys": keys,
            "note": None if score is not None else "no info score line; the spec does not require one",
        },
    )
