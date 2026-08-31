"""Checks for the mandatory part of the UCI protocol, driven over the raw transport."""

from typing import Final

import chess

from uci_test_suite.checks.base import CheckFailure, Outcome
from uci_test_suite.checks.registry import raw_check
from uci_test_suite.checks.session import RawSession
from uci_test_suite.checks.verify import move_details, verify_move, verify_single_bestmove
from uci_test_suite.protocol import LineKind, classify

#: A position where White mates in one with Qxf7 (h5f7).
MATE_IN_ONE_FEN: Final[str] = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1"

#: A position whose only sensible White move is a promotion.
PROMOTION_FEN: Final[str] = "8/P6k/8/8/8/8/8/6K1 w - - 0 1"

#: Milliseconds given to a search that only has to produce some move.
SHORT_MOVETIME: Final[int] = 250


@raw_check("uci_protocol_support")
def check_uci_protocol_support(session: RawSession) -> Outcome:
    """The engine answers ``uci`` with ``uciok``, and says nothing unparsable on the way."""
    handshake = session.handshake
    if handshake.invalid_options:
        raise CheckFailure(
            f"{len(handshake.invalid_options)} malformed lines before uciok",
            invalid_lines=[f"{line} -- {reason}" for line, reason in handshake.invalid_options],
        )
    kinds = sorted({str(classify(line)) for line in handshake.lines})
    return Outcome(
        f"uciok after {handshake.elapsed:.3f} s ({len(handshake.lines)} lines)",
        details={
            "elapsed_s": round(handshake.elapsed, 3),
            "lines": len(handshake.lines),
            "line_kinds": kinds,
            "unrecognized_lines": list(handshake.unrecognized),
        },
    )


@raw_check("engine_identification")
def check_engine_identification(session: RawSession) -> Outcome:
    """The handshake carries ``id name`` and ``id author``."""
    identifiers = session.handshake.id
    missing = [key for key in ("name", "author") if not identifiers.get(key)]
    if missing:
        raise CheckFailure(f"handshake has no id {' and no id '.join(missing)}", id=dict(identifiers))
    return Outcome(
        f"name: {identifiers['name']}, author: {identifiers['author']}",
        details={"id": dict(identifiers)},
    )


@raw_check("options_reporting")
def check_options_reporting(session: RawSession) -> Outcome:
    """Every advertised ``option`` line parses and declares a domain consistent with its type."""
    handshake = session.handshake
    if handshake.invalid_options:
        raise CheckFailure(
            f"{len(handshake.invalid_options)} option lines do not parse",
            invalid_lines=[f"{line} -- {reason}" for line, reason in handshake.invalid_options],
        )
    if not handshake.options:
        raise CheckFailure("engine advertises no options")

    issues = [f"{option.name}: {issue}" for option in handshake.options for issue in option.issues()]
    if issues:
        raise CheckFailure(f"{len(issues)} option declarations violate the spec", issues=issues)

    by_type: dict[str, int] = {}
    for option in handshake.options:
        by_type[str(option.type)] = by_type.get(str(option.type), 0) + 1
    return Outcome(
        f"{len(handshake.options)} options, all well-formed",
        details={
            "count": len(handshake.options),
            "by_type": by_type,
            "names": [option.name for option in handshake.options],
        },
    )


@raw_check("isready_synchronization")
def check_isready_synchronization(session: RawSession) -> Outcome:
    """``isready`` is answered with exactly one ``readyok``, both when idle and after a ``position``."""
    handshake = session.handshake
    first = session.sync()
    session.set_position()
    second = session.sync()
    stray = [line.text for line in session.collect_for(0.15) if classify(line.text) is LineKind.READYOK]
    if stray:
        raise CheckFailure(f"engine sent {len(stray)} extra readyok lines", extra=stray)
    return Outcome(
        f"readyok after {first:.3f} s when idle, {second:.3f} s after a position",
        details={
            "idle_s": round(first, 3),
            "after_position_s": round(second, 3),
            "engine": handshake.id.get("name", "unknown"),
        },
    )


@raw_check("starting_position")
def check_starting_position(session: RawSession) -> Outcome:
    """``position startpos`` followed by a timed ``go`` yields one legal move."""
    board = chess.Board()
    session.set_position()
    result = session.go(f"movetime {SHORT_MOVETIME}")
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, "the starting position")
    return Outcome(f"bestmove {result.bestmove.move} ({board.san(move)})", details=move_details(board, result, move))


