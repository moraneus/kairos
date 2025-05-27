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
