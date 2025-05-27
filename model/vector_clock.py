# model/vector_clock.py

"""
Immutable Mattern–Fidge vector clock.

Supports:
  •  Component-wise ordering (≤) for happens-before checks.
  •  Concurrency detection (‖).
  •  Join (⊔) to merge observations across processes.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class VectorClock:
    clock: Mapping[str, int]

    def leq(self, other: VectorClock) -> bool:
        """
        Component-wise ≤ comparison.
        Missing entries are treated as 0.
        """
        return all(ts <= other.clock.get(p, 0) for p, ts in self.clock.items())

    def concurrent(self, other: VectorClock) -> bool:
        """
        True if neither self ≤ other nor other ≤ self.
        """
        return not self.leq(other) and not other.leq(self)

    def join(self, other: VectorClock) -> VectorClock:
        """
        Component-wise maximum (⊔) of two vector clocks.
        """
        merged = dict(other.clock)
        for p, ts in self.clock.items():
            merged[p] = max(ts, merged.get(p, 0))
        return VectorClock(merged)

    def copy(self) -> VectorClock:
        """
        Return a shallow copy of this clock.
        """
        return VectorClock(dict(self.clock))

    def __le__(self, other: object) -> bool:  # type: ignore[override]
        if not isinstance(other, VectorClock):
            return NotImplemented
        return self.leq(other)

    def __lt__(self, other: object) -> bool:  # type: ignore[override]
        if not isinstance(other, VectorClock):
            return NotImplemented
        return self.leq(other) and self.clock != other.clock

    def __ge__(self, other: object) -> bool:  # type: ignore[override]
        if not isinstance(other, VectorClock):
            return NotImplemented
        return other.leq(self)

    def __gt__(self, other: object) -> bool:  # type: ignore[override]
        if not isinstance(other, VectorClock):
            return NotImplemented
        return other.leq(self) and self.clock != other.clock

    def __eq__(self, other: object) -> bool:  # type: ignore[override]
        if not isinstance(other, VectorClock):
            return NotImplemented
        return self.clock == other.clock

    def __hash__(self) -> int:
        """
        Stable, order-independent hash based on sorted items.
        """
        return hash(tuple(sorted(self.clock.items())))

    def __str__(self) -> str:
        items = ", ".join(f"{p}:{v}" for p, v in sorted(self.clock.items()))
        return f"[{items}]"

    __repr__ = __str__
