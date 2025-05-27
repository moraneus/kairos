# model/initial_event.py

"""
Defines the special literal name for the initial system state and a
function to create the conceptual initial system event.

The initial system event represents time 0 for all participating system processes
and carries the 'iota' proposition. This allows properties to refer to
the system's starting point.
"""
from typing import Set
from .event import Event
from .vector_clock import VectorClock

IOTA_LITERAL_NAME = "iota"  #: The specific proposition name indicating the initial system event.


def create_initial_system_event(system_processes: Set[str]) -> Event:
    """
    Creates the conceptual initial event that involves all specified system processes.

    This event occurs at vector clock 0 for all these processes and carries
    the 'iota' proposition by default. If no system processes are provided (e.g.,
    before they are discovered or defined), it creates a minimal placeholder event.

    Args:
        system_processes: A set of process ID strings that are part of the system.

    Returns:
        An Event object representing the shared initial state.
    """
    if not system_processes:
        # Fallback: Create a minimal placeholder if no system processes are defined.
        # This is used by Monitor if initialized before processes are known.
        placeholder_processes = frozenset({"_internal_placeholder_init_proc"})
        return Event(
            eid=f"{IOTA_LITERAL_NAME}_placeholder",
            processes=placeholder_processes,
            vc=VectorClock({proc: 0 for proc in placeholder_processes}),
            props=frozenset({IOTA_LITERAL_NAME})
        )

    return Event(
        eid=IOTA_LITERAL_NAME,
        processes=frozenset(system_processes),
        vc=VectorClock({proc: 0 for proc in system_processes}),
        props=frozenset({IOTA_LITERAL_NAME})
    )
