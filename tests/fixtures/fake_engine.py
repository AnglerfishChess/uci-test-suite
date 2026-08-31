#!/usr/bin/env python3
"""
A scripted UCI engine double.

With no arguments it behaves conformingly; each flag makes it break one rule: ``--no-uciok``, ``--no-author``,
``--no-options``, ``--bad-option``, ``--double-bestmove``, ``--illegal-move``, ``--die-on-go``,
``--crash-on-fen``, ``--hang-on-stop``, ``--bestmove-without-go``, ``--depth-goes-back``, ``--zombie-on-quit``,
``--copyprotection``, ``--noisy-start``, ``--ignore-searchmoves``.
"""

import sys

import chess

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


def main(flags: set[str]) -> int:
    board = chess.Board(chess960=True)
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
        elif word == "position":
            board = parse_position(command, board, flags)
            if "--bestmove-without-go" in flags:
                emit("bestmove e2e4")
        elif word == "go":
            if "--die-on-go" in flags:
                return 1
            if "infinite" in command or "ponder" in command:
                waiting = True
            else:
                restricted = () if "--ignore-searchmoves" in flags else searchmoves(command)
                answer(board, multipv, flags, restricted)
        elif word in ("stop", "ponderhit"):
            if waiting and "--hang-on-stop" not in flags:
                waiting = False
                answer(board, multipv, flags, ())
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


def parse_position(command: str, current: chess.Board, flags: set[str]) -> chess.Board:
    """Rebuild the board from a ``position`` command, keeping the old one when the command makes no sense."""
    tokens = command.split()
    try:
        moves = tokens[tokens.index("moves") + 1 :] if "moves" in tokens else []
        if "fen" in tokens:
            if "--crash-on-fen" in flags:
                sys.exit(3)
            fen_end = tokens.index("moves") if "moves" in tokens else len(tokens)
            board = chess.Board(" ".join(tokens[tokens.index("fen") + 1 : fen_end]), chess960=True)
        else:
            board = chess.Board(chess960=True)
        for move in moves:
            board.push_uci(move)
    except ValueError:
        return current
    return board


def answer(board: chess.Board, multipv: int, flags: set[str], restricted: tuple[str, ...]) -> None:
    """Report a search and its result."""
    moves = [move.uci() for move in board.legal_moves]
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
