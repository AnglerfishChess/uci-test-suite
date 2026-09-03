#!/usr/bin/env python3
"""
A scripted UCI engine double.

With no arguments it behaves conformingly; each flag makes it break one rule: ``--no-uciok``, ``--no-author``,
``--no-options``, ``--bad-option``, ``--double-bestmove``, ``--illegal-move``, ``--die-on-go``,
``--crash-on-fen``, ``--hang-on-stop``, ``--bestmove-without-go``, ``--depth-goes-back``, ``--zombie-on-quit``,
``--copyprotection``, ``--noisy-start``, ``--ignore-searchmoves``.
"""

import sys

import esca

OPTIONS = [
    "option name Hash type spin default 16 min 1 max 1024",
    "option name Ponder type check default false",
    "option name MultiPV type spin default 1 min 1 max 8",
    "option name Style type combo default Solid var Solid var Wild",
    "option name Clear Hash type button",
    "option name SyzygyPath type string default <empty>",
    "option name UCI_Chess960 type check default false",
    "option name UCI_AnalyseMode type check default false",
]

GO_KEYWORDS = frozenset(
    {
        "searchmoves",
        "ponder",
        "wtime",
        "btime",
        "winc",
        "binc",
        "movestogo",
        "depth",
        "nodes",
        "mate",
        "movetime",
        "infinite",
    }
)


def emit(text: str) -> None:
    print(text, flush=True)


def new_game(chess960: bool) -> esca.Game:
    """A game on the standard array, in the variant the engine is currently switched into."""
    variant = esca.CHESS960 if chess960 else esca.CLASSIC
    game = esca.Game.from_fen(esca.CLASSIC.start_position().fen, variant=variant)
    game.castling_output = esca.KING_TO_ROOK if chess960 else esca.KING_TWO_SQUARES
    return game


def main(flags: set[str]) -> int:
    chess960 = False
    game = new_game(chess960)
    multipv = 1
    waiting = False  # a search that must not answer until stop/ponderhit

    if "--noisy-start" in flags:
        emit("bestmove e2e4")

    for raw in sys.stdin:
        command = raw.strip()
        word = command.split(maxsplit=1)[0] if command else ""

        if word == "uci":
            emit("Fake engine, not a real one")
            emit("id name Fake Engine 1.0")
            if "--no-author" not in flags:
                emit("id author The UCI test suite")
            if "--no-options" not in flags:
                for option in OPTIONS:
                    emit(option)
            if "--bad-option" in flags:
                emit("option name Broken type spin default 99 min 1 max 8")
            if "--no-uciok" not in flags:
                emit("uciok")
            if "--copyprotection" in flags:
                emit("copyprotection checking")
                emit("copyprotection ok")
        elif word == "isready":
            emit("readyok")
        elif word == "setoption":
            if " name MultiPV value " in command:
                multipv = int(command.rsplit(maxsplit=1)[1])
            elif " name UCI_Chess960 value " in command:
                chess960 = command.rsplit(maxsplit=1)[1] == "true"
        elif word == "position":
            game = parse_position(command, game, chess960, flags)
            if "--bestmove-without-go" in flags:
                emit("bestmove e2e4")
        elif word == "go":
            if "--die-on-go" in flags:
                return 1
            if "infinite" in command or "ponder" in command:
                waiting = True
            else:
                restricted = () if "--ignore-searchmoves" in flags else searchmoves(command)
                answer(game, multipv, flags, restricted)
        elif word in ("stop", "ponderhit"):
            if waiting and "--hang-on-stop" not in flags:
                waiting = False
                answer(game, multipv, flags, ())
        elif word == "quit":
            if "--zombie-on-quit" in flags:
                continue
            return 0
    return 0


def searchmoves(command: str) -> tuple[str, ...]:
    """The moves a ``go`` command restricts the search to; empty when it names none."""
    tokens = command.split()
    if "searchmoves" not in tokens:
        return ()
    wanted = []
    for token in tokens[tokens.index("searchmoves") + 1 :]:
        if token in GO_KEYWORDS:
            break
        wanted.append(token)
    return tuple(wanted)


def parse_position(command: str, current: esca.Game, chess960: bool, flags: set[str]) -> esca.Game:
    """Rebuild the game from a ``position`` command, keeping the old one when the command makes no sense."""
    tokens = command.split()
    try:
        moves = tokens[tokens.index("moves") + 1 :] if "moves" in tokens else []
        if "fen" in tokens:
            if "--crash-on-fen" in flags:
                sys.exit(3)
            fen_end = tokens.index("moves") if "moves" in tokens else len(tokens)
            fen = " ".join(tokens[tokens.index("fen") + 1 : fen_end])
            game = esca.Game.from_fen(fen, variant=esca.CHESS960 if chess960 else esca.CLASSIC)
            game.castling_output = esca.KING_TO_ROOK if chess960 else esca.KING_TWO_SQUARES
        else:
            game = new_game(chess960)
        for move in moves:
            game.play(move)
    except ValueError:
        return current
    return game


def answer(game: esca.Game, multipv: int, flags: set[str], restricted: tuple[str, ...]) -> None:
    """Report a search and its result. The move answered is the last legal one, not the first."""
    moves = [game.move_to_uci(move) for move in reversed(game.legal_moves())]
    if restricted:
        moves = [move for move in moves if move in restricted] or moves
    if not moves:
        emit("bestmove (none)")
        return
    depths = (5, 2) if "--depth-goes-back" in flags else (8,)
    for depth in depths:
        for variation in range(1, min(multipv, len(moves)) + 1):
            emit(
                f"info depth {depth} seldepth {depth} multipv {variation} score cp {30 - variation} "
                f"nodes 1234 nps 12340 time 100 pv {moves[variation - 1]}"
            )
    best = "a1a1" if "--illegal-move" in flags else moves[0]
    emit(f"bestmove {best}")
    if "--double-bestmove" in flags:
        emit(f"bestmove {best}")


if __name__ == "__main__":
    sys.exit(main(set(sys.argv[1:])))
