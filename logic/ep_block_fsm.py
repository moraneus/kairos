# logic/ep_block_fsm.py

from dataclasses import dataclass, field
from typing import Optional, Set, Dict, List, Callable

from parser.ast_nodes import And, EP, Expr, Literal, Not
from model.frontier import Frontier
from model.event import Event
from model.initial_event import IOTA_LITERAL_NAME
from utils.logger import get_logger

from .disjunct_state import BlockState, DisjunctRuntime, partition
from .verdict import Verdict
from logic.gamma_analysis import analyze_gamma_mapping
from utils.fsm_visualizer import visualize_ep_block_fsm_state

logger = get_logger(__name__)


def _holds(expr: Expr, fr: Frontier) -> bool:
    """
    Evaluates if the given expression `expr` holds true on the specified frontier `fr`.
    (Implementation remains the same as your provided version)
    """
    if not fr.events: return False

    if isinstance(expr, Literal):
        if expr.name == IOTA_LITERAL_NAME:
            return any(ev.has(IOTA_LITERAL_NAME) for ev in fr.events.values())
        result = any(ev.has(expr.name) for ev in fr.events.values())
        logger.debug(f"_holds({expr.name}) on frontier {fr.id_short()} = {result}")
        return result

    if isinstance(expr, Not): return not _holds(expr.operand, fr)
    if isinstance(expr, And): return _holds(expr.left, fr) and _holds(expr.right, fr)
    if isinstance(expr, EP): return _holds(expr.operand, fr)
    raise TypeError(f"Unsupported expression type in _holds: {expr!r}")


