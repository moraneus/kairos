# logic/verdict.py

"""
Verdict enumeration for the runtime monitor, capturing the three possible
outcomes of evaluating a PBTL property against an event trace.
"""

from enum import Enum, auto


class Verdict(Enum):
    """Three-state result of property monitoring."""
    INCONCLUSIVE = auto()  # monitoring still in progress
    TRUE = auto()  # property has been satisfied
    FALSE = auto()  # property has been violated
