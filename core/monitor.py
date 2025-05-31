# core/monitor.py
# This file is part of Kairos - A PBTL Runtime Verification
#
# Main PBTL monitor implementing the Section 4 algorithm

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional
from parser import parse_and_dlnf
from parser.ast_nodes import EP, Or, And, Not, Literal, Expr
from .event import Event, VectorClock
from .frontier import Frontier
from .verdict import Verdict
from utils.logger import get_logger


def _holds(expr: Expr, frontier: Frontier) -> bool:
    """Evaluate expression truth value on given frontier.

    Recursively evaluates Boolean and temporal expressions against the
    propositions available in the frontier state.

    Args:
        expr: Expression to evaluate
        frontier: Global state to evaluate against

    Returns:
        True if expression holds in the frontier
    """
    if isinstance(expr, Literal):
        if expr.name == "true":
            return True
        elif expr.name == "false":
            return False
        else:
            return frontier.has_prop(expr.name)

    elif isinstance(expr, Not):
        return not _holds(expr.operand, frontier)

    elif isinstance(expr, And):
        return _holds(expr.left, frontier) and _holds(expr.right, frontier)

    elif isinstance(expr, Or):
        return _holds(expr.left, frontier) or _holds(expr.right, frontier)

    elif isinstance(expr, EP):
        # EP semantics handled by monitor context
        return _holds(expr.operand, frontier)

    else:
        raise ValueError(f"Unknown expression type: {type(expr)}")


@dataclass
class EPDisjunct:
    """Tracking state for a single EP disjunct from DLNF formula.

    Implements the 7 cases from Table 1 in the algorithm, managing
    satisfaction states for positive blocks (P), minterms (M), and
    negative blocks (N).

    Attributes:
        ep_formula: Original EP formula
        p_blocks: Positive EP subformulas
        m_literals: Minterm components
        n_blocks: Negative EP subformulas
        p_satisfied_at: P-block satisfaction tracking
        n_satisfied_at: N-block satisfaction tracking
        m_vector: M-search state per process
        m_search_active: Whether M-search is active
        verdict: Current disjunct verdict
        success_frontier: Frontier where success occurred
    """

    ep_formula: EP
    p_blocks: List[EP] = field(default_factory=list)
    m_literals: List[Expr] = field(default_factory=list)
    n_blocks: List[EP] = field(default_factory=list)
    p_satisfied_at: Dict[int, Optional[Frontier]] = field(default_factory=dict)
    n_satisfied_at: Dict[int, Optional[Frontier]] = field(default_factory=dict)
    m_vector: Dict[str, Event] = field(default_factory=dict)
    m_search_active: bool = False
    verdict: Verdict = Verdict.UNKNOWN
    success_frontier: Optional[Frontier] = None

    def initialize_satisfaction_tracking(self):
        """Initialize satisfaction tracking after block population."""
        self.p_satisfied_at.clear()
        self.n_satisfied_at.clear()

        for i in range(len(self.p_blocks)):
            self.p_satisfied_at[i] = None
        for i in range(len(self.n_blocks)):
            self.n_satisfied_at[i] = None

    def case_type(self) -> str:
        """Determine which Table 1 case this disjunct represents.

        Returns:
            Case identifier (P, P+M, P+M+N, P+N, M+N, N, M)
        """
        has_p = len(self.p_blocks) > 0
        has_m = len(self.m_literals) > 0
        has_n = len(self.n_blocks) > 0

        if has_p and has_m and has_n:
            return "P+M+N"
        elif has_p and has_m and not has_n:
            return "P+M"
        elif has_p and not has_m and has_n:
            return "P+N"
        elif has_p and not has_m and not has_n:
            return "P"
        elif not has_p and has_m and has_n:
            return "M+N"
        elif not has_p and not has_m and has_n:
            return "N"
        elif not has_p and has_m and not has_n:
            return "M"
        else:
            return "EMPTY"


