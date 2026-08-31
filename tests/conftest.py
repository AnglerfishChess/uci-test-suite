"""Fixtures giving the tests engine doubles and, when installed, a real engine."""

import os
import shutil
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from uci_test_suite.checks.session import RawSession
from uci_test_suite.transport import RawUciClient

FIXTURES = Path(__file__).parent / "fixtures"


def fake_engine_command(*flags: str) -> list[str]:
    """Argv running the scripted engine double with the given misbehaviour flags."""
    return [sys.executable, str(FIXTURES / "fake_engine.py"), *flags]


def silent_engine_command() -> list[str]:
    """Argv running the engine double that never answers."""
    return [sys.executable, str(FIXTURES / "silent_engine.py")]


@pytest.fixture
def fake_engine() -> Iterator[RawUciClient]:
    """A started transport client talking to a conforming engine double."""
    with RawUciClient(fake_engine_command(), default_timeout=5.0) as client:
        yield client


@pytest.fixture
def fake_session(fake_engine: RawUciClient) -> RawSession:
    """A session on a conforming engine double."""
    return RawSession(fake_engine, timeout=5.0)


@pytest.fixture
def engine_argv() -> Callable[..., list[str]]:
    """A factory for the command line of an engine double with the given misbehaviour flags."""
    return lambda *flags: fake_engine_command(*flags)


@pytest.fixture(scope="session")
def stockfish_path() -> str:
    """Path to the installed Stockfish; skips the test when it is not on PATH."""
    path = shutil.which("stockfish") or os.environ.get("STOCKFISH_PATH")
    if not path:
        pytest.skip("stockfish is not on PATH")
    return path
