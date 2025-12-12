# core/frontier_detector.py
# Simplified and corrected implementation of Section 4 algorithm
#
# This implementation avoids infinite loops and implements the algorithm clearly

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from .event import Event
from .frontier import Frontier


@dataclass
class FrontierDetector:
    """
    Simplified frontier detection algorithm from Section 4.

    Finds minimum frontier satisfying conjunction of minterms η = ⋀ᵢ γᵢ
    """

    minterms: Dict[str, List[str]]  # process -> required propositions
    all_processes: Set[str]
    M: Dict[str, Optional[Event]] = field(default_factory=dict)
    P: Optional[Frontier] = None
    observed_events: List[Event] = field(default_factory=list)

    def __post_init__(self):
        """Initialize M vector."""
        # Initialize M for all processes
        for proc in self.all_processes:
            self.M[proc] = None

        # If P provided, initialize M from P
        if self.P is not None:
            for proc, event in self.P.events_dict.items():
                self.M[proc] = event

    def process_new_event(self, event: Event) -> Optional[Frontier]:
        """
        Process event following Section 4 algorithm.

        Returns frontier if all minterms satisfied, None otherwise.
        """
        # Add to observed events
        self.observed_events.append(event)

        # Component correction with new event α
        for proc in event.processes:
            if proc in self.minterms:
                # Check if M[proc] satisfies minterm
                if not self._satisfies_minterm(self.M.get(proc), proc):
                    # Update M[proc] to α
                    self.M[proc] = event

        # Frontier correction - ensure M forms a frontier
        self._frontier_correction()

        # Repeated component correction
        self._repeated_component_correction()

        # Check if all minterms satisfied
        if self._all_minterms_satisfied():
            return self._create_frontier()

        return None

    def _satisfies_minterm(self, event: Optional[Event], proc: str) -> bool:
        """Check if event satisfies minterm for process."""
        if event is None or proc not in self.minterms:
            return False

        required = self.minterms[proc]
        for prop in required:
            if prop.startswith("!"):
                if prop[1:] in event.props:
                    return False
            else:
                if prop not in event.props:
                    return False
        return True

    def _frontier_correction(self):
        """
        Ensure M represents a valid frontier.

        For each M[j], if there exists successor β with β ⪯ M[i] for some i≠j,
        then set M[j] = β (and update other processes in Pr(β)).
        """
        max_iterations = 100  # Prevent infinite loops

        for _ in range(max_iterations):
            updated = False

            for proc_j in self.all_processes:
                if self.M[proc_j] is None:
                    continue

                # Find successors of M[j]
                for event in self.observed_events:
                    if proc_j not in event.processes:
                        continue

                    # Check if event is successor of M[j]
                    if self.M[proc_j].vc >= event.vc:
                        continue

                    # Check if event ⪯ M[i] for some i≠j
                    can_update = False
                    for proc_i in self.all_processes:
                        if proc_i == proc_j or self.M[proc_i] is None:
                            continue
                        if event.vc <= self.M[proc_i].vc:
                            can_update = True
                            break

                    if can_update:
                        # Update M[j] = event
                        self.M[proc_j] = event

                        # Update all procs in Pr(event)
                        for proc_k in event.processes:
                            if self.M[proc_k] is None or self.M[proc_k].vc < event.vc:
                                self.M[proc_k] = event

                        updated = True
                        break

                if updated:
                    break

            if not updated:
                break

    def _repeated_component_correction(self):
        """
        Fix components that no longer satisfy minterms after frontier correction.
        """
        for proc in self.all_processes:
            if proc not in self.minterms:
                continue

            # If M[proc] doesn't satisfy minterm
            if not self._satisfies_minterm(self.M.get(proc), proc):
                # Find minimal event ν > M[proc] that satisfies minterm
                best_event = None

                for event in self.observed_events:
                    if proc not in event.processes:
                        continue

                    # Check if event > M[proc]
                    if self.M[proc] is not None and event.vc <= self.M[proc].vc:
                        continue

                    # Check if satisfies minterm
                    if self._satisfies_minterm(event, proc):
                        if best_event is None or event.vc < best_event.vc:
                            best_event = event

                # If no satisfying event, take maximal
                if best_event is None:
                    for event in self.observed_events:
                        if proc in event.processes:
                            if best_event is None or event.vc > best_event.vc:
                                best_event = event

                if best_event is not None:
                    self.M[proc] = best_event

    def _all_minterms_satisfied(self) -> bool:
        """Check if all minterms are satisfied."""
        for proc in self.all_processes:
            if proc in self.minterms:
                if not self._satisfies_minterm(self.M.get(proc), proc):
                    return False

        # Also check we have events for all processes
        for proc in self.all_processes:
            if self.M.get(proc) is None:
                return False

        return True

    def _create_frontier(self) -> Frontier:
        """Create frontier from M vector."""
        events = {p: e for p, e in self.M.items() if e is not None}
        return Frontier(events)

    def get_current_M(self) -> Dict[str, Optional[Event]]:
        """Get current M vector state."""
        return self.M.copy()

    def reset(self) -> None:
        """Reset detector to initial state."""
        self.M.clear()
        self.observed_events.clear()

        for proc in self.all_processes:
            self.M[proc] = None

        if self.P is not None:
            for proc, event in self.P.events_dict.items():
                self.M[proc] = event
