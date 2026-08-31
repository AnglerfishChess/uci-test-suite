"""Result and registration types shared by all check groups."""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "Check",
    "CheckFailure",
    "CheckResult",
    "CheckSkipped",
    "Outcome",
    "Scope",
    "Status",
]


class Scope(StrEnum):
    """Which part of the protocol a check speaks for."""

    CORE = "core"
    """Behaviour every UCI engine must implement."""

    OPTIONAL = "optional"
    """UCI features an engine may decline to offer, but must implement correctly once advertised."""

    ACCEPTANCE = "acceptance"
    """Driving the engine through a mainstream UCI client instead of the suite's own transport."""


class Status(StrEnum):
    """Outcome of a single check."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


@dataclass(frozen=True, slots=True)
class Outcome:
    """What a passing check reports."""

    message: str
    details: dict[str, Any] = field(default_factory=dict)


class CheckFailure(Exception):
    """Raised by a check when the engine misbehaves. Details are recorded with the result."""

    def __init__(self, message: str, **details: Any):
        super().__init__(message)
        self.message = message
        self.details = details


class CheckSkipped(Exception):
    """Raised by a check when the engine does not offer the feature under test."""

    def __init__(self, message: str, **details: Any):
        super().__init__(message)
        self.message = message
        self.details = details


@dataclass(frozen=True, slots=True)
class CheckResult:
    """The verdict on one check. All fields are plain data, suitable for machine-readable output."""

    name: str
    scope: Scope
    status: Status
    message: str
    duration: float
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Whether the engine got through this check; a skipped check counts as not failed."""
        return self.status is not Status.FAIL

    def __str__(self) -> str:
        label = self.status.name
        return f"{label}: {self.name} - {self.message}" if self.message else f"{label}: {self.name}"


@dataclass(frozen=True, slots=True)
class Check[S]:
    """A named check, and the session type it needs to run."""

    name: str
    scope: Scope
    func: Callable[[S], Outcome]
