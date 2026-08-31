"""
The checks the suite runs, and the types they are written in.

Importing this package registers every check; :data:`registry.RAW_CHECKS` and :data:`registry.ACCEPTANCE_CHECKS`
then hold them in run order.
"""

from uci_test_suite.checks import acceptance, core, optional  # noqa: F401  (imported for registration)
from uci_test_suite.checks.base import Check, CheckFailure, CheckResult, CheckSkipped, Outcome, Scope, Status
from uci_test_suite.checks.registry import ACCEPTANCE_CHECKS, RAW_CHECKS
from uci_test_suite.checks.session import AcceptanceSession, Handshake, RawSession, SearchResult

__all__ = [
    "ACCEPTANCE_CHECKS",
    "RAW_CHECKS",
    "AcceptanceSession",
    "Check",
    "CheckFailure",
    "CheckResult",
    "CheckSkipped",
    "Handshake",
    "Outcome",
    "RawSession",
    "Scope",
    "SearchResult",
    "Status",
]
