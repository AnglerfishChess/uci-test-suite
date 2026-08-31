"""L1 — the ``uci`` handshake: identity, option declarations, and ``isready``."""

from uci_test_suite.checks.base import CheckFailure, Outcome
from uci_test_suite.checks.registry import raw_check
from uci_test_suite.checks.session import RawSession
from uci_test_suite.levels import Level
from uci_test_suite.protocol import LineKind, classify


@raw_check("uci_uciok", Level.HANDSHAKE, budget=15.0)
def check_uci_uciok(session: RawSession) -> Outcome:
    """
    ``uci`` is answered with ``uciok``, and nothing said on the way breaks its own grammar.

    Spec: "uci ... the engine must answer with 'uciok' ... after that the engine is expected to be in uci mode".
    """
    handshake = session.handshake
    if handshake.invalid_options:
        raise CheckFailure(
            f"{len(handshake.invalid_options)} malformed lines before uciok",
            invalid_lines=[f"{line} -- {reason}" for line, reason in handshake.invalid_options],
        )
    return Outcome(
        f"uciok after {handshake.elapsed:.3f} s ({len(handshake.lines)} lines)",
        details={
            "elapsed_s": round(handshake.elapsed, 3),
            "lines": len(handshake.lines),
            "line_kinds": sorted({str(classify(line)) for line in handshake.lines}),
            "lines_without_a_uci_keyword": list(handshake.unrecognized),
        },
    )


@raw_check("engine_identification", Level.HANDSHAKE, budget=15.0)
def check_engine_identification(session: RawSession) -> Outcome:
    """
    The handshake carries ``id name`` and ``id author``.

    Spec: "id name <x> ... this must be sent after receiving the 'uci' command"; likewise "id author <x>".
    """
    identifiers = session.handshake.id
    missing = [key for key in ("name", "author") if not identifiers.get(key)]
    if missing:
        raise CheckFailure(f"handshake has no id {' and no id '.join(missing)}", id=dict(identifiers))
    return Outcome(
        f"name: {identifiers['name']}, author: {identifiers['author']}",
        details={"id": dict(identifiers)},
    )


@raw_check("option_declarations", Level.HANDSHAKE, budget=15.0)
def check_option_declarations(session: RawSession) -> Outcome:
    """
    Every ``option`` line parses, and declares a domain its type allows; an engine may declare none.

    Spec: "option name <id> type <t> ... this command tells the GUI which parameters can be changed".
    """
    handshake = session.handshake
    if handshake.invalid_options:
        raise CheckFailure(
            f"{len(handshake.invalid_options)} option lines do not parse",
            invalid_lines=[f"{line} -- {reason}" for line, reason in handshake.invalid_options],
        )
    issues = [f"{option.name}: {issue}" for option in handshake.options for issue in option.issues()]
    if issues:
        raise CheckFailure(f"{len(issues)} option declarations contradict the spec", issues=issues)

    warnings = [f"{option.name}: {warning}" for option in handshake.options for warning in option.warnings()]
    by_type: dict[str, int] = {}
    for option in handshake.options:
        by_type[str(option.type)] = by_type.get(str(option.type), 0) + 1
    count = len(handshake.options)
    return Outcome(
        f"{count} options, all well-formed" if count else "engine declares no options",
        details={
            "count": count,
            "by_type": by_type,
            "names": [option.name for option in handshake.options],
            "warnings": warnings,
        },
    )


@raw_check("isready_readyok", Level.HANDSHAKE, budget=15.0)
def check_isready_readyok(session: RawSession) -> Outcome:
    """
    ``isready`` is answered with exactly one ``readyok``, both when idle and after a ``position``.

    Spec: "isready ... this command must always be answered with 'readyok'".
    """
    idle = session.sync()
    session.set_position()
    after_position = session.sync()
    stray = [line.text for line in session.collect_for(0.15) if classify(line.text) is LineKind.READYOK]
    if stray:
        raise CheckFailure(f"engine sent {len(stray)} extra readyok lines", extra=stray)
    return Outcome(
        f"readyok after {idle:.3f} s when idle, {after_position:.3f} s after a position",
        details={"idle_s": round(idle, 3), "after_position_s": round(after_position, 3)},
    )
