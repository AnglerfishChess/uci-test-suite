#!/usr/bin/env python3
"""Command line entry point of the UCI test suite."""

import json
import logging
import os
import shutil
import sys
from typing import Any, Final

import click

from uci_test_suite.checks.base import CheckResult, Status
from uci_test_suite.checks.registry import checks_of
from uci_test_suite.levels import LEVEL_RANGE_SYNTAX, Level, format_levels, parse_levels
from uci_test_suite.report import MINIMUM_NOTE, catalogue, level_summary, payload
from uci_test_suite.runner import run_suite
from uci_test_suite.transport import DEFAULT_TIMEOUT

_STATUS_COLOR: Final[dict[Status, str]] = {
    Status.PASS: "green",
    Status.FAIL: "red",
    Status.SKIP: "yellow",
}


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("engine", nargs=-1, type=click.UNPROCESSED)
@click.option(
    "--level",
    "-l",
    "level_selectors",
    multiple=True,
    metavar="LEVELS",
    help=f"Levels to run: {LEVEL_RANGE_SYNTAX}. Repeatable. All levels by default.",
)
@click.option("--list", "list_checks", is_flag=True, help="List the checks by level and exit")
@click.option("--json", "as_json", is_flag=True, help="Write the results as JSON to stdout, everything else to stderr")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
@click.option("--quiet/--no-quiet", default=False, help="Show only failed checks")
@click.option("--verbose/--no-verbose", default=False, help="Show the details each check recorded")
@click.option(
    "--timeout",
    type=click.FloatRange(min=0.1),
    default=DEFAULT_TIMEOUT,
    show_default=True,
    help="Seconds to wait for a single engine response; also scales every check's own time budget",
)
def main(
    engine: tuple[str, ...],
    level_selectors: tuple[str, ...] = (),
    list_checks: bool = False,
    as_json: bool = False,
    debug: bool = False,
    quiet: bool = False,
    verbose: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
) -> None:
    """
    Check that ENGINE speaks the UCI protocol correctly.

    ENGINE is a whole command line, not only a path: `uci-test-suite ./stockfish`, `uci-test-suite python
    engine.py`, or `uci-test-suite -- java -jar engine.jar --threads 1` when the engine has options of its own.

    The checks are grouped into levels, from L0 (process) to L6 (acceptance); L0-L2 together are the minimum
    UCI engine. Exits with a non-zero status if any selected check failed.
    """
    levels = _selected_levels(level_selectors)
    if list_checks:
        click.echo(catalogue(checks_of(levels)))
        return
    if not engine:
        raise click.UsageError("give the engine command line to check")
    _require_executable(engine[0])

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("uci_test_suite").setLevel(logging.DEBUG if debug else logging.INFO)

    def say(text: str = "", **styles: Any) -> None:
        click.secho(text, err=as_json, **styles)

    say(f"UCI test suite v{get_version()}")
    say(f"Engine: {' '.join(engine)}")
    say(f"Levels: {format_levels(levels)}")

    results = run_suite(list(engine), timeout=timeout, levels=levels)
    display_results(results, say, quiet=quiet, verbose=verbose)
    if as_json:
        click.echo(json.dumps(payload(results), indent=2, default=str))

    if any(result.status is Status.FAIL for result in results):
        sys.exit(1)


def _selected_levels(selectors: tuple[str, ...]) -> frozenset[Level]:
    """The levels the ``--level`` options name, or all of them when none was given."""
    if not selectors:
        return frozenset(Level)
    chosen: set[Level] = set()
    for selector in selectors:
        try:
            chosen.update(parse_levels(selector))
        except ValueError as error:
            raise click.BadParameter(str(error), param_hint="'-l' / '--level'") from None
    return frozenset(chosen)


def _require_executable(command: str) -> None:
    """Fail the invocation unless the first word of the engine command line can be run."""
    if shutil.which(command) is None and not os.path.isfile(command):
        raise click.BadParameter(f"{command!r} is neither a file nor a command on PATH", param_hint="'ENGINE'")


def get_version() -> str:
    """The version of the installed suite, or ``"unknown"``."""
    try:
        from uci_test_suite import __version__

        return __version__
    except ImportError:
        return "unknown"


def display_results(
    results: list[CheckResult],
    say: Any,
    quiet: bool = False,
    verbose: bool = False,
) -> None:
    """
    Print the per-check lines, the per-level summary and the totals.

    Args:
        results: Results to display.
        say: Sink for one line of human output, taking the text and ``click.secho`` styles.
        quiet: Show only the failures.
        verbose: Show the details each check recorded.
    """
    shown = [result for result in results if not quiet or result.status is Status.FAIL]
    if shown:
        say()
        say("Failed checks:" if quiet else "Check results:")
        for result in shown:
            say(str(result), fg=_STATUS_COLOR[result.status])
            if verbose and result.details:
                say("  Details:")
                _say_details(result.details, say, indent=4)

    counts = {status: sum(1 for result in results if result.status is status) for status in Status}
    say()
    say(level_summary(results))
    say(MINIMUM_NOTE)
    say(
        f"Summary: {counts[Status.PASS]} passed, {counts[Status.FAIL]} failed, "
        f"{counts[Status.SKIP]} skipped, {len(results)} total."
    )
    if counts[Status.FAIL] == 0:
        say("All checks passed!", fg="green")
    else:
        say(f"{counts[Status.FAIL]} checks failed.", fg="red")


def _say_details(details: dict[str, Any], say: Any, indent: int) -> None:
    """Print a details mapping, one key per line, nesting sub-mappings."""
    pad = " " * indent
    for key, value in details.items():
        if isinstance(value, dict):
            say(f"{pad}{key}:")
            _say_details(value, say, indent + 2)
        elif isinstance(value, (list, tuple)):
            say(f"{pad}{key}: {', '.join(str(item) for item in value)}")
        else:
            say(f"{pad}{key}: {value}")


if __name__ == "__main__":
    main()
