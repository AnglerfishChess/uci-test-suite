# UCI Test Suite

A Python-based set of tests for UCI server/chess engine implementations (such as Stockfish).

## Overview

The UCI Test Suite is designed to test the correctness of a chess engine's implementation of the Universal Chess Interface (UCI) protocol, not its playing strength. This makes it useful for testing new chess engines or modifications to existing ones.

## Features

- Checks the protocol on the wire: the suite spawns the engine and asserts on the exact protocol text
- Groups the checks by protocol layer, and runs them lowest layer first, each layer on a fresh engine process
- Skips, rather than fails, a feature the engine does not advertise
- Drives the engine through `esca` as well, as a mainstream UCI client would
- Testing continues even if individual checks fail

## Levels

| Level | Name | What it covers |
| ----- | ---- | -------------- |
| L0 | Process | Starts, ignores junk before and after the handshake, keeps stdout well-formed, quits cleanly |
| L1 | Handshake | `uci` → `id name`/`id author`/`option`/`uciok`; `isready` → `readyok` |
| L2 | Play | `position startpos`/`position fen`, `go movetime`, clock controls, `stop`, and a legal `bestmove` every time |
| L3 | Session | `ucinewgame`, `setoption` on every declared option, `debug`, the `go` limits and `searchmoves`, `isready` while searching, the `info` stream |
| L4 | Optional | Ponder, MultiPV, `UCI_Chess960`, `UCI_AnalyseMode`, `register`/`copyprotection` — each skipped when not offered |
| L5 | Robustness | Malformed commands, impossible positions, illegal moves, junk bursts, `quit` mid-search: no crash, no hang, `isready` still answered |
| L6 | Acceptance | `esca` drives the engine end to end |

**L0–L2 together are the minimum UCI engine.** An engine that passes them can be played; the levels above add the
conveniences a GUI expects.

`uci-test-suite --list` prints every check with its purpose.

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

### The engine is a command line

The engine argument is a whole command line, not only a path, so an engine that needs an interpreter or
arguments of its own works too:

```sh
uci-test-suite python my_engine.py
uci-test-suite -- java -jar engine.jar --threads 1
```

Put `--` before the engine when its own options would otherwise be read as the suite's, and put the suite's own
options before it.

### Choosing levels

```sh
uci-test-suite -l 2 ./engine          # one level
uci-test-suite -l 0-2 ./engine        # an inclusive range: the minimum UCI engine
uci-test-suite -l 0-2,5 ./engine      # ranges and levels combined
uci-test-suite --list                 # every check, grouped by level
```

Without `--level`, every level runs. The run ends with a per-level summary, such as
`L0-L2: pass · L3: 7/9 · L4: skipped (none declared) · L5: 2 failed · L6: pass`, and exits non-zero if any
selected check failed.

### Machine-readable output

`--json` writes the full result list — level, name, status, message, details and timings — to standard output,
and everything human-readable to standard error:

```sh
uci-test-suite --json ./engine > results.json
```

### Timeouts

Every check carries its own time budget; `--timeout` scales them all. Raise it for an engine that thinks slowly
(`--timeout 30`), lower it to fail a wedged engine faster.

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
