"""Tests of the raw line transport, against scripted engine doubles."""

import pytest
from conftest import fake_engine_command, silent_engine_command

from uci_test_suite.transport import Direction, EngineDied, EngineTimeout, RawUciClient, TransportError


def test_handshake_lines_are_timestamped(fake_engine: RawUciClient) -> None:
    fake_engine.send("uci")
    lines = fake_engine.expect("uciok", timeout=5.0)
    assert lines[-1].text == "uciok"
    assert any(line.text.startswith("id name ") for line in lines)
    assert all(line.at >= 0 for line in lines)
    assert [line.at for line in lines] == sorted(line.at for line in lines)


def test_transcript_records_both_directions(fake_engine: RawUciClient) -> None:
    fake_engine.send("uci")
    fake_engine.expect("uciok", timeout=5.0)
    transcript = fake_engine.transcript
    assert transcript[0].direction is Direction.SENT
    assert transcript[0].text == "uci"
    assert transcript[-1].direction is Direction.RECEIVED
    assert transcript[-1].text == "uciok"


def test_expect_accepts_a_predicate(fake_engine: RawUciClient) -> None:
    fake_engine.send("uci")
    lines = fake_engine.expect(lambda text: text.startswith("id author"), timeout=5.0)
    assert lines[-1].text.startswith("id author")


def test_expect_times_out_and_reports_what_it_saw(fake_engine: RawUciClient) -> None:
    fake_engine.send("uci")
    with pytest.raises(EngineTimeout) as caught:
        fake_engine.expect("bestmove", timeout=0.5)
    assert any(line.text == "uciok" for line in caught.value.lines)


def test_read_line_times_out_on_a_silent_engine() -> None:
    with RawUciClient(silent_engine_command(), default_timeout=0.2) as client:
        client.send("uci")
        assert client.poll_line(0.2) is None
        with pytest.raises(EngineTimeout):
            client.read_line(0.2)


def test_drain_collects_what_is_pending(fake_engine: RawUciClient) -> None:
    fake_engine.send("uci")
    fake_engine.expect("uciok", timeout=5.0)
    fake_engine.send("isready")
    assert [line.text for line in fake_engine.drain(quiet_for=0.3)] == ["readyok"]


def test_reading_from_a_dead_engine_raises() -> None:
    client = RawUciClient(fake_engine_command(), default_timeout=1.0)
    client.start()
    client.send("quit")
    with pytest.raises(EngineDied):
        client.expect("uciok", timeout=2.0)
    assert not client.is_alive()
    with pytest.raises(EngineDied):
        client.require_alive()
    assert client.quit() == 0


def test_sending_to_a_dead_engine_raises() -> None:
    client = RawUciClient(fake_engine_command(), default_timeout=1.0)
    client.start()
    assert client.quit() == 0
    with pytest.raises(EngineDied):
        client.send("uci")


def test_engine_that_exits_mid_search_is_reported() -> None:
    with RawUciClient(fake_engine_command("--die-on-go"), default_timeout=2.0) as client:
        client.send("uci")
        client.expect("uciok", timeout=5.0)
        client.send("go movetime 10")
        with pytest.raises(EngineDied):
            client.expect("bestmove", timeout=2.0)
        assert client.returncode == 1


def test_kill_stops_the_process() -> None:
    client = RawUciClient(silent_engine_command())
    client.start()
    assert client.is_alive()
    client.kill()
    assert not client.is_alive()


def test_context_manager_quits_the_engine() -> None:
    with RawUciClient(fake_engine_command()) as client:
        client.send("uci")
        client.expect("uciok", timeout=5.0)
    assert client.returncode == 0


def test_unknown_executable_is_reported() -> None:
    client = RawUciClient("/nonexistent/engine/binary")
    with pytest.raises(TransportError):
        client.start()


def test_starting_twice_is_refused(fake_engine: RawUciClient) -> None:
    with pytest.raises(TransportError):
        fake_engine.start()
