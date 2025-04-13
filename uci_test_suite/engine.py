"""
UCI Engine wrapper.

This module provides utilities for communication with UCI-compatible chess engines.
"""

import logging
import subprocess
from typing import Optional, Any, Tuple, Final, Type, TypeVar

import chess
import chess.engine

logger: Final[logging.Logger] = logging.getLogger(__name__)


class UCIEngine:
    """Wrapper for UCI chess engine communication."""

    def __init__(self, engine_path: str):
        """
        Initialize the UCI engine wrapper.

        Args:
            engine_path: Path to the chess engine executable.
        """
        self.engine_path = engine_path
        self.process: Optional[subprocess.Popen] = None
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self.id_info: dict[str, str] = {}
        self.options: dict[str, Any] = {}

    def start(self) -> None:
        """Start the engine process and initialize the UCI connection."""
        logger.debug("Starting engine: %s", self.engine_path)
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            self.id_info = self.engine.id
            self.options = {name: option for name, option in self.engine.options.items()}
            logger.debug("Engine started successfully")
        except (OSError, ValueError):
            logger.exception("Failed to start engine")
            raise

    def stop(self) -> None:
        """Stop the engine process and clean up resources."""
        if self.engine:
            logger.debug("Stopping engine")
            self.engine.quit()
            self.engine = None
            logger.debug("Engine stopped")

    def is_running(self) -> bool:
        """
        Check if the engine is running.

        Returns:
            True if the engine is running, False otherwise.
        """
        return self.engine is not None

    def get_engine_info(self) -> dict[str, str]:
        """
        Get the engine identification information.

        Returns:
            A dictionary with engine identification information.
        """
        return self.id_info

    def get_options(self) -> dict[str, Any]:
        """
        Get the available engine options.

        Returns:
            A dictionary with engine options.
        """
        return self.options

    def set_option(self, name: str, value: Any) -> None:
        """
        Set an engine option.

        Args:
            name: Option name.
            value: Option value.
        """
        if self.engine:
            logger.debug("Setting option %s = %s", name, value)
            try:
                self.engine.configure({name: value})
                logger.debug("Option %s set successfully", name)
            except ValueError:
                logger.exception("Failed to set option %s", name)
                raise
        else:
            raise ValueError("Engine not started")

    def get_best_move(self, position: chess.Board, time_limit: Optional[chess.engine.Limit] = None) -> tuple[Optional[chess.Move], Optional[str]]:
        """
        Get the best move for a given position.

        Args:
            position: Chess position to analyze.
            time_limit: Time limit for analysis.

        Returns:
            A tuple with the best move and ponder move (if available).
        """
        if not self.engine:
            raise ValueError("Engine not started")

        if time_limit is None:
            time_limit = chess.engine.Limit(time=1.0)

        logger.debug("Getting best move for position: %s", position.fen())
        try:
            result = self.engine.play(position, time_limit)
            logger.debug("Best move: %s", result.move)
            return result.move, result.ponder
        except chess.engine.EngineTerminatedError as e:
            logger.exception("Engine terminated unexpectedly")
            self.engine = None
            raise
        except Exception as e:
            logger.exception("Error getting best move")
            raise

    def analyze_position(self, position: chess.Board, time_limit: Optional[chess.engine.Limit] = None) -> dict[str, Any]:
        """
        Analyze a chess position.

        Args:
            position: Chess position to analyze.
            time_limit: Time limit for analysis.

        Returns:
            A dictionary with the analysis results.
        """
        if not self.engine:
            raise ValueError("Engine not started")

        if time_limit is None:
            time_limit = chess.engine.Limit(time=1.0)

        logger.debug("Analyzing position: %s", position.fen())
        try:
            info = self.engine.analyse(position, time_limit)
            logger.debug("Analysis completed: %s", info)
            return info
        except chess.engine.EngineTerminatedError:
            logger.exception("Engine terminated unexpectedly")
            self.engine = None
            raise
        except Exception:
            logger.exception("Error analyzing position")
            raise

    def __enter__(self) -> 'UCIEngine':
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[Any]) -> None:
        """Context manager exit."""
        self.stop()
