"""Running the registered checks against one engine, level by level, and collecting their verdicts."""

import logging
import time
from collections.abc import Collection, Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Final, Self

import chess.engine

from uci_test_suite.checks.base import Check, CheckFailure, CheckResult, CheckSkipped, Driver, Status
from uci_test_suite.checks.registry import checks_of
from uci_test_suite.checks.session import AcceptanceSession, ProcessSession, RawSession
from uci_test_suite.levels import Level
from uci_test_suite.transport import (
    DEFAULT_QUIT_TIMEOUT,
    DEFAULT_TIMEOUT,
    EngineDied,
    RawUciClient,
    TransportError,
)

logger: Final[logging.Logger] = logging.getLogger(__name__)

__all__ = ["run_suite"]


def run_suite(
    engine: str | Sequence[str],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    levels: Collection[Level] | None = None,
) -> list[CheckResult]:
    """
    Run every registered check of the selected levels against the engine, lowest level first.

    Each level gets its own engine process; a crashed engine fails the rest of that level immediately instead of
    waiting for timeouts, and the next level starts afresh.

    Args:
        engine: Engine executable, or its whole command line as an argv sequence.
        timeout: Seconds allowed for a single exchange with the engine; also scales every check's own budget.
        levels: Levels to run; all of them when ``None``.
    """
    command = (engine,) if isinstance(engine, str) else tuple(engine)
    scale = timeout / DEFAULT_TIMEOUT
    selected = checks_of(None if levels is None else set(levels))
    results: list[CheckResult] = []
    for level in sorted({check.level for check in selected}):
        level_checks = [check for check in selected if check.level is level]
        logger.debug("Level %s: %d checks", level, len(level_checks))
        results.extend(_run_level(command, level_checks, scale=scale))
    return results


def _run_level(command: tuple[str, ...], checks: Sequence[Check[Any]], *, scale: float) -> list[CheckResult]:
    """Run one level's checks, opening an engine session per driver and closing them all at the end."""
    results: list[CheckResult] = []
    shared = (Driver.RAW, Driver.PYCHESS)
    with _Sessions(command, scale) as sessions:
        unusable: dict[Driver, str] = {}
        for check in checks:
            if check.driver in unusable:
                results.append(_dead(check, unusable[check.driver]))
                continue
            with sessions.open(check) as (session, refusal):
                if refusal is not None:
                    if check.driver in shared:
                        unusable[check.driver] = refusal
                    results.append(_dead(check, refusal))
                    continue
                results.append(_run(check, session))
                sessions.settle(check)
    return results


class _Sessions:
    """The engine sessions one level needs, each opened on first use and closed when the level ends."""

    def __init__(self, command: tuple[str, ...], scale: float):
        self.command = command
        self.scale = scale
        self._client: RawUciClient | None = None
        self._raw: RawSession | None = None
        self._simple: chess.engine.SimpleEngine | None = None
        self._quit_timeout = DEFAULT_QUIT_TIMEOUT

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        if self._client is not None:
            self._client.quit(timeout=self._quit_timeout)
            logger.debug("Engine exited with code %s", self._client.returncode)
        if self._simple is not None:
            try:
                self._simple.quit()
            except chess.engine.EngineError as error:
                logger.debug("python-chess could not quit the engine cleanly: %s", error)
            self._simple.close()

    @contextmanager
    def open(self, check: Check[Any]) -> Iterator[tuple[Any, str | None]]:
        """The session the check needs, or the reason it cannot be attempted; per-check ones close on exit."""
        budget = check.budget * self.scale
        match check.driver:
            case Driver.PROCESS:
                yield ProcessSession(command=self.command, timeout=budget), None
            case Driver.FRESH:
                client = RawUciClient(self.command, default_timeout=budget)
                try:
                    client.start()
                except TransportError as error:
                    yield None, str(error)
                    return
                try:
                    yield RawSession(client, timeout=budget), None
                finally:
                    client.quit(timeout=min(budget, DEFAULT_QUIT_TIMEOUT))
            case Driver.RAW:
                yield self._raw_session(budget)
            case Driver.PYCHESS:
                yield self._pychess_session(budget)

    def settle(self, check: Check[Any]) -> None:
        """Put a shared session back into an idle, responsive state after a check."""
        if check.driver is not Driver.RAW or self._raw is None or self._client is None:
            return
        if not self._client.is_alive():
            return
        try:
            self._raw.resync()
        except TransportError as error:
            logger.debug("Cannot resynchronize after %s: %s", check.name, error)

    def _raw_session(self, budget: float) -> tuple[RawSession | None, str | None]:
        if self._raw is None:
            client = RawUciClient(self.command, default_timeout=budget)
            try:
                client.start()
            except TransportError as error:
                return None, str(error)
            self._client = client
            self._raw = RawSession(client, timeout=budget)
        if self._client is None or not self._client.is_alive():
            return None, "the engine is no longer running"
        self._client.default_timeout = budget
        self._raw.timeout = budget
        self._quit_timeout = min(budget, DEFAULT_QUIT_TIMEOUT)
        return self._raw, None

    def _pychess_session(self, budget: float) -> tuple[AcceptanceSession | None, str | None]:
        if self._simple is None:
            try:
                self._simple = chess.engine.SimpleEngine.popen_uci(list(self.command), timeout=budget)
            except (OSError, ValueError, chess.engine.EngineError) as error:
                return None, f"python-chess cannot start the engine: {error}"
        self._simple.timeout = budget
        return AcceptanceSession(engine=self._simple), None


def _run[S](check: Check[S], session: S) -> CheckResult:
    """Run one check, turning whatever it raises into a verdict."""
    logger.debug("Running check: %s", check.name)
    started = time.monotonic()
    try:
        outcome = check.func(session)
    except CheckSkipped as skipped:
        return _result(check, Status.SKIP, skipped.message, skipped.details, started)
    except CheckFailure as failure:
        return _result(check, Status.FAIL, failure.message, failure.details, started)
    except EngineDied as died:
        return _result(check, Status.FAIL, f"engine died: {died}", {"returncode": died.returncode}, started)
    except TransportError as error:
        return _result(check, Status.FAIL, str(error), {"error": type(error).__name__}, started)
    except Exception as error:  # A broken check must not abort the suite.
        logger.exception("Check %s raised", check.name)
        return _result(check, Status.FAIL, f"{type(error).__name__}: {error}", {"error": type(error).__name__}, started)
    return _result(check, Status.PASS, outcome.message, outcome.details, started)


def _result(check: Check[Any], status: Status, message: str, details: dict[str, Any], started: float) -> CheckResult:
    return CheckResult(
        name=check.name,
        level=check.level,
        status=status,
        message=message,
        duration=time.monotonic() - started,
        details=details,
    )


def _dead(check: Check[Any], message: str) -> CheckResult:
    """The verdict for a check that could not be attempted at all."""
    return CheckResult(name=check.name, level=check.level, status=Status.FAIL, message=message, duration=0.0)
