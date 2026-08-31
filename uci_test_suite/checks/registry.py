"""The catalogue of checks, in the order they should be run."""

from collections.abc import Callable
from typing import Any, Final

from uci_test_suite.checks.base import Check, Driver, Outcome
from uci_test_suite.checks.session import AcceptanceSession, ProcessSession, RawSession
from uci_test_suite.levels import Level

__all__ = [
    "CHECKS",
    "acceptance_check",
    "checks_of",
    "fresh_check",
    "process_check",
    "raw_check",
]

#: Every registered check, ordered by level and then by registration.
CHECKS: Final[list[Check[Any]]] = []

#: Seconds a check may spend talking to the engine when it does not ask for more.
DEFAULT_BUDGET: Final[float] = 10.0

type ProcessCheckFunc = Callable[[ProcessSession], Outcome]
type RawCheckFunc = Callable[[RawSession], Outcome]
type AcceptanceCheckFunc = Callable[[AcceptanceSession], Outcome]


def checks_of(levels: frozenset[Level] | set[Level] | None = None) -> list[Check[Any]]:
    """Registered checks of the given levels (all of them when ``None``), in run order."""
    wanted = set(Level) if levels is None else set(levels)
    return sorted((check for check in CHECKS if check.level in wanted), key=lambda check: check.level)


def process_check(
    name: str, level: Level, budget: float = DEFAULT_BUDGET
) -> Callable[[ProcessCheckFunc], ProcessCheckFunc]:
    """Register a check that spawns engine processes of its own."""

    def decorate(func: ProcessCheckFunc) -> ProcessCheckFunc:
        CHECKS.append(Check(name=name, level=level, driver=Driver.PROCESS, func=func, budget=budget))
        return func

    return decorate


def raw_check(name: str, level: Level, budget: float = DEFAULT_BUDGET) -> Callable[[RawCheckFunc], RawCheckFunc]:
    """Register a check that talks to the engine over the raw transport."""

    def decorate(func: RawCheckFunc) -> RawCheckFunc:
        CHECKS.append(Check(name=name, level=level, driver=Driver.RAW, func=func, budget=budget))
        return func

    return decorate


def fresh_check(name: str, level: Level, budget: float = DEFAULT_BUDGET) -> Callable[[RawCheckFunc], RawCheckFunc]:
    """Register a check that talks to the engine over the raw transport, on a process of its own."""

    def decorate(func: RawCheckFunc) -> RawCheckFunc:
        CHECKS.append(Check(name=name, level=level, driver=Driver.FRESH, func=func, budget=budget))
        return func

    return decorate


def acceptance_check(name: str, budget: float = DEFAULT_BUDGET) -> Callable[[AcceptanceCheckFunc], AcceptanceCheckFunc]:
    """Register a check that drives the engine through ``python-chess``."""

    def decorate(func: AcceptanceCheckFunc) -> AcceptanceCheckFunc:
        CHECKS.append(Check(name=name, level=Level.ACCEPTANCE, driver=Driver.PYCHESS, func=func, budget=budget))
        return func

    return decorate
