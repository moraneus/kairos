# model/process_chains.py

"""
Infrastructure for tracking per-process event chains and immediate successors.

This module provides the foundation for literal M-vector algorithm
by maintaining the causal structure needed for proper chain reaction updates.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from model.event import Event


@dataclass
class ProcessEventChains:
    """
    Tracks per-process event chains and provides immediate successor lookup.

    This is the infrastructure required for literal algorithm:
    - Maintains ordered event chains per process
    - Provides immediate successor queries
    - Supports the chain reaction algorithm
    """

    # Per-process ordered event chains: process_id -> [events in causal order]
    _chains: Dict[str, List[Event]] = field(default_factory=dict)

    # Fast lookup: (event, process) -> position in that process's chain
    _event_positions: Dict[tuple[Event, str], int] = field(default_factory=dict)

    # All processes that have been observed
    _known_processes: Set[str] = field(default_factory=set)

    def add_event(self, event: Event) -> None:
        """
        Add an event to the appropriate process chains.

        Args:
            event: The event to add (must be causally delivered)
        """
        for process_id in event.processes:
            # Initialize chain if first event for this process
            if process_id not in self._chains:
                self._chains[process_id] = []

            # Add event to the process chain
            chain = self._chains[process_id]
            position = len(chain)
            chain.append(event)

            # Update position lookup
            self._event_positions[(event, process_id)] = position

            # Track known processes
            self._known_processes.add(process_id)

    def get_immediate_successors(self, event: Event, process_id: str) -> List[Event]:
        """
        Get immediate successors of an event on a specific process.

        From source: "if the observed partial order includes an immediate successor β
        to M[j] (then p_j ∈ P(β)) such that β ⪯ M[i], we set M[j] to β"

        Args:
            event: The event to find successors for
            process_id: The process to search on

        Returns:
            List of immediate successor events (usually 0 or 1)
        """
        if process_id not in self._chains:
            return []

        # Find position of this event in the process chain
        key = (event, process_id)
        if key not in self._event_positions:
            return []

        position = self._event_positions[key]
        chain = self._chains[process_id]

        # Immediate successor is the next event in the chain (if any)
        if position + 1 < len(chain):
            return [chain[position + 1]]
        else:
            return []  # No successor yet

    def get_process_chain(self, process_id: str) -> List[Event]:
        """Get the complete event chain for a process."""
        return self._chains.get(process_id, []).copy()

    def get_known_processes(self) -> Set[str]:
        """Get all processes that have been observed."""
        return self._known_processes.copy()

    def get_latest_event(self, process_id: str) -> Optional[Event]:
        """Get the latest event for a process."""
        chain = self._chains.get(process_id)
        if chain:
            return chain[-1]
        return None

    def is_successor_of(self, potential_successor: Event, base_event: Event,
                        process_id: str) -> bool:
        """
        Check if potential_successor comes after base_event on the given process.

        Args:
            potential_successor: Event that might be a successor
            base_event: Base event to check against
            process_id: Process to check on

        Returns:
            True if potential_successor comes after base_event on process_id
        """
        if process_id not in self._chains:
            return False

        base_key = (base_event, process_id)
        succ_key = (potential_successor, process_id)

        if base_key not in self._event_positions or succ_key not in self._event_positions:
            return False

        base_pos = self._event_positions[base_key]
        succ_pos = self._event_positions[succ_key]

        return succ_pos > base_pos