@raw_check("position_setup")
def check_position_setup(session: RawSession) -> Outcome:
    """``position startpos moves ...`` is applied to the board the engine searches."""
    moves = ["e2e4", "e7e5", "g1f3"]
    board = chess.Board()
    for move_text in moves:
        board.push_uci(move_text)
    session.set_position(moves=moves)
    result = session.go(f"movetime {SHORT_MOVETIME}")
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, f"the position after {' '.join(moves)}")
    details = move_details(board, result, move) | {"moves": moves}
    return Outcome(f"bestmove {result.bestmove.move} after {' '.join(moves)}", details=details)


@raw_check("position_with_moves")
def check_position_with_moves(session: RawSession) -> Outcome:
    """``position fen ... moves ...`` is applied to the board the engine searches."""
    moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]
    board = chess.Board()
    for move_text in moves:
        board.push_uci(move_text)
    session.set_position(fen=chess.STARTING_FEN, moves=moves)
    result = session.go(f"movetime {SHORT_MOVETIME}")
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, f"the position after {' '.join(moves)}")
    details = move_details(board, result, move) | {"moves": moves}
    return Outcome(f"bestmove {result.bestmove.move} after {len(moves)} moves from a FEN", details=details)


@raw_check("fen_position")
def check_fen_position(session: RawSession) -> Outcome:
    """A position given as FEN is searched as given."""
    board = chess.Board(MATE_IN_ONE_FEN)
    session.set_position(fen=MATE_IN_ONE_FEN)
    result = session.go(f"movetime {SHORT_MOVETIME}")
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, "the mate-in-one position")
    details = move_details(board, result, move)
    board.push(move)
    found_mate = board.is_checkmate()
    board.pop()
    details["found_mate_in_one"] = found_mate
    return Outcome(
        f"bestmove {result.bestmove.move} ({board.san(move)}), mate found: {found_mate}",
        details=details,
    )


@raw_check("go_command")
def check_go_command(session: RawSession) -> Outcome:
    """``go depth`` and ``go movetime`` both terminate with a legal move, within their limits."""
    board = chess.Board()
    session.set_position()

    depth_result = session.go("depth 8", timeout=20.0)
    verify_single_bestmove(depth_result)
    verify_move(board, depth_result.bestmove, "the starting position")
    depths = [info.depth for info in depth_result.infos if info.depth is not None]

    movetime_result = session.go(f"movetime {SHORT_MOVETIME}")
    verify_single_bestmove(movetime_result)
    verify_move(board, movetime_result.bestmove, "the starting position")
    budget = SHORT_MOVETIME / 1000 + 3.0
    if movetime_result.elapsed > budget:
        raise CheckFailure(
            f"go movetime {SHORT_MOVETIME} took {movetime_result.elapsed:.3f} s, over the {budget:.3f} s budget",
            elapsed_s=round(movetime_result.elapsed, 3),
        )
    return Outcome(
        f"depth 8 in {depth_result.elapsed:.3f} s, movetime {SHORT_MOVETIME} in {movetime_result.elapsed:.3f} s",
        details={
            "depth_elapsed_s": round(depth_result.elapsed, 3),
            "depth_bestmove": depth_result.bestmove.move,
            "max_reported_depth": max(depths) if depths else None,
            "movetime_elapsed_s": round(movetime_result.elapsed, 3),
            "movetime_bestmove": movetime_result.bestmove.move,
        },
    )


@raw_check("stop_command")
def check_stop_command(session: RawSession) -> Outcome:
    """``go infinite`` keeps searching until ``stop``, which produces exactly one ``bestmove``."""
    board = chess.Board()
    session.set_position()
    session.send_go("infinite")
    early = [line.text for line in session.collect_for(0.3) if classify(line.text) is LineKind.BESTMOVE]
    if early:
        raise CheckFailure("engine ended an infinite search before being told to stop", bestmove_lines=early)

    session.stop()
    result = session.collect_search(timeout=5.0)
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, "the starting position")
    session.sync()
    return Outcome(
        f"bestmove {result.bestmove.move} {result.elapsed:.3f} s after stop",
        details=move_details(board, result, move) | {"stop_latency_s": round(result.elapsed, 3)},
    )


@raw_check("long_algebraic_notation")
def check_long_algebraic_notation(session: RawSession) -> Outcome:
    """A promotion is accepted in the ``moves`` list, and the answer is a well-formed LAN move."""
    board = chess.Board(PROMOTION_FEN)
    board.push_uci("a7a8q")
    session.set_position(fen=PROMOTION_FEN, moves=["a7a8q"])
    result = session.go(f"movetime {SHORT_MOVETIME}")
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, "the position after the promotion a7a8q")
    return Outcome(
        f"promotion accepted, answered with {result.bestmove.move}",
        details=move_details(board, result, move) | {"input_move": "a7a8q"},
    )
