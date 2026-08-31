"""
Line-level transport to a UCI engine subprocess.

Owns the process and its pipes, timestamps every line in both directions, and never interprets the protocol.
"""

import io
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import TracebackType
from typing import Final, Self

logger: Final[logging.Logger] = logging.getLogger(__name__)

__all__ = [
    "Direction",
    "EngineDied",
    "EngineTimeout",
    "Line",
    "RawUciClient",
    "TransportError",
]

#: How long to wait for a line when the caller does not say.
DEFAULT_TIMEOUT: Final[float] = 10.0

#: How long a stopping engine gets to exit on its own before being killed.
DEFAULT_QUIT_TIMEOUT: Final[float] = 5.0

#: Keeps a console engine from flashing its own window open on Windows; zero everywhere else.
_NO_WINDOW: Final[int] = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


class TransportError(Exception):
    """Base class for transport failures."""


class EngineTimeout(TransportError):
    """The engine did not produce the awaited line in time."""

    def __init__(self, message: str, lines: Sequence["Line"] = ()):
        super().__init__(message)
        self.lines: tuple[Line, ...] = tuple(lines)


class EngineDied(TransportError):
    """The engine process closed its output or exited."""

    def __init__(self, message: str, returncode: int | None = None):
        super().__init__(message)
        self.returncode = returncode


class Direction(StrEnum):
    """Which way a line travelled."""

    SENT = ">>"
    RECEIVED = "<<"


@dataclass(frozen=True, slots=True)
class Line:
    """One line of the conversation, with the seconds elapsed since the client was started."""

    direction: Direction
    text: str
    at: float

    def __str__(self) -> str:
        return f"[{self.at:8.3f}] {self.direction.value} {self.text}"


