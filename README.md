# UCI Test Suite

A Python-based set of tests for UCI server/chess engine implementations (such as Stockfish).

## Overview

The UCI Test Suite is designed to test the correctness of a chess engine's implementation of the Universal Chess Interface (UCI) protocol, not its playing strength. This makes it useful for testing new chess engines or modifications to existing ones.

## Features

- Tests basic UCI protocol commands and responses
- Checks position handling and move calculation
- Validates different time control parameters
- Supports various UCI options like Ponder and MultiPV
- Tests run in order of increasing complexity
- Testing continues even if individual tests fail

## Dependencies

You need to have Python 3.10 or newer, and also `uv`/`uvx` installed.

## Usage

To function, it requires an installed UCI-compatible chess engine, like Stockfish (has been tested with Stockfish 17).

In case of Stockfish, you can download it from https://stockfishchess.org/download/.

On macOS, you can use `brew install stockfish`.

You need to find out the path to your UCI-capable engine binary; for further example configuration, the path is e.g. `/usr/local/bin/stockfish` (which is default for Stockfish installed on macOS using Brew).

Run with `--help` to see all available command-line options.

### Uvx (recommended)

Uvx is able to directly run the Python application by its name, ensuring all the dependencies, in a automatically-created virtual environment.
This is the preferred way to run the `uci-test-suite`.

Run the test suite using the following command line:

```sh
uvx uci-test-suite@latest /usr/local/bin/stockfish
```

### Uv

Use it if you have the repository cloned locally and run from it:

```sh
uv run uci-test-suite /usr/local/bin/stockfish
```

## Development

```bash
# Clone the repository
git clone https://github.com/AnglerfishChess/uci-test-suite.git
# ... or
#    git clone git@github.com:AnglerfishChess/uci-test-suite.git

cd uci-test-suite

# Create a virtual environment
uv venv --python python3.10

# Activate the virtual environment
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows

# Install the package in development mode
#    uv pip install -e .
# or, with development dependencies
uv pip install -e ".[dev]"

# Resync the packages:
uv sync --extra=dev

# Run tests
pytest

# Check code style
ruff check
```

### Release process

```bash
uv build
uv-publish
```
