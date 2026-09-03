"""L6 — a mainstream UCI client, ``esca``, drives the engine end to end."""

from typing import Final

import esca
from esca.uci import Limits

from uci_test_suite.checks.base import CheckFailure, CheckSkipped, Outcome
from uci_test_suite.checks.registry import acceptance_check
from uci_test_suite.checks.session import AcceptanceSession

#: A Chess960 position with the king on f1/f8 and rooks on b/h, where both sides may castle at once.
CHESS960_FEN: Final[str] = "1r3k1r/pppppppp/8/8/8/8/PPPPPPPP/1R3K1R w KQkq - 0 1"


@acceptance_check("client_handshake", budget=25.0)
def check_client_handshake(session: AcceptanceSession) -> Outcome:
    """A UCI client completes the handshake and reads the engine's identity and options."""
    identifiers = {"name": session.engine.name, "author": session.engine.author}
    missing = [key for key, value in identifiers.items() if not value]
    if missing:
        raise CheckFailure(f"the client did not read the engine {' and '.join(missing)}", id=identifiers)
    options = sorted(session.engine.options)
    return Outcome(
        f"{identifiers['name']} accepted, {len(options)} options read",
        details={"id": identifiers, "options": options},
    )


@acceptance_check("client_play", budget=25.0)
def check_client_play(session: AcceptanceSession) -> Outcome:
    """A UCI client gets a legal move out of the engine with ``play()``."""
    game = esca.Game()
    answer = session.engine.play(game, Limits(movetime=0.25))
    if answer.best is None:
        raise CheckFailure("the client got no move from the engine")
    if answer.best not in game.legal_moves():
        raise CheckFailure(f"the client got the illegal move {answer.best.uci}", bestmove=answer.best.uci)
    return Outcome(
        f"played {game.move_to_san(answer.best)}",
        details={
            "bestmove": answer.best.uci,
            "bestmove_san": game.move_to_san(answer.best),
            "ponder": answer.ponder.uci if answer.ponder is not None else None,
        },
    )


@acceptance_check("client_analyse", budget=45.0)
def check_client_analyse(session: AcceptanceSession) -> Outcome:
    """
    A UCI client gets an analysis out of the engine with ``analyse()``.

    A search that reports no score still conforms: ``info score`` is optional in the spec.
    """
    game = esca.Game()
    reports = session.engine.analyse(game, Limits(depth=8))
    if not reports:
        raise CheckFailure("the client got no info line out of the engine")
    info = reports[0]
    score = f"mate {info.mate}" if info.mate is not None else (f"cp {info.cp}" if info.cp is not None else None)
    return Outcome(
        f"analysis at depth {info.depth} scored {score}"
        if score is not None
        else f"analysis at depth {info.depth}, no score reported",
        details={
            "depth": info.depth,
            "score": score,
            "pv": [move.uci for move in info.pv],
            "variations": len(reports),
            "note": None if score is not None else "no info score line; the spec does not require one",
        },
    )


@acceptance_check("client_chess960", budget=25.0)
def check_client_chess960(session: AcceptanceSession) -> Outcome:
    """
    A UCI client plays a Chess960 game through the engine, switching it into the variant itself.

    Spec: "UCI_Chess960 ... the engine supports Chess960 ... the castling move is a king move to the rook".
    """
    if "UCI_Chess960" not in session.engine.options:
        raise CheckSkipped("engine does not declare the UCI_Chess960 option")

    game = esca.Game.from_fen(CHESS960_FEN, variant=esca.CHESS960)
    game.play("f1h1")
    answer = session.engine.play(game, Limits(movetime=0.3))
    if answer.best is None:
        raise CheckFailure("the client got no move from the engine in a Chess960 position")
    if answer.best not in game.legal_moves():
        raise CheckFailure(
            f"the client got the illegal move {answer.best.uci} in a Chess960 position",
            bestmove=answer.best.uci,
            fen=game.position.fen,
        )
    return Outcome(
        f"Chess960 game accepted, answered {game.move_to_san(answer.best)}",
        details={
            "fen": game.position.fen,
            "castling_move": "f1h1",
            "bestmove": answer.best.uci,
            "bestmove_san": game.move_to_san(answer.best),
        },
    )
