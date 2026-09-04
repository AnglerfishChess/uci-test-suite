# Changelog

## 0.3.0 — 2026-09-04

- The suite reads positions and drives the acceptance level with `esca`.
  L6 now also plays a Chess960 game through the client, in both castling
  spellings.

## 0.2.0 — 2026-08-31

The suite now owns the UCI wire: engines are driven over a raw line-level
transport with timeouts, liveness checks and full transcripts, and every
`bestmove` is verified legal.

- Checks are organised into protocol levels L0–L6; L0–L2 together are the
  minimum UCI engine. `--level/-l` selects levels (`-l 2`, `-l 0-2`,
  `-l 0-2,5`), `--list` names every check, `--json` emits machine-readable
  results.
- 44 checks (from 12), including a robustness level: malformed commands,
  impossible positions, junk bursts, `quit` mid-search — an engine must not
  crash, hang, or stop answering `isready`.
- The engine under test is a command line, not only a binary path:
  `uci-test-suite python my_engine.py`, `uci-test-suite -- java -jar e.jar`.
  Windows is supported and covered by CI alongside Linux and macOS.
- `searchmoves` conformance is enforced; ignoring it is a failure.
- Python 3.13; validated against Stockfish 17 and Leela Chess Zero.
- Removed: the `UCIEngine`/`UCITester` Python API; the suite is a CLI tool.

## 0.1.1 — 2025-04-13

First PyPI release.
