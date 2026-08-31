"""Fixtures giving the tests engine doubles and, when installed, a real engine."""

import os
import shlex
import shutil
import stat
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
def engine_script(tmp_path: Path) -> Callable[..., Path]:
    """A factory for single executable paths running the engine double, as a command line takes one path."""

    def make(*flags: str) -> Path:
        script = tmp_path / f"fake-engine{len(list(tmp_path.iterdir()))}"
        script.write_text(f'#!/bin/sh\nexec {shlex.join(fake_engine_command(*flags))} "$@"\n')
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return script

    return make


@pytest.fixture(scope="session")
def stockfish_path() -> str:
    """Path to the installed Stockfish; skips the test when it is not on PATH."""
    path = shutil.which("stockfish") or os.environ.get("STOCKFISH_PATH")
    if not path:
        pytest.skip("stockfish is not on PATH")
    return path
