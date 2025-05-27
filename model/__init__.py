# model/__init__.py

"""
Domain objects for representing execution traces:
vector clocks, events, partial-order frontiers, and the sliding-window
for frontier generation. These types support the runtime monitor without
pulling in monitoring logic.
"""

from .vector_clock import VectorClock
from .event import Event
from .frontier import Frontier
from .window import SlidingFrontierWindow
from .initial_event import IOTA_LITERAL_NAME, create_initial_system_event

__all__ = [
    "VectorClock",
    "Event",
    "Frontier",
    "SlidingFrontierWindow",
    "IOTA_LITERAL_NAME", # Export the literal name
    "create_initial_system_event", # Export the creation function
]
