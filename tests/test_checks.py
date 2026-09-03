"""Tests of the session layer and of the check verdicts, against scripted engine doubles."""

from collections.abc import Collection

import pytest
from conftest import fake_engine_command

from uci_test_suite.checks.base import CheckResult, Status
from uci_test_suite.checks.registry import checks_of
from uci_test_suite.checks.session import RawSession
from uci_test_suite.levels import Level
from uci_test_suite.protocol import OptionType
from uci_test_suite.runner import run_suite


def verdicts(results: list[CheckResult]) -> dict[str, Status]:
    return {result.name: result.status for result in results}


def message(results: list[CheckResult], name: str) -> str:
    return next(result.message for result in results if result.name == name)


def run(*flags: str, levels: Collection[Level] | None = None, timeout: float = 5.0) -> list[CheckResult]:
    return run_suite(fake_engine_command(*flags), timeout=timeout, levels=levels)


class TestRegistry:
    def test_every_level_has_checks(self) -> None:
        assert {check.level for check in checks_of()} == set(Level)

    def test_checks_come_out_in_level_order(self) -> None:
        levels = [check.level for check in checks_of()]
        assert levels == sorted(levels)

    def test_names_are_unique(self) -> None:
        names = [check.name for check in checks_of()]
        assert len(names) == len(set(names))

    def test_every_check_quotes_its_purpose_and_has_a_budget(self) -> None:
        assert all(check.purpose and check.budget > 0 for check in checks_of())

    def test_a_level_can_be_selected_alone(self) -> None:
        assert {check.level for check in checks_of({Level.PLAY})} == {Level.PLAY}


class TestSession:
    def test_handshake_is_parsed(self, fake_session: RawSession) -> None:
        handshake = fake_session.handshake
        assert handshake.id["name"] == "Fake Engine 1.0"
        assert handshake.id["author"] == "The UCI test suite"
        assert handshake.option("Hash") is not None
        button = handshake.option("Clear Hash")
        assert button is not None
        assert button.type is OptionType.BUTTON
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

    def test_new_game_is_answered(self, fake_session: RawSession) -> None:
        fake_session.new_game()
        assert fake_session.sync() >= 0

    def test_infinite_search_is_held_until_stop(self, fake_session: RawSession) -> None:
        fake_session.set_position()
        fake_session.send_go("infinite")
        assert fake_session.collect_for(0.2) == []
        fake_session.stop()
        assert fake_session.collect_search(timeout=2.0).bestmove.move == "g1h3"


class TestConformingEngine:
    @pytest.fixture(scope="class")
    def results(self) -> list[CheckResult]:
        return run()

    def test_nothing_fails(self, results: list[CheckResult]) -> None:
        assert [str(result) for result in results if result.status is Status.FAIL] == []

    def test_every_level_is_covered(self, results: list[CheckResult]) -> None:
        assert {result.level for result in results} == set(Level)

    def test_only_the_features_it_declines_are_skipped(self, results: list[CheckResult]) -> None:
        skipped = {result.name for result in results if result.status is Status.SKIP}
        assert skipped == {"registration_and_copyprotection"}

    def test_details_are_recorded(self, results: list[CheckResult]) -> None:
        details = next(result.details for result in results if result.name == "position_startpos")
        assert details["bestmove"] == "g1h3"
        assert "fen" in details

    def test_durations_are_measured(self, results: list[CheckResult]) -> None:
        assert all(result.duration >= 0 for result in results)


class TestLevelSelection:
    def test_one_level_runs_alone(self) -> None:
        results = run(levels=[Level.HANDSHAKE])
        assert {result.level for result in results} == {Level.HANDSHAKE}

    def test_a_range_runs_in_order(self) -> None:
        results = run(levels=[Level.PROCESS, Level.HANDSHAKE, Level.PLAY])
        assert [result.level for result in results] == sorted(result.level for result in results)
        assert {result.level for result in results} == {Level.PROCESS, Level.HANDSHAKE, Level.PLAY}


class TestHandshakeFaults:
    def test_missing_author(self) -> None:
        results = run("--no-author", levels=[Level.HANDSHAKE])
        assert verdicts(results)["engine_identification"] is Status.FAIL
        assert "author" in message(results, "engine_identification")
        assert verdicts(results)["uci_uciok"] is Status.PASS

    def test_option_outside_its_own_range(self) -> None:
        results = run("--bad-option", levels=[Level.HANDSHAKE])
        assert verdicts(results)["option_declarations"] is Status.FAIL
        assert "contradict the spec" in message(results, "option_declarations")

    def test_declaring_no_options_is_allowed(self) -> None:
        results = run("--no-options", levels=[Level.HANDSHAKE, Level.OPTIONAL])
        assert verdicts(results)["option_declarations"] is Status.PASS
        assert verdicts(results)["ponder"] is Status.SKIP
        assert verdicts(results)["multipv"] is Status.SKIP
        assert verdicts(results)["chess960"] is Status.SKIP

    def test_no_uciok(self) -> None:
        results = run("--no-uciok", levels=[Level.HANDSHAKE], timeout=0.5)
        assert set(verdicts(results).values()) == {Status.FAIL}


