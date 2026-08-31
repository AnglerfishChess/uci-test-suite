"""Turning check verdicts into the suite's human and machine output."""

from collections.abc import Sequence
from typing import Any, Final

from uci_test_suite.checks.base import Check, CheckResult, Status
from uci_test_suite.levels import MINIMUM_ENGINE, Level, format_levels

__all__ = [
    "MINIMUM_NOTE",
    "catalogue",
    "level_summary",
    "level_verdicts",
    "payload",
]

#: What passing the lowest levels means, said once wherever the levels are listed.
MINIMUM_NOTE: Final[str] = f"{format_levels(set(MINIMUM_ENGINE))} together are the minimum UCI engine."

_SEPARATOR: Final[str] = " · "


def level_verdicts(results: Sequence[CheckResult]) -> dict[Level, str]:
    """One phrase per level that has results, saying how that level went."""
    verdicts: dict[Level, str] = {}
    for level in sorted({result.level for result in results}):
        of_level = [result for result in results if result.level is level]
        failed = sum(1 for result in of_level if result.status is Status.FAIL)
        skipped = sum(1 for result in of_level if result.status is Status.SKIP)
        passed = len(of_level) - failed - skipped
        if failed:
            verdicts[level] = f"{failed} failed"
        elif skipped == len(of_level):
            verdicts[level] = "skipped (none declared)"
        elif skipped:
            verdicts[level] = f"{passed}/{len(of_level)}"
        else:
            verdicts[level] = "pass"
    return verdicts


def level_summary(results: Sequence[CheckResult]) -> str:
    """The per-level summary line, merging neighbouring levels that went the same way."""
    verdicts = level_verdicts(results)
    if not verdicts:
        return "no checks selected"
    parts: list[str] = []
    levels = sorted(verdicts)
    start = previous = levels[0]
    for level in levels[1:]:
        if level == previous + 1 and verdicts[level] == verdicts[start]:
            previous = level
            continue
        parts.append(_part(start, previous, verdicts[start]))
        start = previous = level
    parts.append(_part(start, previous, verdicts[start]))
    return _SEPARATOR.join(parts)


def _part(start: Level, end: Level, verdict: str) -> str:
    span = start.tag if start == end else f"{start.tag}-{end.tag}"
    return f"{span}: {verdict}"


def payload(results: Sequence[CheckResult]) -> dict[str, Any]:
    """The whole run as JSON-ready data."""
    return {
        "checks": [result.as_dict() for result in results],
        "levels": {level.tag: verdict for level, verdict in level_verdicts(results).items()},
        "summary": {
            "passed": sum(1 for result in results if result.status is Status.PASS),
            "failed": sum(1 for result in results if result.status is Status.FAIL),
            "skipped": sum(1 for result in results if result.status is Status.SKIP),
            "total": len(results),
        },
    }


def catalogue(checks: Sequence[Check[Any]]) -> str:
    """The checks grouped by level, one line each, as ``--list`` prints them."""
    lines: list[str] = []
    for level in sorted({check.level for check in checks}):
        lines.append(f"{level} - {level.summary}")
        for check in (one for one in checks if one.level is level):
            lines.append(f"  {check.name:<32} {check.purpose}")
        lines.append("")
    lines.append(MINIMUM_NOTE)
    return "\n".join(lines)
