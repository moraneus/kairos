#!/usr/bin/env python3
# run_monitor.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Command-line interface for PBTL monitoring with configurable logging levels

import sys
import argparse
from pathlib import Path

from core.monitor import PBTLMonitor
from core.verdict import Verdict
from utils.trace_reader import (
    read_trace,
    validate_trace_file,
    TraceFormatError,
    get_system_processes,
)
from utils.logger import LogLevel, get_logger
from parser.exceptions import ParseError


def read_property_file(filepath: Path) -> str:
    """Read PBTL property from file.

    Args:
        filepath: Path to the property file

    Returns:
        Property formula as string

    Raises:
        FileNotFoundError: If property file doesn't exist
        ValueError: If property file is empty or invalid
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            raise ValueError("Property file is empty")

        return content

    except FileNotFoundError:
        raise FileNotFoundError(f"Property file not found: {filepath}")
    except Exception as e:
        raise ValueError(f"Error reading property file: {e}")


def configure_logging_for_monitor(verbose: bool = False, debug: bool = False) -> None:
    """Configure logging levels for PBTL monitor.

    Args:
        verbose: Enable INFO level logging
        debug: Enable DEBUG level logging (overrides verbose)
    """
    logger = get_logger()

    if debug:
        logger.set_level(LogLevel.DEBUG)
    elif verbose:
        logger.set_level(LogLevel.INFO)
    else:
        logger.set_level(LogLevel.INFO)


def validate_formula_syntax(formula: str) -> bool:
    """Validate PBTL formula syntax.

    Args:
        formula: PBTL formula string

    Returns:
        True if formula is well-formed, False otherwise
    """
    try:
        from parser import parse_and_dlnf

        parse_and_dlnf(formula)
        return True
    except Exception:
        return False


def process_monitoring_session(
    monitor: PBTLMonitor, trace_path: str, stop_on_verdict: bool
) -> int:
    """Execute the main monitoring session.

    Args:
        monitor: Initialized PBTL monitor
        trace_path: Path to trace file
        stop_on_verdict: Whether to stop processing when verdict becomes conclusive

    Returns:
        Number of events processed
    """
    event_count = 0
    for event in read_trace(trace_path):
        event_count += 1
        monitor.process_event(event)

        if stop_on_verdict and monitor.is_conclusive():
            break

    return event_count


def print_final_analysis(monitor: PBTLMonitor, event_count: int) -> None:
    """Print detailed final analysis of monitoring results.

    Args:
        monitor: Completed PBTL monitor
        event_count: Total number of events processed
    """
    logger = get_logger()

    logger.info(f"\n📊 Events processed: {event_count}")
    logger.info(f"\n📋 Disjunct breakdown:")

    for i, disjunct in enumerate(monitor.disjuncts):
        case_type = disjunct.case_type()
        verdict = disjunct.verdict

        if verdict == Verdict.TRUE:
            success_info = (
                f" at {disjunct.success_frontier}" if disjunct.success_frontier else ""
            )
            logger.info(f"  Disjunct {i} ({case_type}): ✅ TRUE{success_info}")
        elif verdict == Verdict.FALSE:
            logger.info(f"  Disjunct {i} ({case_type}): ❌ FALSE")
        else:
            logger.info(f"  Disjunct {i} ({case_type}): ❓ UNKNOWN")


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser for command line interface.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="Kairos PBTL Runtime Verification Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_monitor.py -p property.pbtl -t trace.csv
  python run_monitor.py -p property.pbtl -t trace.csv -v
  python run_monitor.py -p property.pbtl -t trace.csv --debug
  python run_monitor.py -p property.pbtl -t trace.csv --validate-only

Property file format:
  Create a .pbtl file containing your PBTL formula, e.g.:

  property.pbtl:
    EP(EP(p) & EP(q) & !EP(r))
        """,
    )

    parser.add_argument(
        "-p", "--property", required=True, type=Path, help="Path to PBTL property file"
    )

    parser.add_argument(
        "-t", "--trace", required=True, type=Path, help="Path to CSV trace file"
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    parser.add_argument(
        "--debug", action="store_true", help="Enable debug output (overrides --verbose)"
    )

    parser.add_argument(
        "--validate-only", action="store_true", help="Only validate trace file format"
    )

    parser.add_argument(
        "--stop-on-verdict",
        action="store_true",
        help="Stop processing when verdict becomes conclusive",
    )

    parser.add_argument(
        "--debug-final", action="store_true", help="Print detailed final state analysis"
    )

    return parser


def main() -> int:
    """Main entry point for PBTL monitoring application.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    parser = create_argument_parser()
    args = parser.parse_args()

    try:
        # Initialize logging system
        configure_logging_for_monitor(verbose=args.verbose, debug=args.debug)
        logger = get_logger()

        # Load and validate property
        formula = read_property_file(args.property)

        if not args.validate_only:
            logger.info(f"📋 Property loaded: {formula}")

            if validate_formula_syntax(formula):
                logger.info("✅ Formula syntax is well-formed")
            else:
                logger.warning("⚠️  Formula syntax may have issues")

        # Validate trace file
        logger.info(f"🔍 Validating trace file: {args.trace}")
        validate_trace_file(str(args.trace))

        if args.validate_only:
            logger.info("✅ Trace validation successful. Exiting.")
            return 0

        # Initialize monitoring system
        monitor = PBTLMonitor(formula)
        monitor.set_verbose(args.debug)

        # Configure system processes if available
        system_processes = get_system_processes(str(args.trace))
        if system_processes:
            monitor.initialize_from_trace_processes(system_processes)

        # Begin monitoring session
        monitor.print_header()
        event_count = process_monitoring_session(
            monitor, str(args.trace), args.stop_on_verdict
        )

        # Finalize and report results
        monitor.finalize()
        monitor.print_final_verdict()

        if args.debug_final:
            print_final_analysis(monitor, event_count)

        return 0

    except TraceFormatError as e:
        logger.error(f"Trace file error: {e}")
        return 1

    except ParseError as e:
        logger.error(f"Formula parsing error: {e}")
        return 2

    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Property file error: {e}")
        return 3

    except KeyboardInterrupt:
        logger.error("Monitoring interrupted by user")
        return 4

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 5


if __name__ == "__main__":
    sys.exit(main())
