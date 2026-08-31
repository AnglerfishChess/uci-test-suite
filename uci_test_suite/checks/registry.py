"""The catalogue of checks, in the order they should be run."""

from collections.abc import Callable
from typing import Final

from uci_test_suite.checks.base import Check, Outcome, Scope
from uci_test_suite.checks.session import AcceptanceSession, RawSession

__all__ = [
    "ACCEPTANCE_CHECKS",
    "RAW_CHECKS",
    "acceptance_check",
    "raw_check",
]

#: Checks driven over the suite's own line transport, in registration order.
RAW_CHECKS: Final[list[Check[RawSession]]] = []

#: Checks driven through ``python-chess``, in registration order.
ACCEPTANCE_CHECKS: Final[list[Check[AcceptanceSession]]] = []

type RawCheckFunc = Callable[[RawSession], Outcome]
type AcceptanceCheckFunc = Callable[[AcceptanceSession], Outcome]


def raw_check(name: str, scope: Scope = Scope.CORE) -> Callable[[RawCheckFunc], RawCheckFunc]:
    """Register a check that talks to the engine over the raw transport."""

    def decorate(func: RawCheckFunc) -> RawCheckFunc:
        RAW_CHECKS.append(Check(name=name, scope=scope, func=func))
        return func

    return decorate


def acceptance_check(name: str) -> Callable[[AcceptanceCheckFunc], AcceptanceCheckFunc]:
    """Register a check that drives the engine through ``python-chess``."""

    def decorate(func: AcceptanceCheckFunc) -> AcceptanceCheckFunc:
        ACCEPTANCE_CHECKS.append(Check(name=name, scope=Scope.ACCEPTANCE, func=func))
        return func

    return decorate
