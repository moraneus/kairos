# model/event.py

"""
Event
=====

Immutable record of an occurrence in the execution trace. An Event may
belong to multiple processes (e.g. an atomic sync on {P, Q}). It carries
a vector clock and a set of propositions (properties) that hold at that
point in the global execution.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import FrozenSet

from .vector_clock import VectorClock


@dataclass(frozen=True, slots=True)
class Event:
    eid: str
    processes: FrozenSet[str]
    vc: VectorClock
    props: FrozenSet[str] = field(default_factory=frozenset)

    def has(self, name: str) -> bool:
        """Return True if this event carries proposition `name`."""
        return name in self.props

    # delegate happens-before relations to the vector clock
    def __le__(self, other: object) -> bool:
        return isinstance(other, Event) and self.vc <= other.vc

    def __lt__(self, other: object) -> bool:
        return isinstance(other, Event) and self.vc < other.vc

    def __ge__(self, other: object) -> bool:
        return isinstance(other, Event) and self.vc >= other.vc

    def __gt__(self, other: object) -> bool:
        return isinstance(other, Event) and self.vc > other.vc

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Event)
            and self.eid == other.eid
            and self.processes == other.processes
            and self.vc == other.vc
            and self.props == other.props
        )

    def __hash__(self) -> int:
        return hash((self.eid, frozenset(self.processes), self.vc, self.props))

    def concurrent(self, other: Event) -> bool:
        """True if this event and `other` are concurrent in the partial order."""
        return self.vc.concurrent(other.vc)

    def __str__(self) -> str:
        procs = ",".join(sorted(self.processes))
        return f"{self.eid}@{procs}:{self.vc}"
