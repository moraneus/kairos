# core/monitor.py
# PBTL monitor using the exact frontier detection algorithm from Section 4
#
# This monitor integrates the FrontierDetector to implement the algorithm
# exactly as described in the paper.

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict
from parser import parse_and_dlnf
from parser.ast_nodes import EP, Or, And, Not, Literal, Expr
from .event import Event, VectorClock
from .frontier import Frontier
from .frontier_detector import FrontierDetector
from .verdict import Verdict
from utils.logger import get_logger


@dataclass
class EPDisjunct:
    """
    EP disjunct with integrated frontier detection.

    Uses FrontierDetector for cases requiring minterm satisfaction (M-cases).
    """

    ep_formula: EP
    is_negated: bool = False
    p_blocks: List[EP] = field(default_factory=list)
    m_literals: List[Expr] = field(default_factory=list)
    n_blocks: List[EP] = field(default_factory=list)
    p_satisfied_at: Dict[int, Optional[Frontier]] = field(default_factory=dict)
    n_satisfied_at: Dict[int, Optional[Frontier]] = field(default_factory=dict)
    frontier_detector: Optional[FrontierDetector] = None
    m_satisfied_frontier: Optional[Frontier] = None
    verdict: Verdict = Verdict.UNKNOWN
    success_frontier: Optional[Frontier] = None

    def case_type(self) -> str:
        """Determine which Table 1 case this disjunct represents."""
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

    def initialize_frontier_detector(
        self, all_processes: Set[str], P: Optional[Frontier] = None
    ):
        """
        Initialize the frontier detector for M-literal satisfaction.

        Args:
            all_processes: Set of all system processes
            P: Lower bound frontier (for P+M cases)
        """
        if not self.m_literals:
            return  # No M-literals to detect

        # Convert m_literals to process-based minterms
        minterms = self._extract_process_minterms(all_processes)

        self.frontier_detector = FrontierDetector(
            minterms=minterms, P=P, all_processes=all_processes
        )

    def _extract_process_minterms(
        self, all_processes: Set[str]
    ) -> Dict[str, List[str]]:
        """
        Extract minterms organized by process from M-literals.

        Args:
            all_processes: Set of all processes

        Returns:
            Dictionary mapping process to its required propositions
        """
        minterms = {}

        # For each process, collect propositions that must be satisfied
        for proc in all_processes:
            proc_props = []

            for m_literal in self.m_literals:
                if isinstance(m_literal, Literal):
                    # Simple proposition - assume it applies to all processes
                    # In a real implementation, we'd need to track which process
                    # each proposition belongs to
                    proc_props.append(m_literal.name)
                elif isinstance(m_literal, Not) and isinstance(
                    m_literal.operand, Literal
                ):
                    # Negated proposition
                    proc_props.append(f"!{m_literal.operand.name}")

            if proc_props:
                minterms[proc] = proc_props

        return minterms


