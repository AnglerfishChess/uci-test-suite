"""Tests of the per-level summary and the machine-readable payload."""

from uci_test_suite.checks.base import CheckResult, Status
from uci_test_suite.checks.registry import checks_of
from uci_test_suite.levels import Level
from uci_test_suite.report import catalogue, level_summary, level_verdicts, payload


def result(level: int, status: Status, name: str = "check") -> CheckResult:
    return CheckResult(name=name, level=Level(level), status=status, message="", duration=0.1)


class TestLevelVerdicts:
    def test_all_passed(self) -> None:
        assert level_verdicts([result(0, Status.PASS)]) == {Level.PROCESS: "pass"}

    def test_all_skipped(self) -> None:
        assert level_verdicts([result(4, Status.SKIP)]) == {Level.OPTIONAL: "skipped (none declared)"}

    def test_failures_win_over_skips(self) -> None:
        results = [result(5, Status.FAIL), result(5, Status.FAIL), result(5, Status.SKIP)]
        assert level_verdicts(results) == {Level.ROBUSTNESS: "2 failed"}

    def test_mixed_pass_and_skip_is_a_ratio(self) -> None:
        results = [result(3, Status.PASS) for _ in range(7)] + [result(3, Status.SKIP) for _ in range(2)]
        assert level_verdicts(results) == {Level.SESSION: "7/9"}


class TestLevelSummary:
    def test_neighbouring_levels_that_went_alike_are_merged(self) -> None:
        results = [
            *[result(level, Status.PASS) for level in (0, 1, 2)],
            *[result(3, Status.PASS) for _ in range(7)],
            *[result(3, Status.SKIP) for _ in range(2)],
            result(4, Status.SKIP),
            result(5, Status.FAIL),
            result(5, Status.FAIL),
            result(6, Status.PASS),
        ]
        assert level_summary(results) == (
            "L0-L2: pass · L3: 7/9 · L4: skipped (none declared) · L5: 2 failed · L6: pass"
        )

    def test_a_single_level_needs_no_range(self) -> None:
        assert level_summary([result(2, Status.PASS)]) == "L2: pass"

    def test_nothing_selected(self) -> None:
        assert level_summary([]) == "no checks selected"


class TestPayload:
    def test_shape(self) -> None:
        data = payload([result(0, Status.PASS, "a"), result(5, Status.FAIL, "b")])
        assert data["summary"] == {"passed": 1, "failed": 1, "skipped": 0, "total": 2}
        assert data["levels"] == {"L0": "pass", "L5": "1 failed"}
        assert data["checks"][0]["level"] == 0
        assert data["checks"][0]["level_name"] == "process"
        assert data["checks"][1]["status"] == "fail"
        assert "duration_s" in data["checks"][0]


class TestCatalogue:
    def test_groups_by_level_with_a_purpose_each(self) -> None:
        text = catalogue(checks_of())
        assert "L0 Process - " in text
        assert "L6 Acceptance - " in text
        assert "uci_uciok" in text
        assert "``" not in text
        assert "L0-L2 together are the minimum UCI engine." in text

    def test_only_the_selected_levels(self) -> None:
        text = catalogue(checks_of({Level.PLAY}))
        assert "L2 Play" in text
        assert "L3 Session" not in text
