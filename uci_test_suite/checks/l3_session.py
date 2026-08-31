"""L3 — a whole session: new games, options, debug, the ``go`` limits, and the ``info`` stream."""

import time
from itertools import pairwise
from typing import Final

import chess

from uci_test_suite.checks.base import CheckFailure, CheckSkipped, Outcome
from uci_test_suite.checks.registry import raw_check
from uci_test_suite.checks.session import RawSession
from uci_test_suite.checks.verify import move_details, verify_move, verify_responsive, verify_single_bestmove
from uci_test_suite.levels import Level
from uci_test_suite.protocol import LineKind, OptionSpec, OptionType, classify

#: A position where White mates in one with Qxf7 (h5f7).
MATE_IN_ONE_FEN: Final[str] = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1"

#: Plies asked of a bounded search.
SEARCH_DEPTH: Final[int] = 8

#: Nodes asked of a bounded search; small enough that a neural-network engine finishes it quickly too.
SEARCH_NODES: Final[int] = 1000


@raw_check("ucinewgame", Level.SESSION, budget=25.0)
def check_ucinewgame(session: RawSession) -> Outcome:
    """
    ``ucinewgame`` is accepted between games, and the engine plays on afterwards.

    Spec: "ucinewgame ... this is sent to the engine when the next search will be from a different game".
    """
    board = chess.Board()
    session.set_position(moves=["d2d4", "d7d5"])
    session.go("movetime 200")
    session.new_game()
    session.set_position()
    result = session.go("movetime 200")
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, "the starting position of the new game")
    return Outcome(
        f"new game accepted, then bestmove {result.bestmove.move}",
        details=move_details(board, result, move),
    )


@raw_check("setoption_roundtrip", Level.SESSION, budget=60.0)
def check_setoption_roundtrip(session: RawSession) -> Outcome:
    """
    Every declared option accepts a value from its own domain, and the engine keeps answering afterwards.

    Spec: "setoption name <id> [value <x>] ... this is sent to the engine when the user wants to change
    the internal parameters of the engine".
    """
    options = session.handshake.options
    if not options:
        raise CheckSkipped("engine declares no options")

    exercised: list[str] = []
    for option in options:
        for value in _probe_values(option):
            session.set_option(option.name, value)
            verify_responsive(session, f"setoption name {option.name}" + (f" value {value}" if value else ""))
        exercised.append(f"{option.name} ({option.type})")
    return Outcome(
        f"{len(exercised)} options set and accepted",
        details={"count": len(exercised), "options": exercised},
    )


def _probe_values(option: OptionSpec) -> list[str | None]:
    """Values to set the option to, in order; ``None`` means a bare ``setoption name``."""
    match option.type:
        case OptionType.BUTTON:
            return [None]
        case OptionType.CHECK:
            flipped = "false" if option.default == "true" else "true"
            return [flipped, option.default or "false"]
        case OptionType.SPIN:
            edge = str(option.min) if option.min is not None else option.default
            return [value for value in (edge, option.default) if value is not None]
        case _:
            return [option.default] if option.default is not None else [""]


@raw_check("debug_mode", Level.SESSION, budget=20.0)
def check_debug_mode(session: RawSession) -> Outcome:
    """
    ``debug on`` and ``debug off`` are accepted at any time and never break the protocol.

    Spec: "debug [ on | off ] ... this mode should be switched off by default".
    """
    session.send("debug on")
    on_latency = verify_responsive(session, "debug on")
    session.set_position()
    noise = [line.text for line in session.collect_for(0.2)]
    stray = [text for text in noise if classify(text) not in (LineKind.INFO, LineKind.UNKNOWN, LineKind.EMPTY)]
    if stray:
        raise CheckFailure("engine sent non-info output in debug mode", lines=stray)
    session.send("debug off")
    off_latency = verify_responsive(session, "debug off")
    return Outcome(
        f"debug on/off accepted ({on_latency:.3f} s / {off_latency:.3f} s)",
        details={"debug_output_lines": len(noise)},
    )


@raw_check("go_depth", Level.SESSION, budget=45.0)
def check_go_depth(session: RawSession) -> Outcome:
    """
    ``go depth N`` finishes on its own with a legal move.

    Spec: "depth <x> ... search x plies only".
    """
    board = chess.Board()
    session.set_position()
    result = session.go(f"depth {SEARCH_DEPTH}")
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, "the starting position")
    depths = [info.depth for info in result.infos if info.depth is not None]
    return Outcome(
        f"depth {SEARCH_DEPTH} finished in {result.elapsed:.3f} s",
        details=move_details(board, result, move)
        | {"requested_depth": SEARCH_DEPTH, "max_reported_depth": max(depths) if depths else None},
    )


@raw_check("go_nodes", Level.SESSION, budget=45.0)
def check_go_nodes(session: RawSession) -> Outcome:
    """
    ``go nodes N`` finishes on its own with a legal move.

    Spec: "nodes <x> ... search x nodes only".
    """
    board = chess.Board()
    session.set_position()
    result = session.go(f"nodes {SEARCH_NODES}")
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, "the starting position")
    nodes = [info.nodes for info in result.infos if info.nodes is not None]
    return Outcome(
        f"nodes {SEARCH_NODES} finished in {result.elapsed:.3f} s",
        details=move_details(board, result, move) | {"max_reported_nodes": max(nodes) if nodes else None},
    )


