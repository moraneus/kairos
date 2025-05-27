# scripts/run_monitor.py

#!/usr/bin/env python3
"""
Command-line tool to evaluate a PBTL property against a causal trace.

Reads a property file and a CSV trace, runs the monitor, and exits with
status 0 on success. Supports optional per-event logging and short-circuiting.
"""

import sys
import argparse
from pathlib import Path

from logic import PropertyAndTraceMonitor, TraceFormatError
from parser.exceptions import ParseError as ParserError


def main():
    parser = argparse.ArgumentParser(
        description="Run a PBTL property monitor over a causal trace"
    )
    parser.add_argument(
        "-s", "--spec",
        type=Path,
        required=True,
        help="Path to the PBTL property file"
    )
    parser.add_argument(
        "-t", "--trace",
        type=Path,
        required=True,
        help="Path to the CSV trace file"
    )
    parser.add_argument(
        "--no-short-circuit",
        action="store_true",
        dest="no_sc",
        help="Continue processing even after a TRUE/FALSE decision"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print per-event delivery logs and intermediate verdicts"
    )
    args = parser.parse_args()

    try:
        runner = PropertyAndTraceMonitor(str(args.spec), str(args.trace))
        runner.run(
            stop_on_decision=not args.no_sc,
            verbose=args.verbose
        )
    except TraceFormatError as e:
        sys.exit(f"ERROR: bad trace format: {e}")
    except ParserError as e:
        sys.exit(f"ERROR: failed to parse property: {e}")
    except Exception as e:
        sys.exit(f"UNEXPECTED ERROR: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