class RawUciClient:
    """
    A UCI engine subprocess addressed one text line at a time.

    Every read is bounded by a timeout and fails loudly rather than blocking; a dead process is reported as
    :class:`EngineDied` instead of an endless wait. Usable as a context manager, which quits the engine on exit.
    """

    def __init__(
        self,
        command: str | Sequence[str],
        *,
        default_timeout: float = DEFAULT_TIMEOUT,
        cwd: str | os.PathLike[str] | None = None,
    ):
        """
        Args:
            command: Engine executable, or an argv sequence.
            default_timeout: Seconds to wait for a line when a call does not specify its own timeout.
            cwd: Working directory for the engine process.
        """
        self.command: tuple[str, ...] = (command,) if isinstance(command, str) else tuple(command)
        self.default_timeout = default_timeout
        self.cwd = cwd
        self._process: subprocess.Popen[str] | None = None
        self._queue: queue.Queue[Line | None] = queue.Queue()
        self._transcript: list[Line] = []
        self._stderr: list[str] = []
        self._lock = threading.Lock()
        self._started_at: float = 0.0
        self._eof = False
        self._killed = False

    @property
    def transcript(self) -> tuple[Line, ...]:
        """Every line sent and received so far, in order."""
        with self._lock:
            return tuple(self._transcript)

    @property
    def stderr_lines(self) -> tuple[str, ...]:
        """Everything the engine wrote to its standard error."""
        with self._lock:
            return tuple(self._stderr)

    @property
    def returncode(self) -> int | None:
        """Exit code of the engine process; ``None`` while it runs or before it is started."""
        return self._process.poll() if self._process is not None else None

    @property
    def killed(self) -> bool:
        """Whether the engine had to be terminated instead of exiting by itself."""
        return self._killed

    def start(self) -> None:
        """Spawn the engine process and begin collecting its output."""
        if self._process is not None:
            raise TransportError("already started")
        logger.debug("Starting engine: %s", " ".join(self.command))
        self._started_at = time.monotonic()
        try:
            self._process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.cwd,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=_NO_WINDOW,
            )
        except OSError as error:
            raise TransportError(f"cannot start {' '.join(self.command)}: {error}") from error
        if isinstance(self._process.stdin, io.TextIOWrapper):
            # UCI commands end in a bare newline on every platform.
            self._process.stdin.reconfigure(newline="\n")
        threading.Thread(target=self._pump_stdout, name="uci-stdout", daemon=True).start()
        threading.Thread(target=self._pump_stderr, name="uci-stderr", daemon=True).start()

    def is_alive(self) -> bool:
        """Whether the engine process is started and still running."""
        return self._process is not None and self._process.poll() is None

    def require_alive(self) -> None:
        """Raise :class:`EngineDied` unless the engine process is still running."""
        if self._process is None:
            raise EngineDied("engine is not started")
        code = self._process.poll()
        if code is not None:
            raise EngineDied(f"engine exited with code {code}", returncode=code)

    def send(self, text: str) -> Line:
        """Write one command line to the engine."""
        self.require_alive()
        process = self._process
        assert process is not None and process.stdin is not None
        line = self._record(Direction.SENT, text)
        logger.debug("%s", line)
        try:
            process.stdin.write(text + "\n")
            process.stdin.flush()
        except OSError as error:
            raise EngineDied(f"cannot write to the engine: {error}", returncode=process.poll()) from error
        return line

    def poll_line(self, timeout: float | None = None) -> Line | None:
        """Next line from the engine, or ``None`` if none arrives within the timeout."""
        deadline = time.monotonic() + (self.default_timeout if timeout is None else timeout)
        while True:
            if self._eof:
                raise EngineDied("the engine closed its output", returncode=self.returncode)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            try:
                item = self._queue.get(timeout=min(remaining, 0.2))
            except queue.Empty:
                continue
            if item is None:
                self._eof = True
                raise EngineDied("the engine closed its output", returncode=self.returncode)
            return item

    def read_line(self, timeout: float | None = None) -> Line:
        """Next line from the engine; raises :class:`EngineTimeout` if none arrives in time."""
        line = self.poll_line(timeout)
        if line is None:
            raise EngineTimeout(f"no line within {self.default_timeout if timeout is None else timeout} s")
        return line

    def expect(self, match: str | Callable[[str], bool], timeout: float | None = None) -> list[Line]:
        """
        Read lines until one matches, and return everything read, the matching line last.

        Args:
            match: A predicate on the line text, or a string to compare with the line's first token.
            timeout: Seconds allowed for the whole wait.

        Raises:
            EngineTimeout: Nothing matched in time; the lines seen so far are on the exception.
        """
        predicate = _first_token_is(match) if isinstance(match, str) else match
        limit = self.default_timeout if timeout is None else timeout
        deadline = time.monotonic() + limit
        seen: list[Line] = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise EngineTimeout(f"no matching line within {limit} s", seen)
            line = self.poll_line(remaining)
            if line is None:
                raise EngineTimeout(f"no matching line within {limit} s", seen)
            seen.append(line)
            if predicate(line.text):
                return seen

    def drain(self, quiet_for: float = 0.1, timeout: float = 2.0) -> list[Line]:
        """Read whatever the engine has to say until it stays silent for ``quiet_for`` seconds."""
        deadline = time.monotonic() + timeout
        collected: list[Line] = []
        while time.monotonic() < deadline:
            try:
                line = self.poll_line(quiet_for)
            except EngineDied:
                break
            if line is None:
                break
            collected.append(line)
        return collected

    def quit(self, timeout: float = DEFAULT_QUIT_TIMEOUT) -> int | None:
        """Ask the engine to quit, then kill it if it lingers. Returns its exit code."""
        process = self._process
        if process is None:
            return None
        if process.poll() is None:
            try:
                self.send("quit")
            except TransportError:
                logger.debug("Engine is already gone, no 'quit' sent")
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning("Engine did not exit within %s s, killing it", timeout)
            self.kill()
        self._close_pipes()
        return process.poll()

    def kill(self) -> None:
        """Terminate the engine process, hard."""
        process = self._process
        if process is None or process.poll() is not None:
            return
        self._killed = True
        process.kill()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            logger.error("Engine survived being killed")

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.quit()

    def _record(self, direction: Direction, text: str) -> Line:
        line = Line(direction=direction, text=text, at=time.monotonic() - self._started_at)
        with self._lock:
            self._transcript.append(line)
        return line

    def _pump_stdout(self) -> None:
        process = self._process
        assert process is not None and process.stdout is not None
        try:
            for raw in process.stdout:
                line = self._record(Direction.RECEIVED, raw.rstrip("\r\n"))
                logger.debug("%s", line)
                self._queue.put(line)
        except (OSError, ValueError):
            logger.debug("Engine stdout reader stopped", exc_info=True)
        finally:
            # Give the process a moment to be reaped, so that its exit code is known by the time the end of its
            # output is reported.
            try:
                process.wait(timeout=DEFAULT_QUIT_TIMEOUT)
            except subprocess.TimeoutExpired:
                logger.debug("Engine closed its output but is still running")
            self._queue.put(None)

    def _pump_stderr(self) -> None:
        process = self._process
        assert process is not None and process.stderr is not None
        try:
            for raw in process.stderr:
                text = raw.rstrip("\r\n")
                with self._lock:
                    self._stderr.append(text)
                logger.debug("engine stderr: %s", text)
        except (OSError, ValueError):
            logger.debug("Engine stderr reader stopped", exc_info=True)

    def _close_pipes(self) -> None:
        process = self._process
        if process is None:
            return
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None:
                try:
                    pipe.close()
                except OSError:
                    pass


def _first_token_is(token: str) -> Callable[[str], bool]:
    def predicate(text: str) -> bool:
        parts = text.split(maxsplit=1)
        return bool(parts) and parts[0] == token

    return predicate
