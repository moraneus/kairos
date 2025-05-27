# logic/runner.py

"""
PropertyAndTraceMonitor: glue code that ties together a PBTL property and
a CSV-formatted trace, driving the runtime Monitor over each event
and producing a final Verdict. Supports an optional “# system_processes: P|Q|…”
directive to enable optimized causal-window pruning.
"""

import csv
from pathlib import Path
from typing import FrozenSet, Dict, Optional, Set, List

from parser import parse_and_dlnf
from parser.exceptions import ParseError

from model.event import Event
from model.vector_clock import VectorClock

from .monitor import Monitor
from .verdict import Verdict


class TraceFormatError(Exception):
    """Raised when the spec or trace file cannot be read or parsed."""


def _read_file_or_error(path: Path, kind: str) -> str:
    """
    Read a text file into a string, raising TraceFormatError on failure.
    'kind' is used to customize the error message.
    """
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise TraceFormatError(f"{kind} file not found: {path}")
    except Exception as e:
        raise TraceFormatError(f"Could not read {kind} file {path}: {e}")


class PropertyAndTraceMonitor:
    """
    Given a PBTL property file and a CSV trace, runs the Monitor to produce
    a final Verdict. Supports per-event verbose logging, optional early
    stopping, and an optional "# system_processes: P|Q|..." directive for
    enabling optimized SlidingFrontierWindow pruning.
    """
    _SYSTEM_PROCESSES_DIRECTIVE = "# system_processes:"

    def __init__(self, spec_path_str: str, trace_path_str: str):
        spec_path = Path(spec_path_str)
        trace_path = Path(trace_path_str)

        # 1) Load and validate the PBTL property
        spec_text = self._load_property_file(spec_path)

        # 2) Scan the trace for a system_processes directive and prepare CSV reader
        self._all_system_processes: Optional[Set[str]]
        self._reader: Optional[csv.DictReader]
        self._id_field: Optional[str]
        self._prepare_trace_reader_and_processes(trace_path)

        # 3) Instantiate the core Monitor
        self._mon = Monitor(spec_text)

        # 4) Activate pruning optimization if directive found
        if self._all_system_processes is not None:
            self._mon.activate_window_optimization(self._all_system_processes)
            print(f"[INFO] Optimized pruning activated for: "
                  f"{sorted(self._all_system_processes) or 'none'}.")
        else:
            print("[INFO] No system_processes directive; running without pruning optimization.")

    def _load_property_file(self, path: Path) -> str:
        text = _read_file_or_error(path, "Property")
        try:
            parse_and_dlnf(text)
        except ParseError as e:
            raise TraceFormatError(f"Failed to parse property {path}: {e}")
        return text

    def _prepare_trace_reader_and_processes(self, path: Path) -> None:
        """
        Scan the trace file for a "# system_processes: ..." directive, skip it,
        then initialize a csv.DictReader over the remaining lines.
        """
        try:
            lines = list(path.open(newline="", encoding="utf-8"))
        except FileNotFoundError:
            raise TraceFormatError(f"Trace file not found: {path}")
        except Exception as e:
            raise TraceFormatError(f"Could not open trace {path}: {e}")

        directive: Optional[Set[str]] = None
        skip = 0
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith(self._SYSTEM_PROCESSES_DIRECTIVE):
                if directive is not None:
                    raise TraceFormatError("Multiple system_processes directives found.")
                procs = s[len(self._SYSTEM_PROCESSES_DIRECTIVE):].strip()
                directive = {p.strip() for p in procs.split("|") if p.strip()}
                skip = i + 1
            elif s and not s.startswith("#"):
                if directive is None:
                    skip = i
                break

        self._all_system_processes = directive
        data_lines = lines[skip:]
        self._reader = csv.DictReader(data_lines)
        self._validate_headers()

    def _validate_headers(self) -> None:
        if not self._reader:
            raise TraceFormatError("CSV reader not initialized.")

        fields = self._reader.fieldnames
        if not fields:
            return  # empty or header-only file

        names = set(fields)
        if "eid" in names:
            self._id_field = "eid"
        elif "id" in names:
            self._id_field = "id"
        else:
            raise TraceFormatError("Trace header must contain 'eid' or 'id'.")

        required = {self._id_field, "processes", "vc", "props"}
        missing = required - names
        if missing:
            raise TraceFormatError(f"Trace header missing columns: {sorted(missing)}")

    def run(self, *, stop_on_decision: bool = False, verbose: bool = False) -> Verdict:
        """
        Process each event in the trace. If verbose, print per-event frontiers
        and verdict. If stop_on_decision is True, halt when the verdict leaves
        INCONCLUSIVE. Finally finalize and return the Verdict.
        """
        if not self._reader:
            print("[ERROR] No trace reader available.")
            return Verdict.INCONCLUSIVE

        spec_one_line = " ".join(self._mon.spec_src.split())
        print("=== Starting Evaluation ===")
        print(f"Property: {spec_one_line}")
        print(f"Initial verdict: {self._format_verdict(self._mon.verdict)}\n")

        # Print the initial system frontier if verbose mode is on
        if verbose:
            if self._mon.initial_system_frontier:  # Defined in monitor.py
                print(f"Initial System Frontier: {str(self._mon.initial_system_frontier)}")
            else:
                print("Initial System Frontier: Not established (this is unexpected if monitor is initialized).")

        count = 0
        for lineno, row in enumerate(self._reader, start=1):
            if self._id_field is None:
                raise TraceFormatError("ID field not set.")

            try:
                eid = row[self._id_field]
                ev = Event(
                    eid=eid,
                    processes=self._parse_processes(row.get("processes", "")),
                    vc=VectorClock(self._parse_vc(row.get("vc", ""))),
                    props=self._parse_props(row.get("props", ""))
                )
            except Exception as e:
                raise TraceFormatError(f"Error parsing row {lineno}: {e}")

            self._mon.process(ev)
            count += 1

            if verbose:
                frs = [str(f) for f in self._mon._window.frontiers]
                print(f"{ev} → frontiers={frs}, verdict={self._format_verdict(self._mon.verdict)}")

            if stop_on_decision and self._mon.verdict is not Verdict.INCONCLUSIVE:
                break

        if count == 0 and self._reader.fieldnames:
            print("[INFO] No event rows processed despite headers present.")

        self._mon.finish()
        print(f"\n>>> FINAL VERDICT: {self._format_verdict(self._mon.verdict)} <<<")
        print("=== Evaluation Complete ===")

        # Optional FSM visualizations
        for idx, fsm in enumerate(self._mon._fsms):
            # Call the new visualization function
            try:
                # Ensure EPBlockFSM class has this method
                if hasattr(fsm, 'visualize_state'):
                    fsm.visualize_state(f"fsm_state_{idx}")  # fmt defaults to "png"
                else:
                    print(f"[INFO] visualize_fsm_state method not found on FSM {idx}.")
            except Exception as e:
                print(f"[WARN] Error during FSM state visualization for FSM {idx}: {e}")

        # Optional FSM visualizations
        for idx, fsm in enumerate(self._mon._fsms):
            try:
                # Ensure EPBlockFSM class has this method
                if hasattr(fsm, 'visualize_fsm_progress'):  # Call the new function
                    fsm.visualize_fsm_progress(f"fsm_progress_{idx}")
                else:
                    print(f"[INFO] visualize_fsm_progress method not found on FSM {idx}.")
            except Exception as e:
                print(f"[WARN] Error during FSM progress visualization for FSM {idx}: {e}")

        # Optional FSM visualizations
        for idx, fsm in enumerate(self._mon._fsms):
            try:
                if hasattr(fsm, 'visualize_decision_path'):  # Call the new function
                    fsm.visualize_decision_path(f"fsm_decision_path_{idx}")
                elif hasattr(fsm, 'visualize_fsm_progress'):  # Fallback to previous if needed
                    fsm.visualize_fsm_progress(f"fsm_progress_{idx}")
                else:
                    print(f"[INFO] No suitable visualization method found on FSM {idx}.")
            except Exception as e:
                print(f"[WARN] Error during FSM visualization for FSM {idx}: {e}")

        # Optional FSM visualizations
        for idx, fsm in enumerate(self._mon._fsms):
            try:
                if hasattr(fsm, 'visualize_satisfaction_timeline'):  # Call the new function
                    fsm.visualize_satisfaction_timeline(f"fsm_timeline_{idx}")
                elif hasattr(fsm, 'visualize_decision_path'):  # Fallback
                    fsm.visualize_decision_path(f"fsm_decision_path_{idx}")
            except Exception as e:
                print(f"[WARN] Error during FSM visualization for FSM {idx}: {e}")

        return self._mon.verdict

    @staticmethod
    def _parse_processes(field: str) -> FrozenSet[str]:
        parts = [p.strip() for p in field.split("|") if p.strip()]
        if not parts:
            raise ValueError("Empty processes field")
        return frozenset(parts)

    @staticmethod
    def _parse_vc(field: str) -> Dict[str, int]:
        clk: Dict[str, int] = {}
        for comp in field.split(";"):
            comp = comp.strip()
            if not comp:
                continue
            pid, ts = comp.split(":", 1)
            clk[pid.strip()] = int(ts)
        return clk

    @staticmethod
    def _parse_props(field: str) -> FrozenSet[str]:
        return frozenset(p.strip() for p in field.split("|") if p.strip())

    @staticmethod
    def _format_verdict(v: Verdict) -> str:
        if v is Verdict.INCONCLUSIVE:
            return f"{Verdict.FALSE.name} (Inconclusive)"
        return v.name
