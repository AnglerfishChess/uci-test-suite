#!/usr/bin/env python3
"""
Entry point for the UCI test suite.

This module provides the main CLI interface for launching the UCI test suite.
"""

import logging
import sys

import click

@click.command()
@click.argument("engine_path", type=click.Path(exists=True))
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
def main(
    engine_path: str,
    debug: bool = False,
) -> None:
    """
    Start the UCI test suite with a specified engine.

    :param engine_path: the path to the UCI-compatible chess engine executable.
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

    click.echo("UCI test suite.")
    click.echo(f"Engine path: {engine_path}")


if __name__ == "__main__":
    main()