@dataclass
class PBTLMonitor:
    """Main PBTL monitor implementing the Section 4 algorithm.

    Parses formulas into DLNF, creates EP disjuncts, and tracks their
    satisfaction using causal delivery and frontier management.

    Attributes:
        formula_text: Original PBTL formula
        disjuncts: EP disjuncts from DLNF transformation
        seen_events: Causal delivery tracking
        event_buffer: Buffered events awaiting delivery
        current_frontiers: Active global states
        all_processes: System process set
        initial_frontier: Initial system state
        global_verdict: Combined verdict from all disjuncts
        verbose: Debug output control
    """

    formula_text: str
    disjuncts: List[EPDisjunct] = field(default_factory=list)
    seen_events: Dict[str, int] = field(default_factory=dict)
    event_buffer: List[Event] = field(default_factory=list)
    current_frontiers: Set[Frontier] = field(default_factory=set)
    all_processes: Set[str] = field(default_factory=set)
    initial_frontier: Optional[Frontier] = None
    global_verdict: Verdict = Verdict.UNKNOWN
    verbose: bool = False

    def __post_init__(self):
        """Parse formula and initialize EP disjuncts."""
        logger = get_logger()
        logger.debug(f"Initializing monitor for formula: {self.formula_text}")

        # Parse to DLNF
        dlnf_ast = parse_and_dlnf(self.formula_text)

        # Extract and create EP disjuncts
        ep_nodes = self._extract_ep_disjuncts(dlnf_ast)
        for ep_node in ep_nodes:
            disjunct = self._create_ep_disjunct(ep_node)
            self.disjuncts.append(disjunct)

        logger.debug(f"Created {len(self.disjuncts)} EP disjuncts")

    def _extract_ep_disjuncts(self, ast: Expr) -> List[EP]:
        """Extract all EP nodes from DLNF structure.

        Args:
            ast: DLNF AST (disjunction of EP nodes)

        Returns:
            List of EP nodes representing disjuncts
        """
        if isinstance(ast, EP):
            return [ast]
        elif isinstance(ast, Or):
            return self._extract_ep_disjuncts(ast.left) + self._extract_ep_disjuncts(
                ast.right
            )
        else:
            raise ValueError(f"Expected DLNF (Or of EP), got: {type(ast)}")

    def _create_ep_disjunct(self, ep_node: EP) -> EPDisjunct:
        """Create EPDisjunct by partitioning operand into P/M/N components.

        Args:
            ep_node: EP node to partition

        Returns:
            Configured EPDisjunct instance
        """
        disjunct = EPDisjunct(ep_formula=ep_node)
        conjuncts = self._flatten_and(ep_node.operand)

        # Partition conjuncts by type
        for conjunct in conjuncts:
            if isinstance(conjunct, EP):
                disjunct.p_blocks.append(conjunct)
            elif isinstance(conjunct, Not) and isinstance(conjunct.operand, EP):
                disjunct.n_blocks.append(conjunct.operand)
            else:
                disjunct.m_literals.append(conjunct)

        disjunct.initialize_satisfaction_tracking()
        return disjunct

    def _flatten_and(self, expr: Expr) -> List[Expr]:
        """Flatten nested And expressions into conjunct list.

        Args:
            expr: Expression to flatten

        Returns:
            List of conjunct expressions
        """
        if isinstance(expr, And):
            return self._flatten_and(expr.left) + self._flatten_and(expr.right)
        else:
            return [expr]

    def set_verbose(self, verbose: bool) -> None:
        """Configure verbose output mode.

        Args:
            verbose: Enable detailed logging
        """
        self.verbose = verbose

    def initialize_from_trace_processes(self, processes: List[str]) -> None:
        """Initialize monitor with system processes from trace."""
        logger = get_logger()
        self.all_processes = set(processes)

        if self.all_processes:
            logger.info(f"Initialized with processes: {sorted(self.all_processes)}")

        # Create initial frontier with iota event
        iota_event = Event(
            eid="iota",
            processes=frozenset(self.all_processes),
            vc=VectorClock({p: 0 for p in self.all_processes}),
            props=frozenset(["iota"]),
        )

        self.initial_frontier = Frontier({p: iota_event for p in self.all_processes})
        self.current_frontiers.add(self.initial_frontier)

        # Initialize M-search for applicable cases
        self._initialize_m_search()

        self._evaluate_initial_frontier()

    def _evaluate_initial_frontier(self) -> None:
        """Evaluate all disjuncts against the initial frontier."""
        logger = get_logger()
        logger.debug("Evaluating formula against initial frontier")

        for disjunct in self.disjuncts:
            if disjunct.verdict.is_conclusive():
                continue

            # Check all frontiers (should just be initial frontier at this point)
            for frontier in self.current_frontiers:
                self._update_disjunct_with_frontier(disjunct, frontier)

        self._update_global_verdict()

    def _initialize_m_search(self):
        """Initialize M-search for applicable disjuncts."""
        for disjunct in self.disjuncts:
            if disjunct.case_type() in ("M", "M+N") and not disjunct.m_search_active:
                self._init_m_search(disjunct)

    def print_header(self) -> None:
        """Print monitoring session header."""
        logger = get_logger()
        verdict_display = (
            "FALSE (Inconclusive)"
            if self.global_verdict == Verdict.UNKNOWN
            else str(self.global_verdict)
        )
        initial_frontier_str = (
            str(self.initial_frontier) if self.initial_frontier else None
        )
        logger.monitor_start(self.formula_text, verdict_display, initial_frontier_str)

    def process_event(self, event: Event) -> None:
        """Process new event using causal delivery.

        Args:
            event: Distributed system event to process
        """
        logger = get_logger()
        logger.debug(f"Processing event: {event.eid}")

        # Initialize system if needed
        if self.initial_frontier is None:
            self.all_processes.update(event.processes)
            self._initialize_system()

        # Buffer and attempt delivery
        self.event_buffer.append(event)
        self._try_deliver_events()

    def _initialize_system(self) -> None:
        """Initialize system state with iota frontier."""
        iota_event = Event(
            eid="iota",
            processes=frozenset(self.all_processes),
            vc=VectorClock({p: 0 for p in self.all_processes}),
            props=frozenset(["iota"]),
        )

        self.initial_frontier = Frontier({p: iota_event for p in self.all_processes})
        self.current_frontiers.add(self.initial_frontier)
        self._initialize_m_search()

    def _try_deliver_events(self) -> None:
        """Deliver causally ready events from buffer."""
        delivered_any = True
        while delivered_any:
            delivered_any = False
            for event in list(self.event_buffer):
                if self._is_deliverable(event):
                    self._deliver_event(event)
                    self.event_buffer.remove(event)
                    delivered_any = True

    def _is_deliverable(self, event: Event) -> bool:
        """Check if event satisfies causal delivery constraints.

        Args:
            event: Event to check for deliverability

        Returns:
            True if event can be delivered now
        """
        event_vc_dict = event.vc.clock_dict

        # Check participating processes have correct timestamps
        for proc in event.processes:
            expected_ts = self.seen_events.get(proc, 0) + 1
            actual_ts = event_vc_dict.get(proc, 0)
            if actual_ts != expected_ts:
                return False

        # Check no process has advanced beyond event's knowledge
        for proc, ts in event_vc_dict.items():
            if proc not in event.processes:
                if ts > self.seen_events.get(proc, 0):
                    return False

        return True

    def _deliver_event(self, event: Event) -> None:
        """Deliver event and update monitoring state.

        Args:
            event: Event ready for delivery
        """
        logger = get_logger()
        logger.debug(f"Delivering event: {event.eid}")

        # Update causal delivery state
        event_vc_dict = event.vc.clock_dict
        for proc in event.processes:
            self.seen_events[proc] = event_vc_dict[proc]

        # Generate new frontiers
        new_frontiers = set()
        for frontier in self.current_frontiers:
            new_frontier = frontier.extend_with_event(event)
            new_frontiers.add(new_frontier)

        self.current_frontiers = new_frontiers

        # Update all disjuncts
        self._update_disjuncts(event, new_frontiers)
        self._update_global_verdict()

        # Cleanup irrelevant events
        # self._cleanup_irrelevant_events()

        self._print_event_result(event, new_frontiers)

    def _cleanup_irrelevant_events(self) -> None:
        """Remove events that cannot contribute to future verdicts."""
        logger = get_logger()

        # Events to remove
        events_to_remove = set()

        for disjunct in self.disjuncts:
            if disjunct.verdict.is_conclusive():
                continue

            # For each M-vector in the disjunct
            for proc, event in disjunct.m_vector.items():
                # Check if this event can be superseded
                for frontier in self.current_frontiers:
                    frontier_dict = frontier.events_dict
                    if proc in frontier_dict:
                        newer_event = frontier_dict[proc]
                        # If newer event exists and event is older
                        if event.vc < newer_event.vc:
                            events_to_remove.add(event)

        # Remove from internal tracking (implementation would depend on data structures)
        if events_to_remove:
            logger.debug(f"Cleaned up {len(events_to_remove)} irrelevant events")

    def _update_disjuncts(self, event: Event, frontiers: Set[Frontier]) -> None:
        """Update all disjunct states with new frontiers.

        Args:
            event: Delivered event
            frontiers: New frontier set
        """
        for disjunct in self.disjuncts:
            if disjunct.verdict.is_conclusive():
                continue

            # Update M-vector if active
            if disjunct.m_search_active:
                self._update_m_vector(disjunct, event)

            # Check satisfaction on all new frontiers
            for frontier in frontiers:
                self._update_disjunct_with_frontier(disjunct, frontier)

    def _print_event_result(self, event: Event, frontiers: Set[Frontier]) -> None:
        """Print event processing result.

        Args:
            event: Processed event
            frontiers: Resulting frontier set
        """
        logger = get_logger()

        # Format event information
        procs = ",".join(sorted(event.processes))
        event_str = f"{event.eid}@{procs}:{event.vc}"

        # Format frontier set
        frontier_strs = [f"'{frontier}'" for frontier in sorted(frontiers, key=str)]
        frontiers_str = f"[{', '.join(frontier_strs)}]"

        # Format verdict
        verdict_str = (
            "FALSE (Inconclusive)"
            if self.global_verdict == Verdict.UNKNOWN
            else str(self.global_verdict)
        )

        logger.event_processed(event_str, frontiers_str, verdict_str)

    def _update_disjunct_with_frontier(
        self, disjunct: EPDisjunct, frontier: Frontier
    ) -> None:
        """Update disjunct satisfaction state with frontier.

        Args:
            disjunct: Disjunct to update
            frontier: New frontier to check
        """
        logger = get_logger()

        if disjunct.verdict.is_conclusive():
            return

        # Check P-block satisfaction
        self._check_p_block_satisfaction(disjunct, frontier)

        # Check N-block satisfaction
        self._check_n_block_satisfaction(disjunct, frontier)

        # Apply case-specific logic
        self._apply_case_logic(disjunct, frontier)

    def _check_p_block_satisfaction(
        self, disjunct: EPDisjunct, frontier: Frontier
    ) -> None:
        """Check and record P-block satisfaction.

        Args:
            disjunct: Disjunct to check
            frontier: Frontier to evaluate
        """
        logger = get_logger()

        for i in range(len(disjunct.p_blocks)):
            if disjunct.p_satisfied_at[i] is None:
                if _holds(disjunct.p_blocks[i], frontier):
                    minimal_frontier = self._create_minimal_p_frontier(
                        disjunct.p_blocks[i], frontier
                    )
                    disjunct.p_satisfied_at[i] = minimal_frontier
                    logger.p_block_satisfied(
                        i, str(disjunct.p_blocks[i]), str(minimal_frontier)
                    )

    def _check_n_block_satisfaction(
        self, disjunct: EPDisjunct, frontier: Frontier
    ) -> None:
        """Check and record N-block satisfaction.

        Args:
            disjunct: Disjunct to check
            frontier: Frontier to evaluate
        """
        logger = get_logger()

        for i in range(len(disjunct.n_blocks)):
            if disjunct.n_satisfied_at[i] is None:
                if _holds(disjunct.n_blocks[i], frontier):
                    minimal_frontier = self._create_minimal_n_frontier(
                        disjunct.n_blocks[i], frontier
                    )
                    disjunct.n_satisfied_at[i] = minimal_frontier
                    logger.n_block_satisfied(
                        i, str(disjunct.n_blocks[i]), str(minimal_frontier)
                    )

    def _create_minimal_p_frontier(
        self, p_block: EP, current_frontier: Frontier
    ) -> Frontier:
        """Create minimal frontier satisfying P-block.

        Args:
            p_block: P-block to satisfy
            current_frontier: Context frontier

        Returns:
            Minimal satisfying frontier
        """
        if isinstance(p_block.operand, Literal):
            prop_name = p_block.operand.name
            target_event = None
            min_timestamp = float("inf")

            # Find earliest event with proposition
            for proc_id, event in current_frontier.events:
                if event.has_prop(prop_name):
                    timestamp = event.vc.clock_dict.get(proc_id, 0)
                    if timestamp < min_timestamp:
                        min_timestamp = timestamp
                        target_event = event

            if target_event:
                # Find process for this event
                for proc_id, event in current_frontier.events:
                    if event == target_event:
                        return Frontier({proc_id: target_event})

        return current_frontier

    def _create_minimal_n_frontier(
        self, n_block: EP, current_frontier: Frontier
    ) -> Frontier:
        """Create minimal frontier satisfying N-block.

        Args:
            n_block: N-block to satisfy
            current_frontier: Context frontier

        Returns:
            Minimal satisfying frontier
        """
        if isinstance(n_block.operand, Literal):
            prop_name = n_block.operand.name
            target_event = None
            min_timestamp = float("inf")

            # Find earliest event with proposition
            for proc_id, event in current_frontier.events:
                if event.has_prop(prop_name):
                    timestamp = event.vc.clock_dict.get(proc_id, 0)
                    if timestamp < min_timestamp:
                        min_timestamp = timestamp
                        target_event = event

            if target_event:
                # Find process for this event
                for proc_id, event in current_frontier.events:
                    if event == target_event:
                        return Frontier({proc_id: target_event})

        return current_frontier

    def _apply_case_logic(self, disjunct: EPDisjunct, frontier: Frontier) -> None:
        """Apply case-specific logic from Table 1.

        Args:
            disjunct: Disjunct to evaluate
            frontier: Current frontier
        """
        case = disjunct.case_type()

        if case == "P":
            self._handle_p_only(disjunct)
        elif case == "P+M":
            self._handle_pm_case(disjunct, frontier)
        elif case == "P+M+N":
            self._handle_pmn_case(disjunct, frontier)
        elif case == "P+N":
            self._handle_pn_case(disjunct)
        elif case == "M+N":
            self._handle_mn_case(disjunct, frontier)
        elif case == "N":
            self._handle_n_only(disjunct)
        elif case == "M":
            self._handle_m_only(disjunct, frontier)

    def _handle_p_only(self, disjunct: EPDisjunct) -> None:
        """Handle Case 1: P only."""
        if all(
            disjunct.p_satisfied_at.get(i) is not None
            for i in range(len(disjunct.p_blocks))
        ):
            disjunct.verdict = Verdict.TRUE
            p_frontiers = [
                disjunct.p_satisfied_at[i] for i in range(len(disjunct.p_blocks))
            ]
            disjunct.success_frontier = max(
                p_frontiers, key=lambda f: sum(f.vc.clock_dict.values())
            )

    def _handle_pm_case(self, disjunct: EPDisjunct, frontier: Frontier) -> None:
        """Handle Case 2: P+M."""
        all_p_satisfied = all(
            disjunct.p_satisfied_at.get(i) is not None
            for i in range(len(disjunct.p_blocks))
        )

        if all_p_satisfied and not disjunct.m_search_active:
            self._init_m_search(disjunct)

        if disjunct.m_search_active and self._check_m_satisfaction(disjunct, frontier):
            disjunct.verdict = Verdict.TRUE
            disjunct.success_frontier = frontier

    def _handle_pmn_case(self, disjunct: EPDisjunct, frontier: Frontier) -> None:
        """Handle Case 3: P+M+N with N-constraint checking."""
        logger = get_logger()
        all_p_satisfied = all(
            disjunct.p_satisfied_at.get(i) is not None
            for i in range(len(disjunct.p_blocks))
        )

        logger.case_debug(
            "P+M+N",
            all_p_satisfied=all_p_satisfied,
            m_search_active=disjunct.m_search_active,
        )

        if all_p_satisfied and not disjunct.m_search_active:
            self._init_m_search(disjunct)
            logger.m_search_activated("P+M+N")

        # Early N-violation detection
        if all_p_satisfied:
            for i in range(len(disjunct.n_blocks)):
                n_frontier = disjunct.n_satisfied_at.get(i)
                if n_frontier is not None:
                    if len(self.all_processes) == 1 and n_frontier <= frontier:
                        logger.early_violation(
                            "P+M+N", "N ≤ current frontier in single-process case"
                        )
                        disjunct.verdict = Verdict.FALSE
                        return

        if disjunct.m_search_active and self._check_m_satisfaction(disjunct, frontier):
            # Create M-satisfaction frontier
            m_satisfaction_frontier = self._create_m_satisfaction_frontier(
                disjunct, frontier
            )

            # Check N constraints
            n_violation = False
            for i in range(len(disjunct.n_blocks)):
                n_frontier = disjunct.n_satisfied_at.get(i)
                if n_frontier is not None and n_frontier <= m_satisfaction_frontier:
                    logger.constraint_check(
                        i, str(n_frontier.vc), str(m_satisfaction_frontier.vc)
                    )
                    n_violation = True
                    break

            if not n_violation:
                disjunct.verdict = Verdict.TRUE
                disjunct.success_frontier = m_satisfaction_frontier
                logger.case_success("P+M+N", str(m_satisfaction_frontier))
            else:
                disjunct.verdict = Verdict.FALSE
                logger.case_failure("P+M+N", "N constraint violation")

    def _handle_pn_case(self, disjunct: EPDisjunct) -> None:
        """Handle Case 4: P+N with N-constraint checking."""
        logger = get_logger()
        all_p_satisfied = all(
            disjunct.p_satisfied_at.get(i) is not None
            for i in range(len(disjunct.p_blocks))
        )

        # Early violation detection for single-process systems
        if not all_p_satisfied and len(self.all_processes) == 1:
            for i in range(len(disjunct.n_blocks)):
                if disjunct.n_satisfied_at.get(i) is not None:
                    logger.early_violation(
                        "P+N", "N satisfied before P in single-process case"
                    )
                    disjunct.verdict = Verdict.FALSE
                    return

        if all_p_satisfied:
            # Calculate P-conjunction frontier
            p_frontiers = [
                disjunct.p_satisfied_at[i] for i in range(len(disjunct.p_blocks))
            ]
            p_conjunction_frontier = self._calculate_frontier_lub(p_frontiers)

            # Check N constraints
            n_violation = False
            for i in range(len(disjunct.n_blocks)):
                n_frontier = disjunct.n_satisfied_at.get(i)
                if n_frontier is not None:
                    logger.constraint_check(
                        i, str(n_frontier.vc), str(p_conjunction_frontier.vc)
                    )
                    if n_frontier <= p_conjunction_frontier:
                        n_violation = True
                        break

            if not n_violation:
                disjunct.verdict = Verdict.TRUE
                disjunct.success_frontier = p_conjunction_frontier
                logger.case_success("P+N")
            else:
                disjunct.verdict = Verdict.FALSE
                logger.case_failure("P+N", "N constraint violation")

    def _handle_mn_case(self, disjunct: EPDisjunct, frontier: Frontier) -> None:
        """Handle Case 5: M+N."""
        if not disjunct.m_search_active:
            self._init_m_search(disjunct)

        if self._check_m_satisfaction(disjunct, frontier):
            # Check N constraints
            n_violation = any(
                disjunct.n_satisfied_at.get(i) is not None
                and disjunct.n_satisfied_at[i] <= frontier
                for i in range(len(disjunct.n_blocks))
            )

            if not n_violation:
                disjunct.verdict = Verdict.TRUE
                disjunct.success_frontier = frontier
            else:
                disjunct.verdict = Verdict.FALSE

    def _handle_n_only(self, disjunct: EPDisjunct) -> None:
        """Handle Case 6: N only."""
        for i in range(len(disjunct.n_blocks)):
            if disjunct.n_satisfied_at.get(i) is not None:
                disjunct.verdict = Verdict.FALSE
                return

    def _handle_m_only(self, disjunct: EPDisjunct, frontier: Frontier) -> None:
        """Handle Case 7: M only."""
        if not disjunct.m_search_active:
            self._init_m_search(disjunct)

        if self._check_m_satisfaction(disjunct, frontier):
            disjunct.verdict = Verdict.TRUE
            disjunct.success_frontier = frontier

    def _create_m_satisfaction_frontier(
        self, disjunct: EPDisjunct, current_frontier: Frontier
    ) -> Frontier:
        """Create frontier for M-satisfaction excluding unnecessary N-block events.

        Args:
            disjunct: Disjunct context
            current_frontier: Current system frontier

        Returns:
            Optimized M-satisfaction frontier
        """
        logger = get_logger()
        logger.debug(f"Creating M-satisfaction frontier from: {current_frontier}")

        m_events = {}
        for proc, event in current_frontier.events:
            event_needed_for_m = self._event_needed_for_m_satisfaction(
                event, disjunct, current_frontier
            )
            event_satisfies_n = self._event_satisfies_n_block(event, disjunct)

            if event_needed_for_m or not event_satisfies_n:
                m_events[proc] = event
            else:
                alternative = self._find_alternative_event_for_m(proc, event, disjunct)
                m_events[proc] = alternative

        return Frontier(m_events)

    def _event_needed_for_m_satisfaction(
        self, event: Event, disjunct: EPDisjunct, current_frontier: Frontier
    ) -> bool:
        """Check if event is causally necessary for M-satisfaction.

        Args:
            event: Event to check
            disjunct: Disjunct context
            current_frontier: Current frontier

        Returns:
            True if event is needed for M-satisfaction
        """
        # Direct M-literal satisfaction
        for m_literal in disjunct.m_literals:
            if _holds(m_literal, Frontier({list(event.processes)[0]: event})):
                return True

        # Causal dependency check
        for proc, other_event in current_frontier.events:
            if other_event != event:
                other_satisfies_m = any(
                    _holds(m_lit, Frontier({proc: other_event}))
                    for m_lit in disjunct.m_literals
                )
                if other_satisfies_m and event.vc <= other_event.vc:
                    if any(
                        proc_id in event.processes for proc_id in other_event.processes
                    ):
                        return True

        return False

    def _event_satisfies_n_block(self, event: Event, disjunct: EPDisjunct) -> bool:
        """Check if event satisfies any N-block.

        Args:
            event: Event to check
            disjunct: Disjunct context

        Returns:
            True if event satisfies an N-block
        """
        for n_block in disjunct.n_blocks:
            if _holds(n_block, Frontier({list(event.processes)[0]: event})):
                return True
        return False

    def _find_alternative_event_for_m(
        self, proc: str, current_event: Event, disjunct: EPDisjunct
    ) -> Event:
        """Find alternative event that doesn't satisfy N-blocks.

        Args:
            proc: Process identifier
            current_event: Current event for process
            disjunct: Disjunct context

        Returns:
            Alternative event or current event if none found
        """
        if self.initial_frontier:
            initial_event = self.initial_frontier.events_dict.get(proc)
            if initial_event and not self._event_satisfies_n_block(
                initial_event, disjunct
            ):
                return initial_event
        return current_event

    def _calculate_frontier_lub(self, frontiers: List[Frontier]) -> Frontier:
        """Calculate least upper bound of multiple frontiers.

        Creates a frontier where each process has the latest event
        from all input frontiers.

        Args:
            frontiers: List of frontiers to combine

        Returns:
            LUB frontier
        """
        if not frontiers:
            return None
        if len(frontiers) == 1:
            return frontiers[0]

        # Collect all processes
        all_processes = set()
        for frontier in frontiers:
            all_processes.update(proc for proc, _ in frontier.events)

        # Find maximum timestamp event per process
        lub_events = {}
        for proc in all_processes:
            max_event = None
            max_ts = -1

            for frontier in frontiers:
                frontier_dict = frontier.events_dict
                if proc in frontier_dict:
                    event = frontier_dict[proc]
                    event_ts = event.vc.clock_dict.get(proc, 0)
                    if event_ts > max_ts:
                        max_ts = event_ts
                        max_event = event

            if max_event:
                lub_events[proc] = max_event

        return Frontier(lub_events)

    def _init_m_search(self, disjunct: EPDisjunct) -> None:
        """Initialize M-vector search for disjunct.

        Args:
            disjunct: Disjunct to initialize
        """
        logger = get_logger()
        disjunct.m_search_active = True
        logger.debug(f"Initialized M-search for {disjunct.case_type()} case")

        # Initialize M-vector with current latest events
        for proc in self.all_processes:
            if proc in self.seen_events:
                events_for_proc = [
                    e
                    for f in self.current_frontiers
                    for _, e in f.events
                    if proc in e.processes
                ]
                if events_for_proc:
                    disjunct.m_vector[proc] = max(
                        events_for_proc, key=lambda e: e.vc.clock_dict.get(proc, 0)
                    )

    def _update_m_vector(self, disjunct: EPDisjunct, event: Event) -> None:
        """Update M-vector with new event.

        Args:
            disjunct: Disjunct to update
            event: New event
        """
        for proc in event.processes:
            disjunct.m_vector[proc] = event

    def _check_m_satisfaction(self, disjunct: EPDisjunct, frontier: Frontier) -> bool:
        """Check if M-literals are satisfied at frontier.

        Args:
            disjunct: Disjunct to check
            frontier: Frontier to evaluate

        Returns:
            True if all M-literals are satisfied
        """
        return all(_holds(m_literal, frontier) for m_literal in disjunct.m_literals)

    def _update_global_verdict(self) -> None:
        """Update global verdict based on disjunct verdicts."""
        verdicts = [d.verdict for d in self.disjuncts]

        if any(v == Verdict.TRUE for v in verdicts):
            self.global_verdict = Verdict.TRUE
        elif all(v == Verdict.FALSE for v in verdicts):
            self.global_verdict = Verdict.FALSE
        else:
            self.global_verdict = Verdict.UNKNOWN

    def finalize(self) -> Verdict:
        """Finalize monitoring by setting remaining UNKNOWN verdicts to FALSE.

        Returns:
            Final global verdict
        """
        logger = get_logger()
        logger.debug("Finalizing monitoring session")

        for disjunct in self.disjuncts:
            if disjunct.verdict == Verdict.UNKNOWN:
                case_type = disjunct.case_type()

                # Special handling for M-cases
                if (
                    case_type in ("P+M", "P+M+N", "M", "M+N")
                    and disjunct.m_search_active
                ):
                    m_ever_satisfied = any(
                        self._check_m_satisfaction(disjunct, f)
                        for f in self.current_frontiers
                    )
                    if not m_ever_satisfied:
                        disjunct.verdict = Verdict.FALSE
                        continue

                # Default: UNKNOWN becomes FALSE
                disjunct.verdict = Verdict.FALSE

        self._update_global_verdict()
        logger.debug(f"Final verdict: {self.global_verdict}")
        return self.global_verdict

    def print_final_verdict(self) -> None:
        """Print final monitoring verdict."""
        logger = get_logger()
        verdict_display = (
            "FALSE (Inconclusive)"
            if self.global_verdict == Verdict.UNKNOWN
            else str(self.global_verdict)
        )
        logger.final_verdict(verdict_display)

    def is_conclusive(self) -> bool:
        """Check if global verdict is conclusive.

        Returns:
            True if verdict is TRUE or FALSE (not UNKNOWN)
        """
        return self.global_verdict.is_conclusive()
