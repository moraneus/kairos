
# logic/gamma_analysis.py

"""
Analysis of M-literals to determine process-specific γᵢ components.

It is necessarily partitioning the M-literal conjunction into process-specific
components γᵢ. This module analyzes PBTL expressions to determine which
processes each M-literal depends on.
"""

from typing import Dict, Set, List, Optional, Protocol
from parser.ast_nodes import Expr, Literal  # Keep this, might be used by ProcessAnnotation or future uses
from model.event import Event  # Used by check_gamma_satisfaction
from model.initial_event import IOTA_LITERAL_NAME


class ProcessAnnotation(Protocol):
    """
    Protocol for future explicit process annotations.

    This defines the interface for explicit process ownership annotations
    that could replace the current naming convention heuristics.
    """

    def get_relevant_processes(self, prop_name: str) -> Set[str]:
        """Return the set of processes that own this proposition."""
        ...


def analyze_gamma_mapping(m_literals: List[Expr], known_processes: Set[str],
                          annotation_provider: Optional[ProcessAnnotation] = None) -> Dict[str, List[Expr]]:
    gamma_mapping: Dict[str, List[Expr]] = {}
    if not m_literals: return gamma_mapping

    # Exclude any process starting with '_' (convention for internal/special processes)
    relevant_system_processes = {p for p in known_processes if not p.startswith("_")}

    if not relevant_system_processes and not all(
            isinstance(m, Literal) and m.name == IOTA_LITERAL_NAME for m in m_literals):
        # No actual system processes known, and M-literals are not exclusively "iota".
        # Cannot form meaningful gamma_i for system processes.
        return gamma_mapping  # Return empty mapping

    for proc in relevant_system_processes:
        gamma_mapping[proc] = list(m_literals)

    # If M-literals *only* contain "iota", and no system processes are known,
    # gamma_mapping would be empty. This is handled by M-search logic:
    # if relevant_processes is empty but M is only "iota", search can still be active.

    return gamma_mapping


def get_gamma_for_process(process_id: str, gamma_mapping: Dict[str, List[Expr]]) -> List[Expr]:
    """
    Get the γᵢ component (M-literals) for a specific process.
    """
    return gamma_mapping.get(process_id, [])


def has_gamma_for_process(process_id: str, gamma_mapping: Dict[str, List[Expr]]) -> bool:
    """
    Check if a process has any γᵢ component (relevant M-literals).
    """
    gamma_i = gamma_mapping.get(process_id, [])
    return len(gamma_i) > 0


def check_gamma_satisfaction(event: Event, process_id: str, gamma_mapping: Dict[str, List[Expr]]) -> bool:
    """
    Check if an event satisfies γᵢ for a specific process.
    """
    gamma_i = get_gamma_for_process(process_id, gamma_mapping)

    if not gamma_i:
        return True

    from model.frontier import Frontier
    temp_frontier = Frontier({process_id: event})

    from logic.ep_block_fsm import _holds  # Circular import guard might be needed if used differently
    return all(_holds(literal, temp_frontier) for literal in gamma_i)