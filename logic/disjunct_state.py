# logic/disjunct_state.py

"""
Defines data structures and logic for tracking the runtime state of
individual disjuncts within a Disjunctive Literal Normal Form (DLNF) formula.

In the context of monitoring EP-formulas, each DLNF disjunct, typically of the
form EP(φ), is analyzed by partitioning φ. If φ is a conjunction, its components
are categorized into:

- P-blocks: Sub-formulas that are themselves EP(...) expressions. These represent
  conditions that must have been true at some point in the past.
- M-literals: Propositional literals (atomic propositions or their negations) or
  negated non-EP expressions. These represent conditions that must hold
  simultaneously at a single global state (frontier) of the system.
- N-blocks: Sub-formulas of the form !EP(...). These represent conditions
  (the inner EP part) that must not have become true in a way that invalidates
  the overall disjunct.

This module provides the `DisjunctRuntime` class to manage the satisfaction
state of these P, M, and N blocks for a single disjunct. This includes implementing
the procedural M-vector search algorithm, which is a core part of determining
if the M-literals can be satisfied.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Set, Callable

from parser.ast_nodes import And, EP, Expr, Literal, Not
from model.frontier import Frontier
from model.event import Event
from model.initial_event import IOTA_LITERAL_NAME
from utils.logger import get_logger

logger = get_logger(__name__)


def partition(ep_node: EP) -> Tuple[List[Expr], List[Expr], List[Expr]]:
    """
    Splits the operand of an EP node into P-blocks, M-literals, and N-block inner expressions.

    The operand of the EP node is assumed to be a conjunction, as per the DLNF structure.
    This function flattens this conjunction and categorizes each conjunct.

    Args:
        ep_node: The EP AST node whose operand is to be partitioned.

    Returns:
        A tuple containing three lists:
        - p_list: List of expressions that are P-blocks (EP subformulas).
        - m_list: List of expressions that are M-literals (literals or other non-EP expressions).
        - n_list: List of inner expressions from N-blocks (the `psi` from `!EP(psi)`).
    """
    # Flatten the conjunction if the operand is an And node.
    components = (
        _flatten_and(ep_node.operand)
        if isinstance(ep_node.operand, And)
        else [ep_node.operand] # Operand is a single component.
    )
    p_list: List[Expr] = []
    m_list: List[Expr] = []
    n_list: List[Expr] = []  # Stores the EP(psi) part of an N-block !EP(psi)

    for comp in components:
        if isinstance(comp, EP):
            p_list.append(comp) # An EP subformula is a P-block.
        elif isinstance(comp, Not) and isinstance(comp.operand, EP):
            n_list.append(comp.operand)  # For !EP(psi), store psi as the N-block's inner expression.
        else:
            m_list.append(comp) # Anything else is considered an M-literal or M-block component.
    return p_list, m_list, n_list


def _flatten_and(node: And) -> List[Expr]:
    """
    Extracts all individual conjuncts from a possibly nested And expression.
    For example, `A & (B & C)` would be flattened to `[A, B, C]`.

    Args:
        node: The root And node of the conjunction.

    Returns:
        A list of all non-And expressions that were part of the conjunction.
    """
    stack = [node]
    result: List[Expr] = []
    while stack:
        current = stack.pop()
        if isinstance(current, And):
            # The parser typically creates right-associative And nodes (A & (B & C)).
            # For collecting conjuncts, the order or associativity doesn't strictly matter,
            # but processing both children ensures all parts are captured.
            stack.append(current.left)
            stack.append(current.right)
        else:
            result.append(current)
    # The order in the result list might not match visual parsing order of nested Ands,
    # but it contains all distinct conjuncts.
    return result


@dataclass(slots=True)
class BlockState:
    """
    Records a subformula (typically a P-block's EP formula or an N-block's inner EP formula)
    and the first frontier at which it was observed to be satisfied.

    Attributes:
        formula: The AST expression for this block.
        satisfied_at: The Frontier where `formula` first held true, if any.
    """
    formula: Expr
    satisfied_at: Optional[Frontier] = None


@dataclass(slots=True)
class DisjunctRuntime:
    """
    Manages the runtime state for monitoring a single DLNF disjunct (EP(P & M & N)).

    This class tracks the satisfaction of P-blocks (past conditions), M-literals
    (current state conditions), and N-blocks (negated past conditions).
    It implements the procedural M-vector search algorithm to find a consistent
    global state (frontier) where all M-literals hold, subject to constraints
    imposed by satisfied P-blocks and N-blocks.

    Attributes:
        p: List of BlockState objects for P-blocks.
        m: List of BlockState objects for M-literals.
        n: List of BlockState objects for N-blocks (tracking their inner EP formulas).
        success: True if the disjunct is determined to be true.
        failure: True if the disjunct is determined to be false.
        first_all_p_conjunctive_satisfaction_frontier: The first frontier where all P-blocks were met.
        m_satisfaction_frontier: The frontier where all M-literals were found to hold.
        m_vector: Maps process IDs to their latest event in the current M-search candidate frontier.
        m_search_active: Flag indicating if the procedural M-vector search is active.
        gamma_mapping: Maps process IDs to lists of M-literals relevant to that process.
        successor_lookup: Function to find successor events for the M-vector search.
        relevant_processes: Set of process IDs involved in the M-literal search.
    """
    p: List[BlockState]
    m: List[BlockState]
    n: List[BlockState]

    success: bool = False
    failure: bool = False

    first_all_p_conjunctive_satisfaction_frontier: Optional[Frontier] = None
    m_satisfaction_frontier: Optional[Frontier] = None

    # --- M-vector search components ---
    m_vector: Dict[str, Event] = field(default_factory=dict)
    m_search_active: bool = False
    gamma_mapping: Dict[str, List[Expr]] = field(default_factory=dict)
    successor_lookup: Optional[Callable[[Event, str], List[Event]]] = None
    relevant_processes: Set[str] = field(default_factory=set)

    def initialize_m_vector_search(self,
                                   gamma_mapping: Dict[str, List[Expr]],
                                   p_frontier: Optional[Frontier] = None,
                                   successor_lookup: Optional[Callable[[Event, str], List[Event]]] = None) -> None:
        """
        Initializes or re-initializes the M-vector search parameters and state.

        This method is typically called when all P-blocks for the disjunct have been satisfied
        (for P+M type formulas), or at the start for M-only formulas, or if the set of
        known system processes changes (which might affect the gamma_mapping).

        Args:
            gamma_mapping: A mapping from process IDs to the M-literals relevant to each process.
            p_frontier: If P-blocks exist and were satisfied, this is the frontier where that occurred.
                        Events from this frontier seed the initial M-vector.
            successor_lookup: A function to find subsequent events for processes, crucial for
                              the chain reaction part of the M-vector algorithm.
        """
        self.gamma_mapping = gamma_mapping
        self.successor_lookup = successor_lookup

        # Relevant processes are those that have some M-literals associated with them.
        self.relevant_processes = {
            proc for proc, gamma_i_literals in gamma_mapping.items() if gamma_i_literals
        }

        # Determine if all M-literals are exclusively the 'iota' literal.
        is_m_block_only_iota = False
        if self.m:
            is_m_block_only_iota = all(
                isinstance(m_block.formula, Literal) and m_block.formula.name == IOTA_LITERAL_NAME
                for m_block in self.m
            )

        if not self.relevant_processes and not is_m_block_only_iota:
            # If there are no relevant system processes for non-'iota' M-literals,
            # the M-search cannot proceed effectively.
            self.m_search_active = False
            self.m_vector.clear()
            return

        self.m_search_active = True
        self.m_vector.clear()  # Always start M-search (or restart) with an empty vector.

        # If a P-frontier is provided (meaning P-blocks were met),
        # initialize the M-vector with events from this frontier for relevant processes.
        if p_frontier and p_frontier.events:
            for proc_id, event_in_p_fr in p_frontier.events.items():
                if proc_id in self.relevant_processes:
                    self.m_vector[proc_id] = event_in_p_fr

    def update_m_vector_with_event(self, event: Event) -> bool:
        """
        Updates the M-vector based on a newly observed event, following the
        procedural algorithm for finding a satisfying frontier for M-literals.

        Args:
            event: The new event to process.

        Returns:
            True if the M-vector was modified as a result of this event, False otherwise.
        """
        if not self.m_search_active or not self.m:
            return False # M-search is not active or no M-literals to satisfy.

        modified = False
        processes_needing_m_vector_update = [] # Processes whose M-vector entry might change.

        for process_id in event.processes:
            if process_id not in self.relevant_processes:
                continue # This process is not relevant to the current M-literal search.

            current_event_in_m_vector = self.m_vector.get(process_id)

            # The algorithm states: "For each pᵢ ∈ P(event) whether M[i] ⊨ γᵢ.
            # If this holds... no need to change M. Otherwise, we set M[i] to event."
            if current_event_in_m_vector is None or \
               not self._check_gamma_satisfaction(current_event_in_m_vector, process_id):
                processes_needing_m_vector_update.append(process_id)

        # Update M-vector entries for processes where current event didn't satisfy gamma.
        for process_id in processes_needing_m_vector_update:
            self.m_vector[process_id] = event
            modified = True

        if modified:
            # If M-vector was changed, propagate updates to ensure consistency (chain reaction).
            self._perform_chain_reaction(event)
        return modified

    def _check_gamma_satisfaction(self, event: Event, process_id: str) -> bool:
        """
        Checks if the given `event` (representing M[process_id]) satisfies the
        M-literals (γ_process_id) relevant to `process_id`.

        Args:
            event: The event to check.
            process_id: The ID of the process.

        Returns:
            True if the event satisfies the gamma condition for the process, False otherwise.
        """
        # Local import to avoid circular dependency issues at module load time.
        from logic.gamma_analysis import check_gamma_satisfaction as external_check_gamma
        return external_check_gamma(event, process_id, self.gamma_mapping)

    def _perform_chain_reaction(self, triggering_event: Event) -> None:
        """
        Performs the chain reaction step of the M-vector search algorithm.
        This step ensures that the M-vector (a collection of events, one per relevant process)
        remains a causally consistent cut (frontier) by advancing events on some processes
        if they are "lagging behind" others, based on causal dependencies revealed by
        event vector clocks and the successor lookup function.

        Args:
            triggering_event: The event that initiated changes to the M-vector.
        """
        if not self.successor_lookup:
            # If no successor lookup function is available, use a simplified consistency check.
            self._simplified_chain_reaction(triggering_event)
            return

        # First, enforce consistency based on the triggering event's knowledge.
        self._enforce_vector_clock_consistency(triggering_event)

        changed_in_iteration = True
        iterations = 0
        # Set a practical limit on iterations to prevent infinite loops in complex scenarios.
        max_iterations = len(self.relevant_processes) * (len(self.relevant_processes) + 5) # Heuristic limit.

        while changed_in_iteration and iterations < max_iterations:
            changed_in_iteration = False
            iterations += 1
            # Iterate over relevant processes to check for necessary advancements.
            for j_proc in list(self.m_vector.keys()): # Use list copy for safe iteration if modifying dict.
                if j_proc not in self.relevant_processes: continue
                current_mj_event = self.m_vector[j_proc] # M[j] in algorithm notation.

                for i_proc in list(self.m_vector.keys()):
                    if i_proc == j_proc or i_proc not in self.relevant_processes: continue
                    mi_event = self.m_vector[i_proc] # M[i] in algorithm notation.

                    # Algorithm step: "If the observed partial order includes an immediate successor β to M[j]...
                    # such that β ≤ M[i] (vector clock comparison), we set M[j] to β."
                    immediate_successors_of_mj = self.successor_lookup(current_mj_event, j_proc)

                    for beta_event in immediate_successors_of_mj:
                        if beta_event.vc <= mi_event.vc:  # β is causally before or concurrent with M[i].
                            if self.m_vector.get(j_proc) != beta_event: # Update only if different.
                                self.m_vector[j_proc] = beta_event
                                changed_in_iteration = True
                                break # M[j] advanced, re-evaluate conditions from start.
                    if changed_in_iteration: break
                if changed_in_iteration: break

        if iterations >= max_iterations and changed_in_iteration:
            logger.warning(f"M-vector chain reaction for disjunct of {self} (triggered by {triggering_event.eid}) "
                           f"exceeded max iterations ({max_iterations}). M-vector might not be fully stable.")

    def _simplified_chain_reaction(self, triggering_event: Event) -> None:
        """
        A simplified chain reaction for M-vector consistency when a full successor lookup
        mechanism is not available. It primarily ensures that events in the M-vector are not
        causally older than the triggering event if they share processes.
        """
        for proc_id in list(self.m_vector.keys()):
            if proc_id not in self.relevant_processes: continue
            current_event_in_m_vector = self.m_vector[proc_id]
            # If the M-vector's event for proc_id is causally before the triggering event...
            if current_event_in_m_vector < triggering_event:
                # ...and the triggering event also involves this process, update M-vector to triggering_event.
                if proc_id in triggering_event.processes:
                    self.m_vector[proc_id] = triggering_event

    def check_m_satisfaction(self) -> Optional[Frontier]:
        """
        Checks if the current M-vector (set of events M[i] for relevant processes)
        forms a frontier that satisfies all M-literals.

        The `_holds` function (which this method calls via `logic.ep_block_fsm`) evaluates
        literals against the properties of events present in the constructed frontier.
        If 'iota' is one of the M-literals, one of the events in the `m_vector`
        (for the relevant processes) must carry the 'iota' property for that literal to hold.

        Returns:
            A Frontier object if all M-literals are satisfied by the current M-vector,
            None otherwise.
        """
        if not self.m_search_active or not self.m:
            return None # M-search not active or no M-literals to satisfy.

        # Check if all M-literals are just 'iota'.
        is_m_block_only_iota = all(
            isinstance(m_block.formula, Literal) and m_block.formula.name == IOTA_LITERAL_NAME
            for m_block in self.m
        )

        if not self.m_vector and not is_m_block_only_iota:
            # M-vector is empty, and M-literals are not exclusively 'iota'.
            # An empty M-vector (representing no specific system events chosen by the procedure)
            # cannot satisfy concrete non-'iota' M-literals.
            return None

        # If there are no M-literals, they are vacuously satisfied.
        # Return a frontier based on the current m_vector (which could be empty if M-search just started from initial state).
        if not self.m:
            return Frontier(dict(self.m_vector))

        # Construct a candidate frontier from the current M-vector.
        # This frontier represents the global state formed by the events in m_vector.
        try:
            # Note: If m_vector is empty (e.g., if M-search started from an initial state without
            # P-block influence and no events have been processed yet for relevant processes),
            # Frontier({}) will be created. _holds(literal, Frontier({})) will be False for any non-iota literal.
            m_frontier_candidate = Frontier(dict(self.m_vector))
        except Exception as e: # Catch potential errors from Frontier constructor.
            logger.error(f"Error constructing Frontier from M-vector {self.m_vector}: {e}")
            return None

        # Local import of _holds to avoid circular dependencies at module load time.
        from logic.ep_block_fsm import _holds
        # Check if all M-literals hold on this candidate frontier.
        if all(_holds(m_block.formula, m_frontier_candidate) for m_block in self.m):
            return m_frontier_candidate

        return None # M-literals not satisfied.

    def stop_m_search(self) -> None:
        """Stops the M-vector search, typically when a verdict for the disjunct is reached."""
        self.m_search_active = False

    def get_relevant_processes(self) -> Set[str]:
        """
        Returns a copy of the set of process IDs deemed relevant for the M-literal search.
        These are processes whose state is tracked in the M-vector.
        """
        return self.relevant_processes.copy()

    def _enforce_vector_clock_consistency(self, triggering_event: Event) -> None:
        """
        Ensures M-vector consistency based on the causal knowledge of the `triggering_event`.

        If the `triggering_event` has explicit knowledge (via its vector clock) that a process
        `p` in the M-vector was in an earlier state than `M[p]` currently indicates,
        then `M[p]` is rolled back to a state consistent with `triggering_event`'s knowledge.
        This prevents the M-vector from representing a state that is causally impossible
        given the `triggering_event`.

        It also handles cases where events in the M-vector might conflict with the
        triggering_event if they involve the same processes but represent different states.

        Args:
            triggering_event: The event whose causal knowledge is used for consistency checks.
        """
        for process_id in self.relevant_processes:
            if process_id in triggering_event.processes:
                # This process is directly updated by the triggering_event itself
                # as part of update_m_vector_with_event; its consistency is handled there.
                continue

            current_event_in_m_vector = self.m_vector.get(process_id)
            if current_event_in_m_vector is None:
                continue # No event in M-vector for this process yet.

            # Check if triggering_event has *explicit* knowledge about this process_id's state.
            if process_id not in triggering_event.vc.clock:
                # If triggering_event's VC has no entry for process_id, it means
                # triggering_event has no causal knowledge of process_id's state (they are concurrent
                # with respect to process_id's timeline up to current_event_in_m_vector).
                # In this case, do NOT roll back M[process_id].
                continue

            # At this point, triggering_event.vc.clock[process_id] exists.
            triggering_event_knowledge_ts = triggering_event.vc.clock[process_id]
            current_event_own_ts = current_event_in_m_vector.vc.clock.get(process_id, 0)

            if triggering_event_knowledge_ts < current_event_own_ts:
                # The triggering_event knows about an *earlier* state of process_id than M[process_id].
                # This is a causality constraint that requires rolling back M[process_id].
                logger.debug(f"M-vector: Rolling back {process_id} due to causality constraint from {triggering_event.eid}. "
                             f"Trigger knows {process_id} at ts {triggering_event_knowledge_ts}, "
                             f"M-vector has {current_event_in_m_vector.eid} at ts {current_event_own_ts}.")

                if triggering_event_knowledge_ts == 0:
                    # Roll back to the conceptual initial state for this process in the M-vector.
                    if process_id in self.m_vector: del self.m_vector[process_id]
                else:
                    # Attempt to find the event at the specific earlier timestamp.
                    # This requires a mechanism to look up past events, which might be complex.
                    # For now, a simplified approach is to remove it, or if _find_event_at_timestamp
                    # is implemented, use that.
                    if self.successor_lookup: # Implies more sophisticated chain traversal might be possible.
                        target_event = self._find_event_at_timestamp(process_id, triggering_event_knowledge_ts)
                        if target_event:
                            self.m_vector[process_id] = target_event
                        else: # Could not find the exact event, so remove from M-vector to reflect uncertainty.
                            if process_id in self.m_vector: del self.m_vector[process_id]
                    else: # No way to find the specific past event, so remove.
                        if process_id in self.m_vector: del self.m_vector[process_id]

        # Additionally, handle scenarios where events in the M-vector might conflict
        # with the triggering_event if they involve the same processes but represent
        # different states (e.g., different timestamps for a shared process).
        self._remove_conflicting_shared_process_events(triggering_event)

    def _remove_conflicting_shared_process_events(self, triggering_event: Event) -> None:
        """
        Removes events from the M-vector if they share any process with the `triggering_event`
        but represent a different state (timestamp) for that shared process than the
        `triggering_event` itself implies for that shared process.

        This is important for consistency when multi-process events occur. For instance,
        if M-vector contains event `ev_ab` (for processes A,B) and `triggering_event` is `ev_bc`
        (for B,C), and `ev_ab`'s view of B is different from `ev_bc`'s view of B,
        then `ev_ab` might be inconsistent with the context of `ev_bc` and should be removed
        to allow `ev_bc` (or parts of it) to correctly seed/update the M-vector.

        Args:
            triggering_event: The event that might conflict with existing M-vector entries.
        """
        processes_to_remove_from_m_vector = [] # Store process IDs whose events in M-vector need removal.

        for m_proc_id, m_event in list(self.m_vector.items()): # Iterate over copy for safe modification.
            if m_proc_id in triggering_event.processes:
                # This m_proc_id is directly part of the triggering_event.
                # Its entry in m_vector will be (or has been) updated by triggering_event itself
                # in update_m_vector_with_event. No conflict removal needed here for m_proc_id.
                continue

            # Check if m_event (not directly associated with triggering_event's primary processes)
            # shares any *other* processes with triggering_event.
            shared_internal_processes = set(m_event.processes) & set(triggering_event.processes)

            if shared_internal_processes:
                # m_event and triggering_event share one or more processes.
                # Check for timestamp conflicts on these shared processes.
                for shared_proc in shared_internal_processes:
                    m_event_ts_for_shared_proc = m_event.vc.clock.get(shared_proc, 0)
                    triggering_event_ts_for_shared_proc = triggering_event.vc.clock.get(shared_proc, 0)

                    if m_event_ts_for_shared_proc != triggering_event_ts_for_shared_proc:
                        # Conflict: Both events involve `shared_proc` but at different timestamps.
                        # This means `m_event` represents an inconsistent state for `shared_proc`
                        # with respect to the `triggering_event`. `m_event` (associated with `m_proc_id`)
                        # should be removed from M-vector.
                        processes_to_remove_from_m_vector.append(m_proc_id)
                        logger.debug(f"M-vector: Removing event for process '{m_proc_id}' ({m_event.eid}) due to "
                                     f"shared process ('{shared_proc}') conflict with triggering event "
                                     f"{triggering_event.eid}. Timestamps: {m_event_ts_for_shared_proc} vs "
                                     f"{triggering_event_ts_for_shared_proc}.")
                        break # Found a conflict for m_event, no need to check other shared processes for it.

        for proc_id_to_remove in processes_to_remove_from_m_vector:
            if proc_id_to_remove in self.m_vector:
                del self.m_vector[proc_id_to_remove]

    def _find_event_at_timestamp(self, process_id: str, target_timestamp: int) -> Optional[Event]:
        """
        Attempts to find the event for `process_id` that corresponds to `target_timestamp`
        in its local vector clock component.

        This method would typically require traversing the process's event chain backwards
        from a known recent event (like the one currently in `m_vector[process_id]`).
        The current implementation is a placeholder. A full implementation depends on
        how event history or predecessor links are maintained.

        Args:
            process_id: The ID of the process.
            target_timestamp: The desired local timestamp for the event.

        Returns:
            The Event object if found, otherwise None.
        """
        if not self.successor_lookup: # Successor lookup might imply ability to go backwards or search.
            logger.debug(f"_find_event_at_timestamp: No successor_lookup, cannot find event for {process_id} at {target_timestamp}.")
            return None

        # If target_timestamp is 0, it implies the state before any events for this process,
        # which means no specific event from this process should be in the M-vector.
        if target_timestamp == 0:
            return None

        # Placeholder: A real implementation would need to access event history or
        # use the successor_lookup in reverse (if possible) or some other mechanism
        # to find an event by its process-local timestamp.
        # For now, this simplified version indicates it cannot find such a specific past event.
        logger.debug(f"_find_event_at_timestamp: Lookup for {process_id} at ts {target_timestamp} not fully implemented, returning None.")
        return None