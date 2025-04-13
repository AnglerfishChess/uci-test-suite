#!/usr/bin/env python3
"""
Entry point for the UCI test suite.

This module provides the main CLI interface for launching the UCI test suite.
"""

import logging
import sys

import click

from uci_test_suite.tests import UCITester, UCITestResult


@click.command()
@click.argument("engine_path", type=click.Path(exists=True))
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
@click.option("--quiet/--no-quiet", default=False, help="Show only failed tests")
@click.option("--verbose/--no-verbose", default=False, help="Show detailed test information")
def main(
    engine_path: str,
    debug: bool = False,
    quiet: bool = False,
    verbose: bool = False,
) -> None:
    """
    Start the UCI test suite with a specified engine.

    Args:
        engine_path: The path to the UCI-compatible chess engine executable.
        debug: Enable debug logging if True.
        quiet: Only show failed tests if True.
        verbose: Show detailed test information if True.
    """
    # Configure logging
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,  # Ensure logs go to stderr, not stdout
    )
    logger = logging.getLogger("uci_test_suite")
    logger.setLevel(log_level)

    click.echo(f"UCI test suite v{get_version()}")
    click.echo(f"Engine path: {engine_path}")

    # Run the tests
    tester = UCITester(engine_path)
    results = tester.run_all_tests(verbose=verbose)

    # Display results
    display_results(results, quiet=quiet, verbose=verbose)

    # Return non-zero exit code if any tests failed
    if any(not result.passed for result in results):
        sys.exit(1)


def get_version() -> str:
    """
    Get the current version of the UCI test suite.

    Returns:
        The version string.
    """
    try:
        from uci_test_suite import __version__
        return __version__
    except ImportError:
        return "unknown"


def display_results(results: list[UCITestResult], quiet: bool = False, verbose: bool = False) -> None:
    """
    Display the test results.

    Args:
        results: List of test results.
        quiet: If True, only show failed tests.
        verbose: If True, show detailed test information.
    """
    passed = sum(1 for result in results if result.passed)
    failed = len(results) - passed

    if not quiet:
        click.echo("\nTest Results:")
        for result in results:
            if result.passed:
                click.secho(str(result), fg="green")
            else:
                click.secho(str(result), fg="red")

            # Display detailed info if verbose
            if verbose and result.details:
                click.echo("  Details:")
                for key, value in result.details.items():
                    if isinstance(value, dict):
                        click.echo(f"    {key}:")
                        for sub_key, sub_value in value.items():
                            click.echo(f"      {sub_key}: {sub_value}")
                    else:
                        click.echo(f"    {key}: {value}")
    else:
        # Only show failed tests in quiet mode
        failed_results = [result for result in results if not result.passed]
        if failed_results:
            click.echo("\nFailed Tests:")
            for result in failed_results:
                click.secho(str(result), fg="red")

                # Display detailed info if verbose
                if verbose and result.details:
                    click.echo("  Details:")
                    for key, value in result.details.items():
                        if isinstance(value, dict):
                            click.echo(f"    {key}:")
                            for sub_key, sub_value in value.items():
                                click.echo(f"      {sub_key}: {sub_value}")
                        else:
                            click.echo(f"    {key}: {value}")

    # Always show summary
    click.echo(f"\nSummary: {passed} passed, {failed} failed, {len(results)} total.")

    if failed == 0:
        click.secho("All tests passed!", fg="green")
    else:
        click.secho(f"{failed} tests failed.", fg="red")


if __name__ == "__main__":
    main()