@dataclass(slots=True)
class EPBlockFSM:
    """
    Finite State Machine (FSM) for monitoring a single EP-disjunct.
    (Docstring and attributes remain the same as your provided version)
    """
    ep: EP
    state: DisjunctRuntime
    _known_processes: Set[str] = field(default_factory=set)
    _successor_lookup: Optional[Callable[[Event, str], List[Event]]] = None
    _infrastructure_provided: bool = False

    @classmethod
    def from_ep(cls, ep: EP) -> "EPBlockFSM":
        """
        Creates an FSM instance from an EP Abstract Syntax Tree (AST) node.
        (Implementation remains the same)
        """
        p_formulas, m_formulas, n_formulas = partition(ep)
        return cls(
            ep=ep,
            state=DisjunctRuntime(
                p=[BlockState(f) for f in p_formulas],
                m=[BlockState(f) for f in m_formulas],
                n=[BlockState(f) for f in n_formulas],
            )
        )

    def seed_with_iota_update(self, initial_system_frontier: Frontier) -> None:
        """
        Processes the initial system frontier to establish the FSM's baseline state.
        (Implementation remains the same)
        """
        ds = self.state
        if not ds.p and ds.m and not ds.m_search_active:
            if any(not p.startswith("_") for p in self._known_processes):
                self._initialize_literal_m_search(None)

        self.update(initial_system_frontier)

        if not ds.p and not ds.m and ds.n:
            any_n_block_inner_ep_holds_on_init = any(
                _holds(n_block_state.formula, initial_system_frontier) for n_block_state in ds.n
            )
            if any_n_block_inner_ep_holds_on_init:
                ds.failure = True
                ds.success = False
            else:
                ds.success = True
                ds.failure = False

    def set_infrastructure(self, known_processes: Set[str],
                           successor_lookup: Optional[Callable[[Event, str], List[Event]]]) -> None:
        """
        Sets or updates the FSM's knowledge of system processes and the event successor lookup function.
        (Implementation remains the same)
        """
        old_known_procs_tuple = tuple(sorted(list(self._known_processes)))
        self._known_processes = known_processes.copy()
        new_known_procs_tuple = tuple(sorted(list(self._known_processes)))
        processes_have_changed = old_known_procs_tuple != new_known_procs_tuple

        self._successor_lookup = successor_lookup
        self._infrastructure_provided = successor_lookup is not None
        ds = self.state

        if ds.m and not (ds.success or ds.failure):
            if processes_have_changed or not ds.gamma_mapping:
                m_literal_exprs = [block.formula for block in ds.m]
                current_gamma = analyze_gamma_mapping(m_literal_exprs, self._known_processes)
                if ds.gamma_mapping != current_gamma:
                    ds.gamma_mapping = current_gamma
                    ds.relevant_processes = {
                        proc for proc, gamma_i in current_gamma.items() if len(gamma_i) > 0
                    }

            needs_m_init_or_reinit = False
            p_fr_for_init: Optional[Frontier] = None
            if not ds.p:
                if ds.relevant_processes and not ds.m_search_active:
                    needs_m_init_or_reinit = True
            elif ds.first_all_p_conjunctive_satisfaction_frontier is not None:
                if ds.relevant_processes and (not ds.m_search_active or processes_have_changed):
                    needs_m_init_or_reinit = True
                    p_fr_for_init = ds.first_all_p_conjunctive_satisfaction_frontier
            if needs_m_init_or_reinit:
                self._initialize_literal_m_search(p_fr_for_init)
            if ds.m_search_active and ds.m_vector:
                m_frontier_now = ds.check_m_satisfaction()
                if m_frontier_now is not None:
                    self._handle_literal_m_satisfaction(m_frontier_now)

        if not self._infrastructure_provided and ds.m:
            logger.warning(f"EPBlockFSM for {self.ep} is operating without full infrastructure "
                           f"(successor_lookup not provided). M-literal search may be limited or rely on updates.")

    def verdict(self) -> Verdict:
        """
        Returns the current verdict (TRUE, FALSE, or INCONCLUSIVE) of the FSM.
        (Implementation remains the same)
        """
        if self.state.success: return Verdict.TRUE
        if self.state.failure: return Verdict.FALSE
        return Verdict.INCONCLUSIVE

    def notify_new_event(self, event: Event) -> None:
        """
        Processes a new event, primarily for updating the procedural search for M-literals.
        (Implementation remains the same)
        """
        ds = self.state
        if ds.success or ds.failure or not ds.m: return
        if not self._infrastructure_provided:
            self._handle_m_without_infrastructure(event)
            return
        if not ds.m_search_active and not ds.p:
            if any(not p.startswith("_") for p in self._known_processes):
                self._initialize_literal_m_search(None)
        if ds.m_search_active:
            ds.update_m_vector_with_event(event)
            m_frontier = ds.check_m_satisfaction()
            if m_frontier is not None:
                self._handle_literal_m_satisfaction(m_frontier)

    def _handle_m_without_infrastructure(self, event: Event) -> None:
        """
        Simplified M-literal handling for scenarios where full infrastructure is not available.
        (Implementation remains the same)
        """
        ds = self.state
        if not hasattr(ds, '_seen_events'):
            ds._seen_events: Dict[str, Event] = {}
        for proc_id in event.processes:
            ds._seen_events[proc_id] = event
        if ds._seen_events:
            current_test_frontier_events = dict(ds._seen_events)
            current_test_frontier = Frontier(current_test_frontier_events)
            if all(_holds(m_block.formula, current_test_frontier) for m_block in ds.m):
                ds.m_satisfaction_frontier = current_test_frontier
                n_violation_prevents_success = False
                if ds.n:
                    for n_block_state in ds.n:
                        if n_block_state.satisfied_at:
                            if not (current_test_frontier < n_block_state.satisfied_at):
                                n_violation_prevents_success = True
                                break
                if not n_violation_prevents_success:
                    ds.success = True
                else:
                    ds.failure = True

    def _initialize_literal_m_search(self, p_frontier: Optional[Frontier]) -> None:
        """
        Initializes or re-initializes the parameters and state for searching M-literals.
        (Implementation remains the same)
        """
        ds = self.state
        meaningful_known_processes = {p for p in self._known_processes if not p.startswith("_")}
        is_m_block_only_iota = ds.m and all(
            isinstance(m_block.formula, Literal) and m_block.formula.name == IOTA_LITERAL_NAME
            for m_block in ds.m
        )
        if not meaningful_known_processes and not is_m_block_only_iota:
            ds.m_search_active = False
            ds.gamma_mapping.clear()
            ds.relevant_processes.clear()
            return
        m_literal_exprs = [block.formula for block in ds.m]
        gamma_mapping = analyze_gamma_mapping(m_literal_exprs, self._known_processes)
        ds.initialize_m_vector_search(gamma_mapping, p_frontier, self._successor_lookup)
        if not ds.relevant_processes and not is_m_block_only_iota:
            ds.m_search_active = False

    def _handle_literal_m_satisfaction(self, m_frontier: Frontier) -> None:
        """
        Handles the FSM state transition once all M-literals are satisfied at `m_frontier`.
        (Implementation remains the same)
        """
        ds = self.state
        if ds.success or ds.failure: return
        ds.m_satisfaction_frontier = m_frontier
        n_block_prevents_success = False
        if ds.n:
            for n_block_state in ds.n:
                if n_block_state.satisfied_at:
                    if not (m_frontier < n_block_state.satisfied_at):
                        n_block_prevents_success = True
                        break
        if not n_block_prevents_success:
            ds.success = True
        else:
            ds.failure = True
        ds.stop_m_search()

    def update(self, fr: Frontier) -> None:
        """
        Processes a new frontier `fr` to update the satisfaction status of P-blocks and N-blocks.
        (Implementation remains the same)
        """
        ds = self.state
        if ds.success or ds.failure: return
        for p_block_state in ds.p:
            if p_block_state.satisfied_at is None and _holds(p_block_state.formula, fr):
                p_block_state.satisfied_at = fr
        for n_block_state in ds.n:
            if n_block_state.satisfied_at is None and _holds(n_block_state.formula, fr):
                n_block_state.satisfied_at = fr
        all_p_blocks_satisfied_on_some_frontier = all(p_bs.satisfied_at for p_bs in ds.p)
        if ds.p and all_p_blocks_satisfied_on_some_frontier and ds.first_all_p_conjunctive_satisfaction_frontier is None:
            if all(p_bs.satisfied_at and p_bs.satisfied_at <= fr for p_bs in ds.p):
                ds.first_all_p_conjunctive_satisfaction_frontier = fr
                if ds.m:
                    if not ds.m_search_active:
                        self._initialize_literal_m_search(fr)
                    if ds.m_search_active and all(_holds(m_block.formula, fr) for m_block in ds.m):
                        self._handle_literal_m_satisfaction(fr)
                        if ds.success or ds.failure: return
        elif not ds.p and ds.m and not ds.m_search_active:
            if any(not p_name.startswith("_") for p_name in self._known_processes):
                self._initialize_literal_m_search(None)
                if ds.m_search_active and all(_holds(m_block.formula, fr) for m_block in ds.m):
                    self._handle_literal_m_satisfaction(fr)
                    if ds.success or ds.failure: return
        if ds.m and ds.m_search_active and not (ds.success or ds.failure) and not self._infrastructure_provided:
            p_conditions_for_m_met = (not ds.p) or \
                                     (ds.p and ds.first_all_p_conjunctive_satisfaction_frontier is not None)
            if p_conditions_for_m_met:
                causally_valid_m_frontier = True
                if ds.p and ds.first_all_p_conjunctive_satisfaction_frontier:
                    if not (ds.first_all_p_conjunctive_satisfaction_frontier <= fr):
                        causally_valid_m_frontier = False
                if causally_valid_m_frontier and all(_holds(m_block.formula, fr) for m_block in ds.m):
                    self._handle_literal_m_satisfaction(fr)
                    if ds.success or ds.failure: return
        if ds.success or ds.failure: return
        if not ds.m:
            n_block_violated_at_or_before_fr = any(
                nb_s.satisfied_at and nb_s.satisfied_at <= fr for nb_s in ds.n
            )
            if ds.p and not ds.n:
                if all_p_blocks_satisfied_on_some_frontier and ds.first_all_p_conjunctive_satisfaction_frontier:
                    ds.success = True
            elif ds.p and ds.n:
                if n_block_violated_at_or_before_fr:
                    ds.failure = True
                elif all_p_blocks_satisfied_on_some_frontier and ds.first_all_p_conjunctive_satisfaction_frontier:
                    ds.success = True
            elif not ds.p and ds.n:
                if n_block_violated_at_or_before_fr and not ds.success:
                    ds.failure = True
        else:
            n_block_inner_ep_true_on_current_fr = any(nb_s.satisfied_at == fr for nb_s in ds.n)
            if n_block_inner_ep_true_on_current_fr:
                is_pmn = ds.p and ds.m and ds.n
                is_mn = not ds.p and ds.m and ds.n
                should_fail_now = False
                if is_pmn:
                    if ds.first_all_p_conjunctive_satisfaction_frontier is None or ds.m_satisfaction_frontier is None:
                        should_fail_now = True
                elif is_mn:
                    if ds.m_satisfaction_frontier is None:
                        should_fail_now = True
                if should_fail_now:
                    ds.failure = True
                    ds.stop_m_search()

    def finalize_at_trace_end(self) -> None:
        """
        Sets the final verdict if the FSM is still inconclusive at the end of the observed trace.
        (Implementation remains the same)
        """
        ds = self.state
        if ds.success or ds.failure: return
        ds.stop_m_search()
        if ds.p and not all(p_block_state.satisfied_at for p_block_state in ds.p):
            ds.failure = True
        elif ds.m and ds.m_satisfaction_frontier is None:
            ds.failure = True
        else:
            ds.failure = True

    def get_debug_info(self) -> Dict:
        """
        Returns a dictionary containing debugging information about the FSM's current state.
        (Implementation remains the same)
        """
        ds = self.state
        return {
            'formula': str(self.ep),
            'verdict': self.verdict().name,
            'infrastructure_provided': self._infrastructure_provided,
            'blocks': {
                'p_count': len(ds.p),
                'm_count': len(ds.m),
                'n_count': len(ds.n)
            },
            'm_search_status': {
                'active': ds.m_search_active,
                'vector_size': len(ds.m_vector) if ds.m_vector else 0,
                'relevant_processes': list(ds.relevant_processes) if ds.relevant_processes else [],
                'satisfaction_frontier_id': str(
                    ds.m_satisfaction_frontier.id_short()) if ds.m_satisfaction_frontier else None
            },
            'p_satisfaction_status': {
                'all_satisfied': all(pst.satisfied_at for pst in ds.p) if ds.p else True,
                'conjunctive_frontier_id': str(ds.first_all_p_conjunctive_satisfaction_frontier.id_short())
                if ds.first_all_p_conjunctive_satisfaction_frontier else None
            },
            'n_block_violations': [
                {'formula_operand': str(nst.formula), 'violated_at_frontier_id': str(nst.satisfied_at.id_short())}
                for nst in ds.n if nst.satisfied_at
            ]
        }

    def visualize_state(self, base_filename: str, fmt: str = "png") -> None:
        """
        Generates a visualization of the FSM's current state by calling
        the external visualization utility.

        Args:
            base_filename: The base name for the output file.
            fmt: The output image format (e.g., "png", "svg").
        """
        visualize_ep_block_fsm_state(self, base_filename, fmt)
