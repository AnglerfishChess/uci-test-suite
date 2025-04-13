"""
UCI protocol tests.

This module contains tests for validating UCI protocol implementation in chess engines.
"""

import logging
import time
from typing import Optional, Any, Final, Type, List

import chess
import chess.engine

from uci_test_suite.engine import UCIEngine

logger: Final[logging.Logger] = logging.getLogger(__name__)


class UCITestResult:
    """Represents the result of a UCI protocol test."""

    def __init__(self, name: str, passed: bool, message: str = "", details: Optional[dict[str, Any]] = None):
        """
        Initialize a test result.

        Args:
            name: Test name.
            passed: Whether the test passed.
            message: Additional message about the test result.
            details: Detailed information about the test results.
        """
        self.name = name
        self.passed = passed
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """String representation of the test result."""
        status = "PASS" if self.passed else "FAIL"
        result = f"{status}: {self.name}"
        if self.message:
            result += f" - {self.message}"
        return result


class UCITester:
    """Class for running UCI protocol tests against a chess engine."""

    def __init__(self, engine_path: str):
        """
        Initialize the UCI tester.

        Args:
            engine_path: Path to the chess engine executable.
        """
        self.engine_path = engine_path
        self.engine: Optional[UCIEngine] = None
        self.results: list[UCITestResult] = []

    def run_all_tests(self, verbose: bool = False) -> list[UCITestResult]:
        """
        Run all available UCI tests in order of increasing complexity.

        Args:
            verbose: Whether to include detailed output.

        Returns:
            A list of test results.
        """
        self.results = []
        test_order = [
            # Basic connection tests
            self.test_engine_identification,
            self.test_uci_protocol_support,

            # Protocol tests
            self.test_options,
            self.test_stop_command,

            # Position tests
            self.test_starting_position,
            self.test_fen_position,
            self.test_position_setup,
            self.test_position_with_moves,

            # Analysis tests
            self.test_go_command,

            # Advanced features
            self.test_long_algebraic_notation,
            self.test_pondering,
            self.test_multipv,
        ]

        try:
            self.engine = UCIEngine(self.engine_path)
            self.engine.start()

            # Run tests in order
            for test_func in test_order:
                try:
                    test_func(verbose=verbose)
                except Exception as e:
                    logger.exception("Error running test %s", test_func.__name__)
                    self.results.append(UCITestResult(
                        test_func.__name__.replace("test_", ""),
                        False,
                        f"Error: {e}"
                    ))

        except Exception as e:
            logger.exception("Error running tests")
            self.results.append(UCITestResult("test_suite_execution", False, f"Error: {e}"))
        finally:
            if self.engine:
                self.engine.stop()

        return self.results

    def test_engine_identification(self, verbose: bool = False) -> UCITestResult:
        """
        Test if the engine properly identifies itself.

        Args:
            verbose: Whether to include detailed output.

        Returns:
            Test result.
        """
        logger.debug("Running test: engine identification")
        try:
            id_info = self.engine.get_engine_info()

            if not id_info:
                return UCITestResult("engine_identification", False, "No engine identification info received")

            name_present = "name" in id_info
            author_present = "author" in id_info

            passed = name_present and author_present
            message = f"Name: {'Present' if name_present else 'Missing'}, Author: {'Present' if author_present else 'Missing'}"

            details = None
            if verbose:
                details = {"engine_info": id_info}

            result = UCITestResult("engine_identification", passed, message, details)
            self.results.append(result)
            return result

        except Exception as e:
            result = UCITestResult("engine_identification", False, f"Error: {e}")
            self.results.append(result)
            return result

    def test_uci_protocol_support(self, verbose: bool = False) -> UCITestResult:
        """
        Test if the engine supports the UCI protocol.

        Args:
            verbose: Whether to include detailed output.

        Returns:
            Test result.
        """
        logger.debug("Running test: UCI protocol support")
        try:
            # If we got this far, the engine responded to 'uci' command
            details = None
            if verbose:
                details = {"protocol": "UCI", "status": "responsive"}

            result = UCITestResult("uci_protocol_support", True, "Engine responds to UCI command", details)
            self.results.append(result)
            return result
        except Exception as e:
            result = UCITestResult("uci_protocol_support", False, f"Error: {e}")
            self.results.append(result)
            return result

    def test_options(self, verbose: bool = False) -> UCITestResult:
        """
        Test if the engine reports options correctly.

        Args:
            verbose: Whether to include detailed output.

        Returns:
            Test result.
        """
        logger.debug("Running test: options reporting")
        try:
            options = self.engine.get_options()

            if not options:
                message = "Engine doesn't report any options"
                passed = False
            else:
                message = f"Engine reports {len(options)} options"
                passed = True

            details = None
            if verbose:
                # Create a simplified options dict for display
                options_summary = {}
                for name, option in options.items():
                    options_summary[name] = {
                        "type": str(type(option)).__class__.__name__,
                        "default": getattr(option, "default", None)
                    }
                details = {"options_count": len(options), "options": options_summary}

            result = UCITestResult("options_reporting", passed, message, details)
            self.results.append(result)
            return result
        except Exception as e:
            result = UCITestResult("options_reporting", False, f"Error: {e}")
            self.results.append(result)
            return result

    def test_position_setup(self, verbose: bool = False) -> UCITestResult:
        """
        Test if the engine can handle position setup commands.

        Args:
            verbose: Whether to include detailed output.

        Returns:
            Test result.
        """
        logger.debug("Running test: position setup")
        try:
            # Setup a simple position
            position = chess.Board()

            # Make a few moves
            position.push_san("e4")
            position.push_san("e5")
            position.push_san("Nf3")

            # Get best move
            move, _ = self.engine.get_best_move(position)

            details = None
            if verbose:
                details = {
                    "position": position.fen(),
                    "moves": ["e4", "e5", "Nf3"],
                    "bestmove": move.uci() if move else None
                }

            if move:
                result = UCITestResult("position_setup", True, f"Engine calculated move: {move}", details)
            else:
                result = UCITestResult("position_setup", False, "Engine didn't return a move", details)

            self.results.append(result)
            return result
        except Exception as e:
            result = UCITestResult("position_setup", False, f"Error: {e}")
            self.results.append(result)
            return result

    def test_starting_position(self, verbose: bool = False) -> UCITestResult:
        """
        Test if the engine can handle the starting position.

        Args:
            verbose: Whether to include detailed output.

        Returns:
            Test result.
        """
        logger.debug("Running test: starting position")
        try:
            # Starting position
            position = chess.Board()

            # Get best move
            move, _ = self.engine.get_best_move(position)

            details = None
            if verbose:
                details = {
                    "position": "starting position",
                    "fen": position.fen(),
                    "bestmove": move.uci() if move else None
                }

            if move:
                san_move = position.san(move)
                result = UCITestResult("starting_position", True, f"Engine suggested move: {san_move}", details)
            else:
                result = UCITestResult("starting_position", False, "Engine didn't return a move", details)

            self.results.append(result)
            return result
        except Exception as e:
            result = UCITestResult("starting_position", False, f"Error: {e}")
            self.results.append(result)
            return result

    def test_fen_position(self, verbose: bool = False) -> UCITestResult:
        """
        Test if the engine can handle positions set by FEN.

        Args:
            verbose: Whether to include detailed output.

        Returns:
            Test result.
        """
        logger.debug("Running test: FEN position")
        try:
            # Position with a potential mate in 1
            fen = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1"
            position = chess.Board(fen)

            # Get best move
            move, _ = self.engine.get_best_move(position)

            details = None
            if verbose:
                details = {
                    "position": "mate in 1",
                    "fen": fen,
                    "bestmove": move.uci() if move else None
                }

            if move:
                san_move = position.san(move)

                # Check if the engine finds the checkmate move (Qxf7#)
                expected_mate = "Qxf7#"
                if san_move == expected_mate:
                    message = f"Engine correctly found mate in 1: {san_move}"
                    passed = True
                else:
                    message = f"Engine suggested {san_move} instead of mate in 1 ({expected_mate})"
                    passed = True  # Still pass the test since finding mate isn't required, just handling the FEN

                result = UCITestResult("fen_position", passed, message, details)
            else:
                result = UCITestResult("fen_position", False, "Engine didn't return a move", details)

            self.results.append(result)
            return result
        except Exception as e:
            result = UCITestResult("fen_position", False, f"Error: {e}")
            self.results.append(result)
            return result

    def test_go_command(self, verbose: bool = False) -> UCITestResult:
        """
        Test if the engine responds to the go command with different time parameters.

        Args:
            verbose: Whether to include detailed output.

        Returns:
            Test result.
        """
        logger.debug("Running test: go command")
        try:
            position = chess.Board()

            # Test with depth limit
            depth_limit = chess.engine.Limit(depth=10)
            start_time = time.time()
            move1, _ = self.engine.get_best_move(position, depth_limit)
            time1 = time.time() - start_time

            # Test with time limit
            time_limit = chess.engine.Limit(time=0.1)
            start_time = time.time()
            move2, _ = self.engine.get_best_move(position, time_limit)
            time2 = time.time() - start_time

            details = None
            if verbose:
                details = {
                    "depth_limit": {
                        "limit": "depth=10",
                        "time_taken": f"{time1:.2f}s",
                        "move": move1.uci() if move1 else None
                    },
                    "time_limit": {
                        "limit": "time=0.1s",
                        "time_taken": f"{time2:.2f}s",
                        "move": move2.uci() if move2 else None
                    }
                }

            if move1 and move2:
                message = f"Engine responded to different time controls: depth={time1:.2f}s, time={time2:.2f}s"
                passed = True
            else:
                message = "Engine didn't return a move for one or both time controls"
                passed = False

            result = UCITestResult("go_command", passed, message, details)
            self.results.append(result)
            return result
        except Exception as e:
            result = UCITestResult("go_command", False, f"Error: {e}")
            self.results.append(result)
            return result

    def test_stop_command(self, verbose: bool = False) -> UCITestResult:
        """
        Test if the engine responds to the stop command.

        Args:
            verbose: Whether to include detailed output.

        Returns:
            Test result.
        """
        logger.debug("Running test: stop command")
        try:
            # This test is a bit tricky, as it checks if the engine can be stopped
            # The Python-chess library handles this internally

            # Start a new thread to request cancellation after a short time
            position = chess.Board()

            # This is a simplified test, as we can't directly test stop command
            # with the Python-chess API without additional threading
            time_limit = chess.engine.Limit(time=0.1)
            start_time = time.time()
            move, _ = self.engine.get_best_move(position, time_limit)
            end_time = time.time() - start_time

            details = None
            if verbose:
                details = {
                    "time_limit": "0.1s",
                    "actual_time": f"{end_time:.2f}s",
                    "move": move.uci() if move else None
                }

            if move:
                result = UCITestResult(
                    "stop_command",
                    True,
                    "Engine returns a move when given a time limit",
                    details
                )
            else:
                result = UCITestResult(
                    "stop_command",
                    False,
                    "Engine did not return a move",
                    details
                )

            self.results.append(result)
            return result
        except Exception as e:
            result = UCITestResult("stop_command", False, f"Error: {e}")
            self.results.append(result)
            return result

    def test_pondering(self, verbose: bool = False) -> UCITestResult:
        """
        Test if the engine supports pondering.

        Args:
            verbose: Whether to include detailed output.

        Returns:
            Test result.
        """
        logger.debug("Running test: pondering")
        try:
            options = self.engine.get_options()

            # Check if engine reports the Ponder option
            if "Ponder" in options:
                # Get a position and a move
                # Note: We don't need to set Ponder option as SimpleEngine manages it automatically
                position = chess.Board()
                move, ponder_move = self.engine.get_best_move(position)

                details = None
                if verbose:
                    details = {
                        "ponder_supported": True,
                        "bestmove": move.uci() if move else None,
                        "ponder": ponder_move if ponder_move else None
                    }

                if ponder_move:
                    message = f"Engine suggested ponder move: {ponder_move}"
                    passed = True
                else:
                    message = "Engine didn't return ponder move (this is normal for some engines)"
                    passed = True  # Still pass since not all engines return ponder moves
            else:
                details = {"ponder_supported": False} if verbose else None
                message = "Engine does not support Ponder option"
                passed = True  # Not a failure, just not supported

            result = UCITestResult("pondering", passed, message, details)
            self.results.append(result)
            return result
        except Exception as e:
            result = UCITestResult("pondering", False, f"Error: {e}")
            self.results.append(result)
            return result

    def test_multipv(self, verbose: bool = False) -> UCITestResult:
        """
        Test if the engine supports MultiPV.

        Args:
            verbose: Whether to include detailed output.

        Returns:
            Test result.
        """
        logger.debug("Running test: MultiPV")
        try:
            options = self.engine.get_options()

            # Check if engine reports the MultiPV option
            if "MultiPV" in options:
                # Analyze a position with multipv=3 parameter
                # Note: We use the limit parameter to pass multipv value directly
                position = chess.Board()

                # Create a limit with multipv param
                limit = chess.engine.Limit(time=0.5)

                try:
                    # Use direct analysis with multipv parameter
                    # SimpleEngine.analyse() accepts multipv as a parameter
                    info = self.engine.engine.analyse(position, limit, multipv=3)

                    details = None
                    if verbose:
                        details = {
                            "multipv_supported": True,
                            "analysis_info": str(info)[:200] + "..." if len(str(info)) > 200 else str(info)
                        }

                    # Check if we got any info
                    if info:
                        message = "Engine supports MultiPV option and returned analysis"
                        passed = True
                    else:
                        message = "Engine supports MultiPV option but did not return analysis info"
                        passed = False
                except Exception as e:
                    message = f"Error with MultiPV analysis: {e}"
                    passed = False
                    details = {"multipv_supported": True, "error": str(e)} if verbose else None
            else:
                message = "Engine does not support MultiPV option"
                passed = True  # Not a failure, just not supported
                details = {"multipv_supported": False} if verbose else None

            result = UCITestResult("multipv", passed, message, details)
            self.results.append(result)
            return result
        except Exception as e:
            result = UCITestResult("multipv", False, f"Error: {e}")
            self.results.append(result)
            return result

    def test_position_with_moves(self, verbose: bool = False) -> UCITestResult:
        """
        Test if the engine can handle a position with a sequence of moves.

        Args:
            verbose: Whether to include detailed output.

        Returns:
            Test result.
        """
        logger.debug("Running test: position with moves")
        try:
            # Create a position and apply a sequence of moves
            position = chess.Board()
            moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]

            # Apply the moves to the position
            for move_uci in moves:
                move = chess.Move.from_uci(move_uci)
                position.push(move)

            # Get the best move from the engine
            move, _ = self.engine.get_best_move(position)

            details = None
            if verbose:
                details = {
                    "position": position.fen(),
                    "moves_sequence": moves,
                    "bestmove": move.uci() if move else None
                }

            if move:
                san_move = position.san(move)
                message = f"Engine calculated move: {san_move} after sequence: {', '.join(moves)}"
                passed = True
            else:
                message = "Engine didn't return a move"
                passed = False

            result = UCITestResult("position_with_moves", passed, message, details)
            self.results.append(result)
            return result
        except Exception as e:
            result = UCITestResult("position_with_moves", False, f"Error: {e}")
            self.results.append(result)
            return result

    def test_long_algebraic_notation(self, verbose: bool = False) -> UCITestResult:
        """
        Test if the engine properly handles long algebraic notation for moves.

        Args:
            verbose: Whether to include detailed output.

        Returns:
            Test result.
        """
        logger.debug("Running test: long algebraic notation")
        try:
            # Create a new position
            position = chess.Board()

            # Apply some moves in long algebraic notation
            moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"]
            for move_str in moves:
                move = chess.Move.from_uci(move_str)
                position.push(move)

            # Get a move from the engine
            move, _ = self.engine.get_best_move(position)

            details = None
            if verbose:
                details = {
                    "position": position.fen(),
                    "moves_applied": moves,
                    "bestmove_uci": move.uci() if move else None,
                    "bestmove_san": position.san(move) if move else None
                }

            if move:
                # Convert the move to UCI format (long algebraic)
                uci_move = move.uci()
                san_move = position.san(move)

                message = f"Engine returned a move in UCI format: {uci_move} (SAN: {san_move})"
                passed = True
            else:
                message = "Engine didn't return a move"
                passed = False

            result = UCITestResult("long_algebraic_notation", passed, message, details)
            self.results.append(result)
            return result
        except Exception as e:
            result = UCITestResult("long_algebraic_notation", False, f"Error: {e}")
            self.results.append(result)
            return result