@raw_check("go_mate", Level.SESSION, budget=45.0)
def check_go_mate(session: RawSession) -> Outcome:
    """
    ``go mate N`` finishes on its own with a legal move.

    Spec: "mate <x> ... search for a mate in x moves".
    """
    board = chess.Board(MATE_IN_ONE_FEN)
    session.set_position(fen=MATE_IN_ONE_FEN)
    result = session.go("mate 1")
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, "the mate-in-one position")
    board.push(move)
    found = board.is_checkmate()
    board.pop()
    return Outcome(
        f"mate 1 finished in {result.elapsed:.3f} s, mate found: {found}",
        details=move_details(board, result, move) | {"found_mate_in_one": found},
    )


@raw_check("go_movestogo", Level.SESSION, budget=25.0)
def check_go_movestogo(session: RawSession) -> Outcome:
    """
    ``go ... movestogo M`` produces a legal move within the time it implies.

    Spec: "movestogo <x> ... there are x moves to the next time control".
    """
    board = chess.Board()
    session.set_position()
    arguments = "wtime 10000 btime 10000 movestogo 20"
    result = session.go(arguments)
    verify_single_bestmove(result)
    move = verify_move(board, result.bestmove, "the starting position")
    if result.elapsed > 10.0:
        raise CheckFailure(
            f"go {arguments} took {result.elapsed:.3f} s, the whole remaining clock",
            elapsed_s=round(result.elapsed, 3),
        )
    return Outcome(
        f"bestmove {result.bestmove.move} in {result.elapsed:.3f} s",
        details=move_details(board, result, move) | {"go": arguments},
    )


@raw_check("isready_while_searching", Level.SESSION, budget=25.0)
def check_isready_while_searching(session: RawSession) -> Outcome:
    """
    ``isready`` is answered during a search, and the search survives it.

    Spec: "this command must always be answered with 'readyok' and can be sent also when the engine is
    calculating in which case the engine should also immediately answer with 'readyok'".
    """
    board = chess.Board()
    session.set_position()
    session.send_go("infinite")
    session.collect_for(0.2)
    asked_at = time.monotonic()
    session.send("isready")
    lines = session.client.expect("readyok", timeout=session.timeout)
    latency = time.monotonic() - asked_at
    early = [line.text for line in lines if classify(line.text) is LineKind.BESTMOVE]
    if early:
        raise CheckFailure("engine ended the search when asked isready", bestmove_lines=early)
    session.stop()
    result = session.collect_search()
    verify_single_bestmove(result)
    verify_move(board, result.bestmove, "the starting position")
    return Outcome(
        f"readyok during the search, then bestmove {result.bestmove.move} after stop",
        details={"lines_before_readyok": len(lines) - 1, "readyok_latency_s": round(latency, 3)},
    )


@raw_check("info_stream", Level.SESSION, budget=45.0)
def check_info_stream(session: RawSession) -> Outcome:
    """
    ``info`` lines parse, and their reported depth never goes backwards within one search.

    Spec: "info ... the engine wants to send information to the GUI ... depth <x> search depth in plies".
    """
    session.set_position()
    result = session.go(f"depth {SEARCH_DEPTH}")
    verify_single_bestmove(result)
    if not result.infos:
        raise CheckSkipped("engine sends no info lines")

    depths = [info.depth for info in result.infos if info.depth is not None]
    regressions = [(before, after) for before, after in pairwise(depths) if after < before]
    if regressions:
        raise CheckFailure(
            f"reported depth went backwards {len(regressions)} times within one search",
            regressions=[f"{before} -> {after}" for before, after in regressions[:5]],
        )
    scored = sum(1 for info in result.infos if info.score is not None)
    return Outcome(
        f"{len(result.infos)} info lines, depth {depths[0] if depths else '?'} to {depths[-1] if depths else '?'}",
        details={
            "info_lines": len(result.infos),
            "with_depth": len(depths),
            "with_score": scored,
            "with_pv": sum(1 for info in result.infos if info.pv),
        },
    )


@raw_check("no_unsolicited_bestmove", Level.SESSION, budget=20.0)
def check_no_unsolicited_bestmove(session: RawSession) -> Outcome:
    """
    Nothing but ``go`` makes the engine send a ``bestmove``.

    Spec: "bestmove <move1> ... the engine has stopped searching and found the move <move> best in this position".
    """
    quiet_commands = ["ucinewgame", "position startpos moves e2e4", "isready", "debug off", "position startpos"]
    for command in quiet_commands:
        session.send(command)
    stray = [line.text for line in session.collect_for(0.6) if classify(line.text) is LineKind.BESTMOVE]
    if stray:
        raise CheckFailure("engine sent a bestmove without a go", bestmove_lines=stray, after=quiet_commands)
    verify_responsive(session, "commands that start no search")
    return Outcome(
        f"no bestmove after {len(quiet_commands)} commands that start no search",
        details={"commands": quiet_commands},
    )
