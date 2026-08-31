"""Tests of the command line interface, against scripted engine doubles."""

from collections.abc import Callable
from pathlib import Path

from click.testing import CliRunner

from uci_test_suite.__main__ import main


def test_conforming_engine_exits_zero(engine_script: Callable[..., Path]) -> None:
    result = CliRunner().invoke(main, [str(engine_script())])
    assert result.exit_code == 0, result.output
    assert "All tests passed!" in result.output
    assert "PASS: uci_protocol_support" in result.output
    assert "0 failed" in result.output


def test_failing_engine_exits_one(engine_script: Callable[..., Path]) -> None:
    result = CliRunner().invoke(main, [str(engine_script("--no-author"))])
    assert result.exit_code == 1
    assert "FAIL: engine_identification" in result.output
    assert "tests failed." in result.output


def test_quiet_shows_only_failures(engine_script: Callable[..., Path]) -> None:
    result = CliRunner().invoke(main, [str(engine_script("--no-author")), "--quiet"])
    assert result.exit_code == 1
    assert "PASS:" not in result.output
    assert "Failed Tests:" in result.output


def test_verbose_shows_details(engine_script: Callable[..., Path]) -> None:
    result = CliRunner().invoke(main, [str(engine_script()), "--verbose"])
    assert result.exit_code == 0
    assert "Details:" in result.output
    assert "bestmove:" in result.output


def test_missing_engine_is_rejected() -> None:
    result = CliRunner().invoke(main, ["/nonexistent/engine/binary"])
    assert result.exit_code == 2
