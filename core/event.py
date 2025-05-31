# core/event.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Event representation with vector clocks for distributed system causality tracking

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, FrozenSet, Tuple


@dataclass(frozen=True)
class VectorClock:
    """Vector clock implementation for tracking causal ordering in distributed systems.

    Implements Lamport's vector clock algorithm to determine happens-before relationships
    between events across multiple processes. Each vector clock maps process identifiers
    to logical timestamps.

    The implementation uses immutable tuples for hashability while providing dictionary
    access for convenience. Supports standard vector clock operations including
    happens-before comparison and partial ordering.

    Attributes:
        clock: Tuple of (process_id, timestamp) pairs sorted by process_id
    """

    clock: Tuple[Tuple[str, int], ...]

    def __init__(self, clock_dict: Dict[str, int]) -> None:
        """Initialize vector clock from process-timestamp mapping.

        Args:
            clock_dict: Dictionary mapping process identifiers to timestamps
        """
        sorted_items = tuple(sorted(clock_dict.items()))
        object.__setattr__(self, "clock", sorted_items)

    @property
    def clock_dict(self) -> Dict[str, int]:
        """Convert vector clock to dictionary representation.

        Returns:
            Dictionary mapping process identifiers to timestamps
        """
        return dict(self.clock)

    def __le__(self, other: VectorClock) -> bool:
        """Determine if this vector clock happened-before or is concurrent with another.

        Implements the standard vector clock comparison: self ≤ other if and only if
        for all processes p, self[p] ≤ other[p].

        Args:
            other: Vector clock to compare against

        Returns:
            True if self happened-before or concurrent with other
        """
        self_dict = self.clock_dict
        other_dict = other.clock_dict

        for proc, timestamp in self_dict.items():
            if timestamp > other_dict.get(proc, 0):
                return False
        return True

    def __lt__(self, other: VectorClock) -> bool:
        """Determine if this vector clock strictly happened-before another.

        Args:
            other: Vector clock to compare against

        Returns:
            True if self strictly happened-before other
        """
        return self <= other and self.clock != other.clock

    def __str__(self) -> str:
        """Generate string representation of vector clock.

        Returns:
            Formatted string showing process:timestamp pairs
        """
        return f"[{', '.join(f'{p}:{t}' for p, t in self.clock)}]"


@dataclass(frozen=True)
class Event:
    """Represents a single event in a distributed system execution.

    Events are the fundamental units of computation in distributed systems,
    each associated with a unique identifier, participating processes,
    causal position (vector clock), and logical propositions that hold
    after the event's execution.

    Events support causal ordering through vector clock comparison,
    enabling proper sequencing in distributed runtime verification.

    Attributes:
        eid: Unique identifier for this event
        processes: Set of process identifiers involved in this event
        vc: Vector clock representing the event's causal position
        props: Set of propositions that hold after event execution
    """

    eid: str
    processes: FrozenSet[str]
    vc: VectorClock
    props: FrozenSet[str]

    def has_prop(self, prop_name: str) -> bool:
        """Check if a specific proposition holds for this event.

        Args:
            prop_name: Name of the proposition to check

        Returns:
            True if the proposition holds for this event
        """
        return prop_name in self.props

    def __le__(self, other: Event) -> bool:
        """Determine causal ordering between events using vector clocks.

        Args:
            other: Event to compare against

        Returns:
            True if this event happened-before or concurrent with other
        """
        return self.vc <= other.vc

    def __lt__(self, other: Event) -> bool:
        """Determine strict causal ordering between events.

        Args:
            other: Event to compare against

        Returns:
            True if this event strictly happened-before other
        """
        return self.vc < other.vc

    def __str__(self) -> str:
        """Generate comprehensive string representation of the event.

        Returns:
            Formatted string including event ID, processes, vector clock, and propositions
        """
        processes_str = ",".join(sorted(self.processes))
        props_str = ",".join(sorted(self.props)) if self.props else ""
        return f"{self.eid}@{processes_str}:{self.vc} [{props_str}]"