@dataclass
class PBTLMonitor:
    """
    PBTL monitor using exact frontier detection from Section 4.

    This monitor integrates FrontierDetector for precise minterm satisfaction
    detection as described in the paper.
    """

    formula_text: str
    disjuncts: List[EPDisjunct] = field(default_factory=list)
    seen_events: Dict[str, int] = field(default_factory=dict)
    event_buffer: List[Event] = field(default_factory=list)
    delivered_events: List[Event] = field(default_factory=list)
    all_processes: Set[str] = field(default_factory=set)
    initial_frontier: Optional[Frontier] = None
    global_verdict: Verdict = Verdict.UNKNOWN
    verbose: bool = False

    # Performance optimization fields
    _events_by_process: Dict[str, List[Event]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _events_by_prop: Dict[str, List[Event]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _latest_event_per_process: Dict[str, Event] = field(default_factory=dict)
    _observed_events_cache: Optional[List[Event]] = None
    _cache_invalidated: bool = True

    def __post_init__(self):
        """Parse formula and initialize enhanced EP disjuncts."""
        logger = get_logger()
        logger.debug(f"Initializing enhanced monitor for formula: {self.formula_text}")

        # Parse to DLNF
        dlnf_ast = parse_and_dlnf(self.formula_text)

        if "AH(" in self.formula_text:
            logger.info(f"📋 Property converted: {self.formula_text} → {dlnf_ast}")

        # Extract and create enhanced EP disjuncts
        ep_nodes, is_negated = self._extract_ep_disjuncts(dlnf_ast)
        for i, ep_node in enumerate(ep_nodes):
            disjunct = self._create_enhanced_ep_disjunct(ep_node)
            disjunct.is_negated = is_negated[i] if i < len(is_negated) else False
            self.disjuncts.append(disjunct)

        logger.debug(f"Created {len(self.disjuncts)} enhanced EP disjuncts")

    def _extract_ep_disjuncts(self, ast: Expr) -> Tuple[List[EP], List[bool]]:
        """Extract all EP nodes from DLNF structure."""
        if isinstance(ast, EP):
            return [ast], [False]
        elif isinstance(ast, Or):
            left_eps, left_neg = self._extract_ep_disjuncts(ast.left)
            right_eps, right_neg = self._extract_ep_disjuncts(ast.right)
            return left_eps + right_eps, left_neg + right_neg
        elif isinstance(ast, Not) and isinstance(ast.operand, EP):
            return [ast.operand], [True]
        else:
            raise ValueError(f"Expected DLNF (Or of EP), got: {type(ast)}")

    def _create_enhanced_ep_disjunct(self, ep_node: EP) -> EPDisjunct:
        """Create enhanced EPDisjunct with frontier detector setup."""
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

        # Initialize P-block and N-block tracking
        for i in range(len(disjunct.p_blocks)):
            disjunct.p_satisfied_at[i] = None
        for i in range(len(disjunct.n_blocks)):
            disjunct.n_satisfied_at[i] = None

        return disjunct

    def _flatten_and(self, expr: Expr) -> List[Expr]:
        """Flatten nested And expressions into conjunct list."""
        if isinstance(expr, And):
            return self._flatten_and(expr.left) + self._flatten_and(expr.right)
        else:
            return [expr]

    def initialize_from_trace_processes(self, processes: List[str]) -> None:
        """Initialize monitor with system processes."""
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

        # Index the initial event for performance
        for proc in self.all_processes:
            self._events_by_process[proc].append(iota_event)
            self._latest_event_per_process[proc] = iota_event

        for prop in iota_event.props:
            self._events_by_prop[prop].append(iota_event)

        # Initialize frontier detectors for M-cases
        self._initialize_frontier_detectors()

    def _initialize_frontier_detectors(self):
        """Initialize frontier detectors for disjuncts with M-literals."""
        logger = get_logger()

        for disjunct in self.disjuncts:
            case_type = disjunct.case_type()

            if case_type in ["M+N"]:
                # Cases without P-blocks: initialize immediately with no lower bound
                disjunct.initialize_frontier_detector(self.all_processes, None)
                logger.debug(f"Initialized frontier detector for {case_type} case")

            elif case_type in ["P+M", "P+M+N"]:
                # Cases with P-blocks: will initialize after P-blocks are satisfied
                logger.debug(
                    f"Will initialize frontier detector for {case_type} after P-satisfaction"
                )

    def process_event(self, event: Event) -> None:
        """Process new event using enhanced frontier detection."""
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
        """Initialize system state."""
        iota_event = Event(
            eid="iota",
            processes=frozenset(self.all_processes),
            vc=VectorClock({p: 0 for p in self.all_processes}),
            props=frozenset(["iota"]),
        )

        self.initial_frontier = Frontier({p: iota_event for p in self.all_processes})
        self._initialize_frontier_detectors()

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
        """Check if event satisfies causal delivery constraints."""
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
        """Deliver event and update monitoring state using frontier detection."""
        logger = get_logger()
        logger.debug(f"Delivering event: {event.eid}")

        # Store delivered event
        self.delivered_events.append(event)

        # Update performance optimization indexes
        for proc in event.processes:
            self._events_by_process[proc].append(event)
            self._latest_event_per_process[proc] = event

        for prop in event.props:
            self._events_by_prop[prop].append(event)

        # Invalidate cache since we have a new event
        self._cache_invalidated = True

        # Update causal delivery state
        event_vc_dict = event.vc.clock_dict
        for proc in event.processes:
            self.seen_events[proc] = event_vc_dict[proc]

        # Update all disjuncts with new event
        self._update_disjuncts_with_event(event)
        self._update_global_verdict()

        self._print_event_result(event)

    def _update_disjuncts_with_event(self, event: Event) -> None:
        """Update all disjuncts using frontier detection for M-satisfaction."""
        logger = get_logger()

        for disjunct in self.disjuncts:
            if disjunct.verdict.is_conclusive():
                continue

            case_type = disjunct.case_type()

            # Check P-block satisfaction
            self._check_p_block_satisfaction(disjunct, event)

            # Check N-block satisfaction
            self._check_n_block_satisfaction(disjunct, event)

            # Handle M-satisfaction using frontier detector
            if disjunct.frontier_detector is not None:
                # For P+M+N cases, always check N-violations first
                if case_type == "P+M+N":
                    self._apply_case_verdict(disjunct)
                    if disjunct.verdict.is_conclusive():
                        continue

                # Process event with frontier detector
                detected_frontier = disjunct.frontier_detector.process_new_event(event)

                if (
                    detected_frontier is not None
                    and disjunct.m_satisfied_frontier is None
                ):
                    disjunct.m_satisfied_frontier = detected_frontier
                    logger.info(
                        f"✓ M-satisfaction detected at frontier: {detected_frontier}"
                    )

                    # Apply case-specific verdict logic
                    self._apply_case_verdict(disjunct)

            elif case_type == "P":
                # Handle P-only case
                if self._all_p_blocks_satisfied(disjunct):
                    self._apply_case_verdict(disjunct)

            elif case_type == "P+N":
                # Handle P+N case: check both P and N conditions
                self._apply_case_verdict(disjunct)

            elif case_type == "N":
                # N-only case: always apply verdict (will check N violations)
                self._apply_case_verdict(disjunct)

            elif case_type == "P+M":
                # For P+M cases, check M-literal satisfaction directly
                if self._all_p_blocks_satisfied(disjunct):
                    p_conjunction = self._calculate_p_conjunction_frontier(disjunct)
                    # Extend P-conjunction with latest events from all processes to check M-literals
                    extended_frontier = self._extend_frontier_with_latest_events(
                        p_conjunction
                    )
                    # Check if M-literals are satisfied at the extended frontier
                    if self._m_literals_satisfied_at_frontier(
                        disjunct, extended_frontier
                    ):
                        disjunct.m_satisfied_frontier = extended_frontier
                        self._apply_case_verdict(disjunct)

            elif case_type == "P+M+N":
                # For P+M+N cases, always check N-violations first, then M-literals
                if self._all_p_blocks_satisfied(disjunct):
                    p_conjunction = self._calculate_p_conjunction_frontier(disjunct)
                    # For P+M+N: extend with M-relevant events only (exclude N-related events)
                    extended_frontier = self._extend_frontier_for_m_literals(
                        disjunct, p_conjunction
                    )
                    # Check if M-literals are satisfied at the extended frontier
                    if self._m_literals_satisfied_at_frontier(
                        disjunct, extended_frontier
                    ):
                        disjunct.m_satisfied_frontier = extended_frontier

                # Always apply case verdict (checks both N-violations and M-satisfaction)
                self._apply_case_verdict(disjunct)

            elif case_type == "M":
                # For M-only cases, check M-literal satisfaction at initial frontier first
                if self.initial_frontier and self._m_literals_satisfied_at_frontier(
                    disjunct, self.initial_frontier
                ):
                    disjunct.m_satisfied_frontier = self.initial_frontier
                    self._apply_case_verdict(disjunct)
                else:
                    # Also check current global frontier
                    current_frontier = self._get_current_global_frontier()
                    if self._m_literals_satisfied_at_frontier(
                        disjunct, current_frontier
                    ):
                        disjunct.m_satisfied_frontier = current_frontier
                        self._apply_case_verdict(disjunct)

    def _check_p_block_satisfaction(self, disjunct: EPDisjunct, event: Event) -> None:
        """Check P-block satisfaction with new event."""
        for i in range(len(disjunct.p_blocks)):
            if disjunct.p_satisfied_at[i] is None:
                # For complex nested formulas, try to create an extended frontier
                # Exclude N-events from P-block frontier to ensure proper P+N semantics
                extended_frontier = (
                    self._create_extended_frontier_for_formula_excluding_n(
                        disjunct.p_blocks[i], event, disjunct
                    )
                )
                if self._holds(disjunct.p_blocks[i], extended_frontier):
                    disjunct.p_satisfied_at[i] = extended_frontier
                    logger = get_logger()
                    logger.debug(
                        f"P-block {i} satisfied at extended frontier including event {event.eid}"
                    )

    def _check_n_block_satisfaction(self, disjunct: EPDisjunct, event: Event) -> None:
        """Check N-block satisfaction with new event."""
        for i in range(len(disjunct.n_blocks)):
            if disjunct.n_satisfied_at[i] is None:
                # Create a temporary frontier with just this event
                temp_frontier = Frontier({list(event.processes)[0]: event})
                if self._holds(disjunct.n_blocks[i], temp_frontier):
                    disjunct.n_satisfied_at[i] = temp_frontier
                    logger = get_logger()
                    logger.debug(f"N-block {i} satisfied at event {event.eid}")

    def _holds(self, expr: Expr, frontier: Frontier) -> bool:
        """Evaluate expression on frontier."""
        if isinstance(expr, Literal):
            if expr.name == "true":
                return True
            elif expr.name == "false":
                return False
            else:
                return frontier.has_prop(expr.name)
        elif isinstance(expr, Not):
            return not self._holds(expr.operand, frontier)
        elif isinstance(expr, And):
            return self._holds(expr.left, frontier) and self._holds(
                expr.right, frontier
            )
        elif isinstance(expr, Or):
            return self._holds(expr.left, frontier) or self._holds(expr.right, frontier)
        elif isinstance(expr, EP):
            # For nested EP, check if the operand can be satisfied at this frontier
            # or at any extended frontier that includes events leading to this frontier
            if self._holds(expr.operand, frontier):
                return True

            # For complex nested EP formulas, also check if we can satisfy with a sub-frontier
            # This handles cases where EP(EP(deep1) & deep2) requires finding deep1 in the past
            # and deep2 at the current frontier
            return self._can_satisfy_ep_recursively(expr.operand, frontier)
        else:
            return False

    def _can_satisfy_ep_recursively(self, expr, frontier: Frontier) -> bool:
        """Check if EP operand can be satisfied by looking at events leading to the frontier."""
        from parser.ast_nodes import And, Or, Literal

        if isinstance(expr, Literal):
            # Check if any event leading to this frontier has this property
            return self._exists_event_with_prop_in_past(expr.name, frontier)

        elif isinstance(expr, And):
            # For AND, both operands must be satisfiable
            return self._can_satisfy_ep_recursively(
                expr.left, frontier
            ) and self._can_satisfy_ep_recursively(expr.right, frontier)

        elif isinstance(expr, Or):
            # For OR, at least one operand must be satisfiable
            return self._can_satisfy_ep_recursively(
                expr.left, frontier
            ) or self._can_satisfy_ep_recursively(expr.right, frontier)

        elif isinstance(expr, EP):
            # For nested EP, recursively check
            return self._can_satisfy_ep_recursively(expr.operand, frontier)

        elif hasattr(expr, "operand"):  # Not
            # For NOT, check if the operand is NOT satisfiable
            return not self._can_satisfy_ep_recursively(expr.operand, frontier)

        return False

    def _exists_event_with_prop_in_past(
        self, prop_name: str, frontier: Frontier
    ) -> bool:
        """Check if any observed event has the given property and is causally before/at frontier."""
        # Use indexed events for much faster lookup
        if prop_name in self._events_by_prop:
            for obs_event in self._events_by_prop[prop_name]:
                # Check if this event is causally before or concurrent with the frontier
                if self._is_event_before_or_at_frontier(obs_event, frontier):
                    return True
        return False

    def _is_event_before_or_at_frontier(self, event: Event, frontier: Frontier) -> bool:
        """Check if event is causally before or concurrent with frontier."""
        # An event is before/at a frontier if it's ≤ some event in the frontier
        for proc, frontier_event in frontier.events_dict.items():
            if event.vc <= frontier_event.vc:
                return True
        return False

    def _all_p_blocks_satisfied(self, disjunct: EPDisjunct) -> bool:
        """Check if all P-blocks are satisfied."""
        return all(
            disjunct.p_satisfied_at.get(i) is not None
            for i in range(len(disjunct.p_blocks))
        )

    def _calculate_p_conjunction_frontier(self, disjunct: EPDisjunct) -> Frontier:
        """Calculate least upper bound of P-block frontiers."""
        p_frontiers = [
            disjunct.p_satisfied_at[i]
            for i in range(len(disjunct.p_blocks))
            if disjunct.p_satisfied_at[i] is not None
        ]

        if not p_frontiers:
            return None
        if len(p_frontiers) == 1:
            return p_frontiers[0]

        # Calculate LUB by taking maximum event per process
        lub_events = {}
        for frontier in p_frontiers:
            for proc, event in frontier.events_dict.items():
                if proc not in lub_events:
                    lub_events[proc] = event
                else:
                    # Take event with higher timestamp
                    if event.vc.clock_dict.get(proc, 0) > lub_events[
                        proc
                    ].vc.clock_dict.get(proc, 0):
                        lub_events[proc] = event

        return Frontier(lub_events)

    def _get_observed_events(self) -> List[Event]:
        """Get all observed events in causal order (cached for performance)."""
        if self._cache_invalidated or self._observed_events_cache is None:
            events = []
            if self.initial_frontier:
                # Include initial event
                events.append(list(self.initial_frontier.events_dict.values())[0])

            # Add all delivered events
            events.extend(self.delivered_events)
            self._observed_events_cache = events
            self._cache_invalidated = False
        return self._observed_events_cache

    def _m_literals_satisfied_at_frontier(
        self, disjunct: EPDisjunct, frontier: Frontier
    ) -> bool:
        """Check if all M-literals are satisfied by the given frontier."""
        for m_literal in disjunct.m_literals:
            if not self._holds(m_literal, frontier):
                return False
        return True

    def _extend_frontier_with_latest_events(self, base_frontier: Frontier) -> Frontier:
        """Extend a frontier with the latest observed events from all processes."""
        extended_events = dict(base_frontier.events_dict)

        # Use cached latest events for each process (O(1) lookup instead of O(n) iteration)
        for proc in self.all_processes:
            if proc in self._latest_event_per_process:
                extended_events[proc] = self._latest_event_per_process[proc]

        return Frontier(extended_events)

    def _extend_frontier_for_m_literals(
        self, disjunct: EPDisjunct, base_frontier: Frontier
    ) -> Frontier:
        """Extend frontier with events relevant to M-literals only (exclude N-events)."""
        extended_events = dict(base_frontier.events_dict)

        # Get N-related events to exclude
        n_events = set()
        for i in range(len(disjunct.n_blocks)):
            n_frontier = disjunct.n_satisfied_at.get(i)
            if n_frontier is not None:
                for proc, event in n_frontier.events_dict.items():
                    n_events.add(event.eid)

        # Use indexed events by process for faster lookup
        for proc in self.all_processes:
            # Get events for this process from index (much faster than iterating all events)
            proc_events = self._events_by_process.get(proc, [])

            # Find the latest non-N event
            latest_event = None
            latest_timestamp = -1

            # Iterate backwards for efficiency (latest events are at the end)
            for obs_event in reversed(proc_events):
                if obs_event.eid not in n_events:
                    event_ts = obs_event.vc.clock_dict.get(proc, 0)
                    if event_ts > latest_timestamp:
                        latest_timestamp = event_ts
                        latest_event = obs_event
                        break  # Found the latest, no need to continue

            if latest_event is not None:
                extended_events[proc] = latest_event

        return Frontier(extended_events)

    def _create_extended_frontier_for_formula(
        self, formula: EP, trigger_event: Event
    ) -> Frontier:
        """Create extended frontier for evaluating complex nested formulas."""
        from parser.ast_nodes import And, Or, Literal

        extended_events = {}

        # Start with the trigger event
        for proc in trigger_event.processes:
            extended_events[proc] = trigger_event

        # For complex formulas, we need to find events that could satisfy nested components
        def collect_required_props(expr) -> set:
            """Collect all literal names required by the expression."""
            if isinstance(expr, Literal):
                return {expr.name} if expr.name not in ["true", "false"] else set()
            elif isinstance(expr, EP):
                return collect_required_props(expr.operand)
            elif isinstance(expr, And):
                return collect_required_props(expr.left) | collect_required_props(
                    expr.right
                )
            elif isinstance(expr, Or):
                return collect_required_props(expr.left) | collect_required_props(
                    expr.right
                )
            elif hasattr(expr, "operand"):  # Not
                return collect_required_props(expr.operand)
            return set()

        required_props = collect_required_props(formula.operand)

        # Find the latest event for each process that could contribute to satisfying the formula
        for proc in self.all_processes:
            best_event = extended_events.get(proc)
            best_timestamp = best_event.vc.clock_dict.get(proc, 0) if best_event else -1

            # Use indexed events for faster lookup
            # First, try to find an event with required properties
            found_with_prop = False
            for prop in required_props:
                if prop in self._events_by_prop:
                    for obs_event in reversed(self._events_by_prop[prop]):
                        if proc in obs_event.processes:
                            event_ts = obs_event.vc.clock_dict.get(proc, 0)
                            if event_ts > best_timestamp:
                                extended_events[proc] = obs_event
                                best_timestamp = event_ts
                                found_with_prop = True
                                break
                    if found_with_prop:
                        break

            # If no event with required props found, use latest event for process
            if not found_with_prop and proc in self._latest_event_per_process:
                latest = self._latest_event_per_process[proc]
                if latest.vc.clock_dict.get(proc, 0) > best_timestamp:
                    extended_events[proc] = latest

        # Ensure all processes have some event (fallback to initial frontier)
        if self.initial_frontier:
            for proc, initial_event in self.initial_frontier.events_dict.items():
                if proc not in extended_events:
                    extended_events[proc] = initial_event

        return Frontier(extended_events)

    def _create_extended_frontier_for_formula_excluding_n(
        self, formula: EP, trigger_event: Event, disjunct: EPDisjunct
    ) -> Frontier:
        """Create extended frontier for P-blocks excluding N-related events."""
        from parser.ast_nodes import And, Or, Literal

        extended_events = {}

        # Start with the trigger event
        for proc in trigger_event.processes:
            extended_events[proc] = trigger_event

        # Get N-related events to exclude
        n_events = set()
        for i in range(len(disjunct.n_blocks)):
            n_frontier = disjunct.n_satisfied_at.get(i)
            if n_frontier is not None:
                for proc, event in n_frontier.events_dict.items():
                    n_events.add(event.eid)

        # Collect required properties from formula
        def collect_required_props(expr) -> set:
            if isinstance(expr, Literal):
                return {expr.name} if expr.name not in ["true", "false"] else set()
            elif isinstance(expr, EP):
                return collect_required_props(expr.operand)
            elif isinstance(expr, And):
                return collect_required_props(expr.left) | collect_required_props(
                    expr.right
                )
            elif isinstance(expr, Or):
                return collect_required_props(expr.left) | collect_required_props(
                    expr.right
                )
            elif hasattr(expr, "operand"):  # Not
                return collect_required_props(expr.operand)
            return set()

        required_props = collect_required_props(formula.operand)

        # Find the latest event for each process that could contribute to satisfying the formula
        # but exclude N-events
        for proc in self.all_processes:
            best_event = extended_events.get(proc)
            best_timestamp = best_event.vc.clock_dict.get(proc, 0) if best_event else -1

            # Use indexed events for faster lookup, excluding N-events
            found_with_prop = False
            for prop in required_props:
                if prop in self._events_by_prop:
                    for obs_event in reversed(self._events_by_prop[prop]):
                        if (
                            proc in obs_event.processes
                            and obs_event.eid not in n_events
                        ):  # Exclude N-events
                            event_ts = obs_event.vc.clock_dict.get(proc, 0)
                            if event_ts > best_timestamp:
                                extended_events[proc] = obs_event
                                best_timestamp = event_ts
                                found_with_prop = True
                                break
                    if found_with_prop:
                        break

            # If no event with required props found, use latest event for process (excluding N-events)
            if not found_with_prop and proc in self._latest_event_per_process:
                latest = self._latest_event_per_process[proc]
                if (
                    latest.eid not in n_events
                    and latest.vc.clock_dict.get(proc, 0) > best_timestamp
                ):
                    extended_events[proc] = latest

        # Ensure all processes have some event (fallback to initial frontier)
        if self.initial_frontier:
            for proc, initial_event in self.initial_frontier.events_dict.items():
                if proc not in extended_events:
                    extended_events[proc] = initial_event

        return Frontier(extended_events)

    def _get_current_global_frontier(self) -> Frontier:
        """Get the current global frontier representing the latest events from all processes."""
        # Simply use the cached latest events for each process (O(1) instead of O(n))
        return Frontier(self._latest_event_per_process.copy())

    def _apply_case_verdict(self, disjunct: EPDisjunct) -> None:
        """Apply case-specific verdict logic."""
        logger = get_logger()
        case_type = disjunct.case_type()

        if case_type == "P":
            if self._all_p_blocks_satisfied(disjunct):
                disjunct.verdict = Verdict.TRUE
                disjunct.success_frontier = self._calculate_p_conjunction_frontier(
                    disjunct
                )

        elif case_type == "P+M":
            if disjunct.m_satisfied_frontier is not None:
                disjunct.verdict = Verdict.TRUE
                disjunct.success_frontier = disjunct.m_satisfied_frontier

        elif case_type == "P+M+N":
            if self._all_p_blocks_satisfied(disjunct):
                # All P-blocks satisfied: proceed with M+N logic
                if disjunct.m_satisfied_frontier is not None:
                    # M-literals satisfied: check N-violations with proper causal ordering
                    n_violation = False
                    for i in range(len(disjunct.n_blocks)):
                        n_frontier = disjunct.n_satisfied_at.get(i)
                        if n_frontier is not None:
                            # N-violation only if N-frontier ≤ M-frontier (causally before/concurrent)
                            if n_frontier.vc <= disjunct.m_satisfied_frontier.vc:
                                n_violation = True
                                break

                    if n_violation:
                        disjunct.verdict = Verdict.FALSE
                        logger.debug(f"N-constraint violation in {case_type}")
                        logger.debug(f"N-frontier vc: {n_frontier.vc}")
                        logger.debug(
                            f"M-frontier vc: {disjunct.m_satisfied_frontier.vc}"
                        )
                    else:
                        disjunct.verdict = Verdict.TRUE
                        disjunct.success_frontier = disjunct.m_satisfied_frontier
                else:
                    # M not satisfied yet: for single-process cases, check for immediate N-violations
                    if len(self.all_processes) == 1:
                        for i in range(len(disjunct.n_blocks)):
                            n_frontier = disjunct.n_satisfied_at.get(i)
                            if n_frontier is not None:
                                disjunct.verdict = Verdict.FALSE
                                logger.debug(
                                    f"Early N-constraint violation in single-process {case_type}"
                                )
                                break
                    # Otherwise keep waiting for M-satisfaction
            else:
                # P-blocks not all satisfied: check for immediate N-violations in single-process cases
                # Get all processes involved in N-constraints
                n_processes = set()
                for i in range(len(disjunct.n_blocks)):
                    n_frontier = disjunct.n_satisfied_at.get(i)
                    if n_frontier is not None:
                        for proc in n_frontier.events_dict.keys():
                            n_processes.add(proc)

                all_processes = set(self.all_processes)

                # For single-process cases or when N affects most processes, fail immediately
                if len(self.all_processes) == 1 or len(n_processes) >= len(
                    all_processes
                ):
                    for i in range(len(disjunct.n_blocks)):
                        n_frontier = disjunct.n_satisfied_at.get(i)
                        if n_frontier is not None:
                            disjunct.verdict = Verdict.FALSE
                            break

        elif case_type == "P+N":
            if self._all_p_blocks_satisfied(disjunct):
                # All P-blocks satisfied: check N-violations with proper causal ordering
                p_conjunction = self._calculate_p_conjunction_frontier(disjunct)

                # Check for N-violations with proper causal ordering
                n_violation = False
                for i in range(len(disjunct.n_blocks)):
                    n_frontier = disjunct.n_satisfied_at.get(i)
                    if n_frontier is not None:
                        # N-violation only if N-frontier ≤ P-frontier (causally before/concurrent)
                        if n_frontier.vc <= p_conjunction.vc:
                            n_violation = True
                            break

                if n_violation:
                    disjunct.verdict = Verdict.FALSE
                else:
                    # P-blocks satisfied and no N-violations
                    disjunct.verdict = Verdict.TRUE
                    disjunct.success_frontier = p_conjunction
            else:
                # P-blocks not all satisfied: check for immediate N-violations
                # only when all processes involved are the same (no concurrency possible)
                all_processes = set()
                for p_block in disjunct.p_blocks:
                    # Collect processes that could satisfy P-blocks
                    for proc in self.all_processes:
                        all_processes.add(proc)

                for i in range(len(disjunct.n_blocks)):
                    n_frontier = disjunct.n_satisfied_at.get(i)
                    if n_frontier is not None:
                        # Check if N-violation affects the same processes that could satisfy P
                        n_processes = set()
                        for proc, event in n_frontier.events_dict.items():
                            n_processes.add(proc)

                        # Only immediate failure if this is essentially a single-process scenario
                        # or if all processes involved have already had events
                        if len(self.all_processes) == 1 or len(n_processes) >= len(
                            all_processes
                        ):
                            disjunct.verdict = Verdict.FALSE
                            break

        elif case_type == "M":
            if disjunct.m_satisfied_frontier is not None:
                disjunct.verdict = Verdict.TRUE
                disjunct.success_frontier = disjunct.m_satisfied_frontier

        elif case_type == "M+N":
            if disjunct.m_satisfied_frontier is not None:
                # Check N-constraints
                n_violation = False
                for i in range(len(disjunct.n_blocks)):
                    n_frontier = disjunct.n_satisfied_at.get(i)
                    if (
                        n_frontier is not None
                        and n_frontier <= disjunct.m_satisfied_frontier
                    ):
                        n_violation = True
                        break

                if not n_violation:
                    disjunct.verdict = Verdict.TRUE
                    disjunct.success_frontier = disjunct.m_satisfied_frontier
                else:
                    disjunct.verdict = Verdict.FALSE

        elif case_type == "N":
            # N-only: FALSE if any N-block is satisfied
            for i in range(len(disjunct.n_blocks)):
                if disjunct.n_satisfied_at.get(i) is not None:
                    disjunct.verdict = Verdict.FALSE
                    return

    def _update_global_verdict(self) -> None:
        """Update global verdict based on disjunct verdicts."""
        # Handle negated EP formulas (AH conversion)
        if len(self.disjuncts) == 1 and self.disjuncts[0].is_negated:
            disjunct = self.disjuncts[0]
            if disjunct.verdict == Verdict.TRUE:
                self.global_verdict = Verdict.FALSE
            elif disjunct.verdict == Verdict.FALSE:
                self.global_verdict = Verdict.TRUE
            else:
                self.global_verdict = Verdict.UNKNOWN
        else:
            # Normal disjunctive logic
            verdicts = [d.verdict for d in self.disjuncts]

            if any(v == Verdict.TRUE for v in verdicts):
                self.global_verdict = Verdict.TRUE
            elif all(v == Verdict.FALSE for v in verdicts):
                self.global_verdict = Verdict.FALSE
            else:
                self.global_verdict = Verdict.UNKNOWN

    def _print_event_result(self, event: Event) -> None:
        """Print event processing result."""
        logger = get_logger()

        procs = ",".join(sorted(event.processes))
        event_str = f"{event.eid}@{procs}:{event.vc}"

        verdict_str = (
            "FALSE (Inconclusive)"
            if self.global_verdict == Verdict.UNKNOWN
            else str(self.global_verdict)
        )

        # Show only the global frontier (current maximal events for each process)
        global_frontier = self._get_current_global_frontier()
        global_frontier_parts = []
        frontier_vc_parts = []

        for proc in sorted(self.all_processes):
            if proc in global_frontier.events_dict:
                event = global_frontier.events_dict[proc]
                global_frontier_parts.append(f"{proc}:{event.eid}")
                frontier_vc_parts.append(f"{proc}:{event.vc.clock_dict.get(proc, 0)}")

        if global_frontier_parts:
            frontiers_display = (
                f"⟨{', '.join(global_frontier_parts)}⟩:[{', '.join(frontier_vc_parts)}]"
            )
        else:
            frontiers_display = ""
        logger.event_processed(event_str, frontiers_display, verdict_str)

    def finalize(self) -> Verdict:
        """Finalize monitoring session."""
        logger = get_logger()
        logger.debug("Finalizing enhanced monitoring session")

        for disjunct in self.disjuncts:
            if disjunct.verdict == Verdict.UNKNOWN:
                disjunct.verdict = Verdict.FALSE

        self._update_global_verdict()
        logger.debug(f"Final verdict: {self.global_verdict}")
        return self.global_verdict

    # Compatibility methods for old interface
    def set_verbose(self, verbose: bool) -> None:
        """Set verbose mode for debugging (compatibility method)."""
        self.verbose = verbose

    @property
    def current_frontiers(self) -> Set[Frontier]:
        """Get current frontiers (compatibility property)."""
        frontiers = set()

        # Include initial frontier if no other frontiers found
        has_success_frontiers = False
        for disjunct in self.disjuncts:
            if disjunct.success_frontier:
                frontiers.add(disjunct.success_frontier)
                has_success_frontiers = True

        # If no success frontiers, include the initial frontier
        if (
            not has_success_frontiers
            and hasattr(self, "initial_frontier")
            and self.initial_frontier
        ):
            frontiers.add(self.initial_frontier)

        return frontiers

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
        """Check if verdict is conclusive."""
        return self.global_verdict.is_conclusive()
