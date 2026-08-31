"""L2 — playing a move: positions in, a timed search, and one legal move out."""

from typing import Final

import chess

from uci_test_suite.checks.base import CheckFailure, Outcome
from uci_test_suite.checks.registry import raw_check
from uci_test_suite.checks.session import RawSession
from uci_test_suite.checks.verify import move_details, verify_move, verify_single_bestmove
from uci_test_suite.levels import Level
from uci_test_suite.protocol import LineKind, classify

#: A position where White mates in one with Qxf7 (h5f7).
MATE_IN_ONE_FEN: Final[str] = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1"

#: A position whose only sensible White move is a promotion.
PROMOTION_FEN: Final[str] = "8/P6k/8/8/8/8/8/6K1 w - - 0 1"

#: Milliseconds given to a search that only has to produce some move.
SHORT_MOVETIME: Final[int] = 250

#: Seconds a search may overrun its own movetime by, covering process and pipe overhead.
MOVETIME_SLACK: Final[float] = 3.0


@raw_check("position_startpos", Level.PLAY, budget=15.0)
def check_position_startpos(session: RawSession) -> Outcome:
    """
    ``position startpos`` followed by a timed ``go`` yields one legal move.

    Spec: "position [fen <fenstring> | startpos ] moves <move1> .... <movei>".
    """
    board = chess.Board()
    session.set_position()
    result = session.go(f"movetime {SHORT_MOVETIME}")
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, "the starting position")
    return Outcome(f"bestmove {result.bestmove.move} ({board.san(move)})", details=move_details(board, result, move))


@raw_check("position_startpos_moves", Level.PLAY, budget=15.0)
def check_position_startpos_moves(session: RawSession) -> Outcome:
    """
    ``position startpos moves ...`` is applied to the board the engine searches.

    Spec: "position ... moves <move1> .... <movei> ... play the moves on the internal chess board".
    """
    moves = ["e2e4", "e7e5", "g1f3"]
    board = chess.Board()
    for text in moves:
        board.push_uci(text)
    session.set_position(moves=moves)
    result = session.go(f"movetime {SHORT_MOVETIME}")
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, f"the position after {' '.join(moves)}")
    return Outcome(
        f"bestmove {result.bestmove.move} after {' '.join(moves)}",
        details=move_details(board, result, move) | {"moves": moves},
    )


@raw_check("position_fen", Level.PLAY, budget=15.0)
def check_position_fen(session: RawSession) -> Outcome:
    """
    A position given as ``position fen ...`` is searched as given.

    Spec: "position [fen <fenstring> | startpos ] ... set up the position described in fenstring".
    """
    board = chess.Board(MATE_IN_ONE_FEN)
    session.set_position(fen=MATE_IN_ONE_FEN)
    result = session.go(f"movetime {SHORT_MOVETIME}")
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, "the mate-in-one position")
    details = move_details(board, result, move)
    board.push(move)
    details["found_mate_in_one"] = board.is_checkmate()
    board.pop()
    return Outcome(f"bestmove {result.bestmove.move} ({board.san(move)})", details=details)


@raw_check("position_fen_moves", Level.PLAY, budget=15.0)
def check_position_fen_moves(session: RawSession) -> Outcome:
    """
    ``position fen ... moves ...`` is applied to the board the engine searches.

    Spec: "position [fen <fenstring> | startpos ] moves <move1> .... <movei>".
    """
    moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]
    board = chess.Board()
    for text in moves:
        board.push_uci(text)
    session.set_position(fen=chess.STARTING_FEN, moves=moves)
    result = session.go(f"movetime {SHORT_MOVETIME}")
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, f"the position after {' '.join(moves)}")
    return Outcome(
        f"bestmove {result.bestmove.move} after {len(moves)} moves from a FEN",
        details=move_details(board, result, move) | {"moves": moves},
    )


@raw_check("promotion_notation", Level.PLAY, budget=15.0)
def check_promotion_notation(session: RawSession) -> Outcome:
    """
    A promotion is accepted in a ``moves`` list, and the answer is a well-formed long algebraic move.

    Spec: "the move format is in long algebraic notation ... examples: e2e4, e1g1, e7e8q".
    """
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


@raw_check("go_movetime", Level.PLAY, budget=15.0)
def check_go_movetime(session: RawSession) -> Outcome:
    """
    ``go movetime N`` answers within N milliseconds plus pipe overhead.

    Spec: "movetime <x> ... search exactly x mseconds".
    """
    board = chess.Board()
    session.set_position()
    result = session.go(f"movetime {SHORT_MOVETIME}")
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, "the starting position")
    budget = SHORT_MOVETIME / 1000 + MOVETIME_SLACK
    if result.elapsed > budget:
        raise CheckFailure(
            f"go movetime {SHORT_MOVETIME} took {result.elapsed:.3f} s, over the {budget:.3f} s budget",
            elapsed_s=round(result.elapsed, 3),
        )
    return Outcome(
        f"answered in {result.elapsed:.3f} s",
        details=move_details(board, result, move) | {"movetime_ms": SHORT_MOVETIME},
    )


@raw_check("go_clock", Level.PLAY, budget=25.0)
def check_go_clock(session: RawSession) -> Outcome:
    """
    ``go wtime .. btime .. winc .. binc ..`` produces a legal move without running out its whole clock.

    Spec: "wtime <x> ... white has x msec left on the clock"; likewise btime, winc and binc.
    """
    board = chess.Board()
    session.set_position()
    clock = "wtime 2000 btime 2000 winc 100 binc 100"
    result = session.go(clock)
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, "the starting position")
    if result.elapsed > 4.0:
        raise CheckFailure(
            f"go {clock} took {result.elapsed:.3f} s, more than the clock allowed",
            elapsed_s=round(result.elapsed, 3),
        )
    return Outcome(
        f"bestmove {result.bestmove.move} in {result.elapsed:.3f} s of a 2 s clock",
        details=move_details(board, result, move) | {"go": clock},
    )


@raw_check("stop_ends_search", Level.PLAY, budget=25.0)
def check_stop_ends_search(session: RawSession) -> Outcome:
    """
    ``go infinite`` keeps searching until ``stop``, which produces exactly one ``bestmove``.

    Spec: "infinite ... search until the 'stop' command. ... stop: stop calculating as soon as possible".
    """
    board = chess.Board()
    session.set_position()
    session.send_go("infinite")
    early = [line.text for line in session.collect_for(0.3) if classify(line.text) is LineKind.BESTMOVE]
    if early:
        raise CheckFailure("engine ended an infinite search before being told to stop", bestmove_lines=early)

    session.stop()
    result = session.collect_search()
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, "the starting position")
    session.sync()
    return Outcome(
        f"bestmove {result.bestmove.move} {result.elapsed:.3f} s after stop",
        details=move_details(board, result, move) | {"stop_latency_s": round(result.elapsed, 3)},
    )
