# model/frontier.py

"""
Frontier
========

Represents a consistent cut in a partial-order execution: for each process,
it records the latest event seen so far.  If a multi-process event arrives,
it replaces the entry for each of its owning processes.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict

from .event import Event
from .vector_clock import VectorClock


@dataclass(frozen=True, slots=True)
class Frontier:
    events: Dict[str, Event] = field(default_factory=dict)

    def id_short(self) -> str:
        """
        Generates a short, human-readable identifier for the frontier.
        This is often based on a hash of its constituent events for brevity.
        """
        if not self.events:
            return "empty_fr"  # Or any other placeholder for an empty frontier

        # Create a stable, sorted representation of the event identifiers (or event hashes)
        # to ensure the ID is consistent for the same frontier content.
        # Assuming Event objects have a stable, hashable 'id' or can be reliably sorted.
        # If events themselves are not directly hashable for this purpose,
        # use their unique IDs or a stable string representation.
        try:
            # Sort by process ID to ensure consistent order for hashing
            # Use event.id if events have a unique identifier, otherwise str(event) or hash(event)
            # This example assumes events have a simple, sortable ID or can be stringified.
            # Adjust based on your Event class structure.
            relevant_event_parts = [f"{proc_id}:{event.eid}" for proc_id, event in sorted(self.events.items())]
            events_tuple = tuple(relevant_event_parts)
        except AttributeError:  # Fallback if event.id isn't available or sortable like this
            events_tuple = tuple(sorted(str(event) for event in self.events.values()))

        # Using the first 7 characters of the hex representation of the hash (excluding "0x")
        # This provides a reasonably short and somewhat unique ID for display.
        return hex(hash(events_tuple))[2:9]

    @property
    def vc(self) -> VectorClock:
        """
        Compute the vector clock of this frontier by taking, for each process,
        the timestamp from its latest event.
        """
        return VectorClock({pid: ev.vc.clock.get(pid, 0) for pid, ev in self.events.items()})

    def extend(self, ev: Event) -> Frontier:
        """
        Return a new Frontier where, for every process in `ev.processes`,
        the latest event is set to `ev`, and all other entries are unchanged.
        """
        updated = dict(self.events)
        for pid in ev.processes:
            updated[pid] = ev
        return Frontier(updated)

    def concurrent(self, other: Frontier) -> bool:
        """True if this frontier and `other` are concurrent (neither happens-before the other)."""
        return self.vc.concurrent(other.vc)

    def __le__(self, other: object) -> bool:
        return isinstance(other, Frontier) and self.vc <= other.vc

    def __lt__(self, other: object) -> bool:
        return isinstance(other, Frontier) and self.vc < other.vc

    def __ge__(self, other: object) -> bool:
        return isinstance(other, Frontier) and self.vc >= other.vc

    def __gt__(self, other: object) -> bool:
        return isinstance(other, Frontier) and self.vc > other.vc

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Frontier) and self.events == other.events

    def __hash__(self) -> int:
        # Sort items to ensure consistent ordering
        return hash(tuple(sorted(self.events.items())))

    def __str__(self) -> str:
        """
        Render as ⟨pid:event_id, ...⟩ for easy reading of which event is latest
        on each process.
        """
        parts = ", ".join(f"{pid}:{ev.eid}" for pid, ev in sorted(self.events.items()))
        return f"⟨{parts}⟩"
