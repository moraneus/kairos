# utils/trace_reader.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# CSV trace file reader for distributed system event sequences

import csv
from pathlib import Path
from typing import List, FrozenSet, Iterator
from core.event import Event, VectorClock
from utils.logger import get_logger


class TraceFormatError(Exception):
    """Exception raised when trace files contain invalid format or data."""

    pass


def read_trace(filepath: str) -> Iterator[Event]:
    """Read events from CSV trace file.

    Parses a CSV file containing distributed system events with vector clocks
    and propositions. Each event includes an identifier, participating processes,
    vector clock for causality tracking, and associated propositions.

    Expected CSV format:
        eid,processes,vc,props
        ev1,PA|PB,PA:1;PB:1,p|q
        ev2,PC,PA:1;PB:1;PC:1,r

    Args:
        filepath: Path to the CSV trace file

    Yields:
        Event: Parsed events in file order

    Raises:
        TraceFormatError: If file format is invalid or events cannot be parsed
    """
    logger = get_logger()
    path = Path(filepath)

    if not path.exists():
        raise TraceFormatError(f"Trace file not found: {filepath}")

    logger.debug(f"Reading trace file: {filepath}")

    try:
        with open(path, "r", newline="", encoding="utf-8") as file:
            # Handle optional system processes directive
            first_line = file.readline().strip()
            if not first_line.startswith("# system_processes:"):
                file.seek(0)

            reader = csv.DictReader(file)

            # Validate required headers
            required_headers = {"eid", "processes", "vc", "props"}
            if not required_headers.issubset(set(reader.fieldnames or [])):
                missing = required_headers - set(reader.fieldnames or [])
                raise TraceFormatError(f"Missing required headers: {missing}")

            # Parse events
            for row_num, row in enumerate(reader, start=2):
                try:
                    event = _parse_event_row(row)
                    logger.debug(f"Parsed event {event.eid} from row {row_num}")
                    yield event
                except Exception as e:
                    raise TraceFormatError(f"Error parsing row {row_num}: {e}")

    except FileNotFoundError:
        raise TraceFormatError(f"Cannot open trace file: {filepath}")
    except Exception as e:
        raise TraceFormatError(f"Error reading trace file: {e}")


def get_system_processes(filepath: str) -> List[str]:
    """Extract system process list from trace file directive.

    Reads the optional system_processes directive from the first line of a trace file.
    This directive specifies all processes in the distributed system.

    Args:
        filepath: Path to the trace file

    Returns:
        List of process names, empty if no directive found
    """
    logger = get_logger()
    path = Path(filepath)

    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as file:
            first_line = file.readline().strip()
            if first_line.startswith("# system_processes:"):
                processes_str = first_line[len("# system_processes:") :].strip()
                processes = [p.strip() for p in processes_str.split("|") if p.strip()]
                logger.debug(f"Found system processes directive: {processes}")
                return processes
    except Exception:
        logger.debug("No system processes directive found or error reading file")

    return []


def validate_trace_file(filepath: str) -> None:
    """Validate trace file format and structure.

    Performs complete validation by attempting to parse all events in the file.
    This ensures the file format is correct before actual monitoring begins.

    Args:
        filepath: Path to the trace file to validate

    Raises:
        TraceFormatError: If validation fails
    """
    logger = get_logger()
    logger.debug(f"Validating trace file: {filepath}")

    try:
        events = list(read_trace(filepath))
        logger.debug(f"Trace validation successful: {len(events)} events")
    except TraceFormatError as e:
        print(f"❌ Trace validation failed: {e}")
        logger.debug(f"Trace validation failed: {e}")
        raise


def _parse_event_row(row: dict) -> Event:
    """Parse a single CSV row into an Event object.

    Args:
        row: Dictionary containing CSV row data

    Returns:
        Event: Parsed event object

    Raises:
        TraceFormatError: If row data is invalid
    """
    return Event(
        eid=row["eid"].strip(),
        processes=_parse_processes(row["processes"]),
        vc=_parse_vector_clock(row["vc"]),
        props=_parse_props(row["props"]),
    )


def _parse_processes(processes_str: str) -> FrozenSet[str]:
    """Parse pipe-separated process list.

    Args:
        processes_str: String like 'PA|PB|PC'

    Returns:
        FrozenSet of process names

    Raises:
        TraceFormatError: If format is invalid
    """
    if not processes_str.strip():
        raise TraceFormatError("Empty processes field")

    processes = {p.strip() for p in processes_str.split("|") if p.strip()}
    if not processes:
        raise TraceFormatError(f"No valid processes in: {processes_str}")

    return frozenset(processes)


def _parse_vector_clock(vc_str: str) -> VectorClock:
    """Parse semicolon-separated vector clock.

    Args:
        vc_str: String like 'PA:1;PB:2;PC:0'

    Returns:
        VectorClock object

    Raises:
        TraceFormatError: If format is invalid
    """
    if not vc_str.strip():
        return VectorClock({})

    clock = {}
    for component in vc_str.split(";"):
        component = component.strip()
        if not component:
            continue

        try:
            process, timestamp_str = component.split(":", 1)
            process = process.strip()
            timestamp = int(timestamp_str.strip())
            clock[process] = timestamp
        except ValueError:
            raise TraceFormatError(f"Invalid vector clock component: {component}")

    return VectorClock(clock)


def _parse_props(props_str: str) -> FrozenSet[str]:
    """Parse pipe-separated proposition list.

    Args:
        props_str: String like 'p|q|r'

    Returns:
        FrozenSet of proposition names
    """
    if not props_str.strip():
        return frozenset()

    props = {p.strip() for p in props_str.split("|") if p.strip()}
    return frozenset(props)
