#!/usr/bin/env python3
"""
A scripted UCI engine double.

With no arguments it behaves conformingly; each flag makes it break one rule:
``--no-uciok``, ``--no-author``, ``--no-options``, ``--bad-option``, ``--double-bestmove``, ``--illegal-move``,
``--die-on-go``.
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
]


def emit(text: str) -> None:
    print(text, flush=True)


def main(flags: set[str]) -> int:
    board = chess.Board()
    multipv = 1
    waiting = False  # a search that must not answer until stop/ponderhit

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
        elif word == "isready":
            emit("readyok")
        elif word == "setoption":
            if " name MultiPV value " in command:
                multipv = int(command.rsplit(maxsplit=1)[1])
        elif word == "position":
            board = parse_position(command)
        elif word == "go":
            if "--die-on-go" in flags:
                return 1
            if "infinite" in command or "ponder" in command:
                waiting = True
            else:
                answer(board, multipv, flags)
        elif word in ("stop", "ponderhit"):
            if waiting:
                waiting = False
                answer(board, multipv, flags)
        elif word == "quit":
            return 0
    return 0


def parse_position(command: str) -> chess.Board:
    """Rebuild the board from a ``position`` command."""
    tokens = command.split()
    moves = tokens[tokens.index("moves") + 1 :] if "moves" in tokens else []
    if "fen" in tokens:
        fen_end = tokens.index("moves") if "moves" in tokens else len(tokens)
        board = chess.Board(" ".join(tokens[tokens.index("fen") + 1 : fen_end]))
    else:
        board = chess.Board()
    for move in moves:
        board.push_uci(move)
    return board


def answer(board: chess.Board, multipv: int, flags: set[str]) -> None:
    """Report a search and its result."""
    moves = [move.uci() for move in board.legal_moves]
    if not moves:
        emit("bestmove (none)")
        return
    for variation in range(1, min(multipv, len(moves)) + 1):
        emit(
            f"info depth 8 seldepth 8 multipv {variation} score cp {30 - variation} "
            f"nodes 1234 nps 12340 time 100 pv {moves[variation - 1]}"
        )
    best = "a1a1" if "--illegal-move" in flags else moves[0]
    emit(f"bestmove {best}")
    if "--double-bestmove" in flags:
        emit(f"bestmove {best}")


if __name__ == "__main__":
    sys.exit(main(set(sys.argv[1:])))
