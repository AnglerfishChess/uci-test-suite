"""UCI-level views of a running engine, handed to the checks."""

import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Final

import esca.uci

from uci_test_suite.protocol import (
    BestMove,
    InfoLine,
    LineKind,
    OptionSpec,
    ProtocolError,
    classify,
    parse_bestmove,
    parse_id,
    parse_info,
    parse_option,
)
from uci_test_suite.transport import EngineTimeout, Line, RawUciClient

__all__ = [
    "AcceptanceSession",
    "Handshake",
    "ProcessSession",
    "RawSession",
    "SearchResult",
]

#: How long the engine may stay silent after a "bestmove" before the search is considered over.
SETTLE_TIME: Final[float] = 0.2

#: How long the engine may keep talking after "uciok" before the handshake is considered over.
HANDSHAKE_TAIL: Final[float] = 0.15


@dataclass(frozen=True, slots=True)
class Handshake:
    """What the engine said in answer to ``uci``, up to ``uciok`` and just after it."""

    id: dict[str, str]
    options: tuple[OptionSpec, ...]
    invalid_options: tuple[tuple[str, str], ...]
    """Option lines that failed to parse, as (line, reason) pairs."""
    unrecognized: tuple[str, ...]
    """Non-empty lines carrying no UCI keyword at all."""
    elapsed: float
    lines: tuple[str, ...]

    def option(self, name: str) -> OptionSpec | None:
        """The option with that exact name, if the engine advertises it."""
        return next((option for option in self.options if option.name == name), None)


@dataclass(frozen=True, slots=True)
class SearchResult:
    """What the engine said between a ``go`` and its ``bestmove``."""

    bestmove: BestMove
    infos: tuple[InfoLine, ...] = ()
    elapsed: float = 0.0
    extra_bestmoves: tuple[str, ...] = ()
    """Further ``bestmove`` lines that arrived after the first one; a conforming engine sends none."""
    invalid_lines: tuple[tuple[str, str], ...] = ()
    """Lines that failed to parse, as (line, reason) pairs."""
    lines: tuple[str, ...] = ()


