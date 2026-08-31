"""L0 — the engine as a pipe citizen: it starts, tolerates junk, keeps stdout clean, and quits."""

import time
from typing import Final

from uci_test_suite.checks.base import CheckFailure, Outcome
from uci_test_suite.checks.registry import process_check
from uci_test_suite.checks.session import ProcessSession
from uci_test_suite.checks.verify import malformed_lines
from uci_test_suite.levels import Level
from uci_test_suite.protocol import ENGINE_COMMANDS, LineKind, classify
from uci_test_suite.transport import Direction, EngineDied, EngineTimeout

#: Lines no engine should act on, used to prove that unknown input is ignored.
JUNK: Final[tuple[str, ...]] = ("", "   ", "junk", "unknown command with arguments", "42", "uciok", "joho debug on")

#: How long a freshly started engine is watched before being addressed.
STARTUP_SILENCE: Final[float] = 0.3


@process_check("engine_starts", Level.PROCESS, budget=15.0)
def check_engine_starts(session: ProcessSession) -> Outcome:
    """
    The engine starts and waits, saying nothing in the protocol until it is addressed.

    Spec: "the engine should never start pondering or/and searching automatically".
    """
    with session.client() as client:
        idle = [line.text for line in client.drain(quiet_for=STARTUP_SILENCE, timeout=1.0)]
        if not client.is_alive():
            raise CheckFailure(f"engine exited with code {client.returncode} before being addressed", startup=idle)
        spoken = [text for text in idle if classify(text) is not LineKind.UNKNOWN and text.strip()]
        if spoken:
            raise CheckFailure("engine sent UCI output before being addressed", lines=spoken)
        client.send("uci")
        try:
            lines = client.expect("uciok")
        except EngineTimeout as timeout:
            raise CheckFailure(f"no uciok after start: {timeout}", startup=idle) from None
        return Outcome(
            f"started, {len(idle)} banner lines, uciok after {lines[-1].at:.3f} s",
            details={"banner": idle, "uciok_at_s": round(lines[-1].at, 3)},
        )


@process_check("junk_before_handshake", Level.PROCESS, budget=15.0)
def check_junk_before_handshake(session: ProcessSession) -> Outcome:
    """
    Unknown lines sent before ``uci`` are ignored, and the handshake still works.

    Spec: "if the engine or the GUI receives an unknown command or token it should just ignore it".
    """
    with session.client() as client:
        for text in JUNK:
            client.send(text)
        client.send("uci")
        try:
            lines = client.expect("uciok")
        except EngineTimeout:
            raise CheckFailure(f"no uciok after {len(JUNK)} unknown lines", junk=list(JUNK)) from None
        except EngineDied as died:
            raise CheckFailure(f"engine died on unknown input: {died}", junk=list(JUNK)) from None
        return Outcome(
            f"{len(JUNK)} unknown lines ignored, uciok in {len(lines)} lines",
            details={"junk_lines": len(JUNK), "handshake_lines": len(lines)},
        )


@process_check("junk_after_handshake", Level.PROCESS, budget=15.0)
def check_junk_after_handshake(session: ProcessSession) -> Outcome:
    """
    Unknown lines sent while the engine is idle in UCI mode are ignored, and ``isready`` still answers.

    Spec: "if the engine or the GUI receives an unknown command or token it should just ignore it".
    """
    with session.session() as raw:
        _ = raw.handshake
        for text in JUNK:
            raw.send(text)
        try:
            elapsed = raw.sync()
        except EngineTimeout:
            raise CheckFailure(f"no readyok after {len(JUNK)} unknown lines", junk=list(JUNK)) from None
        except EngineDied as died:
            raise CheckFailure(f"engine died on unknown input: {died}", junk=list(JUNK)) from None
        return Outcome(
            f"{len(JUNK)} unknown lines ignored, readyok after {elapsed:.3f} s",
            details={"junk_lines": len(JUNK), "readyok_s": round(elapsed, 3)},
        )


@process_check("quit_exits_cleanly", Level.PROCESS, budget=15.0)
def check_quit_exits_cleanly(session: ProcessSession) -> Outcome:
    """
    ``quit`` ends the process promptly, with a success exit code.

    Spec: "quit: quit the program as soon as possible".
    """
    with session.client() as client:
        client.send("uci")
        client.expect("uciok")
        started = time.monotonic()
        code = client.quit(timeout=session.timeout)
        elapsed = time.monotonic() - started
        if client.killed or code is None:
            raise CheckFailure(f"engine did not exit after quit and had to be killed ({elapsed:.3f} s)")
        if code != 0:
            raise CheckFailure(f"engine exited with code {code} after quit", returncode=code)
        return Outcome(
            f"exited with code 0 in {elapsed:.3f} s",
            details={"returncode": code, "exit_s": round(elapsed, 3)},
        )


@process_check("stdout_is_well_formed", Level.PROCESS, budget=25.0)
def check_stdout_is_well_formed(session: ProcessSession) -> Outcome:
    """
    Every line the engine writes either carries no UCI keyword at all, or obeys that keyword's grammar.

    Spec: the engine-to-GUI commands and their arguments, in "Move format" and "Engine to GUI".
    """
    with session.session() as raw:
        _ = raw.handshake
        raw.set_position()
        try:
            raw.go("movetime 200")
        except EngineTimeout:
            raise CheckFailure("engine gave no bestmove for go movetime 200") from None
        received = [line.text for line in raw.client.transcript if line.direction is Direction.RECEIVED]

    broken = malformed_lines(received)
    if broken:
        raise CheckFailure(f"{len(broken)} malformed lines on stdout", malformed=broken[:10])
    unknown = [text for text in received if text.strip() and classify(text) is LineKind.UNKNOWN]
    return Outcome(
        f"{len(received)} lines, all well-formed",
        details={
            "lines": len(received),
            "keywords": sorted({str(classify(text)) for text in received} & {*ENGINE_COMMANDS}),
            "lines_without_a_uci_keyword": unknown[:10],
        },
    )
