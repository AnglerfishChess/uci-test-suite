"""
The checks the suite runs, and the types they are written in.

Importing this package registers every check; :func:`registry.checks_of` then hands them out in run order.
"""

from uci_test_suite.checks import (  # noqa: F401  (imported for registration)
    l0_process,
    l1_handshake,
    l2_play,
    l3_session,
    l4_optional,
    l5_robustness,
    l6_acceptance,
)
from uci_test_suite.checks.base import Check, CheckFailure, CheckResult, CheckSkipped, Driver, Outcome, Status
from uci_test_suite.checks.registry import CHECKS, checks_of
from uci_test_suite.checks.session import AcceptanceSession, Handshake, ProcessSession, RawSession, SearchResult

__all__ = [
    "CHECKS",
    "AcceptanceSession",
    "Check",
    "CheckFailure",
    "CheckResult",
    "CheckSkipped",
    "Driver",
    "Handshake",
    "Outcome",
    "ProcessSession",
    "RawSession",
    "SearchResult",
    "Status",
    "checks_of",
]
