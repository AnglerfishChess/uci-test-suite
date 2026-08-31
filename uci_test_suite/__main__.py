#!/usr/bin/env python3
"""Command line entry point of the UCI test suite."""

import logging
import sys
from typing import Any, Final

import click

from uci_test_suite.checks.base import CheckResult, Status
from uci_test_suite.runner import run_suite
from uci_test_suite.transport import DEFAULT_TIMEOUT

_STATUS_COLOR: Final[dict[Status, str]] = {
    Status.PASS: "green",
    Status.FAIL: "red",
    Status.SKIP: "yellow",
}


@click.command()
@click.argument("engine_path", type=click.Path(exists=True))
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
@click.option("--quiet/--no-quiet", default=False, help="Show only failed tests")
@click.option("--verbose/--no-verbose", default=False, help="Show detailed test information")
@click.option(
    "--timeout",
    type=click.FloatRange(min=0.1),
    default=DEFAULT_TIMEOUT,
    show_default=True,
    help="Seconds to wait for any single engine response",
)
def main(
    engine_path: str,
    debug: bool = False,
    quiet: bool = False,
    verbose: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
) -> None:
    """
    Check that ENGINE_PATH speaks the UCI protocol correctly.

    Exits with a non-zero status if any check failed.
    """
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,  # Ensure logs go to stderr, not stdout
    )
    logging.getLogger("uci_test_suite").setLevel(log_level)

    click.echo(f"UCI test suite v{get_version()}")
    click.echo(f"Engine path: {engine_path}")

    results = run_suite(engine_path, timeout=timeout)
    display_results(results, quiet=quiet, verbose=verbose)

    if any(result.status is Status.FAIL for result in results):
        sys.exit(1)


def get_version() -> str:
    """The version of the installed suite, or ``"unknown"``."""
    try:
        from uci_test_suite import __version__

        return __version__
    except ImportError:
        return "unknown"


def display_results(results: list[CheckResult], quiet: bool = False, verbose: bool = False) -> None:
    """
    Print the results and a summary to standard output.

    Args:
        results: Results to display.
        quiet: Show only the failures.
        verbose: Show the details each check recorded.
    """
    shown = [result for result in results if not quiet or result.status is Status.FAIL]
    if shown:
        click.echo("\nFailed Tests:" if quiet else "\nTest Results:")
        for result in shown:
            click.secho(str(result), fg=_STATUS_COLOR[result.status])
            if verbose and result.details:
                click.echo("  Details:")
                _echo_details(result.details, indent=4)

    counts = {status: sum(1 for result in results if result.status is status) for status in Status}
    click.echo(
        f"\nSummary: {counts[Status.PASS]} passed, {counts[Status.FAIL]} failed, "
        f"{counts[Status.SKIP]} skipped, {len(results)} total."
    )
    if counts[Status.FAIL] == 0:
        click.secho("All tests passed!", fg="green")
    else:
        click.secho(f"{counts[Status.FAIL]} tests failed.", fg="red")


def _echo_details(details: dict[str, Any], indent: int) -> None:
    """Print a details mapping, one key per line, nesting sub-mappings."""
    pad = " " * indent
    for key, value in details.items():
        if isinstance(value, dict):
            click.echo(f"{pad}{key}:")
            _echo_details(value, indent + 2)
        elif isinstance(value, (list, tuple)):
            click.echo(f"{pad}{key}: {', '.join(str(item) for item in value)}")
        else:
            click.echo(f"{pad}{key}: {value}")


if __name__ == "__main__":
    main()
