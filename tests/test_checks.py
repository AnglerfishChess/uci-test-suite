"""Tests of the session layer and of the check verdicts, against scripted engine doubles."""

import pytest
from conftest import fake_engine_command

from uci_test_suite.checks.base import CheckResult, Scope, Status
from uci_test_suite.checks.session import RawSession
from uci_test_suite.protocol import OptionType
from uci_test_suite.runner import run_suite

RAW_SCOPES = (Scope.CORE, Scope.OPTIONAL)


def verdicts(results: list[CheckResult]) -> dict[str, Status]:
    return {result.name: result.status for result in results}


def message(results: list[CheckResult], name: str) -> str:
    return next(result.message for result in results if result.name == name)


class TestSession:
    def test_handshake_is_parsed(self, fake_session: RawSession) -> None:
        handshake = fake_session.handshake
        assert handshake.id["name"] == "Fake Engine 1.0"
        assert handshake.id["author"] == "The UCI test suite"
        assert handshake.option("Hash") is not None
        button = handshake.option("Clear Hash")
        assert button is not None and button.type is OptionType.BUTTON
        assert handshake.unrecognized == ("Fake engine, not a real one",)
        assert handshake.invalid_options == ()

    def test_handshake_is_performed_once(self, fake_session: RawSession) -> None:
        first = fake_session.handshake
        assert fake_session.handshake is first
        assert sum(1 for line in fake_session.client.transcript if line.text == "uci") == 1

    def test_search_reports_infos_and_move(self, fake_session: RawSession) -> None:
        fake_session.set_position(moves=["e2e4"])
        result = fake_session.go("movetime 10")
        assert result.bestmove.move == "g8h6"
        assert result.extra_bestmoves == ()
        assert result.infos[0].depth == 8

    def test_extra_bestmoves_are_noticed(self) -> None:
        results = run_suite(fake_engine_command("--double-bestmove"), timeout=5.0, scopes=[Scope.CORE])
        assert verdicts(results)["starting_position"] is Status.FAIL
        assert "2 bestmove lines" in message(results, "starting_position")

    def test_infinite_search_is_held_until_stop(self, fake_session: RawSession) -> None:
        fake_session.set_position()
        fake_session.send_go("infinite")
        assert fake_session.collect_for(0.2) == []
        fake_session.stop()
        assert fake_session.collect_search(timeout=2.0).bestmove.move == "g1h3"


class TestConformingEngine:
    @pytest.fixture(scope="class")
    def results(self) -> list[CheckResult]:
        return run_suite(fake_engine_command(), timeout=5.0)

    def test_everything_passes(self, results: list[CheckResult]) -> None:
        assert [result for result in results if result.status is not Status.PASS] == []

    def test_every_scope_is_covered(self, results: list[CheckResult]) -> None:
        assert {result.scope for result in results} == set(Scope)

    def test_details_are_recorded(self, results: list[CheckResult]) -> None:
        assert verdicts(results)["starting_position"] is Status.PASS
        details = next(result.details for result in results if result.name == "starting_position")
        assert details["bestmove"] == "g1h3"
        assert "fen" in details


class TestMisbehavingEngines:
    def test_missing_author(self) -> None:
        results = run_suite(fake_engine_command("--no-author"), timeout=5.0, scopes=RAW_SCOPES)
        assert verdicts(results)["engine_identification"] is Status.FAIL
        assert "author" in message(results, "engine_identification")
        assert verdicts(results)["uci_protocol_support"] is Status.PASS

    def test_option_outside_its_own_range(self) -> None:
        results = run_suite(fake_engine_command("--bad-option"), timeout=5.0, scopes=RAW_SCOPES)
        assert verdicts(results)["options_reporting"] is Status.FAIL
        assert "violate the spec" in message(results, "options_reporting")
        assert verdicts(results)["uci_protocol_support"] is Status.PASS

    def test_no_options_at_all(self) -> None:
        results = run_suite(fake_engine_command("--no-options"), timeout=5.0, scopes=RAW_SCOPES)
        assert verdicts(results)["options_reporting"] is Status.FAIL
        assert verdicts(results)["pondering"] is Status.SKIP
        assert verdicts(results)["multipv"] is Status.SKIP

    def test_illegal_bestmove(self) -> None:
        results = run_suite(fake_engine_command("--illegal-move"), timeout=5.0, scopes=[Scope.CORE])
        assert verdicts(results)["starting_position"] is Status.FAIL
        assert "illegal" in message(results, "starting_position")

    def test_no_uciok(self) -> None:
        results = run_suite(fake_engine_command("--no-uciok"), timeout=0.5, scopes=RAW_SCOPES)
        assert {result.status for result in results} == {Status.FAIL}

    def test_engine_dies_mid_suite(self) -> None:
        results = run_suite(fake_engine_command("--die-on-go"), timeout=1.0, scopes=[Scope.CORE])
        assert verdicts(results)["uci_protocol_support"] is Status.PASS
        assert verdicts(results)["starting_position"] is Status.FAIL
        assert "no longer running" in message(results, "long_algebraic_notation")
