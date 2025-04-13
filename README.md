# uci-test-suite

A Python-based set of tests for UCI server/chess engine implementations (such as Stockfish).

## Dependencies

You need to have Python 3.10 or newer, and also `uv`/`uvx` installed.

## Usage

To function, it requires an installed UCI-compatible chess engine, like Stockfish (has been tested with Stockfish 17).

In case of Stockfish, you can download it from https://stockfishchess.org/download/.

On macOS, you can use `brew install stockfish`.

You need to find out the path to your UCI-capable engine binary; for further example configuration, the path is e.g. `/usr/local/bin/stockfish` (which is default for Stockfish installed on macOS using Brew).


### Uvx (recommended)

Uvx is able to directly run the Python application by its name, ensuring all the dependencies, in a automatically-created virtual environment.
This is the preferred way to run the `uci-test-suite`.

Run the test suite using the following command line:

```sh
uvx --from=git+https://github.com/AnglerfishChess/uci-test-suite /usr/local/bin/stockfish
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

# Run tests
pytest

# Check code style
ruff check
```
