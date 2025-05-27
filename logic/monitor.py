# logic/monitor.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Callable

from parser import parse_and_dlnf
from parser.ast_nodes import EP, Or
from utils.logger import get_logger
from .formula import Formula
from .ep_block_fsm import EPBlockFSM
from .verdict import Verdict
from model.event import Event
from model.frontier import Frontier
from model.initial_event import create_initial_system_event
from model.window import SlidingFrontierWindow
from model.process_chains import ProcessEventChains

logger = get_logger(__name__)


def _deliverable(ev: Event, seen: Dict[str, int]) -> bool:
    for pid_ev in ev.processes:
        if ev.vc.clock.get(pid_ev, -1) != seen.get(pid_ev, 0) + 1: return False
    for pid_vc, ts_vc in ev.vc.clock.items():
        if pid_vc not in ev.processes and ts_vc > seen.get(pid_vc, 0): return False
    return True


@dataclass(slots=True)
class Monitor:
    spec_src: str
    _formula: Formula = field(init=False)
    _fsms: List[EPBlockFSM] = field(default_factory=list, init=False)
    _window: SlidingFrontierWindow = field(default_factory=SlidingFrontierWindow)
    verdict: Verdict = Verdict.INCONCLUSIVE
    _seen: Dict[str, int] = field(default_factory=dict, init=False)
    _buffer: List[Event] = field(default_factory=list, init=False)
    _process_chains: ProcessEventChains = field(default_factory=ProcessEventChains, init=False)
    _known_processes: Set[str] = field(default_factory=set, init=False)
    _literal_mode: bool = field(default=True, init=False)

    _initial_system_event: Optional[Event] = field(default=None, init=False)
    initial_system_frontier: Optional[Frontier] = field(default=None, init=False)
    _system_processes_defined_by_directive: bool = field(default=False, init=False)
    _initial_setup_done: bool = field(default=False, init=False)

    def __post_init__(self):
        ast = parse_and_dlnf(self.spec_src)
        self._formula = Formula(ast)
        self._fsms = [EPBlockFSM.from_ep(d) for d in self._collect_disjuncts(ast)]
        if not self._initial_setup_done:  # Should always be false here
            self._establish_initial_state_and_seed_fsms()

    def _establish_initial_state_and_seed_fsms(self) -> None:
        procs_for_initial_event = self._known_processes.copy()

        if not procs_for_initial_event and not self._system_processes_defined_by_directive:
            logger.debug("Monitor: Initializing with placeholder initial event (no processes known yet).")
            self._initial_system_event = create_initial_system_event(set())
        else:
            self._initial_system_event = create_initial_system_event(procs_for_initial_event)

        self.initial_system_frontier = Frontier(
            {proc: self._initial_system_event for proc in self._initial_system_event.processes}
        )

        if self._initial_setup_done:
            logger.debug(f"Monitor: Re-establishing initial state with processes: {procs_for_initial_event}")
            temp_fsms = []
            for fsm_template_ep in self._collect_disjuncts(self._formula.root):
                new_fsm = EPBlockFSM.from_ep(fsm_template_ep)
                temp_fsms.append(new_fsm)
            self._fsms = temp_fsms

        self._window.clear_and_insert(self.initial_system_frontier)

        for fsm in self._fsms:
            fsm.set_infrastructure(procs_for_initial_event.copy(), self._get_successor_lookup())
            fsm.seed_with_iota_update(self.initial_system_frontier)

        self._update_global_verdict()
        self._initial_setup_done = True

    def _collect_disjuncts(self, node) -> List[EP]:
        if isinstance(node, Or): return self._collect_disjuncts(node.left) + self._collect_disjuncts(node.right)
        if isinstance(node, EP): return [node]
        raise ValueError("Expected DLNF Or or EP node")

    def _get_successor_lookup(self) -> Callable[[Event, str], List[Event]]:
        def successor_lookup(event: Event, process_id: str) -> List[Event]:
            return self._process_chains.get_immediate_successors(event, process_id)

        return successor_lookup

    def enable_literal_mode(self, enabled: bool = True) -> None:
        self._literal_mode = enabled

    def process(self, ev: Event) -> None:
        newly_discovered_processes = ev.processes - self._known_processes

        if not self._initial_setup_done:
            if not self._system_processes_defined_by_directive:
                self._known_processes.update(ev.processes)
            self._establish_initial_state_and_seed_fsms()
        elif newly_discovered_processes and not self._system_processes_defined_by_directive:
            self._known_processes.update(newly_discovered_processes)
            for fsm in self._fsms:
                fsm.set_infrastructure(self._known_processes.copy(), self._get_successor_lookup())
        elif newly_discovered_processes and self._system_processes_defined_by_directive:
            logger.warning(f"Monitor: Event from new process(es) {newly_discovered_processes} "
                           f"arrived after system processes were defined by directive.")
            self._known_processes.update(newly_discovered_processes)
            for fsm in self._fsms:
                fsm.set_infrastructure(self._known_processes.copy(), self._get_successor_lookup())

        self._buffer.append(ev)
        self._try_flush()

    def finish(self) -> None:
        if not self._initial_setup_done:
            self._establish_initial_state_and_seed_fsms()
        self._try_flush()
        for fsm in self._fsms:
            if fsm.verdict() is Verdict.INCONCLUSIVE: fsm.finalize_at_trace_end()
        self._update_global_verdict()

    def _try_flush(self) -> None:
        made_progress = True
        while made_progress:
            made_progress = False
            for ev in list(self._buffer):
                if _deliverable(ev, self._seen):
                    self._deliver(ev);
                    self._buffer.remove(ev);
                    made_progress = True

    def _deliver(self, ev: Event) -> None:
        """
        Delivers a causally-ready event to the FSMs and updates the window.
        Ensures that candidate frontiers generated by extending the true initial system
        frontier with the current event are always processed by FSMs.
        """
        for pid_ev in ev.processes: self._seen[pid_ev] = ev.vc.clock.get(pid_ev, 0)
        if self._literal_mode: self._process_chains.add_event(ev)

        # M-search driven by the event itself
        if self._literal_mode:
            for fsm in self._fsms:
                if fsm.verdict() is Verdict.INCONCLUSIVE: fsm.notify_new_event(ev)

        # Generate candidate frontiers from current window state
        candidate_frontiers_from_window = self._window.extend(ev)

        # Ensure the frontier resulting from extending the *absolute initial system frontier*
        # with the current event `ev` is always considered. This is crucial for
        # detecting "pointwise" satisfactions relative to the system start.
        all_candidates = set(candidate_frontiers_from_window)  # Use a set for uniqueness

        if self.initial_system_frontier:  # Should always be true after init
            candidate_from_true_init = self.initial_system_frontier.extend(ev)
            all_candidates.add(candidate_from_true_init)

        # Process all unique candidates
        for fr_cand in all_candidates:
            for fsm in self._fsms:
                if fsm.verdict() is Verdict.INCONCLUSIVE: fsm.update(fr_cand)

        # Commit all generated candidates (including the one from true init) to the window
        # The window's commit_and_prune will handle duplicates and pruning.
        self._window.commit_and_prune_candidates(list(all_candidates))
        self._update_global_verdict()

    def _update_global_verdict(self) -> None:
        if any(f.verdict() is Verdict.TRUE for f in self._fsms):
            self.verdict = Verdict.TRUE
        elif all(f.verdict() is Verdict.FALSE for f in self._fsms):
            self.verdict = Verdict.FALSE
        else:
            self.verdict = Verdict.INCONCLUSIVE

    def activate_window_optimization(self, all_system_processes: Set[str]) -> None:
        self._known_processes.clear()
        self._known_processes.update(all_system_processes)
        self._system_processes_defined_by_directive = True

        self._initial_setup_done = False
        self._establish_initial_state_and_seed_fsms()

        if hasattr(self._window, "activate_optimized_pruning"):
            self._window.activate_optimized_pruning(all_system_processes)

    def get_process_chains(self) -> ProcessEventChains:
        return self._process_chains

    def get_known_processes(self) -> Set[str]:
        return self._known_processes.copy()

    def get_fsm_states(self) -> List[Dict]:
        return [{'fsm_id': i, **fsm.get_debug_info()} for i, fsm in enumerate(self._fsms)]

    def get_performance_stats(self) -> Dict:
        fsm_debug_infos = [fsm.get_debug_info() for fsm in self._fsms] if self._fsms else []
        return {
            'monitor': {
                'literal_mode': self._literal_mode,
                'known_processes': list(self._known_processes),
                'buffered_events': len(self._buffer),
                'verdict': self.verdict.name
            },
            'window': self._window.get_performance_stats() if hasattr(self._window, 'get_performance_stats') else {},
            'fsms': fsm_debug_infos,
            'process_chains': {
                'total_processes': len(self._process_chains.get_known_processes()),
                'chains_tracked': len(
                    [p for p in self._known_processes if self._process_chains.get_latest_event(p) is not None])
            }
        }
