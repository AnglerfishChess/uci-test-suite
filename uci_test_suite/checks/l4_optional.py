"""L4 — features an engine may decline to offer; each check is skipped unless the engine advertises it."""

from typing import Final

import esca

from uci_test_suite.checks.base import CheckFailure, CheckSkipped, Outcome
from uci_test_suite.checks.registry import raw_check
from uci_test_suite.checks.session import RawSession
from uci_test_suite.checks.verify import verify_move, verify_responsive, verify_single_bestmove
from uci_test_suite.levels import Level
from uci_test_suite.protocol import LineKind, OptionType, classify

#: A Chess960 position with the king on f1/f8 and rooks on b/h, where both sides may castle at once.
CHESS960_FEN: Final[str] = "1r3k1r/pppppppp/8/8/8/8/PPPPPPPP/1R3K1R w KQkq - 0 1"

#: White short castling in that position, written the Chess960 way: the king takes its own rook.
CHESS960_CASTLING: Final[str] = "f1h1"


@raw_check("ponder", Level.OPTIONAL, budget=25.0)
def check_ponder(session: RawSession) -> Outcome:
    """
    A ``go ponder`` search runs until ``ponderhit`` or ``stop``, and only then answers.

    Spec: "go ponder ... the engine must not stop searching until the GUI sends 'ponderhit' or 'stop'".
    """
    option = session.handshake.option("Ponder")
    if option is None:
        raise CheckSkipped("engine does not declare the Ponder option")
    if option.type is not OptionType.CHECK:
        raise CheckFailure(f"the Ponder option is of type {option.type}, not check")

    moves = ["e2e4", "e7e5"]
    game = esca.Game()
    for text in moves:
        game.play(text)

    session.set_option("Ponder", "true")
    try:
        session.set_position(moves=moves)
        session.send_go("ponder movetime 300")
        early = [line.text for line in session.collect_for(0.5) if classify(line.text) is LineKind.BESTMOVE]
        if early:
            raise CheckFailure("engine answered a ponder search before ponderhit", bestmove_lines=early)
        session.send("ponderhit")
        result = session.collect_search()
    finally:
        session.resync()
        session.set_option("Ponder", option.default or "false")

    verify_single_bestmove(result)
    move = verify_move(game, result.bestmove, f"the position after {' '.join(moves)}")
    return Outcome(
        f"ponder search held until ponderhit, then answered {result.bestmove.move}",
        details={
            "bestmove": result.bestmove.move,
            "bestmove_san": game.move_to_san(move),
            "ponder": result.bestmove.ponder,
            "ponderhit_latency_s": round(result.elapsed, 3),
        },
    )


@raw_check("multipv", Level.OPTIONAL, budget=45.0)
def check_multipv(session: RawSession) -> Outcome:
    """
    With MultiPV set to N, the engine labels its ``info`` lines with each variation number up to N.

    Spec: "multipv <num> ... this for the multi pv mode ... the engine should send all the 'info' lines".
    """
    option = session.handshake.option("MultiPV")
    if option is None:
        raise CheckSkipped("engine does not declare the MultiPV option")
    if option.type is not OptionType.SPIN:
        raise CheckFailure(f"the MultiPV option is of type {option.type}, not spin")
    wanted = min(3, option.max if option.max is not None else 3)
    if wanted < 2:
        raise CheckSkipped(f"engine caps MultiPV at {option.max}")

    session.set_option("MultiPV", str(wanted))
    try:
        session.set_position()
        result = session.go("depth 8")
    finally:
        session.resync()
        session.set_option("MultiPV", option.default or "1")

    verify_single_bestmove(result)
    game = esca.Game()
    verify_move(game, result.bestmove, "the starting position")

    seen = sorted({info.multipv for info in result.infos if info.multipv is not None})
    if not seen:
        raise CheckFailure(
            f"MultiPV set to {wanted}, but no info line carries a multipv number",
            info_lines=len(result.infos),
        )
    missing = [number for number in range(1, wanted + 1) if number not in seen]
    if missing:
        raise CheckFailure(f"MultiPV set to {wanted}, but variations {missing} were never reported", reported=seen)
    return Outcome(
        f"reported {wanted} variations",
        details={"requested": wanted, "reported": seen, "info_lines": len(result.infos)},
    )


