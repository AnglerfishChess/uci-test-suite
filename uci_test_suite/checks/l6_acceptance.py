"""L6 — a mainstream UCI client, ``esca``, drives the engine end to end."""

import esca
from esca.uci import Limits

from uci_test_suite.checks.base import CheckFailure, Outcome
from uci_test_suite.checks.registry import acceptance_check
from uci_test_suite.checks.session import AcceptanceSession


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
