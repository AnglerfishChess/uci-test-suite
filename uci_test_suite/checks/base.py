"""Result and registration types shared by all levels."""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from uci_test_suite.levels import Level

__all__ = [
    "Check",
    "CheckFailure",
    "CheckResult",
    "CheckSkipped",
    "Driver",
    "Outcome",
    "Status",
]


class Driver(StrEnum):
    """How a check reaches the engine."""

    PROCESS = "process"
    """Spawns and disposes of engine processes of its own."""

    RAW = "raw"
    """Speaks UCI over the suite's own line transport, on the engine session shared by its level."""

    FRESH = "fresh"
    """Speaks UCI over the suite's own line transport, on an engine process started for this check alone."""

    PYCHESS = "pychess"
    """Drives the engine through the ``python-chess`` client."""


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
    level: Level
    status: Status
    message: str
    duration: float
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Whether the engine got through this check; a skipped check counts as not failed."""
        return self.status is not Status.FAIL

    def as_dict(self) -> dict[str, Any]:
        """The verdict as JSON-ready data."""
        return {
            "level": int(self.level),
            "level_name": self.level.title.lower(),
            "name": self.name,
            "status": str(self.status),
            "message": self.message,
            "duration_s": round(self.duration, 3),
            "details": self.details,
        }

    def __str__(self) -> str:
        label = f"{self.status.name} [{self.level.tag}]"
        return f"{label}: {self.name} - {self.message}" if self.message else f"{label}: {self.name}"


@dataclass(frozen=True, slots=True)
class Check[S]:
    """A named check, the layer it speaks for, and the session type it needs to run."""

    name: str
    level: Level
    driver: Driver
    func: Callable[[S], Outcome]
    budget: float
    """Seconds this check may spend talking to the engine, before ``--timeout`` scaling."""

    @property
    def purpose(self) -> str:
        """First line of the check's docstring."""
        doc = (self.func.__doc__ or "").strip().replace("``", "")
        return " ".join(doc.split("\n\n")[0].split())
