"""Integration tests against a real engine; skipped unless Stockfish is installed."""

from collections.abc import Iterator

import pytest

from uci_test_suite.checks.base import Status
from uci_test_suite.checks.session import RawSession
from uci_test_suite.protocol import LineKind, classify
from uci_test_suite.runner import run_suite
from uci_test_suite.transport import RawUciClient

pytestmark = pytest.mark.stockfish


@pytest.fixture
def session(stockfish_path: str) -> Iterator[RawSession]:
    with RawUciClient(stockfish_path, default_timeout=15.0) as client:
        yield RawSession(client, timeout=15.0)


def test_handshake_is_understood(session: RawSession) -> None:
    handshake = session.handshake
    assert handshake.id["name"].startswith("Stockfish")
    assert handshake.id["author"]
    assert handshake.invalid_options == ()
    assert all(option.issues() == () for option in handshake.options)
    assert handshake.option("Hash") is not None


def test_stop_ends_an_infinite_search(session: RawSession) -> None:
    session.set_position()
    session.send_go("infinite")
    assert not [line for line in session.collect_for(0.3) if classify(line.text) is LineKind.BESTMOVE]
    session.stop()
    result = session.collect_search(timeout=10.0)
    assert result.extra_bestmoves == ()
    assert result.bestmove.move


def test_whole_suite_passes(stockfish_path: str) -> None:
    results = run_suite(stockfish_path, timeout=15.0)
    failures = {result.name: result.message for result in results if result.status is Status.FAIL}
    assert failures == {}
    assert len(results) >= 16
