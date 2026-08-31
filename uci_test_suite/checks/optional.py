"""Checks for UCI features an engine may or may not offer; once advertised, they must work as specified."""

import chess

from uci_test_suite.checks.base import CheckFailure, CheckSkipped, Outcome, Scope
from uci_test_suite.checks.registry import raw_check
from uci_test_suite.checks.session import RawSession
from uci_test_suite.checks.verify import verify_move, verify_single_bestmove
from uci_test_suite.protocol import LineKind, OptionType, classify


@raw_check("pondering", Scope.OPTIONAL)
def check_pondering(session: RawSession) -> Outcome:
    """A ``go ponder`` search runs until ``ponderhit``, and only then produces its move."""
    option = session.handshake.option("Ponder")
    if option is None:
        raise CheckSkipped("engine does not advertise the Ponder option")
    if option.type is not OptionType.CHECK:
        raise CheckFailure(f"the Ponder option is of type {option.type}, not check")

    moves = ["e2e4", "e7e5"]
    board = chess.Board()
    for move_text in moves:
        board.push_uci(move_text)

    session.set_option("Ponder", "true")
    try:
        session.set_position(moves=moves)
        session.send_go("ponder movetime 300")
        early = [line.text for line in session.collect_for(0.5) if classify(line.text) is LineKind.BESTMOVE]
        if early:
            raise CheckFailure("engine answered a ponder search before ponderhit", bestmove_lines=early)

        session.client.send("ponderhit")
        result = session.collect_search(timeout=5.0)
    finally:
        session.resync()
        session.set_option("Ponder", option.default or "false")

    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, f"the position after {' '.join(moves)}")
    return Outcome(
        f"ponder search held until ponderhit, then answered {result.bestmove.move}",
        details={
            "bestmove": result.bestmove.move,
            "bestmove_san": board.san(move),
            "ponder": result.bestmove.ponder,
            "ponderhit_latency_s": round(result.elapsed, 3),
        },
    )


@raw_check("multipv", Scope.OPTIONAL)
def check_multipv(session: RawSession) -> Outcome:
    """With MultiPV set to N, the engine labels its ``info`` lines with each variation number up to N."""
    option = session.handshake.option("MultiPV")
    if option is None:
        raise CheckSkipped("engine does not advertise the MultiPV option")
    if option.type is not OptionType.SPIN:
        raise CheckFailure(f"the MultiPV option is of type {option.type}, not spin")
    wanted = min(3, option.max if option.max is not None else 3)
    if wanted < 2:
        raise CheckSkipped(f"engine caps MultiPV at {option.max}")

    session.set_option("MultiPV", str(wanted))
    try:
        session.set_position()
        result = session.go("depth 8", timeout=20.0)
    finally:
        session.resync()
        session.set_option("MultiPV", option.default or "1")

    verify_single_bestmove(result)
    board = chess.Board()
    verify_move(board, result.bestmove, "the starting position")

    seen = sorted({info.multipv for info in result.infos if info.multipv is not None})
    if not seen:
        raise CheckFailure(
            f"MultiPV set to {wanted}, but no info line carries a multipv number",
            info_lines=len(result.infos),
        )
    missing = [number for number in range(1, wanted + 1) if number not in seen]
    if missing:
        raise CheckFailure(
            f"MultiPV set to {wanted}, but variations {missing} were never reported",
            reported=seen,
        )
    return Outcome(
        f"reported {wanted} variations",
        details={"requested": wanted, "reported": seen, "info_lines": len(result.infos)},
    )
