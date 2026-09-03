"""
L5 — unhappy paths.

The contract of every check here is the same: the engine neither crashes nor hangs, keeps answering ``isready``,
and either answers sanely or ignores the input. A graceful rejection passes.
"""

import time
from collections.abc import Sequence
from typing import Any, Final

import esca

from uci_test_suite.checks.base import CheckFailure, Outcome
from uci_test_suite.checks.registry import fresh_check, process_check
from uci_test_suite.checks.session import ProcessSession, RawSession
from uci_test_suite.checks.verify import malformed_lines, move_details, verify_move, verify_responsive
from uci_test_suite.levels import Level
from uci_test_suite.protocol import LineKind, classify
from uci_test_suite.transport import EngineDied

#: Commands that use a real keyword with a broken or missing argument.
MALFORMED: Final[tuple[str, ...]] = (
    "go depth abc",
    "go movetime",
    "go wtime btime",
    "position fen",
    "position",
    "setoption",
    "setoption name",
    "setoption value 3",
    "position startpos moves",
    "debug maybe",
)

#: Positions that cannot occur on a chessboard, or are not FEN at all.
IMPOSSIBLE_FENS: Final[tuple[tuple[str, str], ...]] = (
    ("100 pawns", "pppppppp/pppppppp/pppppppp/pppppppp/pppppppp/pppppppp/pppppppp/pppppppp w - - 0 1"),
    ("no kings", "8/8/8/8/8/8/8/8 w - - 0 1"),
    ("both kings in check", "4k3/4R3/8/8/8/8/4r3/4K3 w - - 0 1"),
    ("side to move gives check", "4k3/8/8/8/8/8/4r3/4K3 b - - 0 1"),
    ("not a FEN at all", "this is not a position"),
)

#: How many junk lines the engine has to swallow in one burst.
JUNK_BURST: Final[int] = 1000


def _survives(session: RawSession, commands: Sequence[str], settle: float = 0.3) -> dict[str, Any]:
    """
    Put each command to the engine on its own, and require it to stay alive, well-spoken and answering.

    Anything the engine says back is allowed as long as it parses; a search the command started is stopped
    before the next one goes out.
    """
    answers: dict[str, list[str]] = {}
    for command in commands:
        try:
            session.send(command)
            noise = [line.text for line in session.collect_for(settle)]
            broken = malformed_lines(noise)
            if broken:
                raise CheckFailure(
                    f"engine sent malformed lines on {command!r}", command=command, malformed=broken[:10]
                )
            session.resync()
            verify_responsive(session, repr(command))
        except EngineDied as died:
            raise CheckFailure(f"engine died on {command!r}: {died}", command=command) from None
        answers[command] = noise[:5]
    return {"commands": list(commands), "answers": answers}


@fresh_check("malformed_commands", Level.ROBUSTNESS, budget=30.0)
def check_malformed_commands(session: RawSession) -> Outcome:
    """
    Commands with a broken or missing argument are survived.

    Spec: "if the engine or the GUI receives an unknown command or token it should just ignore it and try to
    parse the rest of the string".
    """
    session.set_position()
    details = _survives(session, MALFORMED, settle=0.5)
    return Outcome(f"{len(MALFORMED)} malformed commands survived", details=details)


@fresh_check("impossible_fen", Level.ROBUSTNESS, budget=30.0)
def check_impossible_fen(session: RawSession) -> Outcome:
    """
    Positions that cannot occur on a chessboard are survived, and the engine plays on afterwards.

    Spec: "position [fen <fenstring> | startpos ]" — a GUI may send anything; the engine must stay usable.
    """
    for _label, fen in IMPOSSIBLE_FENS:
        _survives(session, [f"position fen {fen}"], settle=0.2)

    game = esca.Game()
    session.set_position()
    result = session.go("movetime 200")
    move = verify_move(game, result.bestmove, "the starting position after the impossible ones")
    return Outcome(
        f"{len(IMPOSSIBLE_FENS)} impossible positions survived, then bestmove {result.bestmove.move}",
        details=move_details(game, result, move) | {"positions": [label for label, _ in IMPOSSIBLE_FENS]},
    )


@fresh_check("illegal_move_in_position", Level.ROBUSTNESS, budget=30.0)
def check_illegal_move_in_position(session: RawSession) -> Outcome:
    """
    A ``position`` whose move list contains an illegal move is survived.

    Spec: "position ... moves <move1> .... <movei>" — the moves are the GUI's to get right.
    """
    commands = [
        "position startpos moves e2e4 e2e4",
        "position startpos moves e2e4 e7e5 e1e8",
        "position startpos moves z9z9",
    ]
    details = _survives(session, commands)
    session.set_position()
    verify_responsive(session, "a good position after the illegal ones")
    return Outcome(f"{len(commands)} illegal move lists survived", details=details)


