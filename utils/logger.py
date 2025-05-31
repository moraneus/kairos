# utils/logger.py
# This file is part of Kairos - Clean PBTL Runtime Verification
#
# Logging utility for PBTL monitoring with configurable levels

import logging
import sys
from enum import Enum
from typing import Optional


class LogLevel(Enum):
    """Log levels for PBTL monitoring."""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR


class PBTLLogger:
    """Centralized logger for PBTL monitoring with emoji support and structured output."""

    def __init__(self, name: str = "pbtl_monitor", level: LogLevel = LogLevel.INFO):
        """Initialize the PBTL logger.

        Args:
            name: Logger name (typically module name)
            level: Default logging level
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level.value)

        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()

        # Create console handler with custom formatter
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level.value)

        # Custom formatter with emoji support
        formatter = PBTLFormatter()
        console_handler.setFormatter(formatter)

        self.logger.addHandler(console_handler)

        # Prevent propagation to root logger
        self.logger.propagate = False

    def set_level(self, level: LogLevel):
        """Change the logging level."""
        self.logger.setLevel(level.value)
        for handler in self.logger.handlers:
            handler.setLevel(level.value)

    # Core logging methods
    def debug(self, message: str, **kwargs):
        """Log debug message (detailed internal state)."""
        self.logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message (general progress)."""
        self.logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message (unexpected but recoverable)."""
        self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message (serious problems)."""
        self.logger.error(message, **kwargs)

    # Specialized methods for PBTL monitoring events
    def monitor_start(
        self, property_text: str, verdict: str, initial_frontier: Optional[str] = None
    ):
        """Log monitor initialization."""
        self.info("=== Starting Evaluation ===")
        self.info(f"Property: {property_text}")
        self.info(f"Initial verdict: {verdict}")
        if initial_frontier:
            self.info(f"Initial System Frontier: {initial_frontier}")

    def event_processed(self, event_str: str, frontiers_str: str, verdict_str: str):
        """Log event processing result."""
        self.info(f"{event_str} → frontiers={frontiers_str}, verdict={verdict_str}")

    def p_block_satisfied(self, block_id: int, block_formula: str, frontier: str):
        """Log P-block satisfaction."""
        self.debug(
            f"        🟢 P-block {block_id} ({block_formula}) satisfied at minimal frontier: {frontier}"
        )

    def n_block_satisfied(self, block_id: int, block_formula: str, frontier: str):
        """Log N-block satisfaction."""
        self.debug(
            f"        🔴 N-block {block_id} ({block_formula}) satisfied at minimal frontier: {frontier}"
        )

    def m_search_activated(self, case_type: str):
        """Log M-search activation."""
        self.debug(f"    🔧 M-search activated for {case_type} case")

    def case_debug(self, case_type: str, **status):
        """Log case-specific debug info."""
        status_str = ", ".join(f"{k}={v}" for k, v in status.items())
        self.debug(f"    🔍 {case_type} DEBUG: {status_str}")

    def frontier_analysis(self, description: str, frontier: str, vc: Optional[str] = None):
        """Log frontier analysis."""
        vc_str = f" (VC: {vc})" if vc else ""
        self.debug(f"      {description}: {frontier}{vc_str}")

    def constraint_check(self, n_id: int, n_vc: str, m_vc: str, result: Optional[str] = None):
        """Log N-constraint checking."""
        if result:
            self.debug(f"      Checking N{n_id}: {n_vc} ≤ {m_vc} → {result}")
        else:
            self.debug(f"      Checking: {n_vc} ≤ {m_vc}")

    def case_success(self, case_type: str, frontier: Optional[str] = None):
        """Log case success."""
        frontier_str = f" at {frontier}" if frontier else ""
        self.debug(f"    🎉 {case_type} case: SUCCESS{frontier_str}")

    def case_failure(self, case_type: str, reason: str):
        """Log case failure."""
        self.debug(f"    💥 {case_type} case: FAILURE - {reason}")

    def early_violation(self, case_type: str, reason: str):
        """Log early violation detection."""
        self.debug(f"    💥 EARLY {case_type} VIOLATION: {reason}")

    def optimization_info(self, message: str):
        """Log optimization information."""
        self.info(f"[INFO] {message}")

    def final_verdict(self, verdict: str):
        """Log final monitoring verdict."""
        self.info(f"\n>>> FINAL VERDICT: {verdict} <<<")

    def validation_result(self, success: bool, message: str = ""):
        """Log validation results."""
        if success:
            self.debug(f"✅ {message}" if message else "✅ Validation successful")
        else:
            self.error(f"❌ {message}" if message else "❌ Validation failed")


class PBTLFormatter(logging.Formatter):
    """Custom formatter for PBTL logging with clean output."""

    def format(self, record):
        # For INFO level and above, show message only (clean output)
        if record.levelno >= logging.INFO:
            return record.getMessage()

        # For DEBUG level, show with level indicator
        if record.levelno == logging.DEBUG:
            return f"[DEBUG] {record.getMessage()}"

        # Default formatting for other levels
        return f"[{record.levelname}] {record.getMessage()}"


# Global logger instance
_global_logger: Optional[PBTLLogger] = None


def get_logger(name: str = "pbtl_monitor") -> PBTLLogger:
    """Get or create the global PBTL logger instance.

    Args:
        name: Logger name (default: "pbtl_monitor")

    Returns:
        PBTLLogger instance
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = PBTLLogger(name)
    return _global_logger


def set_log_level(level: LogLevel):
    """Set the global log level.

    Args:
        level: New log level
    """
    logger = get_logger()
    logger.set_level(level)


def configure_logging(verbose: bool = False, debug: bool = False):
    """Configure logging based on command line flags.

    Args:
        verbose: Enable verbose (INFO) output
        debug: Enable debug output (overrides verbose)
    """
    if debug:
        set_log_level(LogLevel.DEBUG)
    elif verbose:
        set_log_level(LogLevel.INFO)
    else:
        set_log_level(LogLevel.WARNING)


# Convenience functions for common logging patterns
def log_monitor_header(property_text: str, verdict: str, initial_frontier: Optional[str] = None):
    """Log monitor initialization header."""
    get_logger().monitor_start(property_text, verdict, initial_frontier)


def log_event_result(event_str: str, frontiers_str: str, verdict_str: str):
    """Log event processing result."""
    get_logger().event_processed(event_str, frontiers_str, verdict_str)


def log_p_block_satisfaction(block_id: int, block_formula: str, frontier: str):
    """Log P-block satisfaction."""
    get_logger().p_block_satisfied(block_id, block_formula, frontier)


def log_n_block_satisfaction(block_id: int, block_formula: str, frontier: str):
    """Log N-block satisfaction."""
    get_logger().n_block_satisfied(block_id, block_formula, frontier)


def log_case_debug(case_type: str, **status):
    """Log case debug information."""
    get_logger().case_debug(case_type, **status)


def log_final_verdict(verdict: str):
    """Log final verdict."""
    get_logger().final_verdict(verdict)
