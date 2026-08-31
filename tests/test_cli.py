"""Tests of the command line interface, against scripted engine doubles."""

import json
import sys
from collections.abc import Callable

from click.testing import CliRunner

from uci_test_suite import __version__
from uci_test_suite.__main__ import main


class TestEngineCommandLine:
    def test_a_whole_command_line_is_accepted(self, engine_argv: Callable[..., list[str]]) -> None:
        result = CliRunner().invoke(main, ["-l", "1", "--", *engine_argv()])
        assert result.exit_code == 0, result.output
        assert "PASS [L1]: uci_uciok" in result.output

    def test_a_single_path_still_works(self) -> None:
        result = CliRunner().invoke(main, ["-l", "1", "--timeout", "0.1", "--quiet", sys.executable])
        assert f"Engine: {sys.executable}" in result.output
        assert result.exit_code == 1  # A bare interpreter is no UCI engine, but it did start.

    def test_missing_engine_is_rejected(self) -> None:
        result = CliRunner().invoke(main, ["/nonexistent/engine/binary"])
        assert result.exit_code == 2

    def test_no_engine_at_all_is_rejected(self) -> None:
        assert CliRunner().invoke(main, []).exit_code == 2


class TestVerdicts:
    def test_conforming_engine_exits_zero(self, engine_argv: Callable[..., list[str]]) -> None:
        result = CliRunner().invoke(main, ["-l", "0-2", "--", *engine_argv()])
        assert result.exit_code == 0, result.output
        assert "All checks passed!" in result.output
        assert "L0-L2: pass" in result.output
        assert "0 failed" in result.output

    def test_failing_engine_exits_one(self, engine_argv: Callable[..., list[str]]) -> None:
        result = CliRunner().invoke(main, ["-l", "1", "--", *engine_argv("--no-author")])
        assert result.exit_code == 1
        assert "FAIL [L1]: engine_identification" in result.output
        assert "checks failed." in result.output

    def test_quiet_shows_only_failures(self, engine_argv: Callable[..., list[str]]) -> None:
        result = CliRunner().invoke(main, ["-l", "1", "--quiet", "--", *engine_argv("--no-author")])
        assert result.exit_code == 1
        assert "PASS" not in result.output
        assert "Failed checks:" in result.output

    def test_verbose_shows_details(self, engine_argv: Callable[..., list[str]]) -> None:
        result = CliRunner().invoke(main, ["-l", "2", "--verbose", "--", *engine_argv()])
        assert result.exit_code == 0
        assert "Details:" in result.output
        assert "bestmove:" in result.output


class TestLevelOption:
    def test_one_level(self, engine_argv: Callable[..., list[str]]) -> None:
        result = CliRunner().invoke(main, ["-l", "1", "--", *engine_argv()])
        assert "Levels: L1" in result.output
        assert "[L2]" not in result.output

    def test_a_range(self, engine_argv: Callable[..., list[str]]) -> None:
        result = CliRunner().invoke(main, ["--level", "0-1", "--", *engine_argv()])
        assert "Levels: L0-L1" in result.output
        assert "[L2]" not in result.output

    def test_commas_combine(self, engine_argv: Callable[..., list[str]]) -> None:
        result = CliRunner().invoke(main, ["-l", "0-1,4", "--", *engine_argv()])
        assert "Levels: L0-L1, L4" in result.output

    def test_the_option_can_be_repeated(self, engine_argv: Callable[..., list[str]]) -> None:
        result = CliRunner().invoke(main, ["-l", "1", "-l", "4", "--", *engine_argv()])
        assert "Levels: L1, L4" in result.output

    def test_all_levels_by_default(self, engine_argv: Callable[..., list[str]]) -> None:
        result = CliRunner().invoke(main, ["--timeout", "0.2", "--quiet", "--", *engine_argv("--no-uciok")])
        assert "Levels: L0-L6" in result.output

    def test_open_ended_ranges_are_rejected(self, engine_argv: Callable[..., list[str]]) -> None:
        for selector in ("-2", "3-", "0:2", "seven"):
            result = CliRunner().invoke(main, ["-l", selector, "--", *engine_argv()])
            assert result.exit_code == 2, selector
            assert "level" in result.output.lower()

    def test_a_level_that_does_not_exist_is_rejected(self, engine_argv: Callable[..., list[str]]) -> None:
        result = CliRunner().invoke(main, ["-l", "9", "--", *engine_argv()])
        assert result.exit_code == 2
        assert "levels are 0 to 6" in result.output


class TestList:
    def test_lists_every_level_without_an_engine(self) -> None:
        result = CliRunner().invoke(main, ["--list"])
        assert result.exit_code == 0
        assert "L0 Process" in result.output
        assert "L6 Acceptance" in result.output
        assert "uci_uciok" in result.output
        assert "L0-L2 together are the minimum UCI engine." in result.output

    def test_lists_only_the_selected_levels(self) -> None:
        result = CliRunner().invoke(main, ["--list", "-l", "5"])
        assert result.exit_code == 0
        assert "L5 Robustness" in result.output
        assert "L2 Play" not in result.output


class TestJson:
    def test_results_go_to_stdout_and_text_to_stderr(self, engine_argv: Callable[..., list[str]]) -> None:
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["-l", "1", "--json", "--", *engine_argv()], catch_exceptions=False)
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["levels"] == {"L1": "pass"}
        assert data["summary"]["failed"] == 0
        names = [check["name"] for check in data["checks"]]
        assert "uci_uciok" in names
        first = data["checks"][0]
        assert set(first) >= {"level", "name", "status", "message", "duration_s", "details"}

    def test_the_exit_code_still_reports_failures(self, engine_argv: Callable[..., list[str]]) -> None:
        result = CliRunner(mix_stderr=False).invoke(main, ["-l", "1", "--json", "--", *engine_argv("--no-author")])
        assert result.exit_code == 1
        assert json.loads(result.stdout)["summary"]["failed"] == 1


def test_help_names_the_minimum_engine() -> None:
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "L0-L2" in result.output
    assert "minimum" in result.output


def test_version_names_the_program_and_version() -> None:
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "uci-test-suite" in result.output
    assert __version__ in result.output