@fresh_check("go_without_position", Level.ROBUSTNESS, budget=30.0)
def check_go_without_position(session: RawSession) -> Outcome:
    """
    ``go`` sent before any ``position`` is survived.

    Spec: "go ... start calculating on the current position set up with the 'position' command".
    """
    details = _survives(session, ["go movetime 200"], settle=1.0)
    return Outcome("go before any position survived", details=details)


@fresh_check("idle_stop_and_ponderhit", Level.ROBUSTNESS, budget=30.0)
def check_idle_stop_and_ponderhit(session: RawSession) -> Outcome:
    """
    ``stop`` and ``ponderhit`` sent while no search runs produce no ``bestmove``.

    Spec: "stop: stop calculating as soon as possible"; "ponderhit: the user has played the expected move".
    """
    session.set_position()
    session.send("stop")
    session.send("ponderhit")
    session.send("stop")
    stray = [line.text for line in session.collect_for(0.5) if classify(line.text) is LineKind.BESTMOVE]
    if stray:
        raise CheckFailure("engine answered an idle stop/ponderhit with a bestmove", bestmove_lines=stray)
    latency = verify_responsive(session, "an idle stop and ponderhit")
    return Outcome("idle stop and ponderhit ignored", details={"readyok_s": round(latency, 3)})


@fresh_check("consecutive_go", Level.ROBUSTNESS, budget=30.0)
def check_consecutive_go(session: RawSession) -> Outcome:
    """
    Two ``go`` commands in a row are survived, without the engine locking up.

    Spec: "go ... start calculating on the current position".
    """
    session.set_position()
    session.send("go movetime 200")
    session.send("go movetime 200")
    lines = [line.text for line in session.collect_for(2.0)]
    moves = [text for text in lines if classify(text) is LineKind.BESTMOVE]
    broken = malformed_lines(lines)
    if broken:
        raise CheckFailure("engine sent malformed lines on two go commands", malformed=broken[:10])
    session.resync()
    latency = verify_responsive(session, "two go commands in a row")
    return Outcome(
        f"two searches at once survived, {len(moves)} bestmove lines",
        details={"bestmove_lines": moves, "readyok_s": round(latency, 3)},
    )


@fresh_check("junk_burst", Level.ROBUSTNESS, budget=40.0)
def check_junk_burst(session: RawSession) -> Outcome:
    """
    A burst of a thousand unknown lines is swallowed without blocking the engine.

    Spec: "the engine must always be able to process input from stdin".
    """
    started = time.monotonic()
    sent = 0
    try:
        for index in range(JUNK_BURST):
            session.send(f"junk line {index} with some tokens")
            sent = index + 1
    except EngineDied as died:
        raise CheckFailure(f"engine died after {sent} junk lines: {died}", sent=sent) from None
    latency = verify_responsive(session, f"{JUNK_BURST} junk lines")
    session.set_position()
    verify_responsive(session, "a position after the junk")
    return Outcome(
        f"{JUNK_BURST} junk lines swallowed, readyok after {latency:.3f} s",
        details={
            "junk_lines": JUNK_BURST,
            "readyok_s": round(latency, 3),
            "total_s": round(time.monotonic() - started, 3),
        },
    )


@process_check("quit_during_search", Level.ROBUSTNESS, budget=30.0)
def check_quit_during_search(session: ProcessSession) -> Outcome:
    """
    ``quit`` sent during an infinite search ends the process, leaving nothing behind.

    Spec: "quit: quit the program as soon as possible".
    """
    with session.client() as client:
        client.send("uci")
        client.expect("uciok")
        client.send("position startpos")
        client.send("go infinite")
        client.drain(quiet_for=0.2, timeout=0.5)
        started = time.monotonic()
        code = client.quit(timeout=session.timeout)
        elapsed = time.monotonic() - started
        if client.killed:
            raise CheckFailure(f"engine had to be killed after quit during a search ({elapsed:.3f} s)")
        if code != 0:
            raise CheckFailure(f"engine exited with code {code} after quit during a search", returncode=code)
    return Outcome(
        f"exited with code 0 in {elapsed:.3f} s while searching",
        details={"returncode": code, "exit_s": round(elapsed, 3)},
    )
