# core/frontier.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Frontier representation for consistent global states in partial order executions

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple

from .event import Event, VectorClock
from utils.logger import get_logger


@dataclass(frozen=True)
class Frontier:
    """Represents a consistent cut (global state) in partial order execution.

    A frontier corresponds to a consistent global state across all processes in a
    distributed system, where each process is associated with its latest event
    in this particular global state. This concept is fundamental to distributed
    system analysis and represents a snapshot that respects causality constraints.

    In the context of runtime verification, frontiers represent moments in time
    where temporal logic properties can be evaluated against the global system state.
    Each frontier maintains the component-wise maximum vector clock of its constituent
    events, enabling proper causal ordering between different global states.

    The implementation ensures immutability and hashability for use in sets and
    as dictionary keys, while providing convenient dictionary-style access to
    the underlying process-event mappings.

    Attributes:
        events: Tuple of (process_id, event) pairs sorted by process identifier
    """

    events: Tuple[Tuple[str, Event], ...]

    def __init__(self, events_dict: Dict[str, Event]) -> None:
        """Initialize frontier from process-event mapping.

        Creates an immutable frontier by converting the provided dictionary into
        a sorted tuple of process-event pairs. The sorting ensures deterministic
        ordering and consistent string representations.

        Args:
            events_dict: Dictionary mapping process identifiers to their latest events
        """
        logger = get_logger()
        logger.debug(
            f"Creating frontier from {len(events_dict)} process-event mappings"
        )

        sorted_items = tuple(sorted(events_dict.items()))
        object.__setattr__(self, "events", sorted_items)

        logger.debug(f"Frontier created with processes: {list(events_dict.keys())}")

    @property
    def events_dict(self) -> Dict[str, Event]:
        """Convert frontier events to dictionary representation.

        Provides convenient dictionary-style access to the process-event mappings
        while maintaining the immutable tuple-based internal representation.

        Returns:
            Dictionary mapping process identifiers to their latest events
        """
        return dict(self.events)

    @property
    def vc(self) -> VectorClock:
        """Compute the vector clock representing this frontier's causal position.

        The frontier's vector clock is calculated as the component-wise maximum
        of all participating events' vector clocks. This preserves the complete
        causal context and enables proper ordering between different frontiers.

        This computation ensures that the frontier's vector clock accurately
        represents the latest known information about all processes in the system,
        even those not directly represented in the frontier's events.

        Returns:
            Vector clock representing the frontier's causal position
        """
        if not self.events:
            return VectorClock({})

        # Collect all processes from all event vector clocks
        all_processes = set()
        for _, event in self.events:
            all_processes.update(event.vc.clock_dict.keys())

        # Compute component-wise maximum across all events
        clock = {}
        for proc in all_processes:
            max_timestamp = 0
            for _, event in self.events:
                proc_timestamp = event.vc.clock_dict.get(proc, 0)
                max_timestamp = max(max_timestamp, proc_timestamp)
            clock[proc] = max_timestamp

        logger = get_logger()
        logger.debug(f"Computed frontier VC: {clock}")

        return VectorClock(clock)

    def extend_with_event(self, event: Event) -> Frontier:
        """Create new frontier by incorporating an additional event.

        Generates a new frontier where the provided event becomes the latest
        event for all of its participating processes. This operation preserves
        the immutability of the original frontier while creating a causally
        extended global state.

        Args:
            event: Event to incorporate into the new frontier

        Returns:
            New frontier with the event incorporated
        """
        logger = get_logger()
        logger.debug(
            f"Extending frontier with event {event.eid} on processes {event.processes}"
        )

        new_events = self.events_dict
        for proc_id in event.processes:
            new_events[proc_id] = event

        logger.debug(f"New frontier will have {len(new_events)} process mappings")
        return Frontier(new_events)

    def has_prop(self, prop_name: str) -> bool:
        """Check if any event in this frontier satisfies a given proposition.

        Searches through all events in the frontier to determine if the specified
        proposition holds in this global state. This is essential for evaluating
        temporal logic formulas against frontier states.

        Args:
            prop_name: Name of the proposition to check

        Returns:
            True if any event in the frontier has the specified proposition
        """
        result = any(event.has_prop(prop_name) for _, event in self.events)

        logger = get_logger()
        logger.debug(
            f"Proposition '{prop_name}' {'found' if result else 'not found'} in frontier"
        )

        return result

    def __le__(self, other: Frontier) -> bool:
        """Determine causal ordering between frontiers using vector clocks.

        Implements the standard happens-before relationship for global states:
        this frontier happened-before or is concurrent with the other frontier
        if and only if this frontier's vector clock ≤ other frontier's vector clock.

        Args:
            other: Frontier to compare against

        Returns:
            True if this frontier happened-before or concurrent with other
        """
        return self.vc <= other.vc

    def __lt__(self, other: Frontier) -> bool:
        """Determine strict causal ordering between frontiers.

        Args:
            other: Frontier to compare against

        Returns:
            True if this frontier strictly happened-before other
        """
        return self.vc < other.vc

    def __str__(self) -> str:
        """Generate compact string representation of the frontier.

        Creates a human-readable representation showing the process-event mappings
        in a consistent format suitable for logging and debugging.

        Returns:
            Formatted string representation of the frontier
        """
        if not self.events:
            return "⟨empty⟩"

        items = []
        for proc, event in self.events:
            items.append(f"{proc}:{event.eid}")

        return f"⟨{', '.join(items)}⟩"

    def debug_str(self) -> str:
        """Generate detailed string representation including vector clock information.

        Provides comprehensive debugging information by including both the frontier
        structure and its computed vector clock. Useful for detailed analysis
        of causal relationships and frontier evolution.

        Returns:
            Detailed string representation with vector clock information
        """
        return f"{self} VC:{self.vc}"
