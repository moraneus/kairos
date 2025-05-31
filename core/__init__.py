# core/__init__.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Core module public API for PBTL monitoring components

"""Core components for PBTL (Past-Based Temporal Logic) runtime verification.

This module provides the fundamental data structures and algorithms for monitoring
distributed system executions against temporal logic specifications. The core
components implement the theoretical foundations of partial order executions,
vector clocks, global states (frontiers), and three-valued monitoring verdicts.

The module supports runtime verification of temporal properties over distributed
systems where events may occur concurrently and causal relationships must be
preserved during analysis.

Primary Components:
    Event: Represents individual events in distributed system execution
    VectorClock: Implements Lamport's vector clock algorithm for causality
    Frontier: Represents consistent global states (cuts) in partial order executions
    Verdict: Three-valued logic results for property monitoring
    PBTLMonitor: Main monitoring engine implementing Section 4 algorithm
    EPDisjunct: Individual disjunct tracking for DLNF formula evaluation

Example:
    >>> from core import PBTLMonitor, Event, VectorClock
    >>> monitor = PBTLMonitor("EP(EP(p) & !EP(q))")
    >>> event = Event("e1", {"P1"}, VectorClock({"P1": 1}), {"p"})
    >>> monitor.process_event(event)
"""

from .event import Event, VectorClock
from .frontier import Frontier
from .monitor import PBTLMonitor, EPDisjunct
from .verdict import Verdict

__all__ = ["Event", "VectorClock", "Frontier", "PBTLMonitor", "EPDisjunct", "Verdict"]

__version__ = "1.0.0"
__author__ = "Moran Omer"
__description__ = "Core components for PBTL runtime verification"