@raw_check("chess960", Level.OPTIONAL, budget=25.0)
def check_chess960(session: RawSession) -> Outcome:
    """
    With ``UCI_Chess960`` set, a shuffled position is searched and castling is answered king-takes-rook.

    Spec: "UCI_Chess960 ... the engine supports Chess960 ... the castling move is a king move to the rook".
    """
    option = session.handshake.option("UCI_Chess960")
    if option is None:
        raise CheckSkipped("engine does not declare the UCI_Chess960 option")
    if option.type is not OptionType.CHECK:
        raise CheckFailure(f"the UCI_Chess960 option is of type {option.type}, not check")

    game = esca.Game.from_fen(CHESS960_FEN, variant=esca.CHESS960)
    game.play(CHESS960_CASTLING)
    session.set_option("UCI_Chess960", "true")
    try:
        session.set_position(fen=CHESS960_FEN, moves=[CHESS960_CASTLING])
        result = session.go("movetime 300")
    finally:
        session.resync()
        session.set_option("UCI_Chess960", option.default or "false")

    verify_single_bestmove(result)
    move = verify_move(game, result.bestmove, f"the Chess960 position after {CHESS960_CASTLING}")
    return Outcome(
        f"castling as {CHESS960_CASTLING} accepted, answered {result.bestmove.move}",
        details={
            "fen": CHESS960_FEN,
            "castling_move": CHESS960_CASTLING,
            "bestmove": result.bestmove.move,
            "bestmove_san": game.move_to_san(move),
        },
    )


@raw_check("analyse_mode", Level.OPTIONAL, budget=25.0)
def check_analyse_mode(session: RawSession) -> Outcome:
    """
    ``UCI_AnalyseMode`` can be switched on and off, and the engine still searches.

    Spec: "UCI_AnalyseMode ... the engine wants to behave differently when analysing or playing a game".
    """
    option = session.handshake.option("UCI_AnalyseMode")
    if option is None:
        raise CheckSkipped("engine does not declare the UCI_AnalyseMode option")
    if option.type is not OptionType.CHECK:
        raise CheckFailure(f"the UCI_AnalyseMode option is of type {option.type}, not check")

    game = esca.Game()
    session.set_option("UCI_AnalyseMode", "true")
    try:
        session.set_position()
        result = session.go("movetime 300")
    finally:
        session.resync()
        session.set_option("UCI_AnalyseMode", option.default or "false")

    verify_single_bestmove(result)
    move = verify_move(game, result.bestmove, "the starting position")
    return Outcome(
        f"analyse mode accepted, answered {result.bestmove.move}",
        details={"bestmove": result.bestmove.move, "bestmove_san": game.move_to_san(move)},
    )


@raw_check("registration_and_copyprotection", Level.OPTIONAL, budget=25.0)
def check_registration_and_copyprotection(session: RawSession) -> Outcome:
    """
    An engine that reports ``registration`` or ``copyprotection`` resolves both to ``ok`` or ``error``.

    Spec: "copyprotection [ checking | ok | error ]" and "registration [ checking | ok | error ]".
    """
    handshake = session.handshake
    guarded = [line for line in handshake.lines if classify(line) in (LineKind.COPYPROTECTION, LineKind.REGISTRATION)]
    if not guarded:
        raise CheckSkipped("engine sends neither copyprotection nor registration")

    session.send("register later")
    verify_responsive(session, "register later")
    states = {line.split()[0]: line.split()[-1] for line in guarded}
    unresolved = [keyword for keyword, state in states.items() if state not in ("ok", "error")]
    if unresolved:
        settled = [line.text for line in session.collect_for(1.0)]
        for line in settled:
            tokens = line.split()
            if tokens and tokens[0] in ("copyprotection", "registration"):
                states[tokens[0]] = tokens[-1]
        unresolved = [keyword for keyword, state in states.items() if state not in ("ok", "error")]
    if unresolved:
        raise CheckFailure(f"{', '.join(unresolved)} never resolved to ok or error", states=states)
    failed = [keyword for keyword, state in states.items() if state == "error"]
    if failed:
        raise CheckFailure(f"engine reports {', '.join(failed)} error", states=states)
    return Outcome(", ".join(f"{key} {value}" for key, value in states.items()), details={"states": states})
