"""Running the registered checks against one engine and collecting their verdicts."""

import logging
import time
from collections.abc import Collection, Sequence
from typing import Any, Final

import chess.engine

from uci_test_suite.checks import ACCEPTANCE_CHECKS, RAW_CHECKS
from uci_test_suite.checks.base import Check, CheckFailure, CheckResult, CheckSkipped, Scope, Status
from uci_test_suite.checks.session import AcceptanceSession, RawSession
from uci_test_suite.transport import DEFAULT_TIMEOUT, EngineDied, RawUciClient, TransportError

logger: Final[logging.Logger] = logging.getLogger(__name__)

__all__ = ["run_suite"]


def run_suite(
    engine: str | Sequence[str],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    scopes: Collection[Scope] | None = None,
) -> list[CheckResult]:
    """
    Run every registered check of the selected scopes against the engine.

    Each check gets a fresh verdict even if an earlier one failed; a crashed engine fails the rest of its group
    immediately instead of waiting for timeouts.

    Args:
        engine: Engine executable, or an argv sequence.
        timeout: Seconds allowed for a single exchange with the engine.
        scopes: Scopes to run; all of them when ``None``.
    """
    wanted = set(Scope) if scopes is None else set(scopes)
    results: list[CheckResult] = []
    raw_checks = [check for check in RAW_CHECKS if check.scope in wanted]
    if raw_checks:
        results.extend(_run_raw_checks(engine, raw_checks, timeout=timeout))
    acceptance_checks = [check for check in ACCEPTANCE_CHECKS if check.scope in wanted]
    if acceptance_checks:
        results.extend(_run_acceptance_checks(engine, acceptance_checks))
    return results


def _run_raw_checks(
    engine: str | Sequence[str],
    checks: Sequence[Check[RawSession]],
    *,
    timeout: float,
) -> list[CheckResult]:
    """Run the checks that speak to the engine over the suite's own transport, in one engine session."""
    client = RawUciClient(engine, default_timeout=timeout)
    try:
        client.start()
    except TransportError as error:
        return [_dead(check, str(error)) for check in checks]

    session = RawSession(client, timeout=timeout)
    results: list[CheckResult] = []
    try:
        for index, check in enumerate(checks):
            if not client.is_alive():
                results.extend(_dead(rest, "the engine is no longer running") for rest in checks[index:])
                break
            results.append(_run(check, session))
            if client.is_alive():
                try:
                    session.resync()
                except TransportError as error:
                    logger.debug("Cannot resynchronize after %s: %s", check.name, error)
    finally:
        client.quit()
        logger.debug("Engine exited with code %s", client.returncode)
    return results


def _run_acceptance_checks(
    engine: str | Sequence[str],
    checks: Sequence[Check[AcceptanceSession]],
) -> list[CheckResult]:
    """Run the checks that drive the engine through ``python-chess``, in one engine session."""
    command = [engine] if isinstance(engine, str) else list(engine)
    try:
        simple_engine = chess.engine.SimpleEngine.popen_uci(command)
    except (OSError, ValueError, chess.engine.EngineError) as error:
        return [_dead(check, f"python-chess cannot start the engine: {error}") for check in checks]

    session = AcceptanceSession(engine=simple_engine)
    try:
        return [_run(check, session) for check in checks]
    finally:
        try:
            simple_engine.quit()
        except chess.engine.EngineError as error:
            logger.debug("python-chess could not quit the engine cleanly: %s", error)
        simple_engine.close()


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
        scope=check.scope,
        status=status,
        message=message,
        duration=time.monotonic() - started,
        details=details,
    )


def _dead(check: Check[Any], message: str) -> CheckResult:
    """The verdict for a check that could not be attempted at all."""
    return CheckResult(name=check.name, scope=check.scope, status=Status.FAIL, message=message, duration=0.0)
