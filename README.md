# UCI Test Suite

A Python-based set of tests for UCI server/chess engine implementations (such as Stockfish).

## Overview

The UCI Test Suite is designed to test the correctness of a chess engine's implementation of the Universal Chess Interface (UCI) protocol, not its playing strength. This makes it useful for testing new chess engines or modifications to existing ones.

## Features

- Tests basic UCI protocol commands and responses, on the wire: the suite spawns the engine and asserts on the exact protocol text
- Checks position handling and move calculation
- Validates different time control parameters
- Supports various UCI options like Ponder and MultiPV; a test is skipped, not failed, when the engine does not advertise the feature
- Runs a separate group of tests through `python-chess`, checking that a mainstream UCI client can drive the engine
- Tests run in order of increasing complexity
- Testing continues even if individual tests fail

## Dependencies

You need to have Python 3.13 or newer, and also `uv`/`uvx` installed.

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

# Create the virtual environment and install the package and its development dependencies
uv sync

# Run the tests; those needing a real engine are skipped unless `stockfish` is on PATH
uv run pytest

# Check code style and types
uvx ruff check .
uvx ruff format --check .
uvx pyrefly check
```

### Release process

Releases are cut by tagging a commit and publishing a GitHub release from it; that publish event
triggers `.github/workflows/publish.yml`, which builds and uploads the package to PyPI.

Contributors run the same checks CI runs, locally, before opening a PR:

```bash
uv run pytest
uvx ruff check .
uvx ruff format --check .
uvx pyrefly check
```

## License

MIT — see [LICENSE](LICENSE).