class TestPlayFaults:
    def test_extra_bestmove(self) -> None:
        results = run("--double-bestmove", levels=[Level.PLAY])
        assert verdicts(results)["position_startpos"] is Status.FAIL
        assert "2 bestmove lines" in message(results, "position_startpos")

    def test_illegal_bestmove(self) -> None:
        results = run("--illegal-move", levels=[Level.PLAY])
        assert verdicts(results)["position_startpos"] is Status.FAIL
        assert "illegal" in message(results, "position_startpos")

    def test_engine_that_never_stops(self) -> None:
        results = run("--hang-on-stop", levels=[Level.PLAY], timeout=1.0)
        assert verdicts(results)["stop_ends_search"] is Status.FAIL

    def test_engine_dies_mid_level(self) -> None:
        results = run("--die-on-go", levels=[Level.PLAY], timeout=1.0)
        assert verdicts(results)["position_startpos"] is Status.FAIL
        assert "no longer running" in message(results, "stop_ends_search")


class TestProcessFaults:
    def test_engine_that_ignores_quit(self) -> None:
        results = run("--zombie-on-quit", levels=[Level.PROCESS], timeout=0.3)
        assert verdicts(results)["quit_exits_cleanly"] is Status.FAIL
        assert "killed" in message(results, "quit_exits_cleanly")

    def test_engine_that_speaks_before_being_addressed(self) -> None:
        results = run("--noisy-start", levels=[Level.PROCESS], timeout=1.0)
        assert verdicts(results)["engine_starts"] is Status.FAIL
        assert "before being addressed" in message(results, "engine_starts")


class TestSessionFeatures:
    def test_searchmoves_restricts_the_answer(self) -> None:
        results = run(levels=[Level.SESSION])
        assert verdicts(results)["searchmoves"] is Status.PASS


class TestSessionFaults:
    def test_bestmove_without_a_go(self) -> None:
        results = run("--bestmove-without-go", levels=[Level.SESSION], timeout=2.0)
        assert verdicts(results)["no_unsolicited_bestmove"] is Status.FAIL
        assert "without a go" in message(results, "no_unsolicited_bestmove")

    def test_depth_that_goes_backwards(self) -> None:
        results = run("--depth-goes-back", levels=[Level.SESSION], timeout=2.0)
        assert verdicts(results)["info_stream"] is Status.FAIL
        assert "backwards" in message(results, "info_stream")

    def test_searchmoves_ignored(self) -> None:
        results = run("--ignore-searchmoves", levels=[Level.SESSION], timeout=2.0)
        assert verdicts(results)["searchmoves"] is Status.FAIL
        assert "g1h3" in message(results, "searchmoves")
        assert "a2a3" in message(results, "searchmoves")
        assert "h2h3" in message(results, "searchmoves")


class TestRobustnessFaults:
    def test_engine_that_crashes_on_a_fen(self) -> None:
        results = run("--crash-on-fen", levels=[Level.ROBUSTNESS], timeout=2.0)
        assert verdicts(results)["malformed_commands"] is Status.FAIL
        assert "died on 'position fen'" in message(results, "malformed_commands")
        assert verdicts(results)["impossible_fen"] is Status.FAIL

    def test_one_crash_does_not_hide_the_rest_of_the_level(self) -> None:
        results = run("--crash-on-fen", levels=[Level.ROBUSTNESS], timeout=2.0)
        assert verdicts(results)["idle_stop_and_ponderhit"] is Status.PASS
        assert verdicts(results)["junk_burst"] is Status.PASS

    def test_engine_that_ignores_quit_during_a_search(self) -> None:
        results = run("--zombie-on-quit", levels=[Level.ROBUSTNESS], timeout=0.3)
        assert verdicts(results)["quit_during_search"] is Status.FAIL


class TestAcceptance:
    @pytest.fixture(scope="class")
    def results(self) -> list[CheckResult]:
        return run(levels=[Level.ACCEPTANCE])

    def test_the_client_drives_the_engine_end_to_end(self, results: list[CheckResult]) -> None:
        assert set(verdicts(results).values()) == {Status.PASS}

    def test_the_engine_identity_is_read(self, results: list[CheckResult]) -> None:
        assert "Fake Engine 1.0" in message(results, "client_handshake")

    def test_chess960_is_played_in_the_king_takes_rook_spelling(self, results: list[CheckResult]) -> None:
        details = next(result.details for result in results if result.name == "client_chess960")
        assert details["castling_move"] == "f1h1"
        assert details["fen"].startswith("1r3k1r/pppppppp")

    def test_chess960_is_skipped_when_not_offered(self) -> None:
        results = run("--no-options", levels=[Level.ACCEPTANCE])
        assert verdicts(results)["client_chess960"] is Status.SKIP


class TestAcceptanceFaults:
    def test_missing_author(self) -> None:
        results = run("--no-author", levels=[Level.ACCEPTANCE])
        assert verdicts(results)["client_handshake"] is Status.FAIL
        assert "author" in message(results, "client_handshake")

    def test_illegal_bestmove(self) -> None:
        results = run("--illegal-move", levels=[Level.ACCEPTANCE], timeout=2.0)
        assert verdicts(results)["client_play"] is Status.FAIL


class TestOptionalFeatures:
    def test_declared_features_are_exercised(self) -> None:
        results = run(levels=[Level.OPTIONAL])
        assert verdicts(results)["ponder"] is Status.PASS
        assert verdicts(results)["multipv"] is Status.PASS
        assert verdicts(results)["chess960"] is Status.PASS
        assert verdicts(results)["analyse_mode"] is Status.PASS

    def test_copyprotection_is_read_when_sent(self) -> None:
        results = run("--copyprotection", levels=[Level.OPTIONAL])
        assert verdicts(results)["registration_and_copyprotection"] is Status.PASS
        assert "copyprotection ok" in message(results, "registration_and_copyprotection")