class RawSession:
    """
    One engine process, addressed in UCI commands rather than raw lines.

    The ``uci`` handshake is performed on first use and its result reused afterwards. Methods raise
    :class:`uci_test_suite.transport.TransportError` when the engine goes silent or dies.
    """

    def __init__(self, client: RawUciClient, *, timeout: float = 10.0):
        """
        Args:
            client: A started transport client.
            timeout: Seconds allowed for a single exchange, unless a call overrides it.
        """
        self.client = client
        self.timeout = timeout
        self._handshake: Handshake | None = None
        self._handshake_error: Exception | None = None

    @property
    def handshake(self) -> Handshake:
        """
        Send ``uci`` once, and report everything the engine answered with.

        A failed handshake is remembered and re-raised, rather than retried on every use.
        """
        if self._handshake_error is not None:
            raise self._handshake_error
        if self._handshake is None:
            try:
                self._handshake = self._perform_handshake()
            except Exception as error:
                self._handshake_error = error
                raise
        return self._handshake

    def _perform_handshake(self) -> Handshake:
        started = time.monotonic()
        self.client.send("uci")
        lines = self.client.expect("uciok", timeout=self.timeout)
        elapsed = time.monotonic() - started
        lines += self.client.drain(quiet_for=HANDSHAKE_TAIL, timeout=1.0)

        identifiers: dict[str, str] = {}
        options: list[OptionSpec] = []
        invalid: list[tuple[str, str]] = []
        unrecognized: list[str] = []
        for line in lines:
            kind = classify(line.text)
            try:
                match kind:
                    case LineKind.ID:
                        parsed_id = parse_id(line.text)
                        if parsed_id is not None:
                            identifiers[parsed_id.key] = parsed_id.value
                    case LineKind.OPTION:
                        parsed_option = parse_option(line.text)
                        if parsed_option is not None:
                            options.append(parsed_option)
                    case LineKind.UNKNOWN:
                        unrecognized.append(line.text)
                    case _:
                        pass
            except ProtocolError as error:
                invalid.append((line.text, str(error)))
        return Handshake(
            id=identifiers,
            options=tuple(options),
            invalid_options=tuple(invalid),
            unrecognized=tuple(unrecognized),
            elapsed=elapsed,
            lines=tuple(line.text for line in lines),
        )

    def _require_handshake(self) -> None:
        """Put the engine into UCI mode, as every other command needs it to be."""
        _ = self.handshake

    def sync(self, timeout: float | None = None) -> float:
        """Send ``isready``, wait for ``readyok``, and report how long it took."""
        self._require_handshake()
        started = time.monotonic()
        self.client.send("isready")
        self.client.expect("readyok", timeout=self.timeout if timeout is None else timeout)
        return time.monotonic() - started

    def send(self, command: str) -> None:
        """Write one command line to the engine, without waiting for anything."""
        self.client.send(command)

    def new_game(self) -> None:
        """Send ``ucinewgame`` and wait for the engine to digest it."""
        self._require_handshake()
        self.client.send("ucinewgame")
        self.sync()

    def set_option(self, name: str, value: str | None = None) -> None:
        """Send ``setoption`` and wait for the engine to digest it."""
        command = f"setoption name {name}" if value is None else f"setoption name {name} value {value}"
        self.client.send(command)
        self.sync()

    def set_position(self, *, fen: str | None = None, moves: Sequence[str] = ()) -> None:
        """Send ``position`` (``startpos`` when no FEN is given) and wait for the engine to digest it."""
        command = "position startpos" if fen is None else f"position fen {fen}"
        if moves:
            command += " moves " + " ".join(moves)
        self.client.send(command)
        self.sync()

    def go(self, arguments: str = "", timeout: float | None = None) -> SearchResult:
        """Send ``go`` and collect everything up to and including the ``bestmove``."""
        self.send_go(arguments)
        return self.collect_search(timeout=timeout)

    def send_go(self, arguments: str = "") -> None:
        """Start a search without waiting for its result."""
        self._require_handshake()
        self.client.send(f"go {arguments}".rstrip())

    def stop(self) -> None:
        """Ask the engine to end the current search."""
        self.client.send("stop")

    def collect_search(self, timeout: float | None = None, settle: float = SETTLE_TIME) -> SearchResult:
        """
        Wait for the ``bestmove`` of a running search, then keep listening for ``settle`` seconds.

        Raises:
            EngineTimeout: No ``bestmove`` arrived in time.
        """
        started = time.monotonic()
        lines = self.client.expect(
            lambda text: classify(text) is LineKind.BESTMOVE,
            timeout=self.timeout if timeout is None else timeout,
        )
        elapsed = time.monotonic() - started
        infos: list[InfoLine] = []
        invalid: list[tuple[str, str]] = []
        best: BestMove | None = None
        for line in lines:
            try:
                match classify(line.text):
                    case LineKind.INFO:
                        info = parse_info(line.text)
                        if info is not None:
                            infos.append(info)
                    case LineKind.BESTMOVE:
                        best = parse_bestmove(line.text)
                    case _:
                        pass
            except ProtocolError as error:
                invalid.append((line.text, str(error)))
        if best is None:
            raise ProtocolError(f"unparsable bestmove line: {lines[-1].text!r}")

        trailing = self.collect_for(settle)
        extra = [line.text for line in trailing if classify(line.text) is LineKind.BESTMOVE]
        return SearchResult(
            bestmove=best,
            infos=tuple(infos),
            elapsed=elapsed,
            extra_bestmoves=tuple(extra),
            invalid_lines=tuple(invalid),
            lines=tuple(line.text for line in lines) + tuple(line.text for line in trailing),
        )

    def collect_for(self, duration: float) -> list[Line]:
        """Collect every line the engine emits over the next ``duration`` seconds."""
        deadline = time.monotonic() + duration
        collected: list[Line] = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return collected
            line = self.client.poll_line(remaining)
            if line is None:
                return collected
            collected.append(line)

    def resync(self) -> None:
        """Return the engine to an idle, responsive state, whatever the previous check left behind."""
        try:
            self.client.send("stop")
            self.client.drain(quiet_for=0.1, timeout=1.0)
            self.sync(timeout=min(self.timeout, 5.0))
        except EngineTimeout:
            pass


@dataclass(frozen=True, slots=True)
class ProcessSession:
    """The engine as a command line, spawned afresh for each use."""

    command: tuple[str, ...]
    timeout: float = 10.0

    @contextmanager
    def client(self) -> Iterator[RawUciClient]:
        """A started transport client on a new engine process, quit on exit."""
        client = RawUciClient(self.command, default_timeout=self.timeout)
        client.start()
        try:
            yield client
        finally:
            client.quit(timeout=self.timeout)

    @contextmanager
    def session(self) -> Iterator["RawSession"]:
        """A session on a new engine process, quit on exit."""
        with self.client() as client:
            yield RawSession(client, timeout=self.timeout)


@dataclass(slots=True)
class AcceptanceSession:
    """An ``esca`` UCI client bound to the engine, standing in for a mainstream GUI."""

    engine: esca.uci.Engine
    notes: dict[str, str] = field(default_factory=dict)